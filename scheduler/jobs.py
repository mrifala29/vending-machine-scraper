"""
Scheduled jobs for web scraper.
Define and manage recurring scraping tasks.
"""
from datetime import datetime, timezone
from config.config import Config
from utils.logging_setup import logger
from utils.exceptions import ScraperException
from utils.process_lock import ProcessLock
from utils.retry_handler import RetryHandler, RetryConfig


def _execute_sales_scraping(
    session_manager_holder: dict,
    start_date_holder: dict,
    end_date_holder: dict,
    start_time: datetime,
) -> None:
    """
    Inner function for sales data scraping (retryable).
    Designed to be called by retry handler.
    
    Args:
        session_manager_holder: Dict to hold session_manager reference
        start_date_holder: Dict containing start_date
        end_date_holder: Dict containing end_date
        start_time: Job start time for metrics
        
    Raises:
        Exception: On any scraping error (will be caught by retry handler)
    """
    from scrapers.auth_handler import LoginHandler
    from utils.session_manager import SessionManager
    from scrapers.parser import DataExtractor
    from storage.json_storage import JSONStorage
    from models.sales_data import ScrapingReport

    def _cleanup_session_local() -> None:
        """Quit and remove session_manager from holder."""
        sm = session_manager_holder.pop("session_manager", None)
        if sm:
            try:
                sm.quit_driver()
            except Exception as e:
                logger.debug(f"Session cleanup error (ignored): {e}")

    # Always create fresh SessionManager for each attempt
    # Never reuse — a broken driver causes "NoneType has no attribute 'get'"
    logger.info("Step 1: Initializing WebDriver session")
    session_manager = SessionManager()
    session_manager_holder["session_manager"] = session_manager

    try:
        session_manager.initialize_driver()
        logger.info("WebDriver initialized")

        logger.info("Step 2: Authenticating to website")
        login_handler = LoginHandler(session_manager)
        if not login_handler.login():
            raise ScraperException("Login failed - check credentials in .env")
        logger.info("Authentication successful")

        # Build target URLs from config
        logger.info("Step 3: Scraping data from all pages")
        target_urls = {
            name: f"{Config.BASE_URL}{url}" for name, url in Config.get_target_urls().items()
        }

        # Extract data from all pages
        logger.info(f"Extracting data from {len(target_urls)} pages")
        start_date = start_date_holder.get("start_date")
        end_date = end_date_holder.get("end_date")
        logger.info(f"Date range: {start_date.date()} to {end_date.date()}")
        
        all_data = DataExtractor.extract_all_pages(
            session_manager.driver, 
            target_urls,
            start_date=start_date,
            end_date=end_date,
        )
        logger.info(f"Extracted data from {len(all_data)} pages")

        # Build and save report
        logger.info("Step 4: Saving data to JSON")
        end_time = datetime.now(timezone.utc)
        execution_time = (end_time - start_time).total_seconds()

        total_records = sum(len(data.records) for data in all_data)
        total_errors = sum(len(data.errors) for data in all_data)

        report = ScrapingReport(
            run_timestamp=start_time,
            status="success" if total_errors == 0 else "partial",
            total_records_scraped=total_records,
            data_by_submenu={data.submenu: data for data in all_data},
            errors=[],
            execution_time_seconds=execution_time,
        )

        storage = JSONStorage()

        # Save one JSON file per target page
        saved_files = storage.save_per_target(all_data, start_date=start_date, end_date=end_date)
        logger.info(f"Saved {len(saved_files)} per-target JSON files")

        # Also save combined report for reference
        report_data = report.model_dump()
        storage.save_data(report_data, start_date=start_date, end_date=end_date)
        logger.info(f"Combined report saved: {start_date.date()} to {end_date.date()}")

        # Save in additional formats based on config
        if Config.OUTPUT_FORMAT == "jsonl" or Config.OUTPUT_FORMAT == "clickhouse":
            from utils.clickhouse_formatter import ClickHouseFormatter
            jsonl_data = ClickHouseFormatter.to_jsonl(all_data)
            
            # Save JSONL file
            import os
            from pathlib import Path
            
            data_dir = Path(Config.DATA_FOLDER)
            data_dir.mkdir(exist_ok=True)
            
            timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
            jsonl_filename = data_dir / f"scraping_data_{timestamp}.jsonl"
            
            with open(jsonl_filename, "w", encoding="utf-8") as f:
                f.write(jsonl_data)
            
            logger.info(f"JSONL data saved to: {jsonl_filename}")

        # Insert into ClickHouse (if configured)
        if Config.clickhouse_enabled():
            logger.info("Step 5: Inserting data into ClickHouse")
            from storage.clickhouse_storage import ClickHouseStorage
            force_overwrite = Config.get_force_overwrite()
            ch_storage = ClickHouseStorage(
                host=Config.CLICKHOUSE_HOST,
                port=Config.CLICKHOUSE_PORT,
                database=Config.CLICKHOUSE_DATABASE,
                username=Config.CLICKHOUSE_USER,
                password=Config.CLICKHOUSE_PASSWORD,
                secure=Config.CLICKHOUSE_SECURE,
            )
            try:
                ch_storage.connect()
                ch_inserted = ch_storage.insert_all(
                    all_data,
                    start_date=start_date,
                    end_date=end_date,
                    force_overwrite=force_overwrite,
                )
                logger.info(f"ClickHouse: inserted {ch_inserted} total rows across all tables")
            except Exception as ch_exc:
                logger.error(f"ClickHouse insert failed: {ch_exc}", exc_info=True)
                raise ScraperException(f"ClickHouse insert failed: {ch_exc}")
            finally:
                ch_storage.close()
        else:
            logger.info("Step 5: ClickHouse not configured (CLICKHOUSE_HOST empty), skipping")

        # Cleanup old backups
        logger.info("Step 6: Cleaning up old backup files")
        storage.cleanup_old_files(keep_count=10)
        logger.info("Cleanup completed")
        
        # Store results for logging
        session_manager_holder["total_records"] = total_records
        session_manager_holder["execution_time"] = execution_time

    except Exception as e:
        # Cleanup broken session before re-raise so next retry starts fresh
        logger.error(f"Scraping error: {e}")
        _cleanup_session_local()
        raise


def scraping_job() -> None:
    """
    Main scraping job to be executed on schedule with automatic retry.
    Workflow: Initialize → Login → Navigate URLs → Parse → Save → Cleanup
    
    Uses process locking to prevent concurrent execution when multiple
    schedulers run (e.g., machine job every 30min + main.py at 01:00 UTC).
    
    Uses retry handler to recover from connection timeout or temporary failures:
    - Max 4 attempts total
    - 5 minute delay between retries
    - Retries only on connection/scraping errors
    
    IMPORTANT: Lock is acquired AFTER successful WebDriver initialization.
    This ensures lock is released quickly if initialization fails.
    """
    start_time = datetime.now(timezone.utc)
    lock = ProcessLock("sales_scraper")
    session_manager_holder = {}
    start_date_holder = {}
    end_date_holder = {}

    try:
        # Acquire lock at start to prevent concurrent execution.
        # Stale lock detection: if previous process died, lock is stolen automatically.
        # Short timeout: if another live instance is running, exit immediately.
        logger.info("Attempting to acquire sales scraper lock (timeout: 5s)...")
        if not lock.acquire(timeout=5):
            logger.warning(
                "Could not acquire sales scraper lock — another live instance is running. "
                "Skipping this run to prevent concurrent execution."
            )
            return

        logger.info("=" * 60)
        logger.info("Starting scheduled scraping job")
        logger.info(f"Job started at: {start_time.isoformat()}")

        # Cache date parameters for reuse across retries
        start_date_holder["start_date"] = Config.get_start_date()
        end_date_holder["end_date"] = Config.get_end_date()

        # Configure retry handler: max 1 attempt (no retry to avoid password lockout)
        retry_config = RetryConfig(
            max_attempts=1,
            retry_delay_seconds=300,  # 5 minutes (not used when max_attempts=1)
            backoff_multiplier=1.0,   # Fixed delay (no exponential backoff)
            retryable_exceptions=(Exception,),  # Retry on all exceptions
        )
        retry_handler = RetryHandler(retry_config)

        success = retry_handler.execute_with_retry(
            _execute_sales_scraping,
            "sales_scraper",
            session_manager_holder,
            start_date_holder,
            end_date_holder,
            start_time,
        )

        if not success:
            logger.error("Sales scraping job failed after all retry attempts")
            logger.info("=" * 60)
            return

        # Log success metrics
        total_records = session_manager_holder.get("total_records", 0)
        execution_time = session_manager_holder.get("execution_time", 0)
        logger.info("=" * 60)
        logger.info(
            f"Scraping job completed: {total_records} records extracted, "
            f"execution time: {execution_time:.2f}s"
        )
        logger.info("=" * 60)

    except ScraperException as e:
        logger.error(f"Scraping job failed: {str(e)}")
        logger.info("Check .env credentials and website selectors")
    except Exception as e:
        logger.error(f"Unexpected error in scraping job: {str(e)}", exc_info=True)
    finally:
        # Always cleanup: quit driver first
        session_manager = session_manager_holder.get("session_manager")
        if session_manager:
            try:
                logger.info("Closing WebDriver session")
                session_manager.quit_driver()
                logger.info("WebDriver closed")
            except Exception as cleanup_error:
                logger.error(f"Error during driver cleanup: {cleanup_error}")
        
        # Release lock if still held
        if lock.held:
            lock.release()


def health_check_job() -> None:
    """
    Health check job to verify system status.
    """
    try:
        logger.debug("Running health check...")
        logger.debug(f"Config validation: {Config.validate()}")
        logger.debug("Health check passed")
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")

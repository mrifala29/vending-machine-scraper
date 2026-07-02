"""
Main entry point for web scraper application.
Handles both scheduled and manual scraping execution.
"""
import sys
import argparse
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from apscheduler.schedulers.background import BackgroundScheduler
from config.config import Config
from utils.logging_setup import logger
from scheduler.jobs import scraping_job, health_check_job


def _override_dates(start: str | None, end: str | None, yesterday: bool) -> None:
    """
    Override START_DATE / END_DATE in Config from CLI arguments.
    Priority: --start-date/--end-date > --yesterday > .env values
    
    All dates are in UTC (server timezone). Website, ClickHouse, and server all use UTC.
    For Jakarta timezone reference: add 7 hours. Example:
      - UTC: 2026-01-01 00:00:00 = Jakarta: 2026-01-01 07:00:00
    """
    utc = ZoneInfo("UTC")

    if yesterday:
        today = datetime.now(utc).date()
        y = today - timedelta(days=1)
        Config._start_date = datetime(y.year, y.month, y.day, tzinfo=utc)
        Config._end_date = datetime(y.year, y.month, y.day, tzinfo=utc)
        logger.info(f"--yesterday: scraping {y} UTC (cron will use server timezone)")
        return

    if start:
        try:
            d = datetime.strptime(start, "%Y-%m-%d")
            Config._start_date = d.replace(tzinfo=utc)
        except ValueError:
            print(f"ERROR: --start-date format invalid: '{start}'. Use YYYY-MM-DD")
            sys.exit(1)

    if end:
        try:
            d = datetime.strptime(end, "%Y-%m-%d")
            Config._end_date = d.replace(tzinfo=utc)
        except ValueError:
            print(f"ERROR: --end-date format invalid: '{end}'. Use YYYY-MM-DD")
            sys.exit(1)

    if start or end:
        logger.info(
            f"Date range override: {Config._start_date.date()} → {Config._end_date.date()} UTC"
        )


def run_once(start: str | None = None, end: str | None = None, yesterday: bool = False) -> None:
    """
    Execute scraping job once and exit.
    Useful for testing and manual runs.
    """
    if yesterday or start or end:
        _override_dates(start, end, yesterday)
    logger.info("Running scraper in one-time mode...")
    try:
        scraping_job()
        logger.info("One-time scraping completed successfully")
    except Exception as e:
        logger.error(f"One-time scraping failed: {str(e)}")
        sys.exit(1)


def run_scheduled() -> None:
    """
    Start scheduler for continuous scraping on schedule.
    """
    try:
        Config.validate()
        logger.info("Configuration validation passed")

        scheduler = BackgroundScheduler()

        # Parse schedule time
        schedule_time = Config.SCHEDULE_TIME  # Format: HH:MM
        hour, minute = map(int, schedule_time.split(":"))

        logger.info(f"Scheduling scraping job for {schedule_time} daily")
        scheduler.add_job(
            scraping_job,
            "cron",
            hour=hour,
            minute=minute,
            timezone=Config.SCHEDULE_TIMEZONE,
            id="scraping_job",
        )

        # Add health check job (every 6 hours)
        scheduler.add_job(
            health_check_job,
            "interval",
            hours=6,
            id="health_check_job",
        )

        scheduler.start()
        logger.info("Scheduler started successfully")

        # Keep the scheduler running
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received, shutting down...")

    except Exception as e:
        logger.error(f"Scheduler error: {str(e)}")
        sys.exit(1)
    finally:
        if "scheduler" in locals() and scheduler.running:
            scheduler.shutdown()
            logger.info("Scheduler shut down")


def main() -> None:
    """Main application entry point."""
    parser = argparse.ArgumentParser(
        description="Web Scraper for Sales Statistic Data"
    )
    parser.add_argument(
        "--run-once",
        action="store_true",
        help="Run scraper once and exit (useful for testing). Auto-enabled if date args provided.",
    )
    parser.add_argument(
        "--yesterday",
        action="store_true",
        help="Override date range to yesterday (UTC). Auto-enables run-once. Perfect for daily cron on server.",
    )
    parser.add_argument(
        "--start-date",
        metavar="YYYY-MM-DD",
        help="Override START_DATE (UTC). Auto-enables run-once. Use for historical backfill. Max 31 days range recommended.",
    )
    parser.add_argument(
        "--end-date",
        metavar="YYYY-MM-DD",
        help="Override END_DATE (UTC). Auto-enables run-once. Format: YYYY-MM-DD",
    )
    parser.add_argument(
        "--schedule",
        action="store_true",
        help="Run scheduler for continuous scraping",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 1.0.0",
    )

    args = parser.parse_args()

    logger.info(f"Web Scraper started at {datetime.now().isoformat()}")
    logger.info(f"Configuration loaded from environment")

    # Auto-detect run-once if date arguments provided
    if args.schedule:
        run_scheduled()
    elif args.run_once or args.start_date or args.end_date or args.yesterday:
        # Auto-enabled run-once if any date args provided
        if (args.start_date or args.end_date or args.yesterday) and not args.run_once:
            logger.info("Date arguments provided → automatically enabling run-once mode")
        run_once(start=args.start_date, end=args.end_date, yesterday=args.yesterday)
    else:
        # Default behavior: run scheduler (no mode specified, no date args)
        logger.info("No mode specified, running in scheduled mode")
        run_scheduled()


if __name__ == "__main__":
    main()

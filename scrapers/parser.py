"""
HTML parser for extracting sales data from website tables.
"""
import time
from bs4 import BeautifulSoup
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException, 
    TimeoutException, 
    StaleElementReferenceException,
    InvalidSessionIdException,
    WebDriverException
)
import psutil

from models.sales_data import SalesRecord, SalesStatisticData
from utils.logging_setup import logger
from utils.exceptions import ParsingError

# Rows with these values in any cell are footer/summary rows — skip them
_SKIP_ROW_VALUES = {"合计"}

# Column names to exclude from extracted data
_SKIP_COLUMNS = {"checkbox", "操作"}


class DataExtractor:
    """Extract data from HTML pages."""

    # Column mapping for each page target, based on actual <thead> structure
    COLUMN_MAPPING: Dict[str, List[str]] = {
        "paydetail": [
            "序号", "系统订单号", "支付渠道流水号", "设备ID", "设备名称",
            "货道", "持有人", "商品名称", "支付方式", "支付金额",
            "购买数量", "商品进价", "付款人", "支付时间", "支付状态",
            "退款状态", "出货状态", "出货详情", "优惠券码", "折扣详情",
            "优惠金额", "订单金额", "出货编码", "操作"
        ],
        "deliverydetail": [
            "设备ID", "设备名称", "货道", "商品名称", "商品品牌",
            "销售金额", "支付类型", "销售时间", "返回码"
        ],
        "cashdetail": [
            "checkbox", "序号", "设备ID", "设备名称", "持有人",
            "交易类型", "交易方式", "金额", "交易时间"
        ],
        "essDetail": [
            "设备ID", "设备名称", "销售数量", "销售总额", "微信",
            "微信刷脸", "微信刷掌", "支付宝", "支付宝刷脸", "支付宝NFC",
            "现金", "微信会员", "会员卡", "扶贫网", "GHL"
        ],
        "mtOrder": [
            "美团订单号", "美团门店ID", "设备号", "商品名称", "支付金额",
            "订单状态", "取货码", "商品货道", "出货详情", "创建时间"
        ],
        "orderThird": [
            "订单号", "三方订单号", "设备ID", "商品名称", "货道",
            "支付方式", "订单金额", "商品单价", "数量", "购买人",
            "购买ID", "应退款金额", "出货状态", "交易时间", "创建时间"
        ],
        "orderThirdMachine": [
            "设备ID", "设备名称", "销售数量", "销售总额"
        ],
        "onlineOrderDetail": [
            "序号", "系统订单号", "支付渠道流水号", "设备ID", "设备名称",
            "商品名称", "支付方式", "支付金额", "购买数量", "商品进价",
            "支付状态", "出货状态", "退款状态", "支付时间"
        ],
    }

    @staticmethod
    def _parse_one_page(html_content: str, page_name: str, columns: List[str], scrape_date: Optional['date'] = None) -> List[SalesRecord]:
        """
        Extract data rows from a single page of HTML.
        Returns list of SalesRecord with all columns mapped.
        
        Args:
            html_content: HTML page content
            page_name: Name of the page being parsed
            columns: List of column names
            scrape_date: Date of the scraped data (defaults to today if not provided)
        """
        soup = BeautifulSoup(html_content, "html.parser")
        table = soup.find("table")
        if not table:
            logger.warning(f"No table found in {page_name}")
            return []

        # If scrape_date not provided, use today
        from datetime import date as date_class
        if scrape_date is None:
            scrape_date = datetime.now(timezone.utc).date()

        records: List[SalesRecord] = []
        scrape_ts = datetime.now(timezone.utc)
        col_count = 0

        for row in table.find_all("tr")[1:]:  # skip header
            cells = row.find_all("td")
            if not cells:
                continue

            cell_texts = [c.get_text(strip=True) for c in cells]
            col_count = len(cell_texts)

            # Skip footer / summary rows
            if any(v in _SKIP_ROW_VALUES for v in cell_texts):
                continue

            # Build data dict: zip column names with cell values
            # Use provided columns; fallback to positional index if lengths differ
            row_data: Dict[str, Any] = {}
            for idx, text in enumerate(cell_texts):
                col_name = columns[idx] if idx < len(columns) else f"col_{idx}"
                if col_name in _SKIP_COLUMNS:
                    continue
                row_data[col_name] = text

            if row_data:
                records.append(SalesRecord(scrape_date=scrape_date, scrape_timestamp=scrape_ts, data=row_data))

        if records:
            logger.debug(f"{page_name}: parsed {len(records)} records ({col_count} columns)")
        return records

    @staticmethod
    def _apply_date_filter(driver, start_date, end_date) -> bool:
        """
        Set date range filter in the form and click search.
        
        Args:
            driver: Selenium WebDriver
            start_date: datetime object (will be formatted as 'YYYY-MM-DD HH:MM:SS')
            end_date: datetime object
            
        Returns:
            True if filter applied, False if elements not found
        """
        try:
            # Format dates as website expects
            start_str = start_date.strftime("%Y-%m-%d 00:00:00")
            end_str = end_date.strftime("%Y-%m-%d 23:59:59")
            
            logger.info(f"Applying date filter: {start_str} to {end_str}")
            
            # Set startTime field
            start_field = driver.find_element(By.ID, "startTime")
            driver.execute_script("arguments[0].value = arguments[1]", start_field, start_str)
            logger.debug(f"Set startTime: {start_str}")
            
            # Set endTime field
            end_field = driver.find_element(By.ID, "endTime")
            driver.execute_script("arguments[0].value = arguments[1]", end_field, end_str)
            logger.debug(f"Set endTime: {end_str}")
            
            # Click search button
            search_btn = driver.find_element(By.ID, "searchButton")
            driver.execute_script("arguments[0].click();", search_btn)
            logger.info("Clicked search button")
            
            # Increase wait time for table to reload with filtered data
            time.sleep(5)
            
            # Wait explicitly for table to be present after filter
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
                )
                logger.debug("Table reloaded after date filter")
            except TimeoutException:
                logger.warning("Table did not reload within 15s after date filter")
            
            return True
            
        except NoSuchElementException as e:
            logger.warning(f"Date filter elements not found: {e}")
            return False
        except Exception as e:
            logger.warning(f"Error applying date filter: {e}")
            return False

    @staticmethod
    def _has_next_page(driver) -> bool:
        """
        Returns True if a clickable 'next page' button exists.
        Supports AmyUI (.am-pagination-next) and generic patterns.
        """
        try:
            # AmyUI framework next-page button
            next_li = driver.find_element(By.CSS_SELECTOR, "li.am-pagination-next")
            classes = next_li.get_attribute("class") or ""
            return "am-disabled" not in classes
        except NoSuchElementException:
            pass

        try:
            # Generic: link/button containing "下一页"
            btn = driver.find_element(By.XPATH, "//*[contains(text(),'下一页') and not(@disabled)]")
            classes = btn.get_attribute("class") or ""
            return "disabled" not in classes.lower()
        except NoSuchElementException:
            pass

        return False

    @staticmethod
    def _click_next_page(driver) -> bool:
        """Click next page button with verification. Returns True if clicked successfully."""
        try:
            next_li = driver.find_element(By.CSS_SELECTOR, "li.am-pagination-next")
            link = next_li.find_element(By.TAG_NAME, "a")
            driver.execute_script("arguments[0].click();", link)
            logger.debug("Clicked next page button (AmyUI)")
            # Wait for page to load
            time.sleep(3)
            # Verify table is loaded after click
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                logger.warning("Table did not reload after clicking next page")
            return True
        except NoSuchElementException:
            pass

        try:
            btn = driver.find_element(By.XPATH, "//*[contains(text(),'下一页') and not(@disabled)]")
            driver.execute_script("arguments[0].click();", btn)
            logger.debug("Clicked next page button (generic)")
            # Wait for page to load
            time.sleep(3)
            # Verify table is loaded after click
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
                )
            except TimeoutException:
                logger.warning("Table did not reload after clicking next page")
            return True
        except NoSuchElementException:
            pass

        return False

    @staticmethod
    def parse_table_data(html_content: str, page_name: str, scrape_date: Optional['date'] = None) -> SalesStatisticData:
        """
        Parse all records from current page HTML using COLUMN_MAPPING.
        Does NOT handle pagination — use extract_all_pages for that.
        
        Args:
            html_content: HTML page content
            page_name: Name of the page
            scrape_date: Date of the scraped data (defaults to today if not provided)
        """
        from datetime import date as date_class
        if scrape_date is None:
            scrape_date = datetime.now(timezone.utc).date()
            
        columns = DataExtractor.COLUMN_MAPPING.get(page_name, [])
        records = DataExtractor._parse_one_page(html_content, page_name, columns, scrape_date=scrape_date)
        return SalesStatisticData(
            scrape_date=scrape_date,
            scrape_timestamp=datetime.now(timezone.utc),
            submenu=page_name,
            records=records,
            errors=[],
        )

    @staticmethod
    def _check_driver_health(driver) -> bool:
        """
        Check if WebDriver connection is still healthy.
        Returns False if driver is disconnected/crashed.
        """
        try:
            # Simple health check - get current URL
            _ = driver.current_url
            return True
        except (InvalidSessionIdException, WebDriverException):
            logger.warning("WebDriver disconnected or crashed")
            return False
        except Exception as e:
            logger.debug(f"Driver health check exception: {type(e).__name__}")
            return False

    @staticmethod
    def _check_chrome_memory(max_memory_percent: float = 80.0) -> bool:
        """
        Check if Chrome process is consuming too much memory.
        Returns False if memory usage exceeds threshold.
        """
        try:
            for proc in psutil.process_iter(['name', 'memory_percent']):
                if 'chrome' in proc.info['name'].lower():
                    mem_percent = proc.info['memory_percent'] or 0
                    if mem_percent > max_memory_percent:
                        logger.warning(
                            f"Chrome memory high: {mem_percent:.1f}% "
                            f"(limit: {max_memory_percent}%)"
                        )
                        return False
            return True
        except Exception as e:
            logger.debug(f"Memory check failed: {e}")
            return True  # Assume OK if can't check

    @staticmethod
    def extract_all_pages(
        driver,
        urls_dict: dict,
        start_date=None,
        end_date=None,
    ) -> List[SalesStatisticData]:
        """
        Navigate to each URL, apply date filter, paginate through all pages, and extract every row.

        Args:
            driver: Selenium WebDriver instance
            urls_dict: {page_name: full_url}
            start_date: datetime for filtering in website form (e.g., 2026-01-01 00:00:00)
            end_date: datetime for filtering in website form (e.g., 2026-01-30 23:59:59)

        Returns:
            List[SalesStatisticData], one entry per target page
        """
        all_data: List[SalesStatisticData] = []
        logger.info(f"Extracting data from {len(urls_dict)} pages")
        if start_date and end_date:
            logger.info(f"Date range: {start_date.date()} to {end_date.date()}")

        for page_name, url in urls_dict.items():
            columns = DataExtractor.COLUMN_MAPPING.get(page_name, [])
            records: List[SalesRecord] = []
            errors: List[str] = []
            page_num = 1

            try:
                logger.info(f"Navigating to {page_name}: {url}")
                driver.get(url)
                
                # Determine scrape_date: use start_date if provided, otherwise today
                from datetime import date as date_class
                scrape_date_val = start_date.date() if start_date else datetime.now(timezone.utc).date()

                # Check driver health after navigation
                if not DataExtractor._check_driver_health(driver):
                    msg = f"Failed to extract {page_name}: driver disconnected"
                    logger.error(msg)
                    errors.append(msg)
                    all_data.append(
                        SalesStatisticData(
                            scrape_date=scrape_date_val,
                            scrape_timestamp=datetime.now(timezone.utc),
                            submenu=page_name,
                            records=records,
                            errors=errors,
                        )
                    )
                    continue
                
                # Explicit wait for table to be visible
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
                    )
                    logger.debug(f"{page_name}: table loaded")
                except TimeoutException:
                    logger.warning(f"{page_name}: table did not load within 10s")
                
                time.sleep(1)  # Extra buffer for rendering
                
                # Apply date filter if dates provided
                if start_date and end_date:
                    DataExtractor._apply_date_filter(driver, start_date, end_date)
                    # Re-wait for filtered table
                    try:
                        WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.TAG_NAME, "table"))
                        )
                        logger.debug(f"{page_name}: filtered table loaded")
                    except TimeoutException:
                        logger.warning(f"{page_name}: filtered table did not load")

                while True:
                    # Health check before each page
                    if not DataExtractor._check_driver_health(driver):
                        logger.warning(f"{page_name}: driver disconnected at page {page_num}")
                        break
                    
                    # Memory check - increase threshold to 90% to be less aggressive
                    if not DataExtractor._check_chrome_memory(max_memory_percent=90.0):
                        logger.warning(f"{page_name}: Chrome memory too high, stopping pagination")
                        break
                    
                    # Extract current page with retry mechanism
                    retry_count = 0
                    max_page_retries = 3
                    page_extracted = False
                    
                    while retry_count < max_page_retries and not page_extracted:
                        try:
                            html = driver.page_source
                            page_records = DataExtractor._parse_one_page(html, page_name, columns, scrape_date=scrape_date_val)
                            records.extend(page_records)
                            logger.info(f"{page_name} page {page_num}: scraped {len(page_records)} records (total: {len(records)})")
                            page_extracted = True

                            # Check for next button and click
                            if DataExtractor._has_next_page(driver):
                                logger.debug(f"{page_name}: found next button, clicking page {page_num + 1}")
                                click_success = DataExtractor._click_next_page(driver)
                                if click_success:
                                    # Increase wait time after clicking next page
                                    time.sleep(3)
                                    page_num += 1
                                else:
                                    logger.warning(f"{page_name}: failed to click next button, pagination may be incomplete")
                                    break
                            else:
                                logger.info(f"{page_name}: no next button found, pagination complete at page {page_num}")
                                break
                        
                        except (StaleElementReferenceException, WebDriverException) as e:
                            retry_count += 1
                            logger.warning(f"{page_name}: element stale/connection lost at page {page_num} (attempt {retry_count}/{max_page_retries}): {e}")
                            if retry_count < max_page_retries:
                                time.sleep(5)  # Wait before retry
                                try:
                                    # Try to refresh the page state
                                    driver.execute_script("window.scrollTo(0, 0);")
                                    time.sleep(2)
                                except Exception:
                                    pass
                            else:
                                logger.error(f"{page_name}: failed to extract page {page_num} after {max_page_retries} attempts")
                                break
                    
                    if not page_extracted:
                        logger.warning(f"{page_name}: stopping pagination at page {page_num} due to persistent errors")
                        break

                logger.info(f"Parsed {len(records)} total records from {page_name} ({page_num} page(s))")
                
                # Log warning if pagination seems incomplete (no records on last attempt)
                if page_num > 1 and len(records) < page_num * 10:
                    logger.warning(
                        f"{page_name}: Only {len(records)} records from {page_num} pages. "
                        f"Expected ~{page_num * 10} minimum. Pagination may have stopped early."
                    )

            except Exception as e:
                msg = f"Failed to extract {page_name}: {e}"
                logger.error(msg)
                errors.append(msg)

            all_data.append(
                SalesStatisticData(
                    scrape_date=scrape_date_val,
                    scrape_timestamp=datetime.now(timezone.utc),
                    submenu=page_name,
                    records=records,
                    errors=errors,
                )
            )

        return all_data
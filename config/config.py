"""
Configuration management for web scraper.
Loads configuration from environment variables with validation.
"""
import os
import json
from datetime import datetime
from zoneinfo import ZoneInfo
from dotenv import load_dotenv
from typing import Optional, Dict, Any

# Load .env file
load_dotenv()


class Config:
    """Configuration class for web scraper settings."""

    # Credentials
    WEBSITE_MSISDN: str = os.getenv("WEBSITE_MSISDN", "")
    WEBSITE_PASSWORD: str = os.getenv("WEBSITE_PASSWORD", "")

    # URLs
    BASE_URL: str = os.getenv(
        "BASE_URL", "https://xg.smshj.com"
    )
    LOGIN_URL: str = os.getenv(
        "LOGIN_URL", "https://xg.smshj.com/hbshengma/login.html"
    )
    REPORT_URL: str = os.getenv(
        "REPORT_URL", "https://xg.smshj.com"
    )

    # Scraper Settings
    SCRAPE_INTERVAL: int = int(os.getenv("SCRAPE_INTERVAL", "86400"))
    REQUEST_TIMEOUT: int = int(os.getenv("REQUEST_TIMEOUT", "30"))
    MAX_RETRIES: int = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY: int = int(os.getenv("RETRY_DELAY", "5"))

    # Rate Limiting
    MIN_REQUEST_DELAY: float = float(os.getenv("MIN_REQUEST_DELAY", "1"))
    MAX_REQUEST_DELAY: float = float(os.getenv("MAX_REQUEST_DELAY", "3"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/scraper.log")

    # Browser Settings
    BROWSER_TYPE: str = os.getenv("BROWSER_TYPE", "chrome").lower()
    HEADLESS_MODE: bool = os.getenv("HEADLESS_MODE", "true").lower() == "true"
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    )

    # Data Settings
    OUTPUT_FORMAT: str = os.getenv("OUTPUT_FORMAT", "json")
    DATA_FOLDER: str = os.getenv("DATA_FOLDER", "data")
    KEEP_BACKUPS: int = int(os.getenv("KEEP_BACKUPS", "10"))

    # Scheduling
    SCHEDULE_TIME: str = os.getenv("SCHEDULE_TIME", "02:00")
    SCHEDULE_TIMEZONE: str = os.getenv("SCHEDULE_TIMEZONE", "UTC")

    # ClickHouse
    CLICKHOUSE_HOST: str = os.getenv("CLICKHOUSE_HOST", "")
    CLICKHOUSE_PORT: int = int(os.getenv("CLICKHOUSE_PORT", "8123"))
    CLICKHOUSE_DATABASE: str = os.getenv("CLICKHOUSE_DATABASE", "hbshengma")
    CLICKHOUSE_USER: str = os.getenv("CLICKHOUSE_USER", "default")
    CLICKHOUSE_PASSWORD: str = os.getenv("CLICKHOUSE_PASSWORD", "")
    CLICKHOUSE_SECURE: bool = os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true"

    @classmethod
    def clickhouse_enabled(cls) -> bool:
        """Returns True if ClickHouse host is configured."""
        return bool(cls.CLICKHOUSE_HOST)

    # Helper methods - Parse dates and target URLs
    @staticmethod
    def _parse_date(date_str: str) -> datetime:
        """Parse date string (YYYY-MM-DD) to datetime with UTC timezone.
        
        All dates use UTC (server, website, ClickHouse timezone).
        For Jakarta reference: add 7 hours to UTC time.
        """
        utc_tz = ZoneInfo("UTC")
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return dt.replace(tzinfo=utc_tz)
        except ValueError as e:
            raise ValueError(f"Invalid date format '{date_str}': {e}")

    @staticmethod
    def _parse_target_urls(urls_json: str) -> Dict[str, str]:
        """Parse TARGET_URLS from JSON string."""
        try:
            urls_dict = json.loads(urls_json)
            if not isinstance(urls_dict, dict):
                raise ValueError("TARGET_URLS must be a JSON object")
            return urls_dict
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid TARGET_URLS JSON: {e}")

    # Date Range (UTC timezone) - Lazy initialization
    @classmethod
    def get_start_date(cls) -> datetime:
        """Get START_DATE with UTC timezone."""
        if not hasattr(cls, "_start_date"):
            cls._start_date = cls._parse_date(os.getenv("START_DATE", "2026-01-01"))
        return cls._start_date

    @classmethod
    def get_end_date(cls) -> datetime:
        """Get END_DATE with UTC timezone."""
        if not hasattr(cls, "_end_date"):
            cls._end_date = cls._parse_date(os.getenv("END_DATE", "2026-05-05"))
        return cls._end_date

    @classmethod
    def get_target_urls(cls) -> Dict[str, str]:
        """Get TARGET_URLS from config."""
        if not hasattr(cls, "_target_urls"):
            default_urls = (
                '{"paydetail": "/hbshengma/operator/paydetail.html", '
                '"deliverydetail": "/hbshengma/operator/deliverydetail.html", '
                '"cashdetail": "/hbshengma/operator/cashdetail.html", '
                '"essDetail": "/hbshengma/operator/essDetail.html", '
                '"mtOrder": "/hbshengma/operator/mtOrder.html", '
                '"orderThird": "/hbshengma/operator/orderThird.html", '
                '"orderThirdMachine": "/hbshengma/operator/orderThirdMachine.html", '
                '"onlineOrderDetail": "/hbshengma/onlineOrderDetail.html"}'
            )
            cls._target_urls = cls._parse_target_urls(os.getenv("TARGET_URLS", default_urls))
        return cls._target_urls

    @classmethod
    def validate(cls) -> bool:
        """Validate critical configuration values."""
        if not cls.WEBSITE_MSISDN:
            raise ValueError("WEBSITE_MSISDN is not set in .env file")
        if not cls.WEBSITE_PASSWORD:
            raise ValueError("WEBSITE_PASSWORD is not set in .env file")
        return True

    @classmethod
    def get_all(cls) -> dict:
        """Get all configuration as dictionary (for logging)."""
        return {
            k: v
            for k, v in cls.__dict__.items()
            if not k.startswith("_") and k.isupper()
        }

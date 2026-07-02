"""
Centralized logging configuration for web scraper.
"""
import logging
import logging.handlers
import os
from config.config import Config

# Create logs directory if not exists
os.makedirs(os.path.dirname(Config.LOG_FILE), exist_ok=True)


def setup_logging(logger_name: str = "web_scraper") -> logging.Logger:
    """
    Setup logging configuration with both console and file handlers.

    Args:
        logger_name: Name of the logger

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(logger_name)
    logger.setLevel(getattr(logging, Config.LOG_LEVEL))

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    formatter = logging.Formatter(
        fmt="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        Config.LOG_FILE, maxBytes=10 * 1024 * 1024, backupCount=5  # 10MB per file
    )
    file_handler.setLevel(getattr(logging, Config.LOG_LEVEL))
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


# Initialize default logger
logger = setup_logging()

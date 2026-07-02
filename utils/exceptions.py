"""
Custom exceptions for web scraper.
"""


class ScraperException(Exception):
    """Base exception for scraper errors."""

    pass


class LoginFailedError(ScraperException):
    """Raised when login to website fails."""

    pass


class ParsingError(ScraperException):
    """Raised when HTML parsing fails."""

    pass


class NetworkError(ScraperException):
    """Raised when network operation fails."""

    pass


class DataValidationError(ScraperException):
    """Raised when data validation fails."""

    pass


class StorageError(ScraperException):
    """Raised when data storage operation fails."""

    pass


class ConfigurationError(ScraperException):
    """Raised when configuration is invalid."""

    pass

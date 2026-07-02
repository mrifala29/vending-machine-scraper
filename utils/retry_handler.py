"""
Retry handler for resilient job execution.
Automatically retries failed jobs with exponential backoff.
"""
import time
from typing import Callable, Optional, Type, Tuple
from datetime import datetime, timezone
from utils.logging_setup import logger
from utils.exceptions import ScraperException


class RetryConfig:
    """Configuration for retry behavior."""
    
    def __init__(
        self,
        max_attempts: int = 4,
        retry_delay_seconds: int = 300,  # 5 minutes
        backoff_multiplier: float = 1.0,  # No exponential backoff, fixed delay
        retryable_exceptions: Tuple[Type[Exception], ...] = (
            Exception,  # Catch all exceptions by default
        ),
    ):
        """
        Initialize retry configuration.
        
        Args:
            max_attempts: Maximum total attempts (including first try)
            retry_delay_seconds: Delay between retries in seconds
            backoff_multiplier: Multiplier for delay (1.0 = fixed delay, 1.5 = exponential)
            retryable_exceptions: Tuple of exception types to retry on
        """
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.backoff_multiplier = backoff_multiplier
        self.retryable_exceptions = retryable_exceptions


class RetryHandler:
    """
    Smart retry handler for job execution.
    
    Retries failed jobs with configurable delay and attempt limits.
    Perfect for headless servers with intermittent network issues.
    """
    
    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry handler.
        
        Args:
            config: RetryConfig object (uses defaults if not provided)
        """
        self.config = config or RetryConfig()
    
    def execute_with_retry(
        self,
        job_func: Callable,
        job_name: str,
        *args,
        **kwargs
    ) -> bool:
        """
        Execute job with automatic retry on failure.
        
        Args:
            job_func: Function to execute (should raise exception on failure)
            job_name: Name of the job (for logging)
            *args: Positional arguments for job_func
            **kwargs: Keyword arguments for job_func
            
        Returns:
            True if job succeeded, False if failed after all retries
        """
        logger.info(f"[{job_name}] Starting job with retry config: "
                   f"max_attempts={self.config.max_attempts}, "
                   f"retry_delay={self.config.retry_delay_seconds}s")
        
        attempt = 0
        last_error = None
        
        while attempt < self.config.max_attempts:
            attempt += 1
            
            try:
                logger.info(f"[{job_name}] Attempt {attempt}/{self.config.max_attempts}")
                
                # Execute the job
                job_func(*args, **kwargs)
                
                # Success!
                logger.info(f"[{job_name}] ✓ Job succeeded on attempt {attempt}")
                return True
                
            except self.config.retryable_exceptions as e:
                last_error = e
                logger.warning(f"[{job_name}] ✗ Attempt {attempt} failed: {str(e)}")
                
                # If this is the last attempt, don't retry
                if attempt >= self.config.max_attempts:
                    logger.error(f"[{job_name}] Max retries ({self.config.max_attempts}) exceeded")
                    break
                
                # Calculate delay for next retry
                delay = self._calculate_delay(attempt)
                logger.info(
                    f"[{job_name}] Retrying in {delay} seconds "
                    f"({self.config.max_attempts - attempt} attempts remaining)..."
                )
                
                # Sleep before retry
                time.sleep(delay)
                
            except Exception as e:
                # Non-retryable exception (e.g., lock timeout, config error)
                logger.error(f"[{job_name}] Non-retryable error: {str(e)}")
                return False
        
        # All retries exhausted
        logger.error(f"[{job_name}] ✗ Job failed after {attempt} attempts")
        if last_error:
            logger.error(f"[{job_name}] Last error: {last_error}")
        
        return False
    
    def _calculate_delay(self, attempt: int) -> int:
        """
        Calculate delay before next retry with optional exponential backoff.
        
        Args:
            attempt: Current attempt number (1-indexed)
            
        Returns:
            Delay in seconds
        """
        if self.config.backoff_multiplier == 1.0:
            # Fixed delay
            return self.config.retry_delay_seconds
        else:
            # Exponential backoff: delay * (multiplier ^ (attempt - 1))
            delay = self.config.retry_delay_seconds * (
                self.config.backoff_multiplier ** (attempt - 1)
            )
            return int(delay)

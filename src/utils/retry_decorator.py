"""
Retry Decorator with Exponential Backoff and Timeout Support

Provides retry functionality for API calls and network operations.
Updated: 2025-12-04 - Added timeout support to prevent indefinite hangs.
"""

import logging
import signal
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from functools import wraps
from typing import Callable, Optional

logger = logging.getLogger(__name__)


class TimeoutException(Exception):
    """Raised when a function call times out."""
    pass


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    timeout: Optional[float] = 10.0,  # Default 10 second timeout per attempt
    total_timeout: Optional[float] = 60.0,  # Default 60 second total timeout
):
    """
    Decorator for retrying functions with exponential backoff and timeout.

    Args:
        max_retries: Maximum number of retry attempts
        initial_delay: Initial delay in seconds
        backoff_factor: Multiplier for delay after each retry
        exceptions: Tuple of exception types to catch and retry
        timeout: Timeout per attempt in seconds (default: 10s, None to disable)
        total_timeout: Total timeout for all attempts (default: 60s, None to disable)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0, timeout=5.0)
        def fetch_data():
            return api.get_data()
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            delay = initial_delay
            start_time = time.time()

            for attempt in range(max_retries):
                # Check total timeout
                if total_timeout and (time.time() - start_time) >= total_timeout:
                    raise TimeoutException(
                        f"{func.__name__} exceeded total timeout of {total_timeout}s"
                    )

                try:
                    if timeout:
                        # Execute with per-attempt timeout using ThreadPoolExecutor
                        with ThreadPoolExecutor(max_workers=1) as executor:
                            future = executor.submit(func, *args, **kwargs)
                            try:
                                return future.result(timeout=timeout)
                            except FuturesTimeoutError:
                                raise TimeoutException(
                                    f"{func.__name__} timed out after {timeout}s on attempt {attempt + 1}"
                                )
                    else:
                        return func(*args, **kwargs)

                except TimeoutException as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} timed out after {max_retries} attempts")
                        raise
                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} timed out. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)
                    delay *= backoff_factor

                except exceptions as e:
                    if attempt == max_retries - 1:
                        logger.error(f"{func.__name__} failed after {max_retries} attempts: {e}")
                        raise

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_retries} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay *= backoff_factor

            return func(*args, **kwargs)

        return wrapper

    return decorator

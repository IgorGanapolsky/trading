#!/usr/bin/env python3
"""
Exponential retry utilities for robust API calls.
Prevents transient failures from causing workflow failures.
"""

import logging
import time
from functools import wraps
from typing import Any, Callable

logger = logging.getLogger(__name__)


class RetryableError(Exception):
    """Base exception for retryable errors."""

    pass


class TemporaryAPIError(RetryableError):
    """Temporary API error that should be retried."""

    pass


def exponential_retry(
    max_attempts: int = 4,
    base_delay: float = 1.0,
    max_delay: float = 16.0,
    retryable_exceptions: list[type[Exception]] | None = None,
    backoff_multiplier: float = 2.0,
):
    """
    Decorator for exponential backoff retry logic.

    Args:
        max_attempts: Maximum number of attempts (including first try)
        base_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: List of exception types to retry on
        backoff_multiplier: Multiplier for exponential backoff
    """
    if retryable_exceptions is None:
        retryable_exceptions = [
            RetryableError,
            TemporaryAPIError,
            ConnectionError,
            TimeoutError,
        ]

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None

            for attempt in range(max_attempts):
                try:
                    result = func(*args, **kwargs)
                    if attempt > 0:
                        logger.info(f"{func.__name__} succeeded on attempt {attempt + 1}")
                    return result

                except Exception as e:
                    last_exception = e

                    # Check if this exception should be retried
                    should_retry = any(isinstance(e, exc_type) for exc_type in retryable_exceptions)

                    if not should_retry or attempt == max_attempts - 1:
                        # Don't retry this exception type, or we've exhausted attempts
                        logger.error(f"{func.__name__} failed permanently: {e}")
                        raise e

                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (backoff_multiplier**attempt), max_delay)

                    logger.warning(
                        f"{func.__name__} attempt {attempt + 1}/{max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )

                    time.sleep(delay)

            # Should never reach here, but just in case
            raise last_exception

        return wrapper

    return decorator


def retry_api_call(
    func: Callable, *args, max_attempts: int = 3, base_delay: float = 1.0, **kwargs
) -> Any:
    """
    Utility function to retry an API call with exponential backoff.

    Args:
        func: Function to call
        *args: Arguments to pass to function
        max_attempts: Maximum number of attempts
        base_delay: Initial delay between retries
        **kwargs: Keyword arguments to pass to function
    """

    @exponential_retry(max_attempts=max_attempts, base_delay=base_delay)
    def _wrapped_call():
        return func(*args, **kwargs)

    return _wrapped_call()


# Common retry configurations
quick_retry = exponential_retry(max_attempts=2, base_delay=0.5, max_delay=2.0)
standard_retry = exponential_retry(max_attempts=3, base_delay=1.0, max_delay=8.0)
robust_retry = exponential_retry(max_attempts=4, base_delay=1.0, max_delay=16.0)


# Example usage functions
@standard_retry
def fetch_with_retry(url: str, timeout: float = 10.0) -> Any:
    """Example function showing how to use retry decorator."""
    import requests

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        raise TemporaryAPIError(f"Timeout fetching {url}")
    except requests.exceptions.ConnectionError:
        raise TemporaryAPIError(f"Connection error fetching {url}")
    except requests.exceptions.HTTPError as e:
        if e.response.status_code >= 500:
            raise TemporaryAPIError(f"Server error {e.response.status_code}")
        else:
            # Don't retry client errors (4xx)
            raise e


@robust_retry
def check_api_health(api_name: str, check_func: Callable) -> bool:
    """Check API health with retry logic."""
    try:
        check_func()
        logger.info(f"{api_name} health check passed")
        return True
    except Exception as e:
        logger.error(f"{api_name} health check failed: {e}")
        raise TemporaryAPIError(f"{api_name} health check failed")


if __name__ == "__main__":
    # Example usage
    @standard_retry
    def flaky_function():
        import random

        if random.random() < 0.7:  # 70% chance of failure
            raise TemporaryAPIError("Simulated API failure")
        return "Success!"

    try:
        result = flaky_function()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Final failure: {e}")
# ruff: noqa: UP035,UP045

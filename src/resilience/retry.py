"""
Retry Logic with Exponential Backoff.

Provides reliable retry mechanisms for transient failures.

Created: Jan 19, 2026 (LL-249)
"""

import logging
import random
import time
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 4
    base_delay: float = 2.0  # Initial delay in seconds
    max_delay: float = 60.0  # Maximum delay
    exponential_base: float = 2.0
    jitter: bool = True  # Add randomness to prevent thundering herd
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)


def retry_with_backoff(
    config: RetryConfig | None = None,
    max_attempts: int = 4,
    base_delay: float = 2.0,
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    Decorator for retrying functions with exponential backoff.

    Usage:
        @retry_with_backoff(max_attempts=4, base_delay=2.0)
        def call_api():
            return requests.get(url)

    Or with config:
        config = RetryConfig(max_attempts=5, base_delay=1.0)
        @retry_with_backoff(config=config)
        def risky_operation():
            ...
    """
    if config is None:
        config = RetryConfig(
            max_attempts=max_attempts,
            base_delay=base_delay,
            retryable_exceptions=retryable_exceptions,
        )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_exception: Exception | None = None

            for attempt in range(1, config.max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except config.retryable_exceptions as e:
                    last_exception = e

                    if attempt == config.max_attempts:
                        logger.error(
                            f"[{func.__name__}] All {config.max_attempts} attempts failed. "
                            f"Last error: {e}"
                        )
                        raise

                    # Calculate delay with exponential backoff
                    delay = min(
                        config.base_delay * (config.exponential_base ** (attempt - 1)),
                        config.max_delay,
                    )

                    # Add jitter (±25%)
                    if config.jitter:
                        delay *= 0.75 + random.random() * 0.5

                    logger.warning(
                        f"[{func.__name__}] Attempt {attempt}/{config.max_attempts} failed: {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    time.sleep(delay)

            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError(f"Unexpected state in retry for {func.__name__}")

        return wrapper

    return decorator


class RetryableOperation:
    """
    Context manager for retryable operations.

    Usage:
        with RetryableOperation(max_attempts=3, base_delay=1.0) as retry:
            for attempt in retry:
                try:
                    result = risky_operation()
                    break  # Success
                except SomeError as e:
                    retry.record_failure(e)
    """

    def __init__(
        self,
        max_attempts: int = 4,
        base_delay: float = 2.0,
        max_delay: float = 60.0,
        operation_name: str = "operation",
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.operation_name = operation_name
        self._attempt = 0
        self._last_error: Exception | None = None

    def __enter__(self) -> "RetryableOperation":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        # Don't suppress exceptions - let them propagate
        pass

    def __iter__(self):
        """Iterate through retry attempts."""
        for attempt in range(1, self.max_attempts + 1):
            self._attempt = attempt
            yield attempt

    def record_failure(self, error: Exception) -> None:
        """Record a failure and sleep before next attempt."""
        self._last_error = error

        if self._attempt >= self.max_attempts:
            logger.error(
                f"[{self.operation_name}] All {self.max_attempts} attempts exhausted. "
                f"Last error: {error}"
            )
            raise error

        delay = min(self.base_delay * (2 ** (self._attempt - 1)), self.max_delay)
        delay *= 0.75 + random.random() * 0.5  # Jitter

        logger.warning(
            f"[{self.operation_name}] Attempt {self._attempt}/{self.max_attempts} failed: {error}. "
            f"Retrying in {delay:.1f}s..."
        )
        time.sleep(delay)

    @property
    def attempt(self) -> int:
        """Current attempt number."""
        return self._attempt

    @property
    def last_error(self) -> Exception | None:
        """Last recorded error."""
        return self._last_error

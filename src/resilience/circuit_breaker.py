"""
Circuit Breaker Pattern - Prevent Cascading Failures.

Implements the circuit breaker pattern to:
1. Detect when external services are failing
2. Stop making requests to failing services
3. Allow services time to recover
4. Gradually restore traffic

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service failing, requests blocked immediately
- HALF_OPEN: Testing if service recovered

Created: Jan 19, 2026 (LL-249)
"""

import time
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, TypeVar, Any
from functools import wraps
import logging

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal - requests pass through
    OPEN = "open"          # Failing - requests blocked
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for external API calls.

    Usage:
        breaker = CircuitBreaker(name="alpaca_api", failure_threshold=5)

        @breaker
        def call_alpaca():
            return alpaca_client.get_account()

    Or manually:
        with breaker:
            result = risky_operation()
    """
    name: str
    failure_threshold: int = 5      # Failures before opening circuit
    recovery_timeout: float = 60.0  # Seconds before trying half-open
    success_threshold: int = 2      # Successes in half-open to close

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float = field(default=0.0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for timeout transition."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                # Check if we should transition to half-open
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    logger.info(f"[{self.name}] Circuit transitioning OPEN -> HALF_OPEN")
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
            return self._state

    def _record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.success_threshold:
                    logger.info(f"[{self.name}] Circuit CLOSED - service recovered")
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def _record_failure(self, error: Exception) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                logger.warning(f"[{self.name}] Circuit OPEN - failure in half-open: {error}")
                self._state = CircuitState.OPEN
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    logger.warning(f"[{self.name}] Circuit OPEN - threshold reached ({self._failure_count} failures)")
                    self._state = CircuitState.OPEN

    def allow_request(self) -> bool:
        """Check if a request should be allowed."""
        current_state = self.state  # Triggers timeout check
        if current_state == CircuitState.OPEN:
            return False
        return True

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to wrap function with circuit breaker."""
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            if not self.allow_request():
                raise CircuitBreakerOpenError(
                    f"Circuit breaker [{self.name}] is OPEN - "
                    f"service unavailable. Retry after {self.recovery_timeout}s"
                )

            try:
                result = func(*args, **kwargs)
                self._record_success()
                return result
            except Exception as e:
                self._record_failure(e)
                raise

        return wrapper

    def __enter__(self) -> "CircuitBreaker":
        """Context manager entry."""
        if not self.allow_request():
            raise CircuitBreakerOpenError(
                f"Circuit breaker [{self.name}] is OPEN"
            )
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        """Context manager exit."""
        if exc_type is None:
            self._record_success()
        else:
            self._record_failure(exc_val)
        return False  # Don't suppress exceptions

    def reset(self) -> None:
        """Manually reset the circuit breaker."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info(f"[{self.name}] Circuit manually reset to CLOSED")

    def get_status(self) -> dict:
        """Get circuit breaker status for monitoring."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
            "last_failure": self._last_failure_time,
        }


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and blocking requests."""
    pass


# Pre-configured circuit breakers for common services
ALPACA_BREAKER = CircuitBreaker(
    name="alpaca_api",
    failure_threshold=5,
    recovery_timeout=60.0,
)

VERTEX_RAG_BREAKER = CircuitBreaker(
    name="vertex_rag",
    failure_threshold=3,
    recovery_timeout=120.0,
)

GITHUB_API_BREAKER = CircuitBreaker(
    name="github_api",
    failure_threshold=5,
    recovery_timeout=30.0,
)

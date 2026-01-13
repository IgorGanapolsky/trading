"""
API Circuit Breaker - Halt Trading After Repeated API Failures

CRITICAL SAFETY FEATURE - Added Jan 13, 2026

This module implements a circuit breaker pattern for API calls.
After N consecutive failures, trading is halted to prevent blind trading.

Architecture:
    API Call -> Circuit Breaker Check -> Retry Logic -> Execution

The circuit breaker:
1. Tracks consecutive API failures globally
2. Trips (opens) after threshold exceeded
3. Stays open for cooldown period
4. Alerts CEO when tripped
5. Auto-resets after successful calls

Author: AI Trading System
Date: January 13, 2026
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

# Configuration
MAX_CONSECUTIVE_FAILURES = 5  # Trip after 5 consecutive failures
COOLDOWN_SECONDS = 300  # 5 minute cooldown when tripped
STATE_FILE = Path("data/api_circuit_breaker_state.json")


@dataclass
class CircuitBreakerState:
    """State of the API circuit breaker."""

    is_open: bool  # True = tripped, blocking all calls
    consecutive_failures: int
    last_failure_time: str | None
    last_success_time: str | None
    trip_time: str | None
    trip_count: int  # How many times tripped since startup


class APICircuitBreaker:
    """
    Global circuit breaker for API calls.

    Usage:
        breaker = get_api_circuit_breaker()

        # Before API call
        if breaker.is_open():
            raise CircuitBreakerOpen("Trading halted due to API failures")

        try:
            result = api_call()
            breaker.record_success()
        except Exception as e:
            breaker.record_failure(str(e))
            raise
    """

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Singleton pattern - only one circuit breaker."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        self.consecutive_failures = 0
        self.last_failure_time: datetime | None = None
        self.last_success_time: datetime | None = None
        self.trip_time: datetime | None = None
        self.trip_count = 0
        self._is_open = False

        self._load_state()
        logger.info(
            f"🔌 API Circuit Breaker initialized "
            f"(threshold={MAX_CONSECUTIVE_FAILURES}, cooldown={COOLDOWN_SECONDS}s)"
        )

    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking calls)."""
        if not self._is_open:
            return False

        # Check if cooldown has expired
        if self.trip_time:
            cooldown_expires = self.trip_time + timedelta(seconds=COOLDOWN_SECONDS)
            if datetime.now() >= cooldown_expires:
                logger.info("⚡ Circuit breaker cooldown expired, resetting...")
                self._reset()
                return False

        return True

    def record_success(self) -> None:
        """Record a successful API call."""
        self.last_success_time = datetime.now()
        if self.consecutive_failures > 0:
            logger.info(
                f"✅ API call succeeded after {self.consecutive_failures} failures, "
                "resetting counter"
            )
        self.consecutive_failures = 0
        self._is_open = False
        self._save_state()

    def record_failure(self, error_msg: str) -> None:
        """Record a failed API call."""
        self.consecutive_failures += 1
        self.last_failure_time = datetime.now()

        logger.warning(
            f"⚠️ API failure #{self.consecutive_failures}/{MAX_CONSECUTIVE_FAILURES}: {error_msg}"
        )

        if self.consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
            self._trip(error_msg)

        self._save_state()

    def _trip(self, error_msg: str) -> None:
        """Trip the circuit breaker."""
        if self._is_open:
            return  # Already tripped

        self._is_open = True
        self.trip_time = datetime.now()
        self.trip_count += 1

        logger.critical(
            f"🚨 CIRCUIT BREAKER TRIPPED! "
            f"{self.consecutive_failures} consecutive API failures. "
            f"Trading halted for {COOLDOWN_SECONDS}s."
        )

        # Alert CEO
        self._send_alert(error_msg)

    def _reset(self) -> None:
        """Reset the circuit breaker."""
        self._is_open = False
        self.consecutive_failures = 0
        self.trip_time = None
        self._save_state()
        logger.info("✅ Circuit breaker reset, trading resumed")

    def _send_alert(self, error_msg: str) -> None:
        """Send alert to CEO when circuit breaker trips."""
        try:
            from src.utils.error_monitoring import send_slack_alert

            send_slack_alert(
                message=(
                    f"🚨 *API CIRCUIT BREAKER TRIPPED*\n\n"
                    f"Trading has been HALTED due to repeated API failures!\n\n"
                    f"Consecutive Failures: {self.consecutive_failures}\n"
                    f"Last Error: {error_msg}\n"
                    f"Cooldown: {COOLDOWN_SECONDS} seconds\n"
                    f"Trip Count (session): {self.trip_count}\n\n"
                    f"Trading will auto-resume after cooldown, or fix the underlying issue."
                ),
                level="error",
            )
        except Exception as e:
            logger.error(f"Failed to send circuit breaker alert: {e}")

    def _load_state(self) -> None:
        """Load persisted state."""
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    state = json.load(f)
                    self.consecutive_failures = state.get("consecutive_failures", 0)
                    self.trip_count = state.get("trip_count", 0)
                    if state.get("trip_time"):
                        self.trip_time = datetime.fromisoformat(state["trip_time"])
                        # Check if still in cooldown
                        cooldown_expires = self.trip_time + timedelta(seconds=COOLDOWN_SECONDS)
                        self._is_open = datetime.now() < cooldown_expires
            except Exception as e:
                logger.warning(f"Failed to load circuit breaker state: {e}")

    def _save_state(self) -> None:
        """Persist state."""
        try:
            STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(STATE_FILE, "w") as f:
                json.dump(
                    {
                        "consecutive_failures": self.consecutive_failures,
                        "trip_count": self.trip_count,
                        "last_failure_time": self.last_failure_time.isoformat()
                        if self.last_failure_time
                        else None,
                        "last_success_time": self.last_success_time.isoformat()
                        if self.last_success_time
                        else None,
                        "trip_time": self.trip_time.isoformat() if self.trip_time else None,
                        "is_open": self._is_open,
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.warning(f"Failed to save circuit breaker state: {e}")

    def get_status(self) -> CircuitBreakerState:
        """Get current circuit breaker status."""
        return CircuitBreakerState(
            is_open=self.is_open(),
            consecutive_failures=self.consecutive_failures,
            last_failure_time=self.last_failure_time.isoformat()
            if self.last_failure_time
            else None,
            last_success_time=self.last_success_time.isoformat()
            if self.last_success_time
            else None,
            trip_time=self.trip_time.isoformat() if self.trip_time else None,
            trip_count=self.trip_count,
        )


class CircuitBreakerOpen(Exception):
    """Raised when attempting API call while circuit breaker is open."""

    pass


# Singleton accessor
_circuit_breaker: APICircuitBreaker | None = None


def get_api_circuit_breaker() -> APICircuitBreaker:
    """Get the global API circuit breaker instance."""
    global _circuit_breaker
    if _circuit_breaker is None:
        _circuit_breaker = APICircuitBreaker()
    return _circuit_breaker


def check_circuit_breaker() -> None:
    """
    Check if circuit breaker is open and raise exception if so.

    Use this before any critical API call:
        check_circuit_breaker()
        result = alpaca_api.submit_order(...)
    """
    breaker = get_api_circuit_breaker()
    if breaker.is_open():
        raise CircuitBreakerOpen(
            f"Trading halted: {breaker.consecutive_failures} consecutive API failures. "
            f"Cooldown remaining: {COOLDOWN_SECONDS}s"
        )

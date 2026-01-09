"""
Circuit breaker implementation for trading safety.

This module provides a simple CircuitBreaker class that tracks consecutive losses
and API errors to halt trading when thresholds are exceeded.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass
class CircuitBreakerState:
    """State tracking for circuit breaker."""

    is_tripped: bool = False
    trip_reason: str = ""
    trip_details: str = ""
    consecutive_losses: int = 0
    api_errors_today: int = 0
    last_reset: str = ""
    trip_time: str = ""


class CircuitBreaker:
    """
    Circuit breaker that monitors trading health and halts when thresholds exceeded.

    Thresholds:
    - 3 consecutive losses: Trip breaker
    - 5 API errors in a day: Trip breaker
    - Daily loss > 2%: Trip breaker

    The breaker must be manually reset after investigation.
    """

    # Thresholds
    MAX_CONSECUTIVE_LOSSES = 3
    MAX_API_ERRORS_PER_DAY = 5
    MAX_DAILY_LOSS_PCT = 0.02  # 2%

    def __init__(self, state_file: str | Path | None = None):
        """Initialize circuit breaker with optional state file path."""
        self.state_file = Path(state_file or "data/circuit_breaker_state.json")
        self._state = self._load_state()

    def _load_state(self) -> CircuitBreakerState:
        """Load state from file or create new."""
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text())
                return CircuitBreakerState(**data)
            except (json.JSONDecodeError, TypeError):
                pass
        return CircuitBreakerState(last_reset=datetime.now().isoformat())

    def _save_state(self) -> None:
        """Save current state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "is_tripped": self._state.is_tripped,
            "trip_reason": self._state.trip_reason,
            "trip_details": self._state.trip_details,
            "consecutive_losses": self._state.consecutive_losses,
            "api_errors_today": self._state.api_errors_today,
            "last_reset": self._state.last_reset,
            "trip_time": self._state.trip_time,
        }
        self.state_file.write_text(json.dumps(data, indent=2))

    def get_status(self) -> dict:
        """Get current circuit breaker status."""
        return {
            "is_tripped": self._state.is_tripped,
            "trip_reason": self._state.trip_reason,
            "trip_details": self._state.trip_details,
            "consecutive_losses": self._state.consecutive_losses,
            "api_errors_today": self._state.api_errors_today,
            "last_reset": self._state.last_reset,
            "trip_time": self._state.trip_time,
        }

    def record_loss(self) -> bool:
        """
        Record a trading loss. Returns True if breaker trips.
        """
        self._state.consecutive_losses += 1

        if self._state.consecutive_losses >= self.MAX_CONSECUTIVE_LOSSES:
            self._trip(
                reason="consecutive_losses",
                details=f"{self._state.consecutive_losses} consecutive losses",
            )
            return True
        self._save_state()
        return False

    def record_win(self) -> None:
        """Record a trading win - resets consecutive loss counter."""
        self._state.consecutive_losses = 0
        self._save_state()

    def record_api_error(self) -> bool:
        """
        Record an API error. Returns True if breaker trips.
        """
        self._state.api_errors_today += 1

        if self._state.api_errors_today >= self.MAX_API_ERRORS_PER_DAY:
            self._trip(
                reason="api_errors",
                details=f"{self._state.api_errors_today} API errors today",
            )
            return True
        self._save_state()
        return False

    def check_daily_loss(self, current_pnl_pct: float) -> bool:
        """
        Check if daily loss exceeds threshold. Returns True if breaker trips.

        Args:
            current_pnl_pct: Current P&L as decimal (e.g., -0.02 for -2%)
        """
        if current_pnl_pct < -self.MAX_DAILY_LOSS_PCT:
            self._trip(
                reason="daily_loss",
                details=f"Daily loss {current_pnl_pct:.2%} exceeds {self.MAX_DAILY_LOSS_PCT:.2%} threshold",
            )
            return True
        return False

    def _trip(self, reason: str, details: str) -> None:
        """Trip the circuit breaker."""
        self._state.is_tripped = True
        self._state.trip_reason = reason
        self._state.trip_details = details
        self._state.trip_time = datetime.now().isoformat()
        self._save_state()
        print(f"🚨 CIRCUIT BREAKER TRIPPED: {reason} - {details}")

    def reset(self) -> None:
        """Manually reset the circuit breaker after investigation."""
        self._state = CircuitBreakerState(last_reset=datetime.now().isoformat())
        self._save_state()
        print("✅ Circuit breaker reset")

    def reset_daily_counters(self) -> None:
        """Reset daily counters (call at start of each trading day)."""
        self._state.api_errors_today = 0
        self._save_state()


# Convenience function for quick status check
def is_trading_halted() -> bool:
    """Quick check if trading is halted by circuit breaker."""
    return CircuitBreaker().get_status()["is_tripped"]

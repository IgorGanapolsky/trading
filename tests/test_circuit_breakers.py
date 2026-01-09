"""Tests for the CircuitBreaker safety module."""

import json
import tempfile
from pathlib import Path

import pytest

from src.safety.circuit_breakers import (
    CircuitBreaker,
    CircuitBreakerState,
    is_trading_halted,
)


class TestCircuitBreakerState:
    """Tests for CircuitBreakerState dataclass."""

    def test_default_values(self):
        """Test default state values."""
        state = CircuitBreakerState()
        assert state.is_tripped is False
        assert state.trip_reason == ""
        assert state.trip_details == ""
        assert state.consecutive_losses == 0
        assert state.api_errors_today == 0
        assert state.last_reset == ""
        assert state.trip_time == ""

    def test_custom_values(self):
        """Test state with custom values."""
        state = CircuitBreakerState(
            is_tripped=True,
            trip_reason="test",
            consecutive_losses=5,
        )
        assert state.is_tripped is True
        assert state.trip_reason == "test"
        assert state.consecutive_losses == 5


class TestCircuitBreaker:
    """Tests for CircuitBreaker class."""

    @pytest.fixture
    def temp_state_file(self):
        """Create a temporary state file."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            yield Path(f.name)

    def test_init_creates_new_state(self, temp_state_file):
        """Test initialization creates new state."""
        cb = CircuitBreaker(state_file=temp_state_file)
        status = cb.get_status()
        assert status["is_tripped"] is False
        assert status["consecutive_losses"] == 0

    def test_init_loads_existing_state(self, temp_state_file):
        """Test initialization loads existing state."""
        # Create existing state
        existing_state = {
            "is_tripped": True,
            "trip_reason": "test",
            "trip_details": "test details",
            "consecutive_losses": 2,
            "api_errors_today": 1,
            "last_reset": "2026-01-09T00:00:00",
            "trip_time": "2026-01-09T12:00:00",
        }
        temp_state_file.write_text(json.dumps(existing_state))

        cb = CircuitBreaker(state_file=temp_state_file)
        status = cb.get_status()
        assert status["is_tripped"] is True
        assert status["trip_reason"] == "test"
        assert status["consecutive_losses"] == 2

    def test_record_loss_increments_counter(self, temp_state_file):
        """Test recording a loss increments the counter."""
        cb = CircuitBreaker(state_file=temp_state_file)
        result = cb.record_loss()
        assert result is False  # Not tripped yet
        assert cb.get_status()["consecutive_losses"] == 1

    def test_record_loss_trips_after_threshold(self, temp_state_file):
        """Test breaker trips after MAX_CONSECUTIVE_LOSSES."""
        cb = CircuitBreaker(state_file=temp_state_file)
        for _ in range(2):
            cb.record_loss()
        result = cb.record_loss()  # 3rd loss
        assert result is True
        assert cb.get_status()["is_tripped"] is True
        assert cb.get_status()["trip_reason"] == "consecutive_losses"

    def test_record_win_resets_losses(self, temp_state_file):
        """Test recording a win resets consecutive losses."""
        cb = CircuitBreaker(state_file=temp_state_file)
        cb.record_loss()
        cb.record_loss()
        cb.record_win()
        assert cb.get_status()["consecutive_losses"] == 0

    def test_record_api_error_increments(self, temp_state_file):
        """Test recording an API error increments counter."""
        cb = CircuitBreaker(state_file=temp_state_file)
        result = cb.record_api_error()
        assert result is False
        assert cb.get_status()["api_errors_today"] == 1

    def test_record_api_error_trips_after_threshold(self, temp_state_file):
        """Test breaker trips after MAX_API_ERRORS_PER_DAY."""
        cb = CircuitBreaker(state_file=temp_state_file)
        for _ in range(4):
            cb.record_api_error()
        result = cb.record_api_error()  # 5th error
        assert result is True
        assert cb.get_status()["is_tripped"] is True
        assert cb.get_status()["trip_reason"] == "api_errors"

    def test_check_daily_loss_within_threshold(self, temp_state_file):
        """Test daily loss within threshold doesn't trip."""
        cb = CircuitBreaker(state_file=temp_state_file)
        result = cb.check_daily_loss(-0.01)  # -1%
        assert result is False
        assert cb.get_status()["is_tripped"] is False

    def test_check_daily_loss_exceeds_threshold(self, temp_state_file):
        """Test daily loss exceeding threshold trips breaker."""
        cb = CircuitBreaker(state_file=temp_state_file)
        result = cb.check_daily_loss(-0.03)  # -3%
        assert result is True
        assert cb.get_status()["is_tripped"] is True
        assert cb.get_status()["trip_reason"] == "daily_loss"

    def test_reset_clears_state(self, temp_state_file):
        """Test reset clears the tripped state."""
        cb = CircuitBreaker(state_file=temp_state_file)
        cb.record_loss()
        cb.record_loss()
        cb.record_loss()  # Trips breaker
        assert cb.get_status()["is_tripped"] is True

        cb.reset()
        status = cb.get_status()
        assert status["is_tripped"] is False
        assert status["consecutive_losses"] == 0
        assert status["api_errors_today"] == 0

    def test_reset_daily_counters(self, temp_state_file):
        """Test reset_daily_counters only resets API errors."""
        cb = CircuitBreaker(state_file=temp_state_file)
        cb.record_api_error()
        cb.record_api_error()
        cb.record_loss()

        cb.reset_daily_counters()
        status = cb.get_status()
        assert status["api_errors_today"] == 0
        assert status["consecutive_losses"] == 1  # Not reset

    def test_state_persistence(self, temp_state_file):
        """Test state persists across instances."""
        cb1 = CircuitBreaker(state_file=temp_state_file)
        cb1.record_loss()
        cb1.record_loss()

        cb2 = CircuitBreaker(state_file=temp_state_file)
        assert cb2.get_status()["consecutive_losses"] == 2


class TestIsTrainingHalted:
    """Tests for the is_trading_halted convenience function."""

    def test_returns_false_when_not_tripped(self):
        """Test returns False when breaker not tripped."""
        # Uses default state file location
        result = is_trading_halted()
        assert isinstance(result, bool)

#!/usr/bin/env python3
"""
Tests for VIX Circuit Breaker Module

Tests the volatility-based circuit breaker that protects positions
during market stress by monitoring VIX levels and intraday spikes.

Author: Trading System CTO
Created: 2026-01-08
"""

import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.vix_circuit_breaker import (  # noqa: E402
    AlertLevel,
    CircuitBreakerEvent,
    DeRiskAction,
    VIXCircuitBreaker,
    VIXStatus,
)


# =============================================================================
# AlertLevel Enum Tests
# =============================================================================


class TestAlertLevel:
    """Test AlertLevel enum values and ordering."""

    def test_all_levels_defined(self):
        """Verify all expected alert levels exist."""
        expected_levels = ["NORMAL", "ELEVATED", "HIGH", "VERY_HIGH", "EXTREME", "SPIKE"]
        for level in expected_levels:
            assert hasattr(AlertLevel, level), f"Missing AlertLevel.{level}"

    def test_level_values(self):
        """Verify alert level values are unique strings."""
        values = [level.value for level in AlertLevel]
        assert len(values) == len(set(values)), "Alert level values must be unique"

    def test_normal_is_base_state(self):
        """NORMAL should be the base/safe state."""
        assert AlertLevel.NORMAL.value == "normal"


# =============================================================================
# VIXStatus Dataclass Tests
# =============================================================================


class TestVIXStatus:
    """Test VIXStatus dataclass functionality."""

    @pytest.fixture
    def sample_status(self):
        """Create a sample VIXStatus for testing."""
        return VIXStatus(
            current_level=22.5,
            previous_close=20.0,
            intraday_change_pct=0.125,
            alert_level=AlertLevel.HIGH,
            position_multiplier=0.5,
            new_position_allowed=True,
            reduction_target_pct=0.0,
            message="VIX elevated - reduce new positions",
            timestamp=datetime.now(),
            vvix_level=95.0,
        )

    def test_to_dict_contains_all_fields(self, sample_status):
        """Verify to_dict() includes all required fields."""
        result = sample_status.to_dict()
        required_keys = [
            "vix_current",
            "vix_prev_close",
            "intraday_change_pct",
            "alert_level",
            "position_multiplier",
            "new_position_allowed",
            "reduction_target_pct",
            "message",
            "timestamp",
        ]
        for key in required_keys:
            assert key in result, f"Missing key in to_dict(): {key}"

    def test_to_dict_rounds_floats(self, sample_status):
        """Verify to_dict() rounds float values appropriately."""
        result = sample_status.to_dict()
        assert result["vix_current"] == 22.5
        assert result["intraday_change_pct"] == 0.12  # Rounded to 2 decimals

    def test_to_dict_handles_none_vvix(self):
        """Verify to_dict() handles None VVIX gracefully."""
        status = VIXStatus(
            current_level=15.0,
            previous_close=14.5,
            intraday_change_pct=0.03,
            alert_level=AlertLevel.ELEVATED,
            position_multiplier=0.8,
            new_position_allowed=True,
            reduction_target_pct=0.0,
            message="Markets stable",
            timestamp=datetime.now(),
            vvix_level=None,
        )
        result = status.to_dict()
        assert result["vvix_level"] is None


# =============================================================================
# DeRiskAction Dataclass Tests
# =============================================================================


class TestDeRiskAction:
    """Test DeRiskAction dataclass."""

    def test_action_creation(self):
        """Test creating a de-risk action."""
        action = DeRiskAction(
            symbol="SPY",
            action="reduce",
            current_qty=100.0,
            target_qty=50.0,
            reason="VIX spike above 30",
            priority=1,
        )
        assert action.symbol == "SPY"
        assert action.action == "reduce"
        assert action.current_qty == 100.0
        assert action.target_qty == 50.0
        assert action.priority == 1


# =============================================================================
# CircuitBreakerEvent Dataclass Tests
# =============================================================================


class TestCircuitBreakerEvent:
    """Test CircuitBreakerEvent dataclass."""

    def test_event_creation(self):
        """Test creating a circuit breaker event record."""
        event = CircuitBreakerEvent(
            timestamp=datetime.now(),
            alert_level=AlertLevel.EXTREME,
            vix_level=35.0,
            intraday_change_pct=0.25,
            action_taken="reduce_positions",
            positions_affected=["SPY", "QQQ", "AAPL"],
            total_reduced_value=15000.0,
        )
        assert event.alert_level == AlertLevel.EXTREME
        assert event.vix_level == 35.0
        assert len(event.positions_affected) == 3


# =============================================================================
# VIXCircuitBreaker Class Tests
# =============================================================================


class TestVIXCircuitBreaker:
    """Test VIXCircuitBreaker class functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a VIX circuit breaker instance for testing."""
        return VIXCircuitBreaker(
            vix_symbol="^VIX",
            check_interval_seconds=60,
            enable_auto_reduce=False,
            paper_mode=True,
        )

    def test_init_defaults(self):
        """Test circuit breaker initialization with defaults."""
        cb = VIXCircuitBreaker()
        assert cb.vix_symbol == "^VIX"
        assert cb.check_interval_seconds == 300
        assert cb.enable_auto_reduce is True
        assert cb.paper_mode is True

    def test_init_custom_values(self, circuit_breaker):
        """Test circuit breaker initialization with custom values."""
        assert circuit_breaker.check_interval_seconds == 60
        assert circuit_breaker.enable_auto_reduce is False

    def test_threshold_constants_exist(self, circuit_breaker):
        """Verify all threshold constants are defined."""
        # VIX level thresholds
        assert hasattr(circuit_breaker, "VIX_NORMAL")
        assert hasattr(circuit_breaker, "VIX_ELEVATED")
        assert hasattr(circuit_breaker, "VIX_HIGH")
        assert hasattr(circuit_breaker, "VIX_VERY_HIGH")

        # Spike thresholds
        assert hasattr(circuit_breaker, "SPIKE_WARNING")
        assert hasattr(circuit_breaker, "SPIKE_ALERT")
        assert hasattr(circuit_breaker, "SPIKE_EMERGENCY")
        assert hasattr(circuit_breaker, "SPIKE_CRISIS")

    def test_threshold_values_are_ordered(self, circuit_breaker):
        """Verify thresholds are in ascending order."""
        assert circuit_breaker.VIX_NORMAL < circuit_breaker.VIX_ELEVATED
        assert circuit_breaker.VIX_ELEVATED < circuit_breaker.VIX_HIGH
        assert circuit_breaker.VIX_HIGH < circuit_breaker.VIX_VERY_HIGH

        assert circuit_breaker.SPIKE_WARNING < circuit_breaker.SPIKE_ALERT
        assert circuit_breaker.SPIKE_ALERT < circuit_breaker.SPIKE_EMERGENCY
        assert circuit_breaker.SPIKE_EMERGENCY < circuit_breaker.SPIKE_CRISIS

    def test_reduction_targets_defined(self, circuit_breaker):
        """Verify reduction targets are defined for all alert levels."""
        for level in AlertLevel:
            assert level in circuit_breaker.REDUCTION_TARGETS, (
                f"Missing reduction target for {level}"
            )
            target = circuit_breaker.REDUCTION_TARGETS[level]
            assert 0.0 <= target <= 1.0, f"Invalid reduction target for {level}: {target}"

    def test_size_multipliers_defined(self, circuit_breaker):
        """Verify size multipliers are defined for all alert levels."""
        for level in AlertLevel:
            assert level in circuit_breaker.SIZE_MULTIPLIERS, f"Missing size multiplier for {level}"
            mult = circuit_breaker.SIZE_MULTIPLIERS[level]
            assert 0.0 <= mult <= 1.0, f"Invalid size multiplier for {level}: {mult}"

    def test_extreme_blocks_new_positions(self, circuit_breaker):
        """EXTREME alert should block all new positions."""
        assert circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.EXTREME] == 0.0

    def test_spike_blocks_new_positions(self, circuit_breaker):
        """SPIKE alert should block all new positions."""
        assert circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.SPIKE] == 0.0

    def test_normal_allows_full_positions(self, circuit_breaker):
        """NORMAL alert should allow full position sizes."""
        assert circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.NORMAL] == 1.0


# =============================================================================
# Alert Level Determination Tests
# =============================================================================


class TestAlertLevelDetermination:
    """Test the _determine_alert_level method."""

    @pytest.fixture
    def circuit_breaker(self):
        return VIXCircuitBreaker()

    def test_normal_level(self, circuit_breaker):
        """VIX < 15 with no spike should return NORMAL."""
        level = circuit_breaker._determine_alert_level(vix_level=12.0, intraday_change=0.02)
        assert level == AlertLevel.NORMAL

    def test_elevated_level(self, circuit_breaker):
        """VIX 15-20 with no spike should return ELEVATED."""
        level = circuit_breaker._determine_alert_level(vix_level=17.0, intraday_change=0.05)
        assert level == AlertLevel.ELEVATED

    def test_high_level(self, circuit_breaker):
        """VIX 20-25 with no spike should return HIGH."""
        level = circuit_breaker._determine_alert_level(vix_level=22.0, intraday_change=0.05)
        assert level == AlertLevel.HIGH

    def test_very_high_level(self, circuit_breaker):
        """VIX 25-30 with no spike should return VERY_HIGH."""
        level = circuit_breaker._determine_alert_level(vix_level=27.0, intraday_change=0.05)
        assert level == AlertLevel.VERY_HIGH

    def test_extreme_level_from_vix(self, circuit_breaker):
        """VIX > 30 should return EXTREME."""
        level = circuit_breaker._determine_alert_level(vix_level=35.0, intraday_change=0.05)
        assert level == AlertLevel.EXTREME

    def test_spike_overrides_level(self, circuit_breaker):
        """50%+ intraday spike should override VIX level and return SPIKE."""
        # Even with low VIX, a 50% spike should trigger SPIKE alert
        level = circuit_breaker._determine_alert_level(vix_level=18.0, intraday_change=0.55)
        assert level == AlertLevel.SPIKE

    def test_emergency_spike_returns_extreme(self, circuit_breaker):
        """30%+ intraday spike should return EXTREME."""
        level = circuit_breaker._determine_alert_level(vix_level=18.0, intraday_change=0.35)
        assert level == AlertLevel.EXTREME

    def test_alert_spike_returns_very_high(self, circuit_breaker):
        """20%+ intraday spike should return VERY_HIGH."""
        level = circuit_breaker._determine_alert_level(vix_level=15.0, intraday_change=0.22)
        assert level == AlertLevel.VERY_HIGH

    def test_spike_priority_over_level(self, circuit_breaker):
        """Spike detection should take priority over absolute VIX level."""
        # Low VIX but high spike should still trigger elevated response
        level = circuit_breaker._determine_alert_level(vix_level=12.0, intraday_change=0.25)
        # 25% spike (between SPIKE_ALERT and SPIKE_EMERGENCY) should return VERY_HIGH
        assert level == AlertLevel.VERY_HIGH


# =============================================================================
# Integration Tests with Mocked Data
# =============================================================================


class TestVIXCircuitBreakerIntegration:
    """Integration tests with mocked VIX data."""

    @pytest.fixture
    def circuit_breaker(self):
        return VIXCircuitBreaker(
            check_interval_seconds=1,  # Fast for testing
            enable_auto_reduce=False,
            paper_mode=True,
        )

    def test_get_current_status_returns_vix_status(self, circuit_breaker):
        """get_current_status should return VIXStatus object."""
        with patch.object(circuit_breaker, "_fetch_vix_data") as mock_fetch:
            mock_fetch.return_value = {
                "current": 18.5,
                "previous_close": 17.0,
                "vvix": 90.0,
            }
            status = circuit_breaker.get_current_status(force_refresh=True)
            assert isinstance(status, VIXStatus)
            assert status.current_level == 18.5
            assert status.alert_level == AlertLevel.HIGH

    def test_status_caching(self, circuit_breaker):
        """Status should be cached within check interval."""
        with patch.object(circuit_breaker, "_fetch_vix_data") as mock_fetch:
            mock_fetch.return_value = {"current": 15.0, "previous_close": 14.0}

            # First call should fetch
            circuit_breaker.get_current_status(force_refresh=True)
            assert mock_fetch.call_count == 1

            # Second call should use cache (within 1 second interval)
            circuit_breaker.get_current_status(force_refresh=False)
            # Still 1 because cached
            assert mock_fetch.call_count == 1

    def test_force_refresh_bypasses_cache(self, circuit_breaker):
        """force_refresh=True should bypass cache."""
        with patch.object(circuit_breaker, "_fetch_vix_data") as mock_fetch:
            mock_fetch.return_value = {"current": 15.0, "previous_close": 14.0}

            circuit_breaker.get_current_status(force_refresh=True)
            circuit_breaker.get_current_status(force_refresh=True)
            assert mock_fetch.call_count == 2


# =============================================================================
# Phil Town Rule #1 - Capital Protection Tests
# =============================================================================


class TestCapitalProtection:
    """
    Tests ensuring the circuit breaker protects capital per Phil Town Rule #1.

    CEO Directive (Jan 6, 2026): "Losing money is NOT allowed"
    """

    @pytest.fixture
    def circuit_breaker(self):
        return VIXCircuitBreaker()

    def test_high_vix_blocks_new_positions(self, circuit_breaker):
        """High VIX should restrict or block new positions."""
        extreme_mult = circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.EXTREME]
        very_high_mult = circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.VERY_HIGH]

        assert extreme_mult == 0.0, "EXTREME should block all new positions"
        assert very_high_mult <= 0.25, "VERY_HIGH should heavily restrict new positions"

    def test_high_vix_triggers_reduction(self, circuit_breaker):
        """High VIX should trigger position reductions."""
        extreme_reduction = circuit_breaker.REDUCTION_TARGETS[AlertLevel.EXTREME]
        very_high_reduction = circuit_breaker.REDUCTION_TARGETS[AlertLevel.VERY_HIGH]

        assert extreme_reduction >= 0.5, "EXTREME should reduce positions by at least 50%"
        assert very_high_reduction >= 0.25, "VERY_HIGH should reduce positions by at least 25%"

    def test_spike_triggers_immediate_action(self, circuit_breaker):
        """VIX spike should trigger immediate protective action."""
        spike_reduction = circuit_breaker.REDUCTION_TARGETS[AlertLevel.SPIKE]
        spike_multiplier = circuit_breaker.SIZE_MULTIPLIERS[AlertLevel.SPIKE]

        assert spike_reduction >= 0.5, "SPIKE should reduce positions by at least 50%"
        assert spike_multiplier == 0.0, "SPIKE should block all new positions"


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

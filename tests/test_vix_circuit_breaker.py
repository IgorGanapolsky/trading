#!/usr/bin/env python3
"""
Tests for VIX Circuit Breaker Module

Tests the volatility-based circuit breaker that protects positions
during market stress by monitoring VIX levels.

Author: Trading System CTO
Created: 2026-01-08
Updated: 2026-01-12 - Aligned tests with actual module implementation
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
    POSITION_MULTIPLIERS,
    VIX_THRESHOLDS,
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
            alert_level=AlertLevel.HIGH,
            message="High volatility: VIX 22.5",
            position_multiplier=0.5,
            halt_trading=False,
            timestamp=datetime.now(),
        )

    def test_status_creation(self, sample_status):
        """Verify VIXStatus can be created with all fields."""
        assert sample_status.current_level == 22.5
        assert sample_status.alert_level == AlertLevel.HIGH
        assert sample_status.position_multiplier == 0.5
        assert sample_status.halt_trading is False
        assert sample_status.timestamp is not None

    def test_status_default_timestamp(self):
        """Verify VIXStatus auto-generates timestamp if not provided."""
        status = VIXStatus(
            current_level=15.0,
            alert_level=AlertLevel.ELEVATED,
            message="Markets stable",
        )
        assert status.timestamp is not None
        assert isinstance(status.timestamp, datetime)

    def test_status_default_values(self):
        """Verify VIXStatus has correct default values."""
        status = VIXStatus(
            current_level=12.0,
            alert_level=AlertLevel.NORMAL,
            message="Normal volatility",
        )
        assert status.position_multiplier == 1.0
        assert status.halt_trading is False


# =============================================================================
# VIXCircuitBreaker Class Tests
# =============================================================================


class TestVIXCircuitBreaker:
    """Test VIXCircuitBreaker class functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a VIX circuit breaker instance for testing."""
        return VIXCircuitBreaker(halt_threshold=30.0)

    def test_init_defaults(self):
        """Test circuit breaker initialization with defaults."""
        cb = VIXCircuitBreaker()
        assert cb.halt_threshold == 30.0

    def test_init_custom_threshold(self, circuit_breaker):
        """Test circuit breaker initialization with custom values."""
        cb = VIXCircuitBreaker(halt_threshold=25.0)
        assert cb.halt_threshold == 25.0

    def test_position_multipliers_defined(self):
        """Verify position multipliers are defined for all alert levels."""
        for level in AlertLevel:
            assert level in POSITION_MULTIPLIERS, f"Missing multiplier for {level}"
            mult = POSITION_MULTIPLIERS[level]
            assert 0.0 <= mult <= 1.0, f"Invalid multiplier for {level}: {mult}"

    def test_extreme_blocks_new_positions(self):
        """EXTREME alert should block all new positions."""
        assert POSITION_MULTIPLIERS[AlertLevel.EXTREME] == 0.0

    def test_spike_blocks_new_positions(self):
        """SPIKE alert should block all new positions."""
        assert POSITION_MULTIPLIERS[AlertLevel.SPIKE] == 0.0

    def test_normal_allows_full_positions(self):
        """NORMAL alert should allow full position sizes."""
        assert POSITION_MULTIPLIERS[AlertLevel.NORMAL] == 1.0


# =============================================================================
# Alert Level Determination Tests
# =============================================================================


class TestAlertLevelDetermination:
    """Test the _get_alert_level method."""

    @pytest.fixture
    def circuit_breaker(self):
        return VIXCircuitBreaker()

    def test_normal_level(self, circuit_breaker):
        """VIX < 15 should return NORMAL."""
        level = circuit_breaker._get_alert_level(12.0)
        assert level == AlertLevel.NORMAL

    def test_elevated_level(self, circuit_breaker):
        """VIX 15-20 should return ELEVATED."""
        level = circuit_breaker._get_alert_level(17.0)
        assert level == AlertLevel.ELEVATED

    def test_high_level(self, circuit_breaker):
        """VIX 20-25 should return HIGH."""
        level = circuit_breaker._get_alert_level(22.0)
        assert level == AlertLevel.HIGH

    def test_very_high_level(self, circuit_breaker):
        """VIX 25-30 should return VERY_HIGH."""
        level = circuit_breaker._get_alert_level(27.0)
        assert level == AlertLevel.VERY_HIGH

    def test_extreme_level(self, circuit_breaker):
        """VIX 30-40 should return EXTREME."""
        level = circuit_breaker._get_alert_level(35.0)
        assert level == AlertLevel.EXTREME

    def test_spike_level(self, circuit_breaker):
        """VIX >= 40 should return SPIKE."""
        level = circuit_breaker._get_alert_level(45.0)
        assert level == AlertLevel.SPIKE


# =============================================================================
# Integration Tests with Mocked Data
# =============================================================================


class TestVIXCircuitBreakerIntegration:
    """Integration tests with mocked VIX data."""

    @pytest.fixture
    def circuit_breaker(self):
        return VIXCircuitBreaker(halt_threshold=30.0)

    def test_get_current_status_returns_vix_status(self, circuit_breaker):
        """get_current_status should return VIXStatus object."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 18.5
            status = circuit_breaker.get_current_status(force_refresh=True)
            assert isinstance(status, VIXStatus)
            assert status.current_level == 18.5
            # VIX 18.5 is between 15-20, so ELEVATED
            assert status.alert_level == AlertLevel.ELEVATED

    def test_status_caching(self, circuit_breaker):
        """Status should be cached within TTL."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 15.0

            # First call should fetch
            circuit_breaker.get_current_status(force_refresh=True)
            assert mock_fetch.call_count == 1

            # Second call should use cache
            circuit_breaker.get_current_status(force_refresh=False)
            # Still 1 because cached
            assert mock_fetch.call_count == 1

    def test_force_refresh_bypasses_cache(self, circuit_breaker):
        """force_refresh=True should bypass cache."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 15.0

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

    def test_high_vix_blocks_new_positions(self):
        """High VIX should restrict or block new positions."""
        extreme_mult = POSITION_MULTIPLIERS[AlertLevel.EXTREME]
        very_high_mult = POSITION_MULTIPLIERS[AlertLevel.VERY_HIGH]

        assert extreme_mult == 0.0, "EXTREME should block all new positions"
        assert very_high_mult <= 0.25, "VERY_HIGH should heavily restrict new positions"

    def test_spike_blocks_new_positions(self):
        """SPIKE alert should block all new positions."""
        spike_multiplier = POSITION_MULTIPLIERS[AlertLevel.SPIKE]
        assert spike_multiplier == 0.0, "SPIKE should block all new positions"

    def test_should_halt_trading(self, circuit_breaker):
        """should_halt_trading returns True when VIX exceeds threshold."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 35.0  # Above 30 threshold
            circuit_breaker._cached_status = None  # Clear cache
            assert circuit_breaker.should_halt_trading() is True

    def test_should_not_halt_trading_low_vix(self, circuit_breaker):
        """should_halt_trading returns False when VIX is normal."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 15.0  # Below threshold
            circuit_breaker._cached_status = None  # Clear cache
            assert circuit_breaker.should_halt_trading() is False

    def test_check_trade_allowed_normal(self, circuit_breaker):
        """Trade should be allowed during normal VIX."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 12.0
            circuit_breaker._cached_status = None
            allowed, reason = circuit_breaker.check_trade_allowed("AAPL")
            assert allowed is True

    def test_check_trade_blocked_extreme(self, circuit_breaker):
        """Trade should be blocked during extreme VIX."""
        with patch.object(circuit_breaker, "_fetch_vix") as mock_fetch:
            mock_fetch.return_value = 35.0  # Extreme but not halted
            circuit_breaker._cached_status = None
            # At 35 VIX, halt_trading is True (>= 30)
            allowed, reason = circuit_breaker.check_trade_allowed("AAPL")
            assert allowed is False


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

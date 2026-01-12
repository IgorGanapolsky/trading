#!/usr/bin/env python3
"""
Tests for VIX Circuit Breaker Module

Tests the volatility-based circuit breaker that protects positions
during market stress by monitoring VIX levels.

Phil Town Rule #1: Don't lose money.

Author: Trading System CTO
Created: 2026-01-08
Updated: 2026-01-12 (aligned with restored implementation)
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.vix_circuit_breaker import (  # noqa: E402
    AlertLevel,
    VIXCircuitBreaker,
    VIXStatus,
    VIX_THRESHOLDS,
    POSITION_MULTIPLIERS,
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

    def test_status_creation(self):
        """Verify VIXStatus can be created with required fields."""
        status = VIXStatus(
            current_level=22.5,
            alert_level=AlertLevel.HIGH,
            message="Test message",
            position_multiplier=0.5,
            halt_trading=False,
        )
        assert status.current_level == 22.5
        assert status.alert_level == AlertLevel.HIGH
        assert status.position_multiplier == 0.5
        assert status.halt_trading is False

    def test_status_with_halt(self):
        """Verify halt_trading is set correctly for extreme VIX."""
        status = VIXStatus(
            current_level=35.0,
            alert_level=AlertLevel.EXTREME,
            message="Trading halted",
            position_multiplier=0.0,
            halt_trading=True,
        )
        assert status.halt_trading is True
        assert status.position_multiplier == 0.0

    def test_timestamp_auto_set(self):
        """Verify timestamp is automatically set if not provided."""
        status = VIXStatus(
            current_level=15.0,
            alert_level=AlertLevel.NORMAL,
            message="Normal",
        )
        assert status.timestamp is not None
        assert isinstance(status.timestamp, datetime)


# =============================================================================
# VIXCircuitBreaker Tests
# =============================================================================


class TestVIXCircuitBreaker:
    """Test VIX Circuit Breaker functionality."""

    @pytest.fixture
    def circuit_breaker(self):
        """Create a VIXCircuitBreaker for testing."""
        return VIXCircuitBreaker(halt_threshold=30.0)

    def test_init_default_threshold(self):
        """Verify default halt threshold."""
        cb = VIXCircuitBreaker()
        assert cb.halt_threshold == 30.0

    def test_init_custom_threshold(self):
        """Verify custom halt threshold."""
        cb = VIXCircuitBreaker(halt_threshold=25.0)
        assert cb.halt_threshold == 25.0

    def test_get_alert_level_normal(self, circuit_breaker):
        """VIX < 15 should be NORMAL."""
        assert circuit_breaker._get_alert_level(12.0) == AlertLevel.NORMAL

    def test_get_alert_level_elevated(self, circuit_breaker):
        """VIX 15-20 should be ELEVATED."""
        assert circuit_breaker._get_alert_level(17.0) == AlertLevel.ELEVATED

    def test_get_alert_level_high(self, circuit_breaker):
        """VIX 20-25 should be HIGH."""
        assert circuit_breaker._get_alert_level(22.0) == AlertLevel.HIGH

    def test_get_alert_level_very_high(self, circuit_breaker):
        """VIX 25-30 should be VERY_HIGH."""
        assert circuit_breaker._get_alert_level(27.0) == AlertLevel.VERY_HIGH

    def test_get_alert_level_extreme(self, circuit_breaker):
        """VIX 30-40 should be EXTREME."""
        assert circuit_breaker._get_alert_level(35.0) == AlertLevel.EXTREME

    def test_get_alert_level_spike(self, circuit_breaker):
        """VIX >= 40 should be SPIKE."""
        assert circuit_breaker._get_alert_level(45.0) == AlertLevel.SPIKE

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_current_status_normal(self, mock_fetch, circuit_breaker):
        """Test status when VIX is normal."""
        mock_fetch.return_value = 12.0
        status = circuit_breaker.get_current_status(force_refresh=True)

        assert status.current_level == 12.0
        assert status.alert_level == AlertLevel.NORMAL
        assert status.position_multiplier == 1.0
        assert status.halt_trading is False

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_current_status_halt(self, mock_fetch, circuit_breaker):
        """Test status when VIX exceeds halt threshold."""
        mock_fetch.return_value = 35.0
        status = circuit_breaker.get_current_status(force_refresh=True)

        assert status.halt_trading is True
        assert "HALTED" in status.message

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_should_halt_trading_false(self, mock_fetch, circuit_breaker):
        """Test should_halt_trading returns False for normal VIX."""
        mock_fetch.return_value = 15.0
        assert circuit_breaker.should_halt_trading() is False

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_should_halt_trading_true(self, mock_fetch, circuit_breaker):
        """Test should_halt_trading returns True for extreme VIX."""
        mock_fetch.return_value = 35.0
        assert circuit_breaker.should_halt_trading() is True

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_position_multiplier_full(self, mock_fetch, circuit_breaker):
        """Test full position multiplier at normal VIX."""
        mock_fetch.return_value = 12.0
        assert circuit_breaker.get_position_multiplier() == 1.0

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_position_multiplier_reduced(self, mock_fetch, circuit_breaker):
        """Test reduced position multiplier at elevated VIX."""
        mock_fetch.return_value = 17.0
        assert circuit_breaker.get_position_multiplier() == 0.75

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_position_multiplier_half(self, mock_fetch, circuit_breaker):
        """Test half position multiplier at high VIX."""
        mock_fetch.return_value = 22.0
        assert circuit_breaker.get_position_multiplier() == 0.50

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_get_position_multiplier_zero(self, mock_fetch, circuit_breaker):
        """Test zero position multiplier at extreme VIX."""
        mock_fetch.return_value = 35.0
        assert circuit_breaker.get_position_multiplier() == 0.0

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_check_trade_allowed_yes(self, mock_fetch, circuit_breaker):
        """Test trade is allowed at normal VIX."""
        mock_fetch.return_value = 15.0
        allowed, reason = circuit_breaker.check_trade_allowed("SPY")
        assert allowed is True

    @patch.object(VIXCircuitBreaker, "_fetch_vix")
    def test_check_trade_allowed_no(self, mock_fetch, circuit_breaker):
        """Test trade is blocked at extreme VIX."""
        mock_fetch.return_value = 35.0
        allowed, reason = circuit_breaker.check_trade_allowed("SPY")
        assert allowed is False
        assert "halted" in reason.lower() or "HALTED" in reason

    def test_cache_respects_ttl(self, circuit_breaker):
        """Test that cached status is used within TTL."""
        # Manually set cache
        status = VIXStatus(
            current_level=20.0,
            alert_level=AlertLevel.HIGH,
            message="Cached",
            position_multiplier=0.5,
        )
        circuit_breaker._cached_status = status
        circuit_breaker._cache_time = datetime.now()

        # Should return cached value
        result = circuit_breaker.get_current_status(force_refresh=False)
        assert result.message == "Cached"

    def test_force_refresh_bypasses_cache(self, circuit_breaker):
        """Test that force_refresh bypasses cache."""
        # Manually set cache
        status = VIXStatus(
            current_level=20.0,
            alert_level=AlertLevel.HIGH,
            message="Cached",
            position_multiplier=0.5,
        )
        circuit_breaker._cached_status = status
        circuit_breaker._cache_time = datetime.now()

        # Force refresh should fetch new data
        with patch.object(circuit_breaker, "_fetch_vix", return_value=12.0):
            result = circuit_breaker.get_current_status(force_refresh=True)
            assert result.message != "Cached"


# =============================================================================
# Position Multiplier Constants Tests
# =============================================================================


class TestPositionMultipliers:
    """Test position multiplier constants."""

    def test_normal_full_position(self):
        """NORMAL allows full position."""
        assert POSITION_MULTIPLIERS[AlertLevel.NORMAL] == 1.0

    def test_elevated_reduced_position(self):
        """ELEVATED reduces to 75%."""
        assert POSITION_MULTIPLIERS[AlertLevel.ELEVATED] == 0.75

    def test_high_half_position(self):
        """HIGH reduces to 50%."""
        assert POSITION_MULTIPLIERS[AlertLevel.HIGH] == 0.50

    def test_very_high_quarter_position(self):
        """VERY_HIGH reduces to 25%."""
        assert POSITION_MULTIPLIERS[AlertLevel.VERY_HIGH] == 0.25

    def test_extreme_no_position(self):
        """EXTREME stops new positions."""
        assert POSITION_MULTIPLIERS[AlertLevel.EXTREME] == 0.0

    def test_spike_no_position(self):
        """SPIKE halts all trading."""
        assert POSITION_MULTIPLIERS[AlertLevel.SPIKE] == 0.0


# =============================================================================
# VIX Thresholds Tests
# =============================================================================


class TestVIXThresholds:
    """Test VIX threshold constants."""

    def test_thresholds_ascending(self):
        """Verify thresholds are in ascending order."""
        thresholds = [
            VIX_THRESHOLDS[AlertLevel.NORMAL],
            VIX_THRESHOLDS[AlertLevel.ELEVATED],
            VIX_THRESHOLDS[AlertLevel.HIGH],
            VIX_THRESHOLDS[AlertLevel.VERY_HIGH],
            VIX_THRESHOLDS[AlertLevel.EXTREME],
        ]
        assert thresholds == sorted(thresholds)

    def test_normal_threshold(self):
        """NORMAL threshold is 15."""
        assert VIX_THRESHOLDS[AlertLevel.NORMAL] == 15.0

    def test_halt_threshold(self):
        """EXTREME threshold is 40 (halt above 30)."""
        assert VIX_THRESHOLDS[AlertLevel.EXTREME] == 40.0


# =============================================================================
# Integration / Smoke Tests
# =============================================================================


class TestIntegration:
    """Integration tests for VIX circuit breaker."""

    def test_phil_town_rule_one_enforced(self):
        """
        Phil Town Rule #1: Don't lose money.

        The circuit breaker enforces this by:
        1. Halting trades when VIX > 30
        2. Reducing position sizes during volatility
        """
        cb = VIXCircuitBreaker(halt_threshold=30.0)

        with patch.object(cb, "_fetch_vix", return_value=35.0):
            # Must halt trading
            assert cb.should_halt_trading() is True

            # Must not allow trades
            allowed, _ = cb.check_trade_allowed("ANY")
            assert allowed is False

            # Position multiplier must be zero
            assert cb.get_position_multiplier() == 0.0

    def test_gradual_risk_reduction(self):
        """Test that risk reduces gradually as VIX rises."""
        cb = VIXCircuitBreaker()

        vix_to_multiplier = [
            (10.0, 1.0),    # NORMAL
            (17.0, 0.75),   # ELEVATED
            (22.0, 0.50),   # HIGH
            (27.0, 0.25),   # VERY_HIGH
            (35.0, 0.0),    # EXTREME
        ]

        for vix, expected in vix_to_multiplier:
            with patch.object(cb, "_fetch_vix", return_value=vix):
                cb._cached_status = None  # Clear cache
                assert cb.get_position_multiplier() == expected, f"VIX {vix} should give multiplier {expected}"

#!/usr/bin/env python3
"""
Tests for Options Risk Monitor - 2x Credit Stop-Loss Rule

Tests the CLAUDE.md trading rule:
- Stop-loss: Close at 2x credit received ($120 max loss for $60 credit)
- For credit spreads: Close when spread value rises to 3x entry credit

Created: January 15, 2026
"""

import pytest
from datetime import date, datetime

from src.risk.options_risk_monitor import (
    DEFAULT_STOP_LOSS_MULTIPLIER,
    OptionsPosition,
    OptionsRiskMonitor,
)


class TestOptionsPositionDataclass:
    """Tests for the OptionsPosition dataclass."""

    def test_create_basic_position(self):
        """OptionsPosition can be created with required fields."""
        pos = OptionsPosition(
            symbol="SPY240119P00480000",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,  # $60 credit per contract
            current_price=0.60,
            delta=-0.30,
            gamma=0.02,
            theta=0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=480.0,
            opened_at=datetime.now(),
        )
        assert pos.symbol == "SPY240119P00480000"
        assert pos.position_type == "credit_spread"
        assert pos.entry_price == 0.60

    def test_credit_received_defaults_to_zero(self):
        """credit_received field defaults to 0.0."""
        pos = OptionsPosition(
            symbol="SPY240119P00480000",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,
            current_price=0.60,
            delta=-0.30,
            gamma=0.02,
            theta=0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=480.0,
            opened_at=datetime.now(),
        )
        assert pos.credit_received == 0.0

    def test_credit_received_can_be_set(self):
        """credit_received field can be explicitly set."""
        pos = OptionsPosition(
            symbol="SPY240119P00480000",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,
            current_price=0.60,
            delta=-0.30,
            gamma=0.02,
            theta=0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=480.0,
            opened_at=datetime.now(),
            credit_received=60.0,  # Total credit for 1 contract
        )
        assert pos.credit_received == 60.0


class TestOptionsRiskMonitorInit:
    """Tests for OptionsRiskMonitor initialization."""

    def test_default_initialization(self):
        """OptionsRiskMonitor initializes with default values."""
        monitor = OptionsRiskMonitor()
        assert monitor.max_loss_percent == 5.0
        assert monitor.stop_loss_multiplier == DEFAULT_STOP_LOSS_MULTIPLIER
        assert monitor.stop_loss_multiplier == 2.0

    def test_custom_stop_loss_multiplier(self):
        """OptionsRiskMonitor accepts custom stop-loss multiplier."""
        monitor = OptionsRiskMonitor(stop_loss_multiplier=1.5)
        assert monitor.stop_loss_multiplier == 1.5


class TestShouldClosePosition:
    """Tests for the 2x credit stop-loss rule."""

    @pytest.fixture
    def monitor(self):
        """Create an OptionsRiskMonitor with default settings."""
        return OptionsRiskMonitor()

    @pytest.fixture
    def credit_spread_position(self):
        """Create a sample credit spread position.

        Setup:
        - Entry price (credit received): $0.60 per share ($60 per contract)
        - Current price starts at entry price (no loss)
        """
        return OptionsPosition(
            symbol="SPY240119P00480000",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,  # $0.60 per share = $60 credit
            current_price=0.60,  # Start at breakeven
            delta=-0.30,
            gamma=0.02,
            theta=0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=480.0,
            opened_at=datetime.now(),
            credit_received=0.60,  # Same as entry_price for per-share value
        )

    def test_position_at_breakeven_no_close(self, monitor, credit_spread_position):
        """Position at breakeven should not trigger close."""
        monitor.add_position(credit_spread_position)
        should_close, reason = monitor.should_close_position("SPY240119P00480000")

        assert should_close is False
        assert "within risk limits" in reason.lower()

    def test_position_with_small_loss_no_close(self, monitor, credit_spread_position):
        """Position with small loss should not trigger close."""
        # Small loss: spread now costs $0.90 to close (loss = $0.30)
        credit_spread_position.current_price = 0.90
        monitor.add_position(credit_spread_position)
        should_close, reason = monitor.should_close_position("SPY240119P00480000")

        assert should_close is False
        assert "within risk limits" in reason.lower()

    def test_position_at_max_loss_triggers_close(self, monitor, credit_spread_position):
        """Position at 2x credit loss should trigger close.

        CLAUDE.md Rule: Close at 2x credit received
        - Credit = $0.60
        - Max loss = 2 * $0.60 = $1.20
        - Close when current_price = $0.60 + $1.20 = $1.80
        """
        # At stop-loss: spread costs $1.80 to close (loss = $1.20 = 2x credit)
        credit_spread_position.current_price = 1.80
        monitor.add_position(credit_spread_position)
        should_close, reason = monitor.should_close_position("SPY240119P00480000")

        assert should_close is True
        assert "stop-loss triggered" in reason.lower()
        assert "2x credit" in reason.lower()

    def test_position_exceeds_max_loss_triggers_close(self, monitor, credit_spread_position):
        """Position exceeding 2x credit loss should trigger close."""
        # Beyond stop-loss: spread costs $2.40 to close (loss = $1.80 > 2x credit)
        credit_spread_position.current_price = 2.40
        monitor.add_position(credit_spread_position)
        should_close, reason = monitor.should_close_position("SPY240119P00480000")

        assert should_close is True
        assert "stop-loss triggered" in reason.lower()

    def test_position_just_below_max_loss_no_close(self, monitor, credit_spread_position):
        """Position just below 2x credit should not trigger close."""
        # Just below stop-loss: spread costs $1.79 (loss = $1.19 < $1.20)
        credit_spread_position.current_price = 1.79
        monitor.add_position(credit_spread_position)
        should_close, reason = monitor.should_close_position("SPY240119P00480000")

        assert should_close is False
        assert "within risk limits" in reason.lower()

    def test_non_credit_spread_no_stop_loss(self, monitor):
        """Non-credit-spread positions should not trigger 2x stop-loss."""
        covered_call = OptionsPosition(
            symbol="AAPL240119C00180000",
            underlying="AAPL",
            position_type="covered_call",  # Not a credit spread
            side="short",
            quantity=1,
            entry_price=2.00,
            current_price=6.00,  # Large loss
            delta=0.50,
            gamma=0.02,
            theta=-0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=180.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(covered_call)
        should_close, reason = monitor.should_close_position("AAPL240119C00180000")

        assert should_close is False
        assert "not subject to 2x credit stop-loss" in reason.lower()

    def test_position_not_found(self, monitor):
        """Unknown position should return False with appropriate message."""
        should_close, reason = monitor.should_close_position("UNKNOWN")

        assert should_close is False
        assert "not found" in reason.lower()


class TestShouldClosePositionWithDictFormat:
    """Tests for 2x credit stop-loss with legacy dict format."""

    @pytest.fixture
    def monitor(self):
        """Create an OptionsRiskMonitor."""
        return OptionsRiskMonitor()

    def test_dict_position_at_stop_loss(self, monitor):
        """Dict-format position at stop-loss should trigger close."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 1.80,  # Loss = $1.20 = 2x credit
            "position_type": "credit_spread",
            "credit_received": 0.60,
        }
        monitor.add_position("TEST_SPREAD", position_data)
        should_close, reason = monitor.should_close_position("TEST_SPREAD")

        assert should_close is True
        assert "stop-loss triggered" in reason.lower()

    def test_dict_position_within_limits(self, monitor):
        """Dict-format position within limits should not trigger close."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 1.00,  # Loss = $0.40 < 2x credit
            "position_type": "credit_spread",
            "credit_received": 0.60,
        }
        monitor.add_position("TEST_SPREAD", position_data)
        should_close, reason = monitor.should_close_position("TEST_SPREAD")

        assert should_close is False


class TestCheckRisk:
    """Tests for check_risk method."""

    @pytest.fixture
    def monitor(self):
        """Create an OptionsRiskMonitor."""
        return OptionsRiskMonitor()

    def test_check_risk_ok_status(self, monitor):
        """Position with low loss should have 'ok' status."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 0.80,  # Small loss
            "position_type": "credit_spread",
            "credit_received": 0.60,
        }
        monitor.add_position("TEST", position_data)
        risk = monitor.check_risk("TEST")

        assert risk["status"] == "ok"
        assert risk["loss_ratio"] < 0.75

    def test_check_risk_warning_status(self, monitor):
        """Position near stop-loss should have 'warning' status."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 1.60,  # Loss = $1.00, near 2x credit ($1.20)
            "position_type": "credit_spread",
            "credit_received": 0.60,
        }
        monitor.add_position("TEST", position_data)
        risk = monitor.check_risk("TEST")

        assert risk["status"] == "warning"
        assert 0.75 <= risk["loss_ratio"] < 1.0

    def test_check_risk_critical_status(self, monitor):
        """Position at stop-loss should have 'critical' status."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 1.80,  # At stop-loss
            "position_type": "credit_spread",
            "credit_received": 0.60,
        }
        monitor.add_position("TEST", position_data)
        risk = monitor.check_risk("TEST")

        assert risk["status"] == "critical"
        assert "STOP-LOSS TRIGGERED" in risk["message"]

    def test_check_risk_unknown_position(self, monitor):
        """Unknown position should return 'unknown' status."""
        risk = monitor.check_risk("UNKNOWN")

        assert risk["status"] == "unknown"
        assert "not found" in risk["message"].lower()


class TestUpdatePositionPrice:
    """Tests for update_position_price method."""

    @pytest.fixture
    def monitor(self):
        """Create an OptionsRiskMonitor."""
        return OptionsRiskMonitor()

    def test_update_options_position_price(self, monitor):
        """Update price for OptionsPosition object."""
        pos = OptionsPosition(
            symbol="SPY_SPREAD",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,
            current_price=0.60,
            delta=-0.30,
            gamma=0.02,
            theta=0.05,
            vega=0.10,
            expiration_date=date(2024, 1, 19),
            strike=480.0,
            opened_at=datetime.now(),
            credit_received=0.60,
        )
        monitor.add_position(pos)

        # Update price
        result = monitor.update_position_price("SPY_SPREAD", 1.50)
        assert result is True

        # Verify update
        updated = monitor.positions["SPY_SPREAD"]
        assert updated.current_price == 1.50
        assert updated.entry_price == 0.60  # Original entry unchanged

    def test_update_dict_position_price(self, monitor):
        """Update price for dict-format position."""
        position_data = {
            "entry_price": 0.60,
            "current_price": 0.60,
            "position_type": "credit_spread",
        }
        monitor.add_position("TEST", position_data)

        # Update price
        result = monitor.update_position_price("TEST", 1.50)
        assert result is True

        # Verify update
        assert monitor.positions["TEST"]["current_price"] == 1.50

    def test_update_unknown_position(self, monitor):
        """Update for unknown position should return False."""
        result = monitor.update_position_price("UNKNOWN", 1.50)
        assert result is False


class TestRealWorldScenario:
    """Integration tests with real-world scenarios from CLAUDE.md."""

    def test_spy_credit_spread_scenario(self):
        """Test SPY credit spread per CLAUDE.md strategy.

        Setup from CLAUDE.md:
        - Sell 30-delta put, buy 20-delta put
        - ~$500 collateral
        - ~$50-70 premium ($60 typical)
        - Stop-loss: Close at 2x credit received ($120 max loss)
        """
        monitor = OptionsRiskMonitor()

        # Open SPY credit spread: received $60 credit ($0.60 per share)
        spread = OptionsPosition(
            symbol="SPY240215P00475000",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=0.60,  # Credit received per share
            current_price=0.60,  # At entry, breakeven
            delta=-0.30,
            gamma=0.02,
            theta=0.03,
            vega=0.15,
            expiration_date=date(2024, 2, 15),
            strike=475.0,
            opened_at=datetime.now(),
            credit_received=0.60,
        )
        monitor.add_position(spread)

        # Day 1: Small profit (spread worth less)
        monitor.update_position_price("SPY240215P00475000", 0.40)
        should_close, _ = monitor.should_close_position("SPY240215P00475000")
        assert should_close is False  # Profitable, no close

        # Day 5: Market dips, spread underwater
        monitor.update_position_price("SPY240215P00475000", 1.00)
        should_close, _ = monitor.should_close_position("SPY240215P00475000")
        assert should_close is False  # Loss $40, under $120 max

        # Day 7: Market crashes, approaching stop-loss
        monitor.update_position_price("SPY240215P00475000", 1.70)
        risk = monitor.check_risk("SPY240215P00475000")
        assert risk["status"] == "warning"  # 75%+ of max loss

        # Day 8: Stop-loss triggered
        monitor.update_position_price("SPY240215P00475000", 1.80)
        should_close, reason = monitor.should_close_position("SPY240215P00475000")
        assert should_close is True
        assert "2x credit stop-loss triggered" in reason

    def test_iwm_credit_spread_scenario(self):
        """Test IWM credit spread (secondary ticker per CLAUDE.md)."""
        monitor = OptionsRiskMonitor()

        # IWM spread with smaller premium
        spread = {
            "position_type": "credit_spread",
            "entry_price": 0.50,  # $50 credit
            "current_price": 0.50,
            "credit_received": 0.50,
        }
        monitor.add_position("IWM_SPREAD", spread)

        # Max loss = 2 * $0.50 = $1.00
        # Stop-loss at current_price = $1.50

        # Price rises to stop-loss
        monitor.positions["IWM_SPREAD"]["current_price"] = 1.50
        should_close, reason = monitor.should_close_position("IWM_SPREAD")

        assert should_close is True
        assert "stop-loss triggered" in reason.lower()


class TestCustomStopLossMultiplier:
    """Tests for custom stop-loss multiplier configurations."""

    def test_tighter_stop_loss_1_5x(self):
        """Test 1.5x credit stop-loss (more conservative)."""
        monitor = OptionsRiskMonitor(stop_loss_multiplier=1.5)

        spread = {
            "position_type": "credit_spread",
            "entry_price": 0.60,
            "current_price": 1.50,  # Loss = $0.90 = 1.5x credit
            "credit_received": 0.60,
        }
        monitor.add_position("TEST", spread)

        should_close, _ = monitor.should_close_position("TEST")
        assert should_close is True  # 1.5x triggers at $0.90 loss

    def test_looser_stop_loss_3x(self):
        """Test 3x credit stop-loss (more aggressive)."""
        monitor = OptionsRiskMonitor(stop_loss_multiplier=3.0)

        spread = {
            "position_type": "credit_spread",
            "entry_price": 0.60,
            "current_price": 1.80,  # Loss = $1.20 < 3x credit ($1.80)
            "credit_received": 0.60,
        }
        monitor.add_position("TEST", spread)

        should_close, _ = monitor.should_close_position("TEST")
        assert should_close is False  # 3x doesn't trigger until $1.80 loss

        # Now at 3x stop-loss
        monitor.positions["TEST"]["current_price"] = 2.40  # Loss = $1.80 = 3x
        should_close, _ = monitor.should_close_position("TEST")
        assert should_close is True

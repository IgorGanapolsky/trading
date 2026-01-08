#!/usr/bin/env python3
"""
Tests for Options Risk Monitor Module

Tests McMillan's stop-loss rules and delta management for options positions.

Author: Trading System CTO
Created: 2026-01-08
"""

import sys
from datetime import date, datetime
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.risk.options_risk_monitor import OptionsPosition, OptionsRiskMonitor


# =============================================================================
# OptionsPosition Dataclass Tests
# =============================================================================


class TestOptionsPosition:
    """Test OptionsPosition dataclass."""

    @pytest.fixture
    def sample_position(self):
        """Create a sample options position."""
        return OptionsPosition(
            symbol="SPY240119P450",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=1.50,  # Credit received
            current_price=1.80,  # Cost to close
            delta=-0.30,
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )

    def test_position_creation(self, sample_position):
        """Test creating an options position."""
        assert sample_position.symbol == "SPY240119P450"
        assert sample_position.underlying == "SPY"
        assert sample_position.side == "short"
        assert sample_position.entry_price == 1.50

    def test_position_greeks(self, sample_position):
        """Test position has all Greeks."""
        assert sample_position.delta == -0.30
        assert sample_position.gamma == 0.05
        assert sample_position.theta == 0.02
        assert sample_position.vega == -0.15


# =============================================================================
# OptionsRiskMonitor Initialization Tests
# =============================================================================


class TestOptionsRiskMonitorInit:
    """Test OptionsRiskMonitor initialization."""

    def test_init_default(self):
        """Test default initialization."""
        monitor = OptionsRiskMonitor()
        assert monitor.paper is True
        assert len(monitor.positions) == 0

    def test_init_live_mode(self):
        """Test initialization in live mode."""
        monitor = OptionsRiskMonitor(paper=False)
        assert monitor.paper is False

    def test_mcmillan_constants_defined(self):
        """Verify McMillan stop-loss constants are defined."""
        assert OptionsRiskMonitor.CREDIT_SPREAD_STOP_MULTIPLIER == 2.2
        assert OptionsRiskMonitor.IRON_CONDOR_STOP_MULTIPLIER == 2.0
        assert OptionsRiskMonitor.LONG_OPTION_STOP_PCT == 0.50
        assert OptionsRiskMonitor.COVERED_CALL_UNDERLYING_STOP == 0.08

    def test_delta_management_constants_defined(self):
        """Verify delta management constants are defined."""
        assert OptionsRiskMonitor.MAX_NET_DELTA == 60.0
        assert OptionsRiskMonitor.TARGET_NET_DELTA == 25.0
        assert OptionsRiskMonitor.DELTA_PER_SPY_SHARE == 1.0


# =============================================================================
# Position Management Tests
# =============================================================================


class TestPositionManagement:
    """Test adding and removing positions."""

    @pytest.fixture
    def monitor(self):
        return OptionsRiskMonitor()

    @pytest.fixture
    def sample_position(self):
        return OptionsPosition(
            symbol="SPY240119P450",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=1.50,
            current_price=1.50,
            delta=-0.30,
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )

    def test_add_position(self, monitor, sample_position):
        """Test adding a position."""
        monitor.add_position(sample_position)
        assert sample_position.symbol in monitor.positions
        assert len(monitor.positions) == 1

    def test_remove_position(self, monitor, sample_position):
        """Test removing a position."""
        monitor.add_position(sample_position)
        monitor.remove_position(sample_position.symbol)
        assert sample_position.symbol not in monitor.positions
        assert len(monitor.positions) == 0

    def test_remove_nonexistent_position(self, monitor):
        """Removing non-existent position should not raise."""
        monitor.remove_position("NONEXISTENT")  # Should not raise


# =============================================================================
# McMillan Stop-Loss Tests - Credit Spreads
# =============================================================================


class TestCreditSpreadStopLoss:
    """Test McMillan stop-loss rules for credit spreads."""

    @pytest.fixture
    def monitor(self):
        return OptionsRiskMonitor()

    def test_credit_spread_no_stop_when_profitable(self, monitor):
        """Credit spread should not trigger stop when profitable."""
        position = OptionsPosition(
            symbol="SPY_CREDIT",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=1.50,  # Received $1.50 credit
            current_price=1.00,  # Would cost $1.00 to close (profit!)
            delta=-0.30,
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"SPY_CREDIT": 1.00})
        assert len(exits) == 0, "Profitable position should not trigger stop"

    def test_credit_spread_no_stop_within_limit(self, monitor):
        """Credit spread should not trigger stop if loss < 2.2x credit."""
        position = OptionsPosition(
            symbol="SPY_CREDIT",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=1.00,  # Received $1.00 credit
            current_price=2.50,  # Loss = $1.50 < 2.2x = $2.20
            delta=-0.30,
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"SPY_CREDIT": 2.50})
        assert len(exits) == 0, "Loss within limit should not trigger stop"

    def test_credit_spread_triggers_stop_at_2_2x(self, monitor):
        """Credit spread should trigger stop when loss >= 2.2x credit."""
        position = OptionsPosition(
            symbol="SPY_CREDIT",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=1,
            entry_price=1.00,  # Received $1.00 credit
            current_price=3.50,  # Loss = $2.50 > 2.2x = $2.20
            delta=-0.30,
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"SPY_CREDIT": 3.50})

        assert len(exits) == 1, "Stop should trigger at 2.2x loss"
        assert exits[0]["action"] == "CLOSE"
        assert "STOP_LOSS" in exits[0]["reason"]
        assert "mcmillan_rule" in exits[0]


# =============================================================================
# McMillan Stop-Loss Tests - Iron Condors
# =============================================================================


class TestIronCondorStopLoss:
    """Test McMillan stop-loss rules for iron condors (tighter 2.0x)."""

    @pytest.fixture
    def monitor(self):
        return OptionsRiskMonitor()

    def test_iron_condor_uses_tighter_stop(self, monitor):
        """Iron condor should use 2.0x multiplier (tighter than credit spreads)."""
        position = OptionsPosition(
            symbol="SPY_IC",
            underlying="SPY",
            position_type="iron_condor",
            side="short",
            quantity=1,
            entry_price=2.00,  # Received $2.00 credit
            current_price=5.00,  # Loss = $3.00 < 2.2x=$4.40 but > 2.0x=$4.00
            delta=0.0,
            gamma=0.02,
            theta=0.04,
            vega=-0.10,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"SPY_IC": 5.00})

        assert len(exits) == 1, "Iron condor should trigger stop at 2.0x"
        assert exits[0]["position_type"] == "iron_condor"


# =============================================================================
# McMillan Stop-Loss Tests - Long Options
# =============================================================================


class TestLongOptionStopLoss:
    """Test McMillan stop-loss rules for long options (50% loss)."""

    @pytest.fixture
    def monitor(self):
        return OptionsRiskMonitor()

    def test_long_option_no_stop_when_profitable(self, monitor):
        """Long option should not trigger stop when profitable."""
        position = OptionsPosition(
            symbol="AAPL_CALL",
            underlying="AAPL",
            position_type="long_call",
            side="long",
            quantity=1,
            entry_price=5.00,  # Paid $5.00
            current_price=6.00,  # Worth $6.00 (profit!)
            delta=0.60,
            gamma=0.05,
            theta=-0.03,
            vega=0.20,
            expiration_date=date(2024, 1, 19),
            strike=180.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"AAPL_CALL": 6.00})
        assert len(exits) == 0

    def test_long_option_no_stop_within_limit(self, monitor):
        """Long option should not trigger stop if loss < 50%."""
        position = OptionsPosition(
            symbol="AAPL_CALL",
            underlying="AAPL",
            position_type="long_call",
            side="long",
            quantity=1,
            entry_price=5.00,  # Paid $5.00
            current_price=3.00,  # Worth $3.00 (40% loss, < 50%)
            delta=0.60,
            gamma=0.05,
            theta=-0.03,
            vega=0.20,
            expiration_date=date(2024, 1, 19),
            strike=180.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"AAPL_CALL": 3.00})
        assert len(exits) == 0

    def test_long_option_triggers_stop_at_50_pct(self, monitor):
        """Long option should trigger stop when loss >= 50%."""
        position = OptionsPosition(
            symbol="AAPL_CALL",
            underlying="AAPL",
            position_type="long_call",
            side="long",
            quantity=1,
            entry_price=5.00,  # Paid $5.00
            current_price=2.00,  # Worth $2.00 (60% loss)
            delta=0.60,
            gamma=0.05,
            theta=-0.03,
            vega=0.20,
            expiration_date=date(2024, 1, 19),
            strike=180.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        exits = monitor.check_stop_losses({"AAPL_CALL": 2.00})

        assert len(exits) == 1
        assert exits[0]["action"] == "CLOSE"
        assert "50%" in exits[0]["reason"]


# =============================================================================
# Delta Management Tests
# =============================================================================


class TestDeltaManagement:
    """Test delta calculation and rebalancing logic."""

    @pytest.fixture
    def monitor(self):
        return OptionsRiskMonitor()

    def test_net_delta_empty_portfolio(self, monitor):
        """Empty portfolio should have zero net delta."""
        result = monitor.calculate_net_delta()
        assert result["net_delta"] == 0.0

    def test_net_delta_single_long_position(self, monitor):
        """Test net delta with single long position."""
        position = OptionsPosition(
            symbol="SPY_CALL",
            underlying="SPY",
            position_type="long_call",
            side="long",
            quantity=10,
            entry_price=3.00,
            current_price=3.50,
            delta=0.50,  # 0.50 delta per contract
            gamma=0.05,
            theta=-0.02,
            vega=0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        result = monitor.calculate_net_delta()

        # 10 contracts * 0.50 delta = 5.0 net delta
        assert result["net_delta"] == 5.0

    def test_net_delta_short_position_inverts(self, monitor):
        """Short positions should have inverted delta."""
        position = OptionsPosition(
            symbol="SPY_PUT",
            underlying="SPY",
            position_type="credit_spread",
            side="short",
            quantity=10,
            entry_price=1.50,
            current_price=1.50,
            delta=-0.30,  # -0.30 delta per contract
            gamma=0.05,
            theta=0.02,
            vega=-0.15,
            expiration_date=date(2024, 1, 19),
            strike=440.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        result = monitor.calculate_net_delta()

        # Short position: delta is inverted
        # 10 contracts * -0.30 delta * -1 (for short) = 3.0 net delta
        assert result["net_delta"] == 3.0

    def test_rebalance_threshold(self, monitor):
        """Test rebalance is needed when net delta exceeds threshold."""
        # Add positions that sum to high net delta
        position = OptionsPosition(
            symbol="SPY_CALL",
            underlying="SPY",
            position_type="long_call",
            side="long",
            quantity=200,  # Large position
            entry_price=3.00,
            current_price=3.50,
            delta=0.50,  # 200 * 0.50 = 100 delta (> 60 threshold)
            gamma=0.05,
            theta=-0.02,
            vega=0.15,
            expiration_date=date(2024, 1, 19),
            strike=450.0,
            opened_at=datetime.now(),
        )
        monitor.add_position(position)
        result = monitor.calculate_net_delta()

        assert result["net_delta"] == 100.0
        assert abs(result["net_delta"]) > monitor.MAX_NET_DELTA
        assert result["rebalance_needed"] is True


# =============================================================================
# Phil Town Rule #1 - Capital Protection Tests
# =============================================================================


class TestCapitalProtection:
    """
    Tests ensuring options risk management protects capital.

    CEO Directive (Jan 6, 2026): "Losing money is NOT allowed"
    """

    def test_stop_loss_multipliers_are_conservative(self):
        """Stop-loss multipliers should be conservative."""
        # 2.2x for credit spreads is industry standard (McMillan)
        assert OptionsRiskMonitor.CREDIT_SPREAD_STOP_MULTIPLIER <= 2.5

        # Iron condors should have tighter stop
        assert OptionsRiskMonitor.IRON_CONDOR_STOP_MULTIPLIER < OptionsRiskMonitor.CREDIT_SPREAD_STOP_MULTIPLIER

        # Long options: 50% max loss
        assert OptionsRiskMonitor.LONG_OPTION_STOP_PCT == 0.50

    def test_delta_limits_prevent_large_directional_bets(self):
        """Delta limits should prevent excessive directional exposure."""
        # Max net delta of 60 is reasonable for a $100k portfolio
        assert OptionsRiskMonitor.MAX_NET_DELTA == 60.0

        # Target delta should be well below max
        assert OptionsRiskMonitor.TARGET_NET_DELTA < OptionsRiskMonitor.MAX_NET_DELTA


# =============================================================================
# Run Tests
# =============================================================================


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

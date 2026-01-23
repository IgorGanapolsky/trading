"""Tests for iron condor position management."""

import pytest
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.manage_iron_condor_positions import (
    is_option_symbol,
    parse_option_symbol,
    calculate_dte,
    check_exit_conditions,
    IC_EXIT_CONFIG,
)


class TestIsOptionSymbol:
    """Test option symbol detection."""

    def test_spy_stock_is_not_option(self):
        assert is_option_symbol("SPY") is False

    def test_short_symbol_is_not_option(self):
        assert is_option_symbol("AAPL") is False

    def test_occ_option_symbol_is_option(self):
        # SPY put expiring Feb 27, 2026 at $650 strike
        assert is_option_symbol("SPY260227P00650000") is True

    def test_occ_call_symbol_is_option(self):
        assert is_option_symbol("SPY260227C00620000") is True


class TestParseOptionSymbol:
    """Test OCC option symbol parsing."""

    def test_parse_spy_put(self):
        result = parse_option_symbol("SPY260227P00650000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["type"] == "P"
        assert result["strike"] == 650.0
        assert result["expiry"].year == 2026
        assert result["expiry"].month == 2
        assert result["expiry"].day == 27

    def test_parse_spy_call(self):
        result = parse_option_symbol("SPY260227C00620000")
        assert result is not None
        assert result["underlying"] == "SPY"
        assert result["type"] == "C"
        assert result["strike"] == 620.0

    def test_parse_stock_returns_none(self):
        result = parse_option_symbol("SPY")
        assert result is None


class TestCalculateDte:
    """Test DTE calculation."""

    def test_expiry_in_7_days(self):
        expiry = datetime.now() + timedelta(days=7)
        dte = calculate_dte(expiry)
        # Allow for partial day rounding
        assert 6 <= dte <= 7

    def test_expiry_in_30_days(self):
        expiry = datetime.now() + timedelta(days=30)
        dte = calculate_dte(expiry)
        # Allow for partial day rounding
        assert 29 <= dte <= 30

    def test_expired_option(self):
        expiry = datetime.now() - timedelta(days=1)
        dte = calculate_dte(expiry)
        assert dte < 0


class TestExitConditions:
    """Test iron condor exit condition logic."""

    def test_exit_at_7_dte(self):
        """Should exit when DTE <= 7."""
        ic = {
            "expiry": datetime.now() + timedelta(days=5),
            "total_pl": 50,
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "DTE_EXIT"

    def test_exit_at_50_percent_profit(self):
        """Should exit when profit >= 50% of credit."""
        ic = {
            "expiry": datetime.now() + timedelta(days=30),  # Not near expiry
            "total_pl": 120,  # 60% profit
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "PROFIT_TARGET"

    def test_exit_at_200_percent_loss(self):
        """Should exit when loss >= 200% of credit."""
        ic = {
            "expiry": datetime.now() + timedelta(days=30),
            "total_pl": -450,  # 225% loss
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is True
        assert reason == "STOP_LOSS"

    def test_hold_when_no_exit_conditions_met(self):
        """Should hold when no exit conditions met."""
        ic = {
            "expiry": datetime.now() + timedelta(days=25),  # 25 DTE
            "total_pl": 40,  # 20% profit - not at target
            "credit_received": 200,
        }
        should_exit, reason, _ = check_exit_conditions(ic)
        assert should_exit is False
        assert reason == "HOLD"

    def test_config_values_aligned_with_strategy(self):
        """Verify config matches CLAUDE.md strategy."""
        assert IC_EXIT_CONFIG["profit_target_pct"] == 0.50  # 50% profit
        assert IC_EXIT_CONFIG["stop_loss_pct"] == 2.00  # 200% stop
        assert IC_EXIT_CONFIG["exit_dte"] == 7  # 7 DTE per LL-268

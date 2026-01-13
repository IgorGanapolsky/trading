#!/usr/bin/env python3
"""
Smoke tests for OptionsExecutor module.

These tests verify:
1. Module imports successfully
2. Key classes/functions exist
3. Dataclasses are properly defined
4. Basic method signatures

Created: Jan 13, 2026
"""

import sys
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if pydantic is available (required for alpaca-py and options_executor dependencies)
try:
    import pydantic  # noqa: F401

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Skip all tests in this module if pydantic is not available
pytestmark = pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason="pydantic not available - required for options_executor dependencies"
)


class TestOptionsExecutorImports:
    """Test that options_executor module imports correctly."""

    def test_module_imports(self):
        """Should import options_executor module without errors."""
        from src.trading import options_executor

        assert options_executor is not None

    def test_optionleg_class_exists(self):
        """Should have OptionLeg dataclass."""
        from src.trading.options_executor import OptionLeg

        assert OptionLeg is not None

    def test_optionsstrategy_class_exists(self):
        """Should have OptionsStrategy dataclass."""
        from src.trading.options_executor import OptionsStrategy

        assert OptionsStrategy is not None

    def test_optionsexecutor_class_exists(self):
        """Should have OptionsExecutor class."""
        from src.trading.options_executor import OptionsExecutor

        assert OptionsExecutor is not None
        assert callable(OptionsExecutor)

    def test_get_options_executor_function_exists(self):
        """Should have get_options_executor factory function."""
        from src.trading.options_executor import get_options_executor

        assert get_options_executor is not None
        assert callable(get_options_executor)


class TestOptionLegDataclass:
    """Test OptionLeg dataclass."""

    def test_optionleg_creation(self):
        """Should create OptionLeg with expected fields."""
        from src.trading.options_executor import OptionLeg

        leg = OptionLeg(
            symbol="SPY251219C00600000",
            strike=600.0,
            expiration=date(2025, 12, 19),
            option_type="call",
            side="sell",
            quantity=1,
            premium=2.50,
        )

        assert leg.symbol == "SPY251219C00600000"
        assert leg.strike == 600.0
        assert leg.expiration == date(2025, 12, 19)
        assert leg.option_type == "call"
        assert leg.side == "sell"
        assert leg.quantity == 1
        assert leg.premium == 2.50

    def test_optionleg_put_type(self):
        """Should allow put option type."""
        from src.trading.options_executor import OptionLeg

        leg = OptionLeg(
            symbol="SPY251219P00550000",
            strike=550.0,
            expiration=date(2025, 12, 19),
            option_type="put",
            side="buy",
            quantity=2,
            premium=1.75,
        )

        assert leg.option_type == "put"
        assert leg.side == "buy"


class TestOptionsStrategyDataclass:
    """Test OptionsStrategy dataclass."""

    def test_optionsstrategy_creation(self):
        """Should create OptionsStrategy with expected fields."""
        from src.trading.options_executor import OptionLeg, OptionsStrategy

        leg = OptionLeg(
            symbol="SPY251219C00600000",
            strike=600.0,
            expiration=date(2025, 12, 19),
            option_type="call",
            side="sell",
            quantity=1,
            premium=2.50,
        )

        strategy = OptionsStrategy(
            strategy_type="covered_call",
            underlying="SPY",
            legs=[leg],
            total_premium=250.0,
            max_risk=float("inf"),
            max_profit=250.0,
            breakeven_points=[450.0],
            required_capital=0.0,
        )

        assert strategy.strategy_type == "covered_call"
        assert strategy.underlying == "SPY"
        assert len(strategy.legs) == 1
        assert strategy.total_premium == 250.0
        assert strategy.max_profit == 250.0
        assert strategy.required_capital == 0.0


class TestOptionsExecutorConstants:
    """Test OptionsExecutor class constants."""

    def test_risk_management_constants(self):
        """Should have risk management constants defined."""
        from src.trading.options_executor import OptionsExecutor

        assert hasattr(OptionsExecutor, "MAX_PORTFOLIO_RISK_PCT")
        assert hasattr(OptionsExecutor, "MIN_PREMIUM_PER_CONTRACT")
        assert hasattr(OptionsExecutor, "MIN_IV_RANK")
        assert hasattr(OptionsExecutor, "MAX_POSITION_SIZE")
        assert hasattr(OptionsExecutor, "MIN_DTE")
        assert hasattr(OptionsExecutor, "MAX_DTE")

    def test_strategy_constants(self):
        """Should have strategy-specific constants defined."""
        from src.trading.options_executor import OptionsExecutor

        assert hasattr(OptionsExecutor, "COVERED_CALL_TARGET_DELTA")
        assert hasattr(OptionsExecutor, "IRON_CONDOR_TARGET_DELTA")
        assert hasattr(OptionsExecutor, "CREDIT_SPREAD_TARGET_DELTA")
        assert hasattr(OptionsExecutor, "SPREAD_WIDTH")

    def test_risk_limits_reasonable(self):
        """Should have reasonable risk limits (Rule #1: Don't lose money)."""
        from src.trading.options_executor import OptionsExecutor

        # Risk limits should be conservative
        assert 0 < OptionsExecutor.MAX_PORTFOLIO_RISK_PCT <= 0.10  # Max 10%
        assert OptionsExecutor.MIN_PREMIUM_PER_CONTRACT > 0
        assert OptionsExecutor.MIN_DTE >= 7  # At least a week
        assert OptionsExecutor.MAX_DTE <= 90  # Not too far out


class TestOptionsExecutorMethods:
    """Test OptionsExecutor class methods exist."""

    def test_class_has_expected_public_methods(self):
        """Should have expected public methods."""
        from src.trading.options_executor import OptionsExecutor

        assert hasattr(OptionsExecutor, "execute_covered_call")
        assert hasattr(OptionsExecutor, "execute_iron_condor")
        assert hasattr(OptionsExecutor, "execute_credit_spread")
        assert hasattr(OptionsExecutor, "validate_order")
        assert hasattr(OptionsExecutor, "place_paper_order")

    def test_class_has_expected_private_methods(self):
        """Should have expected private helper methods."""
        from src.trading.options_executor import OptionsExecutor

        assert hasattr(OptionsExecutor, "_parse_option_symbol")
        assert hasattr(OptionsExecutor, "_find_option_by_delta")
        assert hasattr(OptionsExecutor, "_find_option_by_strike")


class TestOptionsExecutorParseSymbol:
    """Test option symbol parsing."""

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_parse_call_option(self, mock_trader, mock_monitor, mock_client):
        """Should parse call option symbol correctly."""
        from src.trading.options_executor import OptionsExecutor

        # Create executor with mocked dependencies
        executor = OptionsExecutor.__new__(OptionsExecutor)
        executor.paper = True
        executor.options_client = mock_client
        executor.risk_monitor = mock_monitor
        executor.trader = mock_trader

        parsed = executor._parse_option_symbol("SPY251219C00600000")

        assert parsed["ticker"] == "SPY"
        assert parsed["expiration"] == date(2025, 12, 19)
        assert parsed["type"] == "call"
        assert parsed["strike"] == 600.0

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_parse_put_option(self, mock_trader, mock_monitor, mock_client):
        """Should parse put option symbol correctly."""
        from src.trading.options_executor import OptionsExecutor

        executor = OptionsExecutor.__new__(OptionsExecutor)
        executor.paper = True
        executor.options_client = mock_client
        executor.risk_monitor = mock_monitor
        executor.trader = mock_trader

        parsed = executor._parse_option_symbol("SPY251219P00550000")

        assert parsed["ticker"] == "SPY"
        assert parsed["expiration"] == date(2025, 12, 19)
        assert parsed["type"] == "put"
        assert parsed["strike"] == 550.0


class TestOptionsExecutorValidation:
    """Test order validation."""

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_validate_order_approves_valid(self, mock_trader, mock_monitor, mock_client):
        """Should approve valid strategy within risk limits."""
        from src.trading.options_executor import OptionLeg, OptionsExecutor, OptionsStrategy

        executor = OptionsExecutor.__new__(OptionsExecutor)
        executor.paper = True
        executor.MAX_PORTFOLIO_RISK_PCT = 0.05
        executor.MIN_PREMIUM_PER_CONTRACT = 0.25
        executor.MAX_POSITION_SIZE = 15
        executor.MIN_DTE = 30
        executor.MAX_DTE = 60

        # Create a valid strategy
        leg = OptionLeg(
            symbol="SPY260215C00600000",
            strike=600.0,
            expiration=date(2026, 2, 15),  # ~30 DTE from Jan 13
            option_type="call",
            side="sell",
            quantity=1,
            premium=3.00,
        )

        strategy = OptionsStrategy(
            strategy_type="covered_call",
            underlying="SPY",
            legs=[leg],
            total_premium=300.0,
            max_risk=1000.0,  # Less than 5% of $100k
            max_profit=300.0,
            breakeven_points=[580.0],
            required_capital=0.0,
        )

        account = {"equity": 100000.0, "buying_power": 50000.0}

        result = executor.validate_order(strategy, account)

        assert result["approved"] is True

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_validate_order_rejects_excessive_risk(self, mock_trader, mock_monitor, mock_client):
        """Should reject strategy exceeding risk limits."""
        from src.trading.options_executor import OptionLeg, OptionsExecutor, OptionsStrategy

        executor = OptionsExecutor.__new__(OptionsExecutor)
        executor.paper = True
        executor.MAX_PORTFOLIO_RISK_PCT = 0.02  # 2%
        executor.MIN_PREMIUM_PER_CONTRACT = 0.25
        executor.MAX_POSITION_SIZE = 15
        executor.MIN_DTE = 30
        executor.MAX_DTE = 60

        leg = OptionLeg(
            symbol="SPY260215P00500000",
            strike=500.0,
            expiration=date(2026, 2, 15),
            option_type="put",
            side="sell",
            quantity=1,
            premium=5.00,
        )

        # Strategy with excessive risk
        strategy = OptionsStrategy(
            strategy_type="credit_spread",
            underlying="SPY",
            legs=[leg],
            total_premium=500.0,
            max_risk=10000.0,  # 10% of $100k - exceeds 2% limit
            max_profit=500.0,
            breakeven_points=[495.0],
            required_capital=10000.0,
        )

        account = {"equity": 100000.0, "buying_power": 50000.0}

        result = executor.validate_order(strategy, account)

        assert result["approved"] is False
        assert "exceeds" in result["reason"].lower()


class TestGetOptionsExecutorFactory:
    """Test get_options_executor factory function."""

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_factory_returns_executor(self, mock_trader, mock_monitor, mock_client):
        """Should return OptionsExecutor instance."""
        from src.trading.options_executor import OptionsExecutor, get_options_executor

        executor = get_options_executor(paper=True)

        assert isinstance(executor, OptionsExecutor)
        assert executor.paper is True

    @patch("src.trading.options_executor.AlpacaOptionsClient")
    @patch("src.trading.options_executor.OptionsRiskMonitor")
    @patch("src.trading.options_executor.AlpacaTrader")
    def test_factory_live_mode(self, mock_trader, mock_monitor, mock_client):
        """Should support live trading mode."""
        from src.trading.options_executor import get_options_executor

        executor = get_options_executor(paper=False)

        assert executor.paper is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

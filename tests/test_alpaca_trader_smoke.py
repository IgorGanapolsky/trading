#!/usr/bin/env python3
"""
Smoke tests for AlpacaTrader module.

These tests verify:
1. Module imports successfully
2. Key classes/exceptions exist
3. Class has expected methods
4. Exception classes are properly defined

Created: Jan 13, 2026
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if pydantic is available (required for alpaca-py and config module)
try:
    import pydantic  # noqa: F401

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Skip all tests in this module if pydantic is not available
# The alpaca_trader module requires pydantic via src.core.config
pytestmark = pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason="pydantic not available - required for alpaca_trader dependencies"
)


class TestAlpacaTraderImports:
    """Test that alpaca_trader module imports correctly."""

    def test_module_imports(self):
        """Should import alpaca_trader module without errors."""
        from src.core import alpaca_trader

        assert alpaca_trader is not None

    def test_alpacatrader_class_exists(self):
        """Should have AlpacaTrader class."""
        from src.core.alpaca_trader import AlpacaTrader

        assert AlpacaTrader is not None
        assert callable(AlpacaTrader)

    def test_alpaca_available_constant(self):
        """Should have ALPACA_AVAILABLE constant."""
        from src.core.alpaca_trader import ALPACA_AVAILABLE

        assert isinstance(ALPACA_AVAILABLE, bool)


class TestAlpacaTraderExceptions:
    """Test exception classes."""

    def test_alpacatradererror_exists(self):
        """Should have AlpacaTraderError exception."""
        from src.core.alpaca_trader import AlpacaTraderError

        assert issubclass(AlpacaTraderError, Exception)

    def test_orderexecutionerror_exists(self):
        """Should have OrderExecutionError exception."""
        from src.core.alpaca_trader import OrderExecutionError

        assert issubclass(OrderExecutionError, Exception)

    def test_accounterror_exists(self):
        """Should have AccountError exception."""
        from src.core.alpaca_trader import AccountError

        assert issubclass(AccountError, Exception)

    def test_marketdataerror_exists(self):
        """Should have MarketDataError exception."""
        from src.core.alpaca_trader import MarketDataError

        assert issubclass(MarketDataError, Exception)

    def test_exceptions_inherit_from_base(self):
        """All exceptions should inherit from AlpacaTraderError."""
        from src.core.alpaca_trader import (
            AccountError,
            AlpacaTraderError,
            MarketDataError,
            OrderExecutionError,
        )

        assert issubclass(OrderExecutionError, AlpacaTraderError)
        assert issubclass(AccountError, AlpacaTraderError)
        assert issubclass(MarketDataError, AlpacaTraderError)

    def test_exception_can_be_raised(self):
        """Should be able to raise and catch exceptions."""
        from src.core.alpaca_trader import AlpacaTraderError, OrderExecutionError

        with pytest.raises(AlpacaTraderError):
            raise OrderExecutionError("Test error message")


class TestAlpacaTraderClassConstants:
    """Test AlpacaTrader class constants."""

    def test_tier_allocations_defined(self):
        """Should have TIER_ALLOCATIONS constant."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "TIER_ALLOCATIONS")
        assert isinstance(AlpacaTrader.TIER_ALLOCATIONS, dict)
        assert "T1_CORE" in AlpacaTrader.TIER_ALLOCATIONS

    def test_max_order_multiplier_defined(self):
        """Should have MAX_ORDER_MULTIPLIER safety constant."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "MAX_ORDER_MULTIPLIER")
        assert AlpacaTrader.MAX_ORDER_MULTIPLIER > 0

    def test_tier_allocations_sum_to_one(self):
        """Tier allocations should sum to 1.0 (100%)."""
        from src.core.alpaca_trader import AlpacaTrader

        total = sum(AlpacaTrader.TIER_ALLOCATIONS.values())
        assert abs(total - 1.0) < 0.01


class TestAlpacaTraderClassMethods:
    """Test AlpacaTrader class has expected methods."""

    def test_has_get_account_info(self):
        """Should have get_account_info method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "get_account_info")
        assert callable(AlpacaTrader.get_account_info)

    def test_has_execute_order(self):
        """Should have execute_order method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "execute_order")
        assert callable(AlpacaTrader.execute_order)

    def test_has_get_positions(self):
        """Should have get_positions method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "get_positions")
        assert callable(AlpacaTrader.get_positions)

    def test_has_get_portfolio_performance(self):
        """Should have get_portfolio_performance method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "get_portfolio_performance")
        assert callable(AlpacaTrader.get_portfolio_performance)

    def test_has_set_stop_loss(self):
        """Should have set_stop_loss method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "set_stop_loss")
        assert callable(AlpacaTrader.set_stop_loss)

    def test_has_set_take_profit(self):
        """Should have set_take_profit method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "set_take_profit")
        assert callable(AlpacaTrader.set_take_profit)

    def test_has_get_historical_bars(self):
        """Should have get_historical_bars method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "get_historical_bars")
        assert callable(AlpacaTrader.get_historical_bars)

    def test_has_cancel_all_orders(self):
        """Should have cancel_all_orders method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "cancel_all_orders")
        assert callable(AlpacaTrader.cancel_all_orders)

    def test_has_close_position(self):
        """Should have close_position method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "close_position")
        assert callable(AlpacaTrader.close_position)

    def test_has_close_all_positions(self):
        """Should have close_all_positions method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "close_all_positions")
        assert callable(AlpacaTrader.close_all_positions)

    def test_has_validate_order_amount(self):
        """Should have validate_order_amount safety method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "validate_order_amount")
        assert callable(AlpacaTrader.validate_order_amount)

    def test_has_get_current_quote(self):
        """Should have get_current_quote method."""
        from src.core.alpaca_trader import AlpacaTrader

        assert hasattr(AlpacaTrader, "get_current_quote")
        assert callable(AlpacaTrader.get_current_quote)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not available")
class TestAlpacaTraderInstantiation:
    """Test AlpacaTrader instantiation with mocked dependencies."""

    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.core.alpaca_trader.load_config")
    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_init_paper_mode(
        self, mock_get_creds, mock_config, mock_data_client, mock_trading_client
    ):
        """Should initialize in paper trading mode."""
        # Setup mocks
        mock_get_creds.return_value = ("test-api-key", "test-secret-key")
        mock_config.return_value = MagicMock(
            USE_LIMIT_ORDERS=False,
            LIMIT_ORDER_BUFFER_PCT=0.5,
            LIMIT_ORDER_TIMEOUT_SECONDS=30,
        )

        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_trading_client.return_value.get_account.return_value = mock_account

        from src.core.alpaca_trader import AlpacaTrader

        trader = AlpacaTrader(paper=True)

        assert trader.paper is True
        mock_trading_client.assert_called_once()

    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.core.alpaca_trader.load_config")
    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_init_fails_without_credentials(
        self, mock_get_creds, mock_config, mock_data_client, mock_trading_client
    ):
        """Should raise error when credentials missing."""
        mock_get_creds.return_value = (None, None)
        mock_config.return_value = MagicMock()

        from src.core.alpaca_trader import AlpacaTrader, AlpacaTraderError

        with pytest.raises(AlpacaTraderError, match="Missing API credentials"):
            AlpacaTrader(paper=True)


@pytest.mark.skipif(not PYDANTIC_AVAILABLE, reason="pydantic not available")
class TestAlpacaTraderValidation:
    """Test order validation functionality."""

    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.core.alpaca_trader.load_config")
    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_validate_order_amount_passes_normal(
        self, mock_get_creds, mock_config, mock_data_client, mock_trading_client
    ):
        """Should pass validation for normal order amounts."""
        mock_get_creds.return_value = ("test-key", "test-secret")
        mock_config.return_value = MagicMock(
            USE_LIMIT_ORDERS=False,
            LIMIT_ORDER_BUFFER_PCT=0.5,
            LIMIT_ORDER_TIMEOUT_SECONDS=30,
        )
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_trading_client.return_value.get_account.return_value = mock_account

        from src.core.alpaca_trader import AlpacaTrader

        with patch.dict(os.environ, {"DAILY_INVESTMENT": "10.0"}):
            trader = AlpacaTrader(paper=True)

            # Normal T1_CORE order: 60% of $10 = $6
            # Should pass without raising
            trader.validate_order_amount("SPY", 6.0, "T1_CORE")

    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.core.alpaca_trader.load_config")
    @patch("src.utils.alpaca_client.get_alpaca_credentials")
    def test_validate_order_amount_rejects_excessive(
        self, mock_get_creds, mock_config, mock_data_client, mock_trading_client
    ):
        """Should reject orders that are way too large (Rule #1: Don't lose money)."""
        mock_get_creds.return_value = ("test-key", "test-secret")
        mock_config.return_value = MagicMock(
            USE_LIMIT_ORDERS=False,
            LIMIT_ORDER_BUFFER_PCT=0.5,
            LIMIT_ORDER_TIMEOUT_SECONDS=30,
        )
        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_trading_client.return_value.get_account.return_value = mock_account

        from src.core.alpaca_trader import AlpacaTrader, OrderExecutionError

        with patch.dict(os.environ, {"DAILY_INVESTMENT": "10.0"}):
            trader = AlpacaTrader(paper=True)

            # Excessive order: $1000 when expected is $6 (T1_CORE = 60% of $10)
            # Max allowed = $6 * 10 = $60, so $1000 should fail
            with pytest.raises(OrderExecutionError, match="ORDER REJECTED FOR SAFETY"):
                trader.validate_order_amount("SPY", 1000.0, "T1_CORE")


class TestAlpacaImportFallback:
    """Test that module handles missing alpaca-py gracefully."""

    def test_module_loads_without_alpaca(self):
        """Should load module even if alpaca-py not installed."""
        # The module already handles ImportError for alpaca
        from src.core.alpaca_trader import ALPACA_AVAILABLE

        # We just verify the constant exists and is boolean
        assert isinstance(ALPACA_AVAILABLE, bool)

    def test_exception_classes_always_available(self):
        """Exception classes should always be importable."""
        from src.core.alpaca_trader import (
            AccountError,
            AlpacaTraderError,
            MarketDataError,
            OrderExecutionError,
        )

        # All should be available regardless of alpaca-py
        assert AlpacaTraderError is not None
        assert OrderExecutionError is not None
        assert AccountError is not None
        assert MarketDataError is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

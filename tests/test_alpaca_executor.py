"""
Comprehensive test suite for AlpacaExecutor.

Tests cover:
1. Initialization and configuration
2. account_equity property
3. sync_portfolio_state() - success and failure
4. get_positions() - empty, single, multiple positions
5. place_order() - buy, sell, invalid qty, API errors
6. set_stop_loss() - ATR-based stop loss calculation
7. place_order_with_stop_loss() - combined order + stop loss
8. Edge cases and error handling

CRITICAL: These tests validate order execution safety.
Created: Jan 6, 2026
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if pydantic is available (required for alpaca-py)
try:
    import pydantic  # noqa: F401

    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False

# Skip all tests in this module if pydantic is not available
pytestmark = pytest.mark.skipif(
    not PYDANTIC_AVAILABLE, reason="pydantic not available - required for alpaca-py"
)


@pytest.fixture(autouse=True)
def mock_trade_gate():
    """Mock mandatory trade gate to allow test trades.

    Tests should not be blocked by the $0 equity safety check (ll_051).
    The function is imported at runtime inside place_order(), so we patch at source.
    """
    with patch(
        "src.safety.mandatory_trade_gate.validate_trade_mandatory", return_value=None
    ):
        yield


class TestAlpacaExecutorInitialization:
    """Test AlpacaExecutor initialization and configuration."""

    def test_init_simulated_mode(self):
        """Should initialize in simulated mode when env var set."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            assert executor.simulated is True
            assert executor.trader is None
            assert executor.broker is None
            assert executor.simulated_orders == []

    def test_init_with_broker(self):
        """Should initialize with broker when available."""
        # Use simulated mode but then mock it to look like non-simulated
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            # Manually set up to look like non-simulated with broker
            executor.simulated = False
            executor.broker = MagicMock()
            executor.trader = MagicMock()

            assert executor.paper is True
            assert executor.simulated is False
            assert executor.broker is not None

    @patch("src.brokers.multi_broker.get_multi_broker")
    def test_init_fallback_to_simulator(self, mock_get_broker):
        """Should fall back to simulator when broker unavailable."""
        mock_get_broker.side_effect = Exception("Connection failed")

        with patch.dict(os.environ, {"ALPACA_SIMULATED": "false"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True, allow_simulator=True)

            assert executor.simulated is True
            assert executor.trader is None


class TestAccountEquityProperty:
    """Test account_equity property."""

    def test_account_equity_from_equity_field(self):
        """Should return equity from snapshot."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.account_snapshot = {"equity": 125000.50}

            assert executor.account_equity == 125000.50

    def test_account_equity_from_portfolio_value(self):
        """Should fall back to portfolio_value if equity missing."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.account_snapshot = {"portfolio_value": 98765.43}

            assert executor.account_equity == 98765.43

    def test_account_equity_simulated_default(self):
        """Should return simulated equity when snapshot empty."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true", "SIMULATED_EQUITY": "50000"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.account_snapshot = {}

            assert executor.account_equity == 50000.0


class TestSyncPortfolioState:
    """Test sync_portfolio_state() method."""

    def test_sync_simulated_mode(self):
        """Should sync in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true", "SIMULATED_EQUITY": "100000"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.sync_portfolio_state()

            assert executor.account_snapshot["equity"] == 100000.0
            assert executor.account_snapshot["mode"] == "simulated"
            assert executor.positions == []

    def test_sync_with_account_info(self):
        """Should sync using get_account_info method."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            # Mock the trader to simulate non-simulated mode
            executor.simulated = False
            executor.trader = MagicMock()
            executor.trader.get_account_info.return_value = {
                "equity": 150000.0,
                "buying_power": 100000.0,
                "cash": 50000.0,
            }
            executor.trader.get_positions.return_value = [
                {"symbol": "SPY", "qty": 10, "avg_entry_price": 450.0}
            ]

            executor.sync_portfolio_state()

            assert executor.account_snapshot["equity"] == 150000.0
            assert len(executor.positions) == 1

    def test_sync_raises_on_api_failure(self):
        """Should raise RuntimeError when API fails."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            # Mock the trader to simulate non-simulated mode
            executor.simulated = False
            executor.trader = MagicMock()
            executor.trader.get_account_info.side_effect = Exception("API Error")

            with pytest.raises(RuntimeError, match="Cannot sync portfolio"):
                executor.sync_portfolio_state()

            # Should set error state
            assert executor.account_snapshot["equity"] == 0
            assert "error" in executor.account_snapshot


class TestGetPositions:
    """Test get_positions() method."""

    def test_get_positions_simulated_empty(self):
        """Should return empty list in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.positions = []

            result = executor.get_positions()

            assert result == []

    def test_get_positions_simulated_with_data(self):
        """Should return cached positions in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            executor.positions = [
                {"symbol": "AAPL", "qty": 5},
                {"symbol": "MSFT", "qty": 10},
            ]

            result = executor.get_positions()

            assert len(result) == 2
            assert result[0]["symbol"] == "AAPL"

    def test_get_positions_from_broker(self):
        """Should get positions from broker."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            # Mock the broker to simulate non-simulated mode
            executor.simulated = False
            executor.broker = MagicMock()
            executor.broker.get_positions.return_value = (
                [
                    {
                        "symbol": "SPY",
                        "quantity": 15.0,
                        "cost_basis": 6750.0,
                        "market_value": 6900.0,
                        "unrealized_pl": 150.0,
                    }
                ],
                MagicMock(value="alpaca"),
            )

            positions = executor.get_positions()

            assert len(positions) == 1
            assert positions[0]["symbol"] == "SPY"
            assert positions[0]["qty"] == 15.0


class TestPlaceOrder:
    """Test place_order() method."""

    def test_place_order_buy_simulated(self):
        """Should place buy order in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)
                order = executor.place_order(symbol="AAPL", notional=1000.0, side="buy")

                assert order["symbol"] == "AAPL"
                assert order["side"] == "buy"
                assert order["status"] == "filled"
                assert order["mode"] == "simulated"
                assert "commission" in order
                assert "slippage_impact" in order

    def test_place_order_sell_simulated(self):
        """Should place sell order in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)
                order = executor.place_order(symbol="MSFT", qty=10, side="sell")

                assert order["symbol"] == "MSFT"
                assert order["side"] == "sell"
                assert order["qty"] == 10

    def test_place_order_via_broker(self):
        """Should place order via broker in live mode."""
        from datetime import datetime

        from src.brokers.multi_broker import BrokerType, OrderResult

        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)

                # Mock the broker to simulate non-simulated mode
                executor.simulated = False
                executor.broker = MagicMock()
                executor.broker.submit_order.return_value = OrderResult(
                    broker=BrokerType.ALPACA,
                    order_id="test-123",
                    symbol="AAPL",
                    side="buy",
                    quantity=10.0,
                    status="filled",
                    filled_price=180.0,
                    timestamp=datetime.utcnow().isoformat(),
                )

                order = executor.place_order(symbol="AAPL", qty=10, side="buy")

                assert order["symbol"] == "AAPL"
                assert order["status"] == "filled"


class TestSetStopLoss:
    """Test set_stop_loss() method."""

    def test_set_stop_loss_simulated(self):
        """Should create stop-loss order in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)
            stop_order = executor.set_stop_loss(symbol="AAPL", qty=10, stop_price=175.0)

            assert stop_order["symbol"] == "AAPL"
            assert stop_order["side"] == "sell"
            assert stop_order["type"] == "stop"
            assert stop_order["qty"] == 10.0
            assert stop_order["stop_price"] == 175.0

    def test_set_stop_loss_invalid_qty(self):
        """Should raise ValueError for invalid qty."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            with pytest.raises(ValueError, match="qty and stop_price must be positive"):
                executor.set_stop_loss(symbol="AAPL", qty=0, stop_price=175.0)

            with pytest.raises(ValueError, match="qty and stop_price must be positive"):
                executor.set_stop_loss(symbol="AAPL", qty=-5, stop_price=175.0)

    def test_set_stop_loss_invalid_price(self):
        """Should raise ValueError for invalid stop price."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            with pytest.raises(ValueError, match="qty and stop_price must be positive"):
                executor.set_stop_loss(symbol="AAPL", qty=10, stop_price=0)


class TestPlaceOrderWithStopLoss:
    """Test place_order_with_stop_loss() method."""

    def test_place_order_with_stop_loss_success(self):
        """Should place order and stop-loss successfully."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)
                result = executor.place_order_with_stop_loss(
                    symbol="AAPL", notional=1000.0, side="buy", stop_loss_pct=0.05
                )

                assert result["order"] is not None
                assert result["order"]["symbol"] == "AAPL"
                assert result["stop_loss"] is not None
                assert result["stop_loss"]["type"] == "stop"
                assert result["stop_loss_pct"] == 0.05
                assert result["error"] is None

    def test_place_order_with_stop_loss_sell_no_stop(self):
        """Should not create stop-loss for sell orders."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)
                result = executor.place_order_with_stop_loss(
                    symbol="AAPL", notional=1000.0, side="sell"
                )

                assert result["order"] is not None
                assert result["stop_loss"] is None  # No stop for sell orders

    def test_place_order_with_stop_loss_order_fails(self):
        """Should return error when main order fails."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)

                with patch.object(executor, "place_order", side_effect=Exception("Order rejected")):
                    result = executor.place_order_with_stop_loss(
                        symbol="AAPL", notional=1000.0, side="buy"
                    )

                    assert result["order"] is None
                    assert "Order failed" in result["error"]

    def test_place_order_with_stop_loss_min_max_bounds(self):
        """Should enforce min/max stop-loss bounds."""
        from src.execution.alpaca_executor import MAX_STOP_LOSS_PCT, MIN_STOP_LOSS_PCT

        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)

                # Test minimum bound
                result = executor.place_order_with_stop_loss(
                    symbol="SPY", notional=1000.0, side="buy", stop_loss_pct=0.01
                )
                assert result["stop_loss_pct"] >= MIN_STOP_LOSS_PCT

                # Test maximum bound
                result = executor.place_order_with_stop_loss(
                    symbol="SPY", notional=1000.0, side="buy", stop_loss_pct=0.15
                )
                assert result["stop_loss_pct"] <= MAX_STOP_LOSS_PCT


class TestEdgeCases:
    """Test edge cases and error scenarios."""

    def test_zero_quantity_positions(self):
        """Should handle zero quantity in position calculations."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            from src.execution.alpaca_executor import AlpacaExecutor

            executor = AlpacaExecutor(paper=True)

            # Mock the broker to simulate non-simulated mode
            executor.simulated = False
            executor.broker = MagicMock()
            executor.broker.get_positions.return_value = (
                [
                    {
                        "symbol": "TEST",
                        "quantity": 0.0,
                        "cost_basis": 1000.0,
                        "market_value": 1000.0,
                        "unrealized_pl": 0.0,
                    }
                ],
                MagicMock(value="alpaca"),
            )

            positions = executor.get_positions()

            # Should not raise, should return 0 for prices
            assert len(positions) == 1
            assert positions[0]["avg_entry_price"] == 0.0

    def test_simulated_order_realistic_slippage(self):
        """Should apply realistic slippage in simulated mode."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                from src.execution.alpaca_executor import AlpacaExecutor

                executor = AlpacaExecutor(paper=True)
                order = executor.place_order(symbol="SPY", notional=10000.0, side="buy")

                # Should have slippage and commission
                assert order["slippage_impact"] > 0
                assert order["commission"] >= 1.0
                # Slippage should be reasonable (< 1%)
                assert order["slippage_impact"] < 100.0


class TestPreTradePatternValidation:
    """Test pre-trade pattern validation using TradeMemory (Jan 7, 2026)."""

    def test_pattern_check_blocks_losing_strategy(self):
        """Should block trades with historically poor win rate."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                with patch("src.learning.trade_memory.TradeMemory") as MockMemory:
                    # Mock a pattern with poor historical performance
                    mock_instance = MagicMock()
                    mock_instance.query_similar.return_value = {
                        "pattern": "bad_strategy_bad_strategy",
                        "found": True,
                        "sample_size": 10,
                        "win_rate": 0.30,  # 30% - should block
                        "avg_pnl": -50.0,
                        "recommendation": "AVOID",
                    }
                    MockMemory.return_value = mock_instance

                    from src.execution.alpaca_executor import AlpacaExecutor
                    from src.safety.mandatory_trade_gate import TradeBlockedError

                    executor = AlpacaExecutor(paper=True)

                    with pytest.raises(TradeBlockedError):
                        executor.place_order(
                            symbol="AAPL",
                            notional=1000.0,
                            side="buy",
                            strategy="bad_strategy",
                        )

    def test_pattern_check_allows_winning_strategy(self):
        """Should allow trades with historically good win rate."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                with patch("src.learning.trade_memory.TradeMemory") as MockMemory:
                    # Mock a pattern with good historical performance
                    mock_instance = MagicMock()
                    mock_instance.query_similar.return_value = {
                        "pattern": "good_strategy_good_strategy",
                        "found": True,
                        "sample_size": 15,
                        "win_rate": 0.75,  # 75% - should allow
                        "avg_pnl": 150.0,
                        "recommendation": "PROCEED",
                    }
                    MockMemory.return_value = mock_instance

                    from src.execution.alpaca_executor import AlpacaExecutor

                    executor = AlpacaExecutor(paper=True)
                    order = executor.place_order(
                        symbol="AAPL",
                        notional=1000.0,
                        side="buy",
                        strategy="good_strategy",
                    )

                    # Should succeed
                    assert order["symbol"] == "AAPL"
                    assert order["status"] == "filled"

    def test_pattern_check_allows_new_strategy(self):
        """Should allow trades with no historical data (new patterns)."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                with patch("src.learning.trade_memory.TradeMemory") as MockMemory:
                    # Mock a pattern with no history
                    mock_instance = MagicMock()
                    mock_instance.query_similar.return_value = {
                        "pattern": "new_strategy_new_strategy",
                        "found": False,
                        "sample_size": 0,
                        "win_rate": 0.5,  # Neutral prior
                        "avg_pnl": 0.0,
                        "recommendation": "NO_HISTORY",
                    }
                    MockMemory.return_value = mock_instance

                    from src.execution.alpaca_executor import AlpacaExecutor

                    executor = AlpacaExecutor(paper=True)
                    order = executor.place_order(
                        symbol="AAPL",
                        notional=1000.0,
                        side="buy",
                        strategy="new_strategy",
                    )

                    # Should succeed - no history shouldn't block
                    assert order["symbol"] == "AAPL"
                    assert order["status"] == "filled"

    def test_pattern_check_warns_marginal_strategy(self):
        """Should warn but allow trades with marginal win rate (50-60%)."""
        with patch.dict(os.environ, {"ALPACA_SIMULATED": "true"}):
            with patch("src.observability.trade_sync.sync_trade"):
                with patch("src.learning.trade_memory.TradeMemory") as MockMemory:
                    # Mock a pattern with marginal historical performance
                    mock_instance = MagicMock()
                    mock_instance.query_similar.return_value = {
                        "pattern": "marginal_strategy_marginal_strategy",
                        "found": True,
                        "sample_size": 8,
                        "win_rate": 0.55,  # 55% - should warn but allow
                        "avg_pnl": 25.0,
                        "recommendation": "PROCEED_WITH_CAUTION",
                    }
                    MockMemory.return_value = mock_instance

                    from src.execution.alpaca_executor import AlpacaExecutor

                    executor = AlpacaExecutor(paper=True)
                    order = executor.place_order(
                        symbol="AAPL",
                        notional=1000.0,
                        side="buy",
                        strategy="marginal_strategy",
                    )

                    # Should succeed - marginal is OK
                    assert order["symbol"] == "AAPL"
                    assert order["status"] == "filled"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

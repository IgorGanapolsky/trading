"""Tests proving all execution paths enforce ticker validation.

Every order submission method must call validate_ticker() and reject non-SPY symbols.
This prevents the bug where 4 out of 5 execution paths bypassed the trade gate.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.safety.mandatory_trade_gate import validate_ticker

# -------------------------------------------------------------------
# Direct validate_ticker tests (sanity)
# -------------------------------------------------------------------


class TestValidateTicker:
    def test_spy_allowed(self):
        valid, error = validate_ticker("SPY")
        assert valid is True
        assert error == ""

    def test_non_spy_blocked(self):
        valid, error = validate_ticker("AAPL")
        assert valid is False
        assert "SPY ONLY" in error

    def test_spy_option_allowed(self):
        valid, error = validate_ticker("SPY260220P00660000")
        assert valid is True

    def test_sofi_option_blocked(self):
        valid, error = validate_ticker("SOFI260206P00024000")
        assert valid is False
        assert "SOFI" in error


# -------------------------------------------------------------------
# MultiBroker.submit_order
# -------------------------------------------------------------------


class TestMultiBrokerValidation:
    def test_submit_order_blocks_non_spy(self):
        from src.brokers.multi_broker import MultiBroker

        broker = MultiBroker()
        with pytest.raises(ValueError, match="ORDER BLOCKED"):
            broker.submit_order("AAPL", 10, "buy")

    def test_submit_order_allows_spy(self):
        """SPY passes validation (Alpaca call mocked to avoid network)."""
        from src.brokers.multi_broker import MultiBroker

        broker = MultiBroker()
        mock_client = MagicMock()
        mock_order = MagicMock()
        mock_order.id = "test-123"
        mock_order.status = MagicMock(value="accepted")
        mock_order.filled_avg_price = None
        mock_client.submit_order.return_value = mock_order
        broker._alpaca_client = mock_client

        result = broker.submit_order("SPY", 1, "buy")
        assert result.symbol == "SPY"


# -------------------------------------------------------------------
# ExecutionAgent._execute_order
# -------------------------------------------------------------------


class TestExecutionAgentValidation:
    def test_execute_order_blocks_non_spy(self):
        from src.agents.execution_agent import ExecutionAgent

        agent = ExecutionAgent(alpaca_api=MagicMock(), paper=True)
        result = agent._execute_order("AAPL", "BUY", 1000.0)
        assert result["status"] == "BLOCKED"
        assert "TICKER NOT ALLOWED" in result["error"]

    def test_submit_option_order_blocks_non_spy(self):
        from src.agents.execution_agent import ExecutionAgent

        agent = ExecutionAgent(alpaca_api=MagicMock(), paper=True)
        with pytest.raises(ValueError, match="OPTION ORDER BLOCKED"):
            agent.submit_option_order(
                option_symbol="SOFI260206P00024000",
                qty=1,
                side="sell_to_open",
            )

    def test_submit_option_order_allows_spy(self):
        """SPY option passes validation (simulated fallback, no Alpaca client)."""
        from src.agents.execution_agent import ExecutionAgent

        agent = ExecutionAgent(alpaca_api=MagicMock(), paper=True)
        # No options client set = will use simulation fallback
        result = agent.submit_option_order(
            option_symbol="SPY260220P00660000",
            qty=1,
            side="sell_to_open",
        )
        assert result["status"] == "SIMULATED"
        assert result["option_symbol"] == "SPY260220P00660000"


# -------------------------------------------------------------------
# AlpacaTrader.set_stop_loss / set_take_profit
# -------------------------------------------------------------------


class TestAlpacaTraderValidation:
    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.utils.alpaca_client.get_alpaca_credentials", return_value=("key", "secret"))
    def test_stop_loss_blocks_non_spy(self, mock_creds, mock_data, mock_trading):
        from src.core.alpaca_trader import AlpacaTrader, OrderExecutionError

        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_trading.return_value.get_account.return_value = mock_account

        trader = AlpacaTrader(paper=True)
        with pytest.raises(OrderExecutionError, match="STOP-LOSS BLOCKED"):
            trader.set_stop_loss("AAPL", 1.0, 150.0)

    @patch("src.core.alpaca_trader.TradingClient")
    @patch("src.core.alpaca_trader.StockHistoricalDataClient")
    @patch("src.utils.alpaca_client.get_alpaca_credentials", return_value=("key", "secret"))
    def test_take_profit_blocks_non_spy(self, mock_creds, mock_data, mock_trading):
        from src.core.alpaca_trader import AlpacaTrader, OrderExecutionError

        mock_account = MagicMock()
        mock_account.status = "ACTIVE"
        mock_trading.return_value.get_account.return_value = mock_account

        trader = AlpacaTrader(paper=True)
        with pytest.raises(OrderExecutionError, match="TAKE-PROFIT BLOCKED"):
            trader.set_take_profit("AAPL", 1.0, 480.0)

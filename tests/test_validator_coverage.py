"""Tests proving all execution paths enforce ticker validation.

Every order submission method must call validate_ticker() and reject non-SPY symbols.
This prevents the bug where 4 out of 5 execution paths bypassed the trade gate.
"""

from unittest.mock import MagicMock, patch

import pytest

from src.safety.mandatory_trade_gate import (
    safe_close_position,
    safe_submit_order,
    validate_ticker,
)

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
        assert "SPY/SPX/XSP ONLY" in error

    def test_spy_option_allowed(self):
        valid, error = validate_ticker("SPY260220P00660000")
        assert valid is True

    def test_spx_option_allowed(self):
        valid, error = validate_ticker("SPX260220P00660000")
        assert valid is True

    def test_xsp_option_allowed(self):
        valid, error = validate_ticker("XSP260220P00066000")
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


# -------------------------------------------------------------------
# safe_submit_order wrapper
# -------------------------------------------------------------------


class TestSafeSubmitOrder:
    def test_blocks_non_spy_symbol(self):
        """safe_submit_order rejects non-SPY order requests."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = "AAPL"
        mock_request.legs = None

        with pytest.raises(ValueError, match="ORDER BLOCKED"):
            safe_submit_order(mock_client, mock_request)

        mock_client.submit_order.assert_not_called()

    def test_allows_spy_symbol(self):
        """safe_submit_order allows SPY and delegates to client."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = "SPY"
        mock_request.legs = None

        safe_submit_order(mock_client, mock_request)
        mock_client.submit_order.assert_called_once_with(mock_request)

    def test_blocks_non_spy_option(self):
        """safe_submit_order rejects SOFI option symbols."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = "SOFI260206P00024000"
        mock_request.legs = None

        with pytest.raises(ValueError, match="ORDER BLOCKED"):
            safe_submit_order(mock_client, mock_request)

    def test_allows_spy_option(self):
        """safe_submit_order allows SPY option symbols."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = "SPY260220P00660000"
        mock_request.legs = None

        safe_submit_order(mock_client, mock_request)
        mock_client.submit_order.assert_called_once()

    def test_blocks_non_spy_mleg_leg(self):
        """safe_submit_order rejects MLEG orders with non-SPY legs."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = None

        leg1 = MagicMock()
        leg1.symbol = "SPY260220P00660000"
        leg2 = MagicMock()
        leg2.symbol = "AAPL260220P00200000"
        mock_request.legs = [leg1, leg2]

        with pytest.raises(ValueError, match="ORDER BLOCKED \\(leg\\)"):
            safe_submit_order(mock_client, mock_request)

    def test_allows_spy_mleg(self):
        """safe_submit_order allows MLEG orders with all SPY legs."""
        mock_client = MagicMock()
        mock_request = MagicMock()
        mock_request.symbol = None

        leg1 = MagicMock()
        leg1.symbol = "SPY260220P00660000"
        leg2 = MagicMock()
        leg2.symbol = "SPY260220C00670000"
        mock_request.legs = [leg1, leg2]

        safe_submit_order(mock_client, mock_request)
        mock_client.submit_order.assert_called_once()


# -------------------------------------------------------------------
# safe_close_position wrapper
# -------------------------------------------------------------------


class TestSafeClosePosition:
    def test_blocks_non_spy(self):
        """safe_close_position rejects non-SPY symbols."""
        mock_client = MagicMock()

        with pytest.raises(ValueError, match="CLOSE BLOCKED"):
            safe_close_position(mock_client, "AAPL")

        mock_client.close_position.assert_not_called()

    def test_allows_spy(self):
        """safe_close_position allows SPY and delegates to client."""
        mock_client = MagicMock()

        safe_close_position(mock_client, "SPY")
        mock_client.close_position.assert_called_once_with("SPY")

    def test_blocks_sofi_option(self):
        """safe_close_position rejects non-SPY option symbols."""
        mock_client = MagicMock()

        with pytest.raises(ValueError, match="CLOSE BLOCKED"):
            safe_close_position(mock_client, "SOFI260206P00024000")

    def test_allows_spy_option(self):
        """safe_close_position allows SPY option symbols."""
        mock_client = MagicMock()

        safe_close_position(mock_client, "SPY260220P00660000")
        mock_client.close_position.assert_called_once()

    def test_passes_kwargs(self):
        """safe_close_position passes through kwargs like close_options."""
        mock_client = MagicMock()
        mock_opts = MagicMock()

        safe_close_position(mock_client, "SPY", close_options=mock_opts)
        mock_client.close_position.assert_called_once_with("SPY", close_options=mock_opts)

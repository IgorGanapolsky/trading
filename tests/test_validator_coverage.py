"""Tests proving all execution paths enforce ticker validation.

Every order submission method must call validate_ticker() and reject non-SPY symbols.
This prevents the bug where 4 out of 5 execution paths bypassed the trade gate.
"""

from unittest.mock import MagicMock, patch

import pytest

try:
    from src.safety import mandatory_trade_gate as gate_mod
    from src.safety.mandatory_trade_gate import (
        safe_close_position,
        safe_submit_order,
        validate_ticker,
    )
except ImportError:
    pytest.skip(
        "mandatory_trade_gate imports unavailable in this environment", allow_module_level=True
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
        assert "Liquid ETFs only" in error

    def test_spy_option_allowed(self):
        valid, error = validate_ticker("SPY260220P00660000")
        assert valid is True

    def test_spx_option_blocked(self):
        """SPX blocked — SPY ONLY per CLAUDE.md."""
        valid, error = validate_ticker("SPX260220P00660000")
        assert valid is False
        assert "SPX" in error

    def test_xsp_option_blocked(self):
        """XSP blocked — SPY ONLY per CLAUDE.md."""
        valid, error = validate_ticker("XSP260220P00066000")
        assert valid is False
        assert "XSP" in error

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
        pytest.importorskip("anthropic")
        from src.agents.execution_agent import ExecutionAgent

        agent = ExecutionAgent(alpaca_api=MagicMock(), paper=True)
        result = agent._execute_order("AAPL", "BUY", 1000.0)
        assert result["status"] == "BLOCKED"
        assert "TICKER NOT ALLOWED" in result["error"]

    def test_submit_option_order_blocks_non_spy(self):
        pytest.importorskip("anthropic")
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
        pytest.importorskip("anthropic")
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
    def test_infers_paper_mode_from_two_value_paper_credentials(self, monkeypatch):
        """Workflow credentials are two-value tuples; paper env vars must still infer paper."""
        monkeypatch.setenv("ALPACA_PAPER_TRADING_API_KEY", "paper-key")
        monkeypatch.setenv("ALPACA_PAPER_TRADING_API_SECRET", "paper-secret")
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials",
            return_value=("paper-key", "paper-secret"),
        ):
            assert gate_mod._infer_paper_trading_client(object()) is True

    def test_infers_live_mode_from_two_value_live_credentials(self, monkeypatch):
        """Unknown paper status stays closed unless credentials match live fallback only."""
        monkeypatch.delenv("ALPACA_PAPER_TRADING_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_PAPER_TRADING_API_SECRET", raising=False)
        monkeypatch.setenv("ALPACA_API_KEY", "live-key")
        monkeypatch.setenv("ALPACA_SECRET_KEY", "live-secret")

        with patch(
            "src.utils.alpaca_client.get_alpaca_credentials",
            return_value=("live-key", "live-secret"),
        ):
            assert gate_mod._infer_paper_trading_client(object()) is False

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

    @patch("src.safety.mandatory_trade_gate._get_positions_qty_map", return_value={})
    @patch("src.safety.mandatory_trade_gate.validate_trade_mandatory")
    @patch("src.safety.mandatory_trade_gate._infer_is_closing_order", return_value=False)
    def test_blocks_debit_oriented_iron_condor_entry(
        self, _mock_is_closing, mock_gate, _mock_qty_map
    ):
        """Opening options-income structures must be short-credit oriented."""
        mock_gate.return_value = MagicMock(approved=True, reason="")

        mock_client = MagicMock(spec=["get_account", "submit_order"])
        mock_client.get_account.return_value = MagicMock(equity="10000")

        mock_request = MagicMock()
        mock_request.symbol = None
        mock_request.limit_price = None
        mock_request.qty = 1
        mock_request.legs = [
            MagicMock(symbol="SPY260402P00645000", side="BUY", ratio_qty=1),
            MagicMock(symbol="SPY260402P00635000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260402C00725000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260402C00715000", side="BUY", ratio_qty=1),
        ]

        with pytest.raises(ValueError, match="OPTIONS-INCOME BLOCKED"):
            safe_submit_order(mock_client, mock_request, strategy="iron_condor")

        mock_client.submit_order.assert_not_called()

    @patch("src.safety.mandatory_trade_gate._get_positions_qty_map", return_value={})
    @patch("src.safety.mandatory_trade_gate._estimate_opening_max_loss")
    @patch("src.safety.mandatory_trade_gate.validate_trade_mandatory")
    @patch("src.safety.mandatory_trade_gate._infer_is_closing_order", return_value=False)
    def test_allows_credit_oriented_iron_condor_entry(
        self, _mock_is_closing, mock_gate, mock_estimate_opening_max_loss, _mock_qty_map
    ):
        """Proper short iron condors should still pass through safe_submit_order."""
        mock_gate.return_value = MagicMock(approved=True, reason="")
        mock_estimate_opening_max_loss.return_value = (100.0, 35, "SPY")

        mock_client = MagicMock(spec=["get_account", "submit_order"])
        mock_client.get_account.return_value = MagicMock(equity="10000")
        mock_client.submit_order.return_value = MagicMock(id="ok")

        mock_request = MagicMock()
        mock_request.symbol = None
        mock_request.limit_price = 1.5
        mock_request.qty = 1
        mock_request.legs = [
            MagicMock(symbol="SPY260402P00630000", side="BUY", ratio_qty=1),
            MagicMock(symbol="SPY260402P00635000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260402C00710000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260402C00715000", side="BUY", ratio_qty=1),
        ]

        safe_submit_order(mock_client, mock_request, strategy="iron_condor")
        mock_client.submit_order.assert_called_once_with(mock_request)

    @patch("src.safety.mandatory_trade_gate.validate_trade_mandatory")
    @patch("src.safety.milestone_controller.get_milestone_context")
    @patch("src.safety.north_star_guard.get_guard_context")
    def test_injects_guard_and_positions_context_for_openings(
        self, mock_guard, mock_milestone, mock_gate
    ):
        """safe_submit_order injects dynamic context when it can infer an opening order."""
        guard_ctx = {
            "enabled": True,
            "mode": "test",
            "max_position_pct": 0.01,
            "block_new_positions": False,
            "block_reason": "",
        }
        milestone_ctx = {
            "enabled": True,
            "strategy_family": "options_income",
            "family_status": "active",
            "pause_buy_for_family": False,
            "block_reason": "",
        }
        mock_guard.return_value = guard_ctx
        mock_milestone.return_value = milestone_ctx
        mock_gate.return_value = MagicMock(approved=True, reason="")

        # Use a strict spec so MagicMock doesn't fabricate get_all_positions(),
        # which would prevent _infer_is_closing_order() from inferring openings.
        mock_client = MagicMock(spec=["get_positions", "get_account", "submit_order"])
        # Ensure _infer_is_closing_order can infer "opening":
        # qty_map must be non-empty, and the order symbol must not exist yet.
        mock_client.get_positions.return_value = [{"symbol": "QQQ", "qty": "1"}]
        mock_client.get_account.return_value = MagicMock(equity="10000")
        mock_client.submit_order.return_value = MagicMock()

        mock_request = MagicMock()
        mock_request.symbol = "SPY"
        mock_request.legs = None
        mock_request.side = "BUY"
        mock_request.qty = 1

        safe_submit_order(mock_client, mock_request)

        assert mock_gate.call_count == 1
        call_kwargs = mock_gate.call_args.kwargs
        assert "context" in call_kwargs
        ctx = call_kwargs["context"]
        assert ctx.get("north_star_guard") == guard_ctx
        assert ctx.get("milestone_controller") == milestone_ctx
        assert isinstance(ctx.get("positions"), list)
        assert ctx["positions"]
        mock_client.submit_order.assert_called_once_with(mock_request)

    @patch("src.safety.mandatory_trade_gate._infer_paper_trading_client", return_value=True)
    @patch("src.safety.mandatory_trade_gate._get_positions_qty_map", return_value={})
    @patch("src.safety.mandatory_trade_gate._estimate_opening_max_loss")
    @patch("src.safety.mandatory_trade_gate.validate_trade_mandatory")
    @patch("src.safety.mandatory_trade_gate._infer_is_closing_order", return_value=False)
    def test_marks_one_lot_paper_ic_as_controlled_validation_entry(
        self,
        _mock_is_closing,
        mock_gate,
        mock_estimate_opening_max_loss,
        _mock_qty_map,
        _mock_paper,
    ):
        """The final order gate gets enough context to keep live/scaling blocked."""
        mock_gate.return_value = MagicMock(approved=True, reason="")
        mock_estimate_opening_max_loss.return_value = (500.0, 35, "SPY")

        mock_client = MagicMock(spec=["get_account", "submit_order"])
        mock_client.get_account.return_value = MagicMock(equity="100000")
        mock_client.submit_order.return_value = MagicMock(id="ok")

        mock_request = MagicMock()
        mock_request.symbol = None
        mock_request.limit_price = -2.05
        mock_request.qty = 1
        mock_request.legs = [
            MagicMock(symbol="SPY260515P00634000", side="BUY", ratio_qty=1),
            MagicMock(symbol="SPY260515P00639000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260515C00712000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260515C00717000", side="BUY", ratio_qty=1),
        ]

        safe_submit_order(mock_client, mock_request, strategy="iron_condor")

        ctx = mock_gate.call_args.kwargs["context"]
        assert ctx["paper_trading"] is True
        assert ctx["validation_entry_quantity"] == 1
        assert ctx["controlled_paper_validation_entry"] is True
        mock_client.submit_order.assert_called_once_with(mock_request)

    def test_one_lot_paper_validation_order_bypasses_legacy_ml_halt(self, monkeypatch, tmp_path):
        """Regression for IC Simple live E2E: two-value paper creds must open validation reset."""
        from src.safety.trading_halt import TradingHaltState

        state_path = tmp_path / "system_state.json"
        state_path.write_text(
            """
            {
              "north_star_weekly_gate": {
                "mode": "validation_reset",
                "allow_validation_entries": true,
                "block_live_new_positions": true
              }
            }
            """,
            encoding="utf-8",
        )
        monkeypatch.setattr(gate_mod, "_SYSTEM_STATE_PATH", state_path)
        monkeypatch.setenv("ALPACA_PAPER_TRADING_API_KEY", "paper-key")
        monkeypatch.setenv("ALPACA_PAPER_TRADING_API_SECRET", "paper-secret")
        monkeypatch.delenv("ALPACA_API_KEY", raising=False)
        monkeypatch.delenv("ALPACA_SECRET_KEY", raising=False)
        monkeypatch.delenv("SKIP_POLICY_GATE", raising=False)

        mock_client = MagicMock(spec=["get_account", "submit_order"])
        mock_client.get_account.return_value = MagicMock(equity="100000")
        mock_client.submit_order.return_value = MagicMock(id="validation-ok")

        mock_request = MagicMock()
        mock_request.symbol = None
        mock_request.limit_price = -1.88
        mock_request.qty = 1
        mock_request.side = "SELL"
        mock_request.legs = [
            MagicMock(symbol="SPY260515P00634000", side="BUY", ratio_qty=1),
            MagicMock(symbol="SPY260515P00639000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260515C00712000", side="SELL", ratio_qty=1),
            MagicMock(symbol="SPY260515C00717000", side="BUY", ratio_qty=1),
        ]

        with (
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=("paper-key", "paper-secret"),
            ),
            patch("src.utils.alpaca_client.get_options_data_client", return_value=MagicMock()),
            patch("src.safety.macro_risk_guard.MacroRiskGuard") as mock_macro_guard,
            patch("src.safety.trading_halt.get_trading_halt_state") as mock_halt,
            patch.object(gate_mod, "_infer_is_closing_order", return_value=False),
            patch.object(gate_mod, "_get_positions_qty_map", return_value={}),
            patch.object(gate_mod, "_estimate_opening_max_loss", return_value=(500.0, 35, "SPY")),
            patch.object(gate_mod, "_enforce_intraday_guardrails", return_value=(True, "")),
            patch.object(gate_mod, "_query_rag_for_blocking_lessons", return_value=(False, [])),
            patch.object(gate_mod, "_check_market_regime", return_value=(1.0, [])),
            patch.object(gate_mod, "check_context_freshness") as mock_freshness,
            patch("src.safety.multi_model_juror.MultiModelJuror") as mock_juror,
            patch("src.safety.reasoning_evaluator.ReasoningEvaluator") as mock_evaluator,
            patch("src.rag.lessons_search.LessonsSearch") as mock_lessons,
        ):
            mock_macro_guard.return_value.get_macro_snapshot.return_value = {}
            mock_macro_guard.return_value.check_macro_vitals.return_value = (True, "")
            mock_halt.return_value = TradingHaltState(
                active=True,
                kind="system_halt",
                path="data/TRADING_HALTED",
                reason="ML GATE BLOCKED: Win rate 24.2% < 50.0%",
            )
            mock_freshness.return_value = MagicMock(
                is_stale=False, blocking=False, sources=[], stale_sources=[]
            )
            mock_juror.return_value.get_consensus.return_value = True
            mock_evaluator.return_value.evaluate.return_value = MagicMock(
                is_hallucination_risk=False,
                groundedness=0.95,
                reasoning_trace="grounded",
            )
            mock_lessons.return_value.search.return_value = []

            safe_submit_order(mock_client, mock_request, strategy="iron_condor")

        mock_client.submit_order.assert_called_once_with(mock_request)


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

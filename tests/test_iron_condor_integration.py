"""Integration tests for full iron condor lifecycle.

Tests the end-to-end flow:
  Signal -> Order creation -> Gate validation -> Submission -> Fill -> State persistence

Scenarios:
1. Successful entry: VIX favorable -> find trade -> gate passes -> submit -> fill
2. Gate rejection: trade found but mandatory gate blocks it
3. API failure: Alpaca API error during submission

All external calls are mocked. No real API calls.
"""

import sys
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Skip all tests if dotenv is not installed (required by iron_condor_trader)
pytest.importorskip("dotenv", reason="python-dotenv required for iron_condor_trader")


class TestIronCondorSuccessfulEntry:
    """Test a successful end-to-end iron condor entry."""

    @patch("scripts.iron_condor_trader.acquire_trade_lock")
    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_full_simulated_flow(self, mock_rag_class, mock_lock):
        """Full flow: find trade -> RAG check -> execute (simulated)."""
        from scripts.iron_condor_trader import IronCondorStrategy

        # Mock RAG to return no blocking lessons
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        # Mock trade lock
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        strategy = IronCondorStrategy()

        # Step 1: Find trade (mock price)
        with patch.object(strategy, "get_underlying_price", return_value=690.0):
            ic = strategy.find_trade()

        assert ic is not None
        assert ic.underlying == "SPY"
        assert ic.long_put < ic.short_put < ic.short_call < ic.long_call

        # Step 2: Execute in simulated mode
        with patch.object(strategy, "_record_trade"):
            trade = strategy.execute(ic, live=False)

        # Step 3: Verify trade result
        assert trade["status"] == "SIMULATED"
        assert trade["strategy"] == "iron_condor"
        assert trade["underlying"] == "SPY"
        assert "legs" in trade
        assert trade["legs"]["long_put"] == ic.long_put
        assert trade["legs"]["short_put"] == ic.short_put
        assert trade["legs"]["short_call"] == ic.short_call
        assert trade["legs"]["long_call"] == ic.long_call
        assert trade["credit"] > 0
        assert trade["max_profit"] > 0
        assert trade["max_risk"] > 0

        # Step 4: Verify decision trace is populated
        assert "decision_trace" in trade
        trace = trade["decision_trace"]
        assert "captured_at" in trace
        assert "strike_selection" in trace
        assert trace["strike_selection"]["method"] in (
            "live_delta",
            "heuristic_fallback",
            "unknown",
        )

    @patch("scripts.iron_condor_trader.acquire_trade_lock")
    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    @patch("scripts.iron_condor_trader.safe_submit_order")
    def test_full_live_flow_with_mleg(self, mock_submit, mock_rag_class, mock_lock):
        """Full live flow: position check -> RAG -> MLeg order submission."""
        from scripts.iron_condor_trader import IronCondorLegs, IronCondorStrategy

        # Mock RAG
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        # Mock trade lock
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        # Mock Alpaca order submission
        mock_order = MagicMock()
        mock_order.id = "mleg-order-001"
        mock_order.status = "accepted"
        mock_submit.return_value = mock_order

        ic = IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=655.0,
            long_put=645.0,
            short_call=725.0,
            long_call=735.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )

        strategy = IronCondorStrategy()

        # Mock position check - 0 existing positions
        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = []
        with (
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=("test_key", "test_secret"),
            ),
            patch("alpaca.trading.client.TradingClient", return_value=mock_client),
        ):
            with patch.object(strategy, "_record_trade"):
                trade = strategy.execute(ic, live=True)

        assert trade["status"] == "LIVE_SUBMITTED"
        assert len(trade["order_ids"]) == 1
        assert trade["order_ids"][0]["type"] == "mleg_iron_condor"
        assert len(trade["order_ids"][0]["legs"]) == 4


class TestIronCondorGateRejection:
    """Test gate rejection scenarios."""

    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    def test_rag_critical_lesson_blocks_entry(self, mock_rag_class):
        """Critical RAG lesson about iron condor should block the entire flow."""
        from scripts.iron_condor_trader import IronCondorLegs, IronCondorStrategy

        @dataclass
        class FakeLesson:
            id: str
            title: str
            severity: str
            snippet: str
            prevention: str
            file: str

        # Critical unresolved lesson about iron condors
        critical = FakeLesson(
            id="LL-999",
            title="iron condor MLeg order bug",
            severity="CRITICAL",
            snippet="MLeg orders failing silently, losing $2K",
            prevention="Fix MLeg order handling",
            file="test.md",
        )

        mock_rag = MagicMock()
        mock_rag.search.return_value = [(critical, 0.90)]
        mock_rag_class.return_value = mock_rag

        strategy = IronCondorStrategy()
        ic = IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=655.0,
            long_put=645.0,
            short_call=725.0,
            long_call=735.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )

        trade = strategy.execute(ic, live=False)

        assert trade["status"] == "BLOCKED_BY_RAG"
        assert trade["lesson_id"] == "LL-999"
        assert "iron condor" in trade["reason"].lower()


class TestIronCondorAPIFailure:
    """Test API failure handling."""

    @patch("scripts.iron_condor_trader.acquire_trade_lock")
    @patch("scripts.iron_condor_trader.LessonsLearnedRAG")
    @patch("scripts.iron_condor_trader.safe_submit_order")
    def test_mleg_order_api_failure(self, mock_submit, mock_rag_class, mock_lock):
        """MLeg order API failure should result in LIVE_FAILED status."""
        from scripts.iron_condor_trader import IronCondorLegs, IronCondorStrategy

        # Mock RAG
        mock_rag = MagicMock()
        mock_rag.search.return_value = []
        mock_rag_class.return_value = mock_rag

        # Mock trade lock
        mock_lock.return_value.__enter__ = MagicMock(return_value=None)
        mock_lock.return_value.__exit__ = MagicMock(return_value=False)

        # Mock order submission failure
        mock_submit.side_effect = Exception("Order rejected: insufficient buying power")

        ic = IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=30,
            short_put=655.0,
            long_put=645.0,
            short_call=725.0,
            long_call=735.0,
            credit_received=2.00,
            max_risk=800.0,
            max_profit=200.0,
        )

        strategy = IronCondorStrategy()

        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = []
        with (
            patch(
                "src.utils.alpaca_client.get_alpaca_credentials",
                return_value=("test_key", "test_secret"),
            ),
            patch("alpaca.trading.client.TradingClient", return_value=mock_client),
        ):
            trade = strategy.execute(ic, live=True)

        assert trade["status"] == "LIVE_FAILED"
        # Failed trades should NOT be recorded
        assert trade["order_ids"] == []

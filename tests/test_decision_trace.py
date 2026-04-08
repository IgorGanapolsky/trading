"""Tests for iron condor decision trace (Context Graph pattern)."""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Mock heavy module-level imports that iron_condor_trader.py performs at load
# (dotenv, sentry, RAG, safety gates, etc.)
# ---------------------------------------------------------------------------
_STUB_MODULES = [
    "dotenv",
    "src.rag.lessons_learned_rag",
    "src.safety.mandatory_trade_gate",
    "src.safety.trade_lock",
    "src.utils.error_monitoring",
    "src.constants.trading_thresholds",
    "src.signals.vix_mean_reversion_signal",
    "src.utils.yfinance_wrapper",
    "src.data.iv_data_provider",
]

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))
_STUB_OVERRIDES: dict[str, ModuleType] = {}
for _mod_name in _STUB_MODULES:
    stub = ModuleType(_mod_name)
    if _mod_name == "dotenv":
        stub.load_dotenv = lambda *a, **kw: None  # type: ignore[attr-defined]
    if _mod_name == "src.utils.error_monitoring":
        stub.init_sentry = lambda *a, **kw: None  # type: ignore[attr-defined]
    if _mod_name == "src.safety.trade_lock":
        stub.TradeLockTimeout = type("TradeLockTimeout", (Exception,), {})  # type: ignore[attr-defined]
        stub.acquire_trade_lock = MagicMock()  # type: ignore[attr-defined]
    if _mod_name == "src.safety.mandatory_trade_gate":
        stub.safe_submit_order = MagicMock()  # type: ignore[attr-defined]
        stub.GateResult = type(
            "GateResult", (), {"__init__": lambda self, **kw: self.__dict__.update(kw)}
        )  # type: ignore[attr-defined]
    if _mod_name == "src.rag.lessons_learned_rag":
        _rag_cls = MagicMock()
        _rag_cls.return_value.search.return_value = []
        stub.LessonsLearnedRAG = _rag_cls  # type: ignore[attr-defined]
    if _mod_name == "src.constants.trading_thresholds":

        class _RT:
            VIX_OPTIMAL_MIN = 15.0
            VIX_OPTIMAL_MAX = 25.0
            VIX_HALT_THRESHOLD = 35.0

        stub.RiskThresholds = _RT  # type: ignore[attr-defined]
    _STUB_OVERRIDES[_mod_name] = stub

with patch.dict(sys.modules, _STUB_OVERRIDES):
    from scripts.iron_condor_trader import IronCondorLegs, IronCondorStrategy

# Alias used in tests (the spec says IronCondorTrader)
IronCondorTrader = IronCondorStrategy


class TestDecisionTrace:
    """Tests for _build_decision_trace method."""

    def _make_trader(self):
        """Create an IronCondorTrader with default config."""
        return IronCondorTrader()

    def _make_ic(self):
        """Create sample IronCondorLegs."""
        return IronCondorLegs(
            underlying="SPY",
            expiry="2026-03-20",
            dte=35,
            short_put=655.0,
            long_put=650.0,
            short_call=725.0,
            long_call=730.0,
            credit_received=3.50,
            max_risk=150.0,
            max_profit=350.0,
        )

    def test_trace_has_required_fields(self):
        """Decision trace must have core fields."""
        trader = self._make_trader()
        ic = self._make_ic()
        trace = trader._build_decision_trace(ic, "VIX 18.5 favorable")

        assert "captured_at" in trace
        assert "entry_reason" in trace
        assert "market_context" in trace
        assert "signals_checked" in trace
        assert "strike_selection" in trace
        assert trace["entry_reason"] == "VIX 18.5 favorable"

    def test_trace_is_serializable(self):
        """Trace must be JSON-serializable for persistence."""
        trader = self._make_trader()
        ic = self._make_ic()
        trace = trader._build_decision_trace(ic, "test reason")

        # Must not raise
        serialized = json.dumps(trace)
        assert len(serialized) > 0

    def test_trace_captures_strike_selection(self):
        """Strike selection reasoning must be present."""
        trader = self._make_trader()
        ic = self._make_ic()
        trace = trader._build_decision_trace(ic, "test")

        ss = trace["strike_selection"]
        assert ss["method"] in ("live_delta", "heuristic_fallback", "unknown")
        assert ss["wing_width"] == 5.0  # 730 - 725

    def test_trace_survives_import_failures(self):
        """Trace must still return valid dict even if all imports fail."""
        trader = self._make_trader()
        ic = self._make_ic()

        with patch.dict(
            "sys.modules",
            {
                "src.signals.vix_mean_reversion_signal": None,
                "src.utils.yfinance_wrapper": None,
                "src.data.iv_data_provider": None,
            },
        ):
            trace = trader._build_decision_trace(ic, "fallback test")

        assert isinstance(trace, dict)
        assert trace["entry_reason"] == "fallback test"
        assert isinstance(trace["market_context"], dict)

    def test_trace_included_in_trade_record(self):
        """The execute method should include decision_trace in returned trade dict."""
        trader = self._make_trader()
        ic = self._make_ic()

        # Execute in simulated mode (no live trading)
        result = trader.execute(ic, live=False, entry_reason="test entry")

        assert "decision_trace" in result
        assert result["decision_trace"]["entry_reason"] == "test entry"

    def test_trace_timestamp_is_recent(self):
        """captured_at should be within a few seconds of now."""
        trader = self._make_trader()
        ic = self._make_ic()
        trace = trader._build_decision_trace(ic, "timing test")

        captured = datetime.fromisoformat(trace["captured_at"])
        delta = (datetime.now() - captured).total_seconds()
        assert delta < 30  # Trace may attempt API calls

    def test_precedent_query_includes_ticker_and_dte(self):
        """precedent_query should be useful for future lookups."""
        trader = self._make_trader()
        ic = self._make_ic()
        trace = trader._build_decision_trace(ic, "test")

        assert "SPY" in trace["precedent_query"]
        assert "35" in trace["precedent_query"]

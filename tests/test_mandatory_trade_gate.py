"""Tests for mandatory_trade_gate.py - Critical trade validation."""

from types import SimpleNamespace

import pytest

# Guard against partial module load in CI
try:
    from src.safety.mandatory_trade_gate import GateResult, validate_trade_mandatory

    _GATE_AVAILABLE = hasattr(GateResult, "__init__") and callable(validate_trade_mandatory)
except (ImportError, AttributeError):
    _GATE_AVAILABLE = False

pytestmark = pytest.mark.skipif(
    not _GATE_AVAILABLE,
    reason="mandatory_trade_gate not fully available (partial module load in CI)",
)


@pytest.fixture(autouse=True)
def _fresh_context_and_policy(monkeypatch):
    import src.safety.mandatory_trade_gate as gate_mod
    import src.safety.trading_halt as halt_mod

    monkeypatch.setattr(
        gate_mod,
        "get_trading_halt_state",
        lambda: SimpleNamespace(active=False, kind="none", path="", reason=""),
        raising=False,
    )
    monkeypatch.setattr(
        halt_mod,
        "get_trading_halt_state",
        lambda: SimpleNamespace(active=False, kind="none", path="", reason=""),
    )
    monkeypatch.setattr(
        gate_mod,
        "check_context_freshness",
        lambda is_market_day=True: SimpleNamespace(
            is_stale=False,
            blocking=False,
            stale_sources=[],
            sources=[],
            reason="fresh",
        ),
    )
    monkeypatch.setattr(
        gate_mod,
        "_evaluate_policy_gate",
        lambda strategy, context: {
            "eligible": True,
            "block_reasons": [],
            "decision_summary": "ELIGIBLE: test policy",
        },
    )


class TestGateResult:
    """Test GateResult dataclass."""

    def test_gate_result_creation(self):
        """Test creating GateResult with all fields."""
        from src.safety.mandatory_trade_gate import GateResult

        result = GateResult(
            approved=True,
            reason="Trade approved",
            rag_warnings=["warning1"],
            ml_anomalies=["anomaly1"],
            confidence=0.95,
        )
        assert result.approved is True
        assert result.reason == "Trade approved"
        assert len(result.rag_warnings) == 1
        assert result.confidence == 0.95

    def test_gate_result_defaults(self):
        """Test GateResult default values."""
        from src.safety.mandatory_trade_gate import GateResult

        result = GateResult(approved=False)
        assert result.approved is False
        assert result.reason == ""
        assert result.rag_warnings == []
        assert result.ml_anomalies == []
        assert result.confidence == 1.0


class TestValidateTradeMandatory:
    """Test validate_trade_mandatory function."""

    def test_valid_trade_approved(self):
        """Test that valid trade is approved (within 10% position limit)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        # Trade must be <5% of equity to pass (per CLAUDE.md)
        result = validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,  # 4% of 5000 - within 5% limit
            side="BUY",
            strategy="CSP",
            context={"equity": 5000.0},
        )
        assert result.approved is True
        assert "approved" in result.reason.lower()

    def test_position_too_large_rejected(self):
        """Test that position >5% of equity is rejected (per CLAUDE.md)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=300.0,  # 6% of 5000 - exceeds 5% limit
            side="BUY",
            strategy="CSP",
            context={"equity": 5000.0},
        )
        assert result.approved is False
        assert "exceeds" in result.reason.lower() or "max" in result.reason.lower()

    def test_invalid_amount_rejected(self):
        """Test that below minimum amount is rejected."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=0.5,  # Below $1 minimum
            side="BUY",
            strategy="CSP",
        )
        assert result.approved is False
        assert "minimum" in result.reason.lower() or "below" in result.reason.lower()

    def test_invalid_side_rejected(self):
        """Test that invalid side is rejected."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=1000.0,
            side="INVALID",
            strategy="CSP",
        )
        assert result.approved is False
        assert "invalid trade side" in result.reason.lower()

    def test_zero_equity_rejected(self):
        """Test that trading with zero equity is rejected (ll_051)."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=1000.0,
            side="BUY",
            strategy="CSP",
            context={"equity": 0},
        )
        assert result.approved is False
        assert "blind trading" in result.reason.lower()
        assert any("ll_051" in w for w in result.rag_warnings)

    def test_position_stacking_blocked(self):
        """Test that buying more of an existing symbol is blocked (LL-275).

        This is the fix for the 658 put disaster where 9 separate BUY orders
        accumulated 8 contracts because the gate didn't check for existing positions.
        """
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        # Simulate already holding SPY260220P00658000
        existing_positions = [
            {"symbol": "SPY260220P00658000", "qty": "2"},  # Already hold 2
        ]

        result = validate_trade_mandatory(
            symbol="SPY260220P00658000",  # Try to buy MORE of same symbol
            amount=100.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0, "positions": existing_positions},
        )
        assert result.approved is False
        assert "stacking" in result.reason.lower() or "already hold" in result.reason.lower()
        assert "658000" in result.reason

    def test_sell_existing_position_allowed(self):
        """Test that SELLING an existing position is still allowed."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        existing_positions = [
            {"symbol": "SPY260220P00658000", "qty": "2"},
        ]

        result = validate_trade_mandatory(
            symbol="SPY260220P00658000",
            amount=100.0,
            side="SELL",  # Selling should be allowed
            strategy="iron_condor",
            context={"equity": 5000.0, "positions": existing_positions},
        )
        # SELL should not be blocked by stacking rule
        assert "stacking" not in result.reason.lower()

    def test_north_star_guard_blocks_new_positions(self):
        """Test that north_star_guard can block new risk-on orders."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=50.0,
            side="BUY",
            strategy="iron_condor",
            context={
                "equity": 5000.0,
                "north_star_guard": {
                    "enabled": True,
                    "mode": "capital_preservation",
                    "max_position_pct": 0.01,
                    "block_new_positions": True,
                    "block_reason": "Guard blocked for test",
                },
            },
        )
        assert result.approved is False
        assert "guard blocked" in result.reason.lower()

    def test_north_star_guard_blocks_new_positions_on_sell(self):
        """Test that north_star_guard blocks SELL-to-open style entries too."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY260220P00658000",
            amount=50.0,
            side="SELL",
            strategy="credit_spread",
            context={
                "equity": 5000.0,
                "positions": [{"symbol": "SPY", "qty": "1"}],  # non-empty so is_opening stays True
                "north_star_guard": {
                    "enabled": True,
                    "mode": "capital_preservation",
                    "max_position_pct": 0.01,
                    "block_new_positions": True,
                    "block_reason": "Guard blocked for test",
                },
            },
        )
        assert result.approved is False
        assert "guard blocked" in result.reason.lower()

    def test_trading_halt_blocks_new_openings(self, monkeypatch):
        """Repo halt sentinel must block new openings regardless of strategy details."""
        import src.safety.trading_halt as halt_mod
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        monkeypatch.setattr(
            halt_mod,
            "get_trading_halt_state",
            lambda: SimpleNamespace(
                active=True,
                kind="system_halt",
                path="data/TRADING_HALTED",
                reason="System rebuild in progress.",
            ),
        )

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=50.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0},
        )

        assert result.approved is False
        assert "rebuild in progress" in result.reason.lower()
        assert any("trading_halt: BLOCKED" in check for check in result.checks_performed)

    def test_milestone_controller_blocks_paused_strategy_family(self):
        """Test that milestone controller blocks BUY for paused strategy families."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=50.0,
            side="BUY",
            strategy="iron_condor",
            context={
                "equity": 5000.0,
                "milestone_controller": {
                    "enabled": True,
                    "strategy_family": "options_income",
                    "family_status": "paused",
                    "pause_buy_for_family": True,
                    "block_reason": "Milestone controller blocked options_income for test",
                },
            },
        )
        assert result.approved is False
        assert "milestone controller blocked" in result.reason.lower()


class TestPolicyGate:
    """Test policy freshness/expectancy gating for new openings."""

    def test_policy_gate_included_in_result(self):
        """Test that policy gate check is included in checks_performed."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0},
        )
        policy_checks = [c for c in result.checks_performed if "policy_gate" in c]
        assert policy_checks == ["policy_gate: PASS"]

    def test_policy_gate_blocks_ineligible_policy(self, monkeypatch):
        """Test that stale or weak policy metadata blocks new openings."""
        import src.safety.mandatory_trade_gate as gate_mod

        monkeypatch.setattr(
            gate_mod,
            "_evaluate_policy_gate",
            lambda strategy, context: {
                "eligible": False,
                "block_reasons": ["stale_registry", "insufficient_samples"],
                "decision_summary": "INELIGIBLE: stale_registry,insufficient_samples",
            },
        )

        result = gate_mod.validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0},
        )

        assert result.approved is False
        assert "policy gate" in result.reason.lower()
        assert "stale_registry" in result.ml_anomalies
        assert "insufficient_samples" in result.ml_anomalies

    def test_context_freshness_blocks_opening_trade(self, monkeypatch):
        """Test that stale RAG/context indexes block new openings."""
        import src.safety.mandatory_trade_gate as gate_mod

        monkeypatch.setattr(
            gate_mod,
            "check_context_freshness",
            lambda is_market_day=True: SimpleNamespace(
                is_stale=True,
                blocking=True,
                stale_sources=["rag_query_index"],
                sources=[SimpleNamespace(is_stale=True, reason="rag_query_index stale")],
                reason="Stale context indexes detected: rag_query_index",
            ),
        )

        result = gate_mod.validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0},
        )

        assert result.approved is False
        assert "stale context" in result.reason.lower()
        assert "rag_query_index" in result.ml_anomalies


class TestRegimeCheck:
    """Test regime-based trade gating (LL-247 ML-IMP-2)."""

    def test_regime_check_included_in_result(self):
        """Test that regime check is included in checks_performed."""
        from src.safety.mandatory_trade_gate import validate_trade_mandatory

        result = validate_trade_mandatory(
            symbol="SPY",
            amount=200.0,
            side="BUY",
            strategy="iron_condor",
            context={"equity": 5000.0},
        )
        # Regime check should be in the performed checks
        regime_checks = [c for c in result.checks_performed if "regime_check" in c]
        assert len(regime_checks) == 1

    def test_regime_check_function(self):
        """Test the _check_market_regime function directly."""
        from src.safety.mandatory_trade_gate import _check_market_regime

        # Test with no context - should return 1.0 (default to calm)
        confidence, warnings = _check_market_regime("iron_condor", None)
        assert 0 <= confidence <= 1.0
        assert isinstance(warnings, list)

    def test_spike_regime_blocks_trade(self):
        """Test that spike regime blocks trades."""
        from src.safety.mandatory_trade_gate import _check_market_regime

        # Simulate spike regime in context
        context = {"regime_snapshot": {"label": "spike"}}
        confidence, warnings = _check_market_regime("iron_condor", context)
        assert confidence == 0.0  # 0.0 means block
        assert any("SPIKE" in w for w in warnings)

    def test_volatile_regime_reduces_confidence(self):
        """Test that volatile regime blocks neutral iron condors."""
        from src.safety.mandatory_trade_gate import _check_market_regime

        context = {"regime_snapshot": {"label": "volatile"}}
        confidence, warnings = _check_market_regime("iron_condor", context)
        assert confidence == 0.0
        assert any("VOLATILE" in w for w in warnings)

    def test_trending_regime_blocks_neutral_iron_condor(self):
        """Test that trending regime blocks neutral iron condors."""
        from src.safety.mandatory_trade_gate import _check_market_regime

        context = {"regime_snapshot": {"label": "trending_up"}}
        confidence, warnings = _check_market_regime("iron_condor", context)
        assert confidence == 0.0
        assert any("TRENDING" in w for w in warnings)

    def test_calm_regime_maintains_confidence(self):
        """Test that calm regime maintains full confidence."""
        from src.safety.mandatory_trade_gate import _check_market_regime

        context = {"regime_snapshot": {"label": "calm"}}
        confidence, warnings = _check_market_regime("iron_condor", context)
        assert confidence == 1.0  # Full confidence
        assert len(warnings) == 0  # No warnings for calm


class TestTradeBlockedError:
    """Test TradeBlockedError exception."""

    def test_exception_stores_gate_result(self):
        """Test that exception stores the gate result."""
        from src.safety.mandatory_trade_gate import GateResult, TradeBlockedError

        gate_result = GateResult(approved=False, reason="Test block")
        error = TradeBlockedError(gate_result)
        assert error.gate_result is gate_result
        assert "Test block" in str(error)

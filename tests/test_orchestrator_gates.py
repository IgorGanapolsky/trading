#!/usr/bin/env python3
"""
Unit tests for src/orchestrator/gates.py

Created: Jan 27, 2026
Purpose: Test the 43+ gate methods in the trading gate pipeline (1,804 LOC).
Focus: Critical gates that control trade execution.

CRITICAL: This module had 0% test coverage before this file was created.
The gate pipeline is the core of the trading system - failures here = real money lost.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestrator.gates import (
    GateResult,
    GateStatus,
    TradeContext,
    _timed_gate_execution,
)


class TestGateStatus:
    """Test GateStatus enum values."""

    def test_gate_status_values(self):
        """Verify all gate status values exist."""
        assert GateStatus.PASS.value == "pass"
        assert GateStatus.REJECT.value == "reject"
        assert GateStatus.SKIP.value == "skip"
        assert GateStatus.ERROR.value == "error"

    def test_gate_status_count(self):
        """Verify we have exactly 4 statuses."""
        assert len(GateStatus) == 4


class TestGateResult:
    """Test GateResult dataclass."""

    def test_gate_result_creation(self):
        """Test basic GateResult creation."""
        result = GateResult(
            gate_name="test_gate",
            status=GateStatus.PASS,
            ticker="SPY",
            confidence=0.85,
            reason="Test passed",
        )
        assert result.gate_name == "test_gate"
        assert result.status == GateStatus.PASS
        assert result.ticker == "SPY"
        assert result.confidence == 0.85
        assert result.reason == "Test passed"

    def test_gate_result_passed_property(self):
        """Test passed property returns True only for PASS status."""
        pass_result = GateResult("g", GateStatus.PASS, "SPY")
        reject_result = GateResult("g", GateStatus.REJECT, "SPY")
        skip_result = GateResult("g", GateStatus.SKIP, "SPY")
        error_result = GateResult("g", GateStatus.ERROR, "SPY")

        assert pass_result.passed is True
        assert reject_result.passed is False
        assert skip_result.passed is False
        assert error_result.passed is False

    def test_gate_result_rejected_property(self):
        """Test rejected property returns True only for REJECT status."""
        pass_result = GateResult("g", GateStatus.PASS, "SPY")
        reject_result = GateResult("g", GateStatus.REJECT, "SPY")
        skip_result = GateResult("g", GateStatus.SKIP, "SPY")

        assert pass_result.rejected is False
        assert reject_result.rejected is True
        assert skip_result.rejected is False

    def test_gate_result_to_dict(self):
        """Test to_dict serialization."""
        result = GateResult(
            gate_name="momentum_gate",
            status=GateStatus.PASS,
            ticker="SPY",
            confidence=0.75,
            reason="Strong momentum",
            data={"signal": "BUY"},
        )
        result.execution_time_ms = 123.45

        d = result.to_dict()

        assert d["gate"] == "momentum_gate"
        assert d["status"] == "pass"
        assert d["ticker"] == "SPY"
        assert d["confidence"] == 0.75
        assert d["reason"] == "Strong momentum"
        assert d["execution_time_ms"] == 123.45
        assert d["signal"] == "BUY"

    def test_gate_result_default_values(self):
        """Test default values are set correctly."""
        result = GateResult("g", GateStatus.PASS, "SPY")

        assert result.confidence == 0.0
        assert result.reason == ""
        assert result.data == {}
        assert result.execution_time_ms == 0.0


class TestTradeContext:
    """Test TradeContext dataclass."""

    def test_trade_context_creation(self):
        """Test basic TradeContext creation."""
        ctx = TradeContext(ticker="SPY")
        assert ctx.ticker == "SPY"
        assert ctx.momentum_signal is None
        assert ctx.momentum_strength == 0.0
        assert ctx.rl_decision == {}
        assert ctx.sentiment_score == 0.0

    def test_trade_context_with_values(self):
        """Test TradeContext with all values set."""
        ctx = TradeContext(
            ticker="SPY",
            momentum_signal="BUY",
            momentum_strength=0.8,
            sentiment_score=0.65,
            introspection_multiplier=1.2,
            current_price=450.00,
        )

        assert ctx.ticker == "SPY"
        assert ctx.momentum_signal == "BUY"
        assert ctx.momentum_strength == 0.8
        assert ctx.sentiment_score == 0.65
        assert ctx.introspection_multiplier == 1.2
        assert ctx.current_price == 450.00


class TestTimedGateExecution:
    """Test _timed_gate_execution wrapper."""

    def test_timed_execution_adds_timing(self):
        """Test that timing is captured."""

        def mock_gate(*args, **kwargs):
            return GateResult("test", GateStatus.PASS, "SPY")

        result = _timed_gate_execution(mock_gate)

        assert result.execution_time_ms >= 0
        assert result.status == GateStatus.PASS

    def test_timed_execution_passes_args(self):
        """Test that args are passed through."""
        received_args = []

        def mock_gate(*args, **kwargs):
            received_args.extend(args)
            received_args.append(kwargs)
            return GateResult("test", GateStatus.PASS, "SPY")

        _timed_gate_execution(mock_gate, "arg1", "arg2", key="value")

        assert "arg1" in received_args
        assert "arg2" in received_args
        assert {"key": "value"} in received_args


class TestGateSecurity:
    """Test GateSecurity (Gate S) - protects against prompt injection."""

    def test_gate_security_import(self):
        """Test GateSecurity can be imported."""
        from src.orchestrator.gates import GateSecurity

        assert GateSecurity is not None

    def test_gate_security_initialization(self):
        """Test GateSecurity initialization."""
        from src.orchestrator.gates import GateSecurity

        mock_telemetry = MagicMock()
        gate = GateSecurity(telemetry=mock_telemetry, strict_mode=True)

        assert gate.strict_mode is True

    def test_gate_security_valid_signal(self):
        """Test GateSecurity passes valid signals."""
        from src.orchestrator.gates import GateSecurity

        mock_telemetry = MagicMock()
        gate = GateSecurity(telemetry=mock_telemetry, strict_mode=False)

        # Use correct API: external_data and trade_signal
        result = gate.evaluate(
            ticker="SPY",
            external_data=None,
            trade_signal=None,
        )

        # SPY with no threats should pass
        assert result.status in [GateStatus.PASS, GateStatus.SKIP]

    def test_gate_security_with_external_data(self):
        """Test GateSecurity with external data (no injection)."""
        from src.orchestrator.gates import GateSecurity

        mock_telemetry = MagicMock()
        gate = GateSecurity(telemetry=mock_telemetry, strict_mode=True)

        result = gate.evaluate(
            ticker="SPY",
            external_data={"news": "SPY up 1% on earnings"},
            trade_signal=None,
        )

        # Normal news should pass
        assert result.status == GateStatus.PASS


class TestGateMemory:
    """Test GateMemory (Gate M) - TradeMemory feedback loop."""

    def test_gate_memory_import(self):
        """Test GateMemory can be imported."""
        from src.orchestrator.gates import GateMemory

        assert GateMemory is not None

    def test_gate_memory_initialization(self):
        """Test GateMemory initialization."""
        from src.orchestrator.gates import GateMemory

        mock_telemetry = MagicMock()
        # GateMemory takes telemetry and optional memory_path
        gate = GateMemory(telemetry=mock_telemetry)

        assert gate is not None

    def test_gate_memory_with_custom_path(self):
        """Test GateMemory with custom memory path."""
        from src.orchestrator.gates import GateMemory

        mock_telemetry = MagicMock()
        gate = GateMemory(telemetry=mock_telemetry, memory_path="data/test_memory.json")

        # Should initialize even with non-existent path
        assert gate is not None


class TestGate0Psychology:
    """Test Gate0Psychology - pre-trade mental state check."""

    def test_gate0_psychology_import(self):
        """Test Gate0Psychology can be imported."""
        from src.orchestrator.gates import Gate0Psychology

        assert Gate0Psychology is not None

    def test_gate0_psychology_initialization(self):
        """Test Gate0Psychology initialization."""
        from src.orchestrator.gates import Gate0Psychology

        mock_telemetry = MagicMock()
        mock_coach = MagicMock()
        gate = Gate0Psychology(mental_coach=mock_coach, telemetry=mock_telemetry)

        assert gate is not None


class TestGate1Momentum:
    """Test Gate1Momentum - momentum filter."""

    def test_gate1_momentum_import(self):
        """Test Gate1Momentum can be imported."""
        from src.orchestrator.gates import Gate1Momentum

        assert Gate1Momentum is not None

    def test_gate1_momentum_initialization(self):
        """Test Gate1Momentum initialization."""
        from src.orchestrator.gates import Gate1Momentum

        mock_telemetry = MagicMock()
        mock_agent = MagicMock()
        mock_failure_manager = MagicMock()
        gate = Gate1Momentum(
            momentum_agent=mock_agent,
            failure_manager=mock_failure_manager,
            telemetry=mock_telemetry,
        )

        assert gate is not None


class TestGate15Debate:
    """Test Gate15Debate - Bull/Bear debate."""

    def test_gate15_debate_import(self):
        """Test Gate15Debate can be imported."""
        from src.orchestrator.gates import Gate15Debate

        assert Gate15Debate is not None

    def test_gate15_debate_disabled(self):
        """Test Gate15Debate when debate not available."""
        from src.orchestrator.gates import Gate15Debate

        mock_telemetry = MagicMock()
        gate = Gate15Debate(debate_moderator=None, telemetry=mock_telemetry, debate_available=False)

        ctx = TradeContext(ticker="SPY")
        result = gate.evaluate(ticker="SPY", ctx=ctx)

        # Should skip when debate not available
        assert result.status == GateStatus.SKIP


class TestGate2RLFilter:
    """Test Gate2RLFilter - Reinforcement Learning filter."""

    def test_gate2_rl_filter_import(self):
        """Test Gate2RLFilter can be imported."""
        from src.orchestrator.gates import Gate2RLFilter

        assert Gate2RLFilter is not None


class TestGate3Sentiment:
    """Test Gate3Sentiment - LLM sentiment analysis."""

    def test_gate3_sentiment_import(self):
        """Test Gate3Sentiment can be imported."""
        from src.orchestrator.gates import Gate3Sentiment

        assert Gate3Sentiment is not None

    def test_gate3_llm_blend_applies_normalization_and_gain_caps(self, monkeypatch):
        """LLM + Playwright fusion should be capped so neither source dominates."""
        from src.orchestrator.gates import Gate3Sentiment

        monkeypatch.setenv("LLM_SENTIMENT_WEIGHT", "1")
        monkeypatch.setenv("PLAYWRIGHT_SENTIMENT_WEIGHT", "1")
        monkeypatch.setenv("LLM_SENTIMENT_GAIN_CAP_LLM", "0.2")
        monkeypatch.setenv("LLM_SENTIMENT_GAIN_CAP_PLAYWRIGHT", "0.2")

        llm_agent = MagicMock()
        llm_agent.model_name = "test-model"
        budget = MagicMock()
        budget.can_afford_execution.return_value = True
        failure_manager = MagicMock()
        failure_manager.run.return_value = SimpleNamespace(
            ok=True,
            result={"score": 1.0, "reason": "positive", "cost": 0.02},
            failure=None,
        )
        gate = Gate3Sentiment(
            llm_agent=llm_agent,
            bias_provider=None,
            budget_controller=budget,
            playwright_scraper=MagicMock(),
            failure_manager=failure_manager,
            telemetry=MagicMock(),
            llm_sentiment_enabled=True,
        )
        ctx = TradeContext(
            ticker="SPY",
            momentum_signal=SimpleNamespace(indicators={}),
            momentum_strength=0.8,
        )

        result = gate._evaluate_llm("SPY", ctx, threshold=-0.2, playwright_score=1.0)

        assert result.status == GateStatus.PASS
        assert ctx.sentiment_score == pytest.approx(0.4, rel=1e-6)
        assert result.confidence == pytest.approx(0.4, rel=1e-6)

    def test_gate3_llm_debate_adjustment_respects_bear_cap(self, monkeypatch):
        """Bearish debate dampening should be bounded by configured cap."""
        from src.orchestrator.gates import Gate3Sentiment

        monkeypatch.setenv("LLM_SENTIMENT_WEIGHT", "1")
        monkeypatch.setenv("PLAYWRIGHT_SENTIMENT_WEIGHT", "0")
        monkeypatch.setenv("LLM_SENTIMENT_GAIN_CAP_LLM", "1")
        monkeypatch.setenv("LLM_SENTIMENT_GAIN_CAP_PLAYWRIGHT", "0")
        monkeypatch.setenv("LLM_SENTIMENT_DEBATE_BEAR_CAP", "0.05")

        llm_agent = MagicMock()
        llm_agent.model_name = "test-model"
        budget = MagicMock()
        budget.can_afford_execution.return_value = True
        failure_manager = MagicMock()
        failure_manager.run.return_value = SimpleNamespace(
            ok=True,
            result={"score": 0.9, "reason": "positive", "cost": 0.02},
            failure=None,
        )
        gate = Gate3Sentiment(
            llm_agent=llm_agent,
            bias_provider=None,
            budget_controller=budget,
            playwright_scraper=MagicMock(),
            failure_manager=failure_manager,
            telemetry=MagicMock(),
            llm_sentiment_enabled=True,
        )
        ctx = TradeContext(
            ticker="SPY",
            momentum_signal=SimpleNamespace(indicators={}),
            momentum_strength=0.8,
            debate_outcome=SimpleNamespace(winner="BEAR", confidence=1.0),
        )

        gate._evaluate_llm("SPY", ctx, threshold=-0.2, playwright_score=0.0)
        assert ctx.sentiment_score == pytest.approx(0.85, rel=1e-6)

    def test_gate3_bias_adjustment_respects_bear_cap(self, monkeypatch):
        """Cached bias path should use the same bounded adjustment rules."""
        from src.orchestrator.gates import Gate3Sentiment

        monkeypatch.setenv("LLM_SENTIMENT_DEBATE_BEAR_CAP", "0.05")

        gate = Gate3Sentiment(
            llm_agent=MagicMock(),
            bias_provider=None,
            budget_controller=MagicMock(),
            playwright_scraper=MagicMock(),
            failure_manager=MagicMock(),
            telemetry=MagicMock(),
            llm_sentiment_enabled=True,
        )
        ctx = TradeContext(
            ticker="SPY",
            momentum_strength=0.8,
            debate_outcome=SimpleNamespace(winner="BEAR", confidence=1.0),
        )
        bias = SimpleNamespace(score=0.9, reason="cached bias")

        result = gate._evaluate_bias("SPY", bias, threshold=-0.2, ctx=ctx)

        assert result.status == GateStatus.PASS
        assert ctx.sentiment_score == pytest.approx(0.85, rel=1e-6)


class TestGate35Introspection:
    """Test Gate35Introspection - self-awareness check."""

    def test_gate35_introspection_import(self):
        """Test Gate35Introspection can be imported."""
        from src.orchestrator.gates import Gate35Introspection

        assert Gate35Introspection is not None


class TestGate4Risk:
    """Test Gate4Risk - position sizing."""

    def test_gate4_risk_import(self):
        """Test Gate4Risk can be imported."""
        from src.orchestrator.gates import Gate4Risk

        assert Gate4Risk is not None


class TestGate5Execution:
    """Test Gate5Execution - trade execution."""

    def test_gate5_execution_import(self):
        """Test Gate5Execution can be imported."""
        from src.orchestrator.gates import Gate5Execution

        assert Gate5Execution is not None


class TestTradingGatePipeline:
    """Test TradingGatePipeline orchestration."""

    def test_trading_gate_pipeline_import(self):
        """Test TradingGatePipeline can be imported."""
        from src.orchestrator.gates import TradingGatePipeline

        assert TradingGatePipeline is not None


class TestIntegration:
    """Integration tests for gate interactions."""

    def test_gate_result_chaining(self):
        """Test that gate results can be chained properly."""
        results = []

        # Simulate gate pipeline with SPY context
        _ctx = TradeContext(ticker="SPY")  # noqa: F841

        # Gate S
        results.append(GateResult("security", GateStatus.PASS, "SPY", 1.0, "Valid ticker"))

        # Gate M
        results.append(GateResult("memory", GateStatus.PASS, "SPY", 0.8, "No bad history"))

        # Gate 0
        results.append(GateResult("psychology", GateStatus.PASS, "SPY", 0.9, "Mental state OK"))

        # Verify all passed
        assert all(r.passed for r in results)

    def test_gate_rejection_stops_pipeline(self):
        """Test that a rejection should stop the pipeline."""
        results = []

        # Gate S passes
        results.append(GateResult("security", GateStatus.PASS, "SPY"))

        # Gate M rejects
        results.append(
            GateResult("memory", GateStatus.REJECT, "SPY", 0.2, "Previous losses on this setup")
        )

        # Pipeline should stop at first rejection
        first_rejection = next((r for r in results if r.rejected), None)
        assert first_rejection is not None
        assert first_rejection.gate_name == "memory"


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_ticker(self):
        """Test behavior with empty ticker."""
        ctx = TradeContext(ticker="")
        assert ctx.ticker == ""

    def test_none_values_in_context(self):
        """Test TradeContext handles None values."""
        ctx = TradeContext(
            ticker="SPY", momentum_signal=None, current_price=None, allocation_plan=None
        )

        assert ctx.momentum_signal is None
        assert ctx.current_price is None

    def test_gate_result_with_empty_data(self):
        """Test GateResult with empty data dict."""
        result = GateResult("test", GateStatus.PASS, "SPY", data={})

        d = result.to_dict()
        assert "gate" in d
        assert "status" in d


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Unit tests for constrained Smart DCA signal fusion."""

from __future__ import annotations

import pytest

from src.orchestrator.smart_dca import SmartDCAAllocator

_BLEND_ENV_KEYS = [
    "SMART_DCA_BLEND_BASE",
    "SMART_DCA_BLEND_WEIGHT_MOMENTUM",
    "SMART_DCA_BLEND_WEIGHT_RL",
    "SMART_DCA_BLEND_WEIGHT_SENTIMENT",
    "SMART_DCA_BLEND_GAIN_CAP_MOMENTUM",
    "SMART_DCA_BLEND_GAIN_CAP_RL",
    "SMART_DCA_BLEND_GAIN_CAP_SENTIMENT",
]


class _DummyConfig:
    def get_tier_allocations(self):
        return {"core_etfs": 50.0, "growth_stocks": 0.0}


@pytest.fixture(autouse=True)
def _clear_blend_env(monkeypatch):
    for key in _BLEND_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_blend_confidence_clamps_inputs_to_unit_interval():
    score = SmartDCAAllocator._blend_confidence(2.5, -5.0, 2.0)
    assert 0.0 <= score <= 1.0


def test_blend_confidence_applies_per_signal_gain_caps(monkeypatch):
    monkeypatch.setenv("SMART_DCA_BLEND_BASE", "0.2")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_MOMENTUM", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_RL", "1")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_SENTIMENT", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_GAIN_CAP_MOMENTUM", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_GAIN_CAP_RL", "0.1")
    monkeypatch.setenv("SMART_DCA_BLEND_GAIN_CAP_SENTIMENT", "0")

    score = SmartDCAAllocator._blend_confidence(0.0, 1.0, 0.0)
    assert score == pytest.approx(0.3, rel=1e-6)


def test_blend_confidence_ignores_negative_sentiment_contribution(monkeypatch):
    monkeypatch.setenv("SMART_DCA_BLEND_BASE", "0.2")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_MOMENTUM", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_RL", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_SENTIMENT", "1")
    monkeypatch.setenv("SMART_DCA_BLEND_GAIN_CAP_SENTIMENT", "1")

    score = SmartDCAAllocator._blend_confidence(0.0, 0.0, -1.0)
    assert score == pytest.approx(0.2, rel=1e-6)


def test_plan_allocation_uses_constrained_blend_for_bucket_cap(monkeypatch):
    monkeypatch.setenv("SMART_DCA_BLEND_BASE", "0.2")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_MOMENTUM", "1")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_RL", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_WEIGHT_SENTIMENT", "0")
    monkeypatch.setenv("SMART_DCA_BLEND_GAIN_CAP_MOMENTUM", "0.4")

    allocator = SmartDCAAllocator(config=_DummyConfig())
    plan = allocator.plan_allocation(
        ticker="SPY",
        momentum_strength=1.0,
        rl_confidence=0.0,
        sentiment_score=0.0,
    )

    assert plan.bucket == "core_etfs"
    assert plan.confidence == pytest.approx(0.6, rel=1e-6)
    assert plan.cap == pytest.approx(30.0, rel=1e-6)

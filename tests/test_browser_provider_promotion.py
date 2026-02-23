"""Tests for browser provider promotion decision engine."""

from __future__ import annotations

from pathlib import Path

from src.analytics.browser_provider_promotion import (
    load_policy,
    load_previous_provider,
    recommend_provider,
)


def test_recommend_provider_prefers_local_when_anchor_is_expensive() -> None:
    summary = {
        "local": {
            "attempted": 6,
            "success_rate": 1.0,
            "avg_latency_ms": 600.0,
            "cost_per_success_usd": 0.0,
        },
        "anchor": {
            "attempted": 6,
            "success_rate": 1.0,
            "avg_latency_ms": 500.0,
            "cost_per_success_usd": 0.12,
        },
    }
    decision = recommend_provider(summary)
    assert decision["recommended_provider"] == "local"
    assert "cost_per_success" in " ".join(decision["candidates"]["anchor"]["ineligible_reasons"])


def test_recommend_provider_can_select_anchor_when_reliable_and_cheap() -> None:
    summary = {
        "local": {
            "attempted": 6,
            "success_rate": 0.91,
            "avg_latency_ms": 900.0,
            "cost_per_success_usd": 0.0,
        },
        "anchor": {
            "attempted": 6,
            "success_rate": 0.99,
            "avg_latency_ms": 350.0,
            "cost_per_success_usd": 0.005,
        },
    }
    decision = recommend_provider(summary)
    assert decision["recommended_provider"] == "anchor"
    assert decision["confidence"] > 0.5


def test_recommend_provider_hysteresis_keeps_previous_provider() -> None:
    summary = {
        "local": {
            "attempted": 6,
            "success_rate": 0.95,
            "avg_latency_ms": 700.0,
            "cost_per_success_usd": 0.0,
        },
        "anchor": {
            "attempted": 6,
            "success_rate": 0.96,
            "avg_latency_ms": 680.0,
            "cost_per_success_usd": 0.001,
        },
    }
    decision = recommend_provider(summary, previous_provider="local")
    assert decision["recommended_provider"] == "local"
    assert "hysteresis" in decision["reason"]


def test_load_previous_provider_handles_missing_or_invalid(tmp_path: Path) -> None:
    state_path = tmp_path / "state.json"
    assert load_previous_provider(state_path) is None

    state_path.write_text("{}", encoding="utf-8")
    assert load_previous_provider(state_path) is None

    state_path.write_text('{"preferred_provider": "anchor"}', encoding="utf-8")
    assert load_previous_provider(state_path) == "anchor"


def test_load_policy_defaults_when_missing(tmp_path: Path) -> None:
    policy_path = tmp_path / "policy.json"
    policy = load_policy(policy_path)
    assert policy["default_provider"] == "local"
    assert policy["min_attempted"] >= 1

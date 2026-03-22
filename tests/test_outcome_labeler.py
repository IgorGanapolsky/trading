"""Tests for outcome label normalization helpers."""

from __future__ import annotations

from src.learning.outcome_labeler import build_outcome_label


def test_build_outcome_label_profitable_iron_condor():
    result = build_outcome_label(
        {
            "underlying": "SPY",
            "strategy": "iron_condor",
            "total_pl": 150.0,
            "credit_received": 300.0,
            "entry_time": "2026-03-17T13:00:00Z",
            "exit_time": "2026-03-17T15:30:00Z",
            "exit_reason": "PROFIT_TARGET",
        }
    )

    assert result["reward"] == 150.0
    assert result["return_pct"] == 50.0
    assert result["won"] is True
    assert result["lost"] is False
    assert result["holding_minutes"] == 150
    assert result["outcome"] == "won"
    assert result["summary"] == {
        "symbol": "SPY",
        "strategy": "iron_condor",
        "outcome": "won",
        "reward": 150.0,
        "return_pct": 50.0,
        "holding_minutes": 150,
        "exit_reason": "PROFIT_TARGET",
    }


def test_build_outcome_label_losing_trade():
    result = build_outcome_label(
        {
            "symbol": "QQQ",
            "strategy": "iron_condor",
            "pnl": -80.0,
            "credit": 200.0,
            "entry_timestamp": "2026-03-17T09:45:00Z",
            "exit_timestamp": "2026-03-17T10:30:00Z",
            "exit_reason": "STOP_LOSS",
        }
    )

    assert result["reward"] == -80.0
    assert result["return_pct"] == -40.0
    assert result["won"] is False
    assert result["lost"] is True
    assert result["holding_minutes"] == 45
    assert result["outcome"] == "lost"
    assert result["summary"] == {
        "symbol": "QQQ",
        "strategy": "iron_condor",
        "outcome": "lost",
        "reward": -80.0,
        "return_pct": -40.0,
        "holding_minutes": 45,
        "exit_reason": "STOP_LOSS",
    }


def test_build_outcome_label_partial_missing_data():
    result = build_outcome_label(
        {
            "symbol": "IWM",
            "strategy": "iron_condor",
            "entry_time": "not-a-timestamp",
            "exit_time": None,
        }
    )

    assert result["reward"] == 0.0
    assert result["return_pct"] is None
    assert result["won"] is False
    assert result["lost"] is False
    assert result["holding_minutes"] is None
    assert result["outcome"] == "unknown"
    assert result["summary"] == {
        "symbol": "IWM",
        "strategy": "iron_condor",
        "outcome": "unknown",
        "reward": 0.0,
    }

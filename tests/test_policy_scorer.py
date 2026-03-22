from datetime import datetime, timezone

from src.ml.policy_registry import PolicyRegistry
from src.ml.policy_scorer import PolicyScorer


def test_policy_scorer_blocks_stale_registry() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "1.0.0",
                "trained_at": "2026-03-01T00:00:00+00:00",
                "trades_trained_on": 200,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )
    scorer = PolicyScorer(registry)

    decision = scorer.score(
        "iron_condor",
        model_metrics={"expected_return_per_trade": 0.12},
        as_of=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert decision["eligible"] is False
    assert "stale_registry" in decision["block_reasons"]


def test_policy_scorer_blocks_insufficient_samples() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "1.1.0",
                "trained_at": "2026-03-16T00:00:00+00:00",
                "trades_trained_on": 8,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )
    scorer = PolicyScorer(registry)

    decision = scorer.score(
        "iron_condor",
        model_metrics={"expected_return_per_trade": 0.11},
        as_of=datetime(2026, 3, 17, 10, 0, tzinfo=timezone.utc),
    )

    assert decision["eligible"] is False
    assert "insufficient_samples" in decision["block_reasons"]


def test_policy_scorer_blocks_negative_expectancy() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "1.2.0",
                "trained_at": "2026-03-17T00:00:00+00:00",
                "trades_trained_on": 100,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )
    scorer = PolicyScorer(registry)

    decision = scorer.score(
        "iron_condor",
        model_metrics={"expected_return_per_trade": -0.01},
        as_of=datetime(2026, 3, 17, 11, 0, tzinfo=timezone.utc),
    )

    assert decision["eligible"] is False
    assert "negative_expectancy" in decision["block_reasons"]


def test_policy_scorer_passes_when_all_checks_pass() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "2.0.0",
                "trained_at": "2026-03-16T00:00:00+00:00",
                "trades_trained_on": 140,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )
    scorer = PolicyScorer(registry)

    decision = scorer.score(
        "iron_condor",
        model_metrics={"expected_return_per_trade": 0.08},
        as_of=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc),
    )

    assert decision["eligible"] is True
    assert decision["block_reasons"] == []
    assert decision["decision_summary"].startswith("ELIGIBLE:")

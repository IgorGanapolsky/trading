from datetime import datetime, timezone

from src.ml.policy_registry import PolicyRegistry


def test_policy_registry_marks_stale_metadata() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "1.0.0",
                "trained_at": "2026-03-01T00:00:00+00:00",
                "trades_trained_on": 120,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )

    status = registry.status("iron_condor", as_of=datetime(2026, 3, 17, 12, 0, tzinfo=timezone.utc))

    assert status["exists"] is True
    assert status["age_days"] == 16
    assert status["is_fresh"] is False
    assert status["sufficient_samples"] is True


def test_policy_registry_marks_insufficient_samples() -> None:
    registry = PolicyRegistry(
        entries={
            "iron_condor": {
                "version": "1.0.1",
                "trained_at": "2026-03-16T00:00:00+00:00",
                "trades_trained_on": 12,
                "max_age_days": 7,
                "min_trades_required": 50,
            }
        }
    )

    status = registry.status("iron_condor", as_of=datetime(2026, 3, 17, 9, 0, tzinfo=timezone.utc))

    assert status["exists"] is True
    assert status["is_fresh"] is True
    assert status["sufficient_samples"] is False


def test_policy_registry_roundtrip_serialization() -> None:
    registry = PolicyRegistry()
    registry.upsert(
        "iron_condor",
        {
            "version": "2.0.0",
            "trained_at": "2026-03-17T00:00:00+00:00",
            "trades_trained_on": 88,
            "max_age_days": 10,
            "min_trades_required": 30,
        },
    )

    serialized = registry.to_dict()
    assert serialized["iron_condor"]["version"] == "2.0.0"
    assert serialized["iron_condor"]["trades_trained_on"] == 88

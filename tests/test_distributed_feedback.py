from __future__ import annotations

import json
from pathlib import Path

from src.learning.distributed_feedback import LocalBackend, aggregate_feedback


class FakeBackend:
    def __init__(self, *, rank: int, world_size: int, global_positive: float, global_negative: float):
        self._rank = rank
        self._world_size = world_size
        self._global_positive = global_positive
        self._global_negative = global_negative

    def get_rank(self) -> int:
        return self._rank

    def get_world_size(self) -> int:
        return self._world_size

    def all_reduce_sum_pair(self, positive: float, negative: float) -> tuple[float, float]:
        _ = positive, negative
        return self._global_positive, self._global_negative


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_aggregate_feedback_single_process_applies_once(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude" / "memory" / "feedback").mkdir(parents=True)

    first = aggregate_feedback(
        project_root=project,
        event_key="evt-1",
        feedback_type="positive",
        context="pytest workflow fix",
        backend=LocalBackend(),
    )
    second = aggregate_feedback(
        project_root=project,
        event_key="evt-1",
        feedback_type="positive",
        context="pytest workflow fix",
        backend=LocalBackend(),
    )

    assert first["applied"] is True
    assert second["applied"] is False
    assert second["skipped_reason"] == "duplicate_event"

    model = _read_json(project / "models" / "ml" / "feedback_model.json")
    assert model["alpha"] == 2.0
    assert model["beta"] == 1.0
    assert model["feature_weights"]["test"] > 0
    assert model["feature_weights"]["ci"] > 0

    stats = _read_json(project / "data" / "feedback" / "stats.json")
    assert stats["positive"] == 1
    assert stats["negative"] == 0
    assert stats["total"] == 1


def test_aggregate_feedback_distributed_rank_zero_applies_global_sum(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude" / "memory" / "feedback").mkdir(parents=True)
    backend = FakeBackend(rank=0, world_size=4, global_positive=3.0, global_negative=1.0)

    outcome = aggregate_feedback(
        project_root=project,
        event_key="evt-dist",
        feedback_type="positive",
        context="trade backtest analysis",
        backend=backend,
    )

    assert outcome["distributed"] is True
    assert outcome["applied"] is True
    assert outcome["global_positive"] == 3.0
    assert outcome["global_negative"] == 1.0

    model = _read_json(project / "models" / "ml" / "feedback_model.json")
    assert model["alpha"] == 4.0
    assert model["beta"] == 2.0

    stats = _read_json(project / "data" / "feedback" / "stats.json")
    assert stats["positive"] == 3
    assert stats["negative"] == 1
    assert stats["total"] == 4


def test_aggregate_feedback_distributed_non_zero_rank_no_file_writes(tmp_path: Path) -> None:
    project = tmp_path / "project"
    (project / ".claude" / "memory" / "feedback").mkdir(parents=True)
    backend = FakeBackend(rank=2, world_size=4, global_positive=2.0, global_negative=2.0)

    outcome = aggregate_feedback(
        project_root=project,
        event_key="evt-nonzero",
        feedback_type="negative",
        context="debug logs",
        backend=backend,
    )

    assert outcome["applied"] is False
    assert outcome["skipped_reason"] == "non_zero_rank"
    assert not (project / "models" / "ml" / "feedback_model.json").exists()
    assert not (project / "data" / "feedback" / "stats.json").exists()

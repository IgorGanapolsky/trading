"""Distributed Thompson feedback aggregation with rank-0 atomic apply.

This module provides a safe bridge between per-worker feedback events and a
single source of truth for global bandit stats/model files.

Design goals:
- Works in single-process mode with no PyTorch dependency.
- Uses torch.distributed all_reduce when available/initialized.
- Applies model/stats updates once on rank 0 with event-key idempotency.
- Keeps writes atomic and lock-protected to prevent race conditions.
"""

from __future__ import annotations

import json
import os
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

try:
    import fcntl
except ImportError:  # pragma: no cover
    fcntl = None


DEFAULT_CATEGORIES: dict[str, dict[str, float | int]] = {
    "test": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "ci": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "trade": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "pr": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "refactor": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "analysis": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "log_parsing": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "system_health": {"alpha": 1.0, "beta": 1.0, "count": 0},
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class DistBackend(Protocol):
    def get_rank(self) -> int: ...

    def get_world_size(self) -> int: ...

    def all_reduce_sum_pair(self, positive: float, negative: float) -> tuple[float, float]: ...


@dataclass(frozen=True)
class LocalBackend:
    @staticmethod
    def _env_int(name: str, default: int) -> int:
        raw = os.getenv(name)
        if raw is None:
            return default
        try:
            return int(raw)
        except (TypeError, ValueError):
            return default

    def get_rank(self) -> int:
        return self._env_int("RANK", 0)

    def get_world_size(self) -> int:
        return max(1, self._env_int("WORLD_SIZE", 1))

    def all_reduce_sum_pair(self, positive: float, negative: float) -> tuple[float, float]:
        return positive, negative


class TorchDistBackend:
    """Thin adapter around torch.distributed for all_reduce operations."""

    def __init__(self, *, force_enable: bool = False) -> None:
        self._dist: Any | None = None
        self._torch: Any | None = None
        try:
            import torch
            import torch.distributed as dist
        except ImportError:
            return

        if not force_enable and not dist.is_initialized():
            return

        self._dist = dist
        self._torch = torch

    def is_ready(self) -> bool:
        return self._dist is not None and self._torch is not None

    def get_rank(self) -> int:
        if not self.is_ready():
            return 0
        return int(self._dist.get_rank())

    def get_world_size(self) -> int:
        if not self.is_ready():
            return 1
        return int(self._dist.get_world_size())

    def all_reduce_sum_pair(self, positive: float, negative: float) -> tuple[float, float]:
        if not self.is_ready():
            return positive, negative
        tensor = self._torch.tensor([positive, negative], dtype=self._torch.float64)
        self._dist.all_reduce(tensor, op=self._dist.ReduceOp.SUM)
        return float(tensor[0].item()), float(tensor[1].item())


def default_backend() -> DistBackend:
    backend = TorchDistBackend()
    if backend.is_ready():
        return backend
    return LocalBackend()


@dataclass(frozen=True)
class DistributedFeedbackPaths:
    project_root: Path
    model_file: Path
    stats_file: Path
    state_file: Path
    ledger_file: Path
    lock_file: Path


def build_paths(project_root: Path) -> DistributedFeedbackPaths:
    memory_feedback = project_root / ".claude" / "memory" / "feedback"
    return DistributedFeedbackPaths(
        project_root=project_root,
        model_file=project_root / "models" / "ml" / "feedback_model.json",
        stats_file=project_root / "data" / "feedback" / "stats.json",
        state_file=memory_feedback / "distributed_feedback_state.json",
        ledger_file=memory_feedback / "distributed_feedback_ledger.jsonl",
        lock_file=memory_feedback / "distributed_feedback.lock",
    )


def _load_json(path: Path, fallback: dict[str, Any]) -> dict[str, Any]:
    if not path.exists():
        return dict(fallback)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return dict(fallback)
    if isinstance(raw, dict):
        return raw
    return dict(fallback)


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    tmp_path.replace(path)


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


@contextmanager
def _exclusive_lock(lock_file: Path):
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    with lock_file.open("a+", encoding="utf-8") as handle:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            if fcntl is not None:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _extract_features(context: str) -> list[str]:
    rules = {
        "test": r"test|pytest|unittest",
        "ci": r"ci|workflow|action",
        "fix": r"bug|fix|error|issue",
        "trade": r"trade|order|position",
        "entry": r"entry|exit|close",
        "rag": r"rag|lesson|learn",
        "pr": r"pr|merge|branch",
        "refactor": r"refactor|clean|improve",
        "analysis": r"analys|research|backtest",
        "log_parsing": r"log|parse|output",
        "system_health": r"health|system|check|monitor",
    }
    text = (context or "").lower()
    features: list[str] = []
    for feature, pattern in rules.items():
        if re.search(pattern, text):
            features.append(feature)
    return features


def _apply_model_update(
    model_file: Path,
    *,
    global_positive: float,
    global_negative: float,
    context: str,
) -> dict[str, Any]:
    default_model = {
        "alpha": 1.0,
        "beta": 1.0,
        "feature_weights": {},
        "per_category": json.loads(json.dumps(DEFAULT_CATEGORIES)),
        "last_updated": None,
    }
    model = _load_json(model_file, default_model)
    if "feature_weights" not in model or not isinstance(model["feature_weights"], dict):
        model["feature_weights"] = {}
    if "per_category" not in model or not isinstance(model["per_category"], dict):
        model["per_category"] = json.loads(json.dumps(DEFAULT_CATEGORIES))

    model["alpha"] = float(model.get("alpha", 1.0)) + float(global_positive)
    model["beta"] = float(model.get("beta", 1.0)) + float(global_negative)

    features = _extract_features(context)
    weight_delta = (0.1 * float(global_positive)) - (0.1 * float(global_negative))
    total_delta = int(round(float(global_positive) + float(global_negative)))
    per_category = model["per_category"]

    for feature in features:
        current = float(model["feature_weights"].get(feature, 0.0))
        model["feature_weights"][feature] = round(current + weight_delta, 4)
        if feature not in per_category:
            per_category[feature] = {"alpha": 1.0, "beta": 1.0, "count": 0}
        per_category[feature]["alpha"] = float(per_category[feature].get("alpha", 1.0)) + float(
            global_positive
        )
        per_category[feature]["beta"] = float(per_category[feature].get("beta", 1.0)) + float(
            global_negative
        )
        per_category[feature]["count"] = int(per_category[feature].get("count", 0)) + total_delta

    model["last_updated"] = _now_iso()
    _atomic_write_json(model_file, model)
    return model


def _apply_stats_update(
    stats_file: Path,
    *,
    global_positive: float,
    global_negative: float,
    feedback_type: str,
) -> dict[str, Any]:
    default_stats = {
        "positive": 0,
        "negative": 0,
        "total": 0,
        "last_feedback": None,
        "last_updated": None,
        "satisfaction_rate": 0.0,
    }
    stats = _load_json(stats_file, default_stats)
    pos_inc = int(round(float(global_positive)))
    neg_inc = int(round(float(global_negative)))
    stats["positive"] = int(stats.get("positive", 0)) + pos_inc
    stats["negative"] = int(stats.get("negative", 0)) + neg_inc
    stats["total"] = int(stats.get("positive", 0)) + int(stats.get("negative", 0))
    stats["last_feedback"] = feedback_type
    stats["last_updated"] = _now_iso()
    total = int(stats["total"])
    stats["satisfaction_rate"] = round((stats["positive"] / total) * 100.0, 2) if total > 0 else 0.0
    _atomic_write_json(stats_file, stats)
    return stats


def aggregate_feedback(
    *,
    project_root: Path,
    event_key: str,
    feedback_type: str,
    context: str,
    backend: DistBackend | None = None,
) -> dict[str, Any]:
    """Aggregate worker deltas and atomically apply model/stats once on rank 0."""
    selected_backend = backend or default_backend()
    rank = int(selected_backend.get_rank())
    world_size = int(selected_backend.get_world_size())
    distributed = world_size > 1

    local_positive = 1.0 if feedback_type == "positive" else 0.0
    local_negative = 1.0 if feedback_type == "negative" else 0.0
    global_positive, global_negative = selected_backend.all_reduce_sum_pair(
        local_positive, local_negative
    )

    outcome = {
        "timestamp": _now_iso(),
        "event_key": event_key,
        "feedback_type": feedback_type,
        "rank": rank,
        "world_size": world_size,
        "distributed": distributed,
        "local_positive": local_positive,
        "local_negative": local_negative,
        "global_positive": global_positive,
        "global_negative": global_negative,
        "applied": False,
        "skipped_reason": None,
    }

    if rank != 0:
        outcome["skipped_reason"] = "non_zero_rank"
        return outcome

    paths = build_paths(project_root)
    with _exclusive_lock(paths.lock_file):
        state = _load_json(paths.state_file, {"recent_event_keys": []})
        recent = state.get("recent_event_keys", [])
        if not isinstance(recent, list):
            recent = []
        if event_key in recent:
            outcome["skipped_reason"] = "duplicate_event"
            state["last_outcome"] = outcome
            state["last_updated"] = _now_iso()
            _atomic_write_json(paths.state_file, state)
            _append_jsonl(paths.ledger_file, outcome)
            return outcome

        model = _apply_model_update(
            paths.model_file,
            global_positive=global_positive,
            global_negative=global_negative,
            context=context,
        )
        stats = _apply_stats_update(
            paths.stats_file,
            global_positive=global_positive,
            global_negative=global_negative,
            feedback_type=feedback_type,
        )

        outcome["applied"] = True
        outcome["model_alpha"] = float(model.get("alpha", 1.0))
        outcome["model_beta"] = float(model.get("beta", 1.0))
        outcome["stats_total"] = int(stats.get("total", 0))

        recent.append(event_key)
        state["recent_event_keys"] = recent[-4000:]
        state["last_outcome"] = outcome
        state["last_updated"] = _now_iso()
        _atomic_write_json(paths.state_file, state)
        _append_jsonl(paths.ledger_file, outcome)

    return outcome

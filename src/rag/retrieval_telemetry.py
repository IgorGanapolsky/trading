"""Retrieval score telemetry for production observability.

Writes JSONL events for retrieval queries: scores, mode, latency, empty hits.
Does not log full document bodies (avoid secret/lesson dump).
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
_DEFAULT_PATH = Path("data/telemetry/retrieval_events.jsonl")


@dataclass
class RetrievalEvent:
    query_hash: str
    top_k: int
    hit_count: int
    top_score: float
    top_ids: list[str] = field(default_factory=list)
    mode: str = "advisory"
    latency_ms: float = 0.0
    index_size: int | None = None
    empty_index: bool = False
    ood: bool = False
    cache_hit: bool = False
    gate_severity: str | None = None
    gate_approved: bool | None = None
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _hash_query(query: str) -> str:
    # Stable short hash without storing raw query (may contain account notes).
    import hashlib

    return hashlib.sha256((query or "").strip().lower().encode("utf-8")).hexdigest()[:16]


def record_retrieval_event(
    *,
    query: str,
    hit_count: int,
    top_score: float,
    top_ids: list[str] | None = None,
    top_k: int = 5,
    mode: str = "advisory",
    latency_ms: float = 0.0,
    index_size: int | None = None,
    empty_index: bool = False,
    ood: bool = False,
    cache_hit: bool = False,
    gate_severity: str | None = None,
    gate_approved: bool | None = None,
    log_path: Path | None = None,
) -> RetrievalEvent:
    event = RetrievalEvent(
        query_hash=_hash_query(query),
        top_k=top_k,
        hit_count=hit_count,
        top_score=float(top_score or 0.0),
        top_ids=list(top_ids or [])[:10],
        mode=mode,
        latency_ms=round(float(latency_ms), 2),
        index_size=index_size,
        empty_index=empty_index,
        ood=ood,
        cache_hit=cache_hit,
        gate_severity=gate_severity,
        gate_approved=gate_approved,
    )
    path = log_path or _DEFAULT_PATH
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with _LOCK:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(event.to_dict()) + "\n")
    except OSError:
        pass
    return event

"""Retrieval / generation observability for trading RAG.

Emits structured traces (JSONL) without shipping secrets. Used by retrieve path
and verify_rag_aplus gates.
"""

from __future__ import annotations

import json
import os
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

_LOCK = threading.Lock()
DEFAULT_TRACE_PATH = Path(os.getenv("RAG_TRACE_PATH", "data/audit/rag_retrieval_traces.jsonl"))


@dataclass
class RetrievalTrace:
    trace_id: str
    query: str
    principal: str
    started_at: str
    latency_ms: float = 0.0
    strategy: str = ""
    stages: list[str] = field(default_factory=list)
    fts_hits: int = 0
    hybrid_pool: int = 0
    variants: list[str] = field(default_factory=list)
    top_scores: list[float] = field(default_factory=list)
    top_ids: list[str] = field(default_factory=list)
    acl_dropped: int = 0
    token_estimate: int = 0
    cache_hit: bool = False
    error: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def new_trace(query: str, principal: str = "operator") -> RetrievalTrace:
    return RetrievalTrace(
        trace_id=uuid.uuid4().hex[:16],
        query=(query or "")[:500],
        principal=principal,
        started_at=datetime.now(UTC).isoformat(),
    )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, (len(text) + 3) // 4)


def finish_trace(trace: RetrievalTrace, *, t0: float) -> RetrievalTrace:
    trace.latency_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    return trace


def emit_trace(trace: RetrievalTrace, path: Path | None = None) -> None:
    """Append one JSON line. Never raises into the retrieve path."""
    out = path or DEFAULT_TRACE_PATH
    try:
        out.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(trace.to_dict(), default=str, separators=(",", ":"))
        with _LOCK:
            with out.open("a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except OSError:
        pass


def summarize_traces(path: Path | None = None, *, limit: int = 200) -> dict[str, Any]:
    p = path or DEFAULT_TRACE_PATH
    if not p.exists():
        return {"count": 0, "avg_latency_ms": 0.0, "cache_hit_rate": 0.0}
    rows: list[dict[str, Any]] = []
    try:
        lines = p.read_text(encoding="utf-8").splitlines()[-limit:]
        for line in lines:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        return {"count": 0, "avg_latency_ms": 0.0, "cache_hit_rate": 0.0}
    if not rows:
        return {"count": 0, "avg_latency_ms": 0.0, "cache_hit_rate": 0.0}
    lat = [float(r.get("latency_ms") or 0) for r in rows]
    hits = sum(1 for r in rows if r.get("cache_hit"))
    return {
        "count": len(rows),
        "avg_latency_ms": round(sum(lat) / len(lat), 3),
        "p95_latency_ms": round(sorted(lat)[max(0, int(len(lat) * 0.95) - 1)], 3),
        "cache_hit_rate": round(hits / len(rows), 4),
        "errors": sum(1 for r in rows if r.get("error")),
    }

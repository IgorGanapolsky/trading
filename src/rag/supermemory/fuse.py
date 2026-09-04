"""Fuse local RAG hits with SuperMemory v4 results. Local ledgers stay edge truth."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from src.rag.supermemory.contract import route_query

RRF_K = 60.0
DEFAULT_TOP_N = 12


def _hit_text(item: Mapping[str, Any]) -> str:
    for key in ("memory", "chunk", "content", "snippet", "title", "text"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def normalize_supermemory_results(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    """Map official v4 results onto a stable local shape."""
    if not payload:
        return []
    rows = payload.get("results")
    if not isinstance(rows, list):
        return []
    out: list[dict[str, Any]] = []
    for raw in rows:
        if not isinstance(raw, dict):
            continue
        text = _hit_text(raw)
        if not text:
            continue
        out.append(
            {
                "id": str(raw.get("id") or ""),
                "text": text,
                "similarity": float(raw.get("similarity") or 0.0),
                "source": "supermemory",
                "not_edge_evidence": True,
                "metadata": raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {},
            }
        )
    return out


def fuse_local_with_supermemory(
    query: str,
    local_hits: Sequence[Mapping[str, Any]],
    supermemory_payload: Mapping[str, Any] | None,
    *,
    top_n: int = DEFAULT_TOP_N,
) -> dict[str, Any]:
    """RRF-merge local lessons with SuperMemory. Edge questions stay local."""
    route = route_query(query)
    local = [dict(hit) | {"source": hit.get("source") or "local_rag"} for hit in local_hits]
    remote = normalize_supermemory_results(supermemory_payload)
    use_remote = route != "local_ledger" and bool(remote)

    scores: dict[str, float] = {}
    records: dict[str, dict[str, Any]] = {}

    def _add(key: str, rank: int, record: dict[str, Any]) -> None:
        scores[key] = scores.get(key, 0.0) + (1.0 / (RRF_K + rank))
        records.setdefault(key, record)

    for rank, hit in enumerate(local, 1):
        key = f"local:{hit.get('id') or hit.get('title') or rank}"
        _add(key, rank, hit)

    if use_remote:
        for rank, hit in enumerate(remote, 1):
            _add(f"sm:{hit.get('id') or rank}", rank, hit)

    ranked_keys = sorted(scores, key=lambda item: scores[item], reverse=True)[:top_n]
    fused = [records[key] | {"rrf": round(scores[key], 6)} for key in ranked_keys]
    return {
        "route": route,
        "edge_source": "local_ledgers",
        "supermemory_authoritative_for_edge": False,
        "supermemory_used": use_remote,
        "local": local,
        "supermemory": remote,
        "hits": fused,
        "validity_window": None,
    }

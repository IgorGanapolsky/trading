"""Always fuse search hits with bounded Graphify traversal (1–2 hops + RRF)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping, Sequence

from src.rag.graphify.contract import is_html_visualization
from src.rag.graphify.graph import CodeGraph

RRF_K = 60.0
DEFAULT_HOPS = 2


def fuse_hits_with_graph(
    hits: Sequence[Mapping[str, Any]],
    graph: CodeGraph | None,
    *,
    max_hops: int = DEFAULT_HOPS,
    top_n: int = 12,
) -> dict[str, Any]:
    """Merge lexical/semantic hits with graph neighbors. Never reads HTML."""
    usable_hits: list[dict[str, Any]] = []
    dropped_html: list[str] = []
    for raw in hits:
        item = dict(raw)
        path = str(item.get("file") or item.get("path") or item.get("source_file") or "")
        if path and is_html_visualization(path):
            dropped_html.append(path)
            continue
        usable_hits.append(item)

    if graph is None:
        return {
            "graph_used": False,
            "reason": "graph.json missing",
            "hits": usable_hits[:top_n],
            "graph_nodes": [],
            "graph_edges": [],
            "dropped_html": dropped_html,
            "validity_window": None,
        }

    scores: dict[str, float] = {}
    records: dict[str, dict[str, Any]] = {}

    def _add(key: str, rank: int, record: dict[str, Any]) -> None:
        scores[key] = scores.get(key, 0.0) + (1.0 / (RRF_K + rank))
        records.setdefault(key, record)

    for rank, hit in enumerate(usable_hits, 1):
        key = str(hit.get("id") or hit.get("file") or hit.get("path") or f"hit_{rank}")
        _add(f"hit:{key}", rank, {"kind": "search", **hit})

    seeds: list[str] = []
    for hit in usable_hits:
        needles = [
            str(hit.get("id") or ""),
            str(hit.get("title") or ""),
            Path(str(hit.get("file") or hit.get("path") or "")).stem,
            Path(str(hit.get("file") or hit.get("path") or "")).name,
        ]
        for needle in needles:
            if not needle:
                continue
            for node in graph.match_nodes(needle):
                if node.id not in seeds:
                    seeds.append(node.id)

    graph_edges: list[dict[str, Any]] = []
    graph_nodes: list[dict[str, Any]] = []
    seen_nodes: set[str] = set()
    seen_edges: set[tuple[str, str, str, str]] = set()
    for seed in seeds:
        if seed in graph.nodes and seed not in seen_nodes:
            seen_nodes.add(seed)
            graph_nodes.append(graph.nodes[seed].to_dict())
        for rank, edge in enumerate(graph.neighbors(seed, max_hops=max_hops), 1):
            key = (edge.source, edge.target, edge.relation, edge.confidence)
            if key not in seen_edges:
                seen_edges.add(key)
                graph_edges.append(edge.to_dict())
            _add(
                f"edge:{edge.source}:{edge.target}:{edge.relation}",
                rank,
                {"kind": "graph", **edge.to_dict()},
            )
            for endpoint in (edge.source, edge.target):
                if endpoint in graph.nodes and endpoint not in seen_nodes:
                    seen_nodes.add(endpoint)
                    graph_nodes.append(graph.nodes[endpoint].to_dict())

    ranked = sorted(scores, key=lambda item: scores[item], reverse=True)[:top_n]
    return {
        "graph_used": True,
        "max_hops": max_hops,
        "hits": usable_hits,
        "fused": [records[key] | {"rrf": round(scores[key], 6)} for key in ranked],
        "graph_nodes": graph_nodes,
        "graph_edges": graph_edges,
        "dropped_html": dropped_html,
        "seeds": seeds,
        "validity_window": None,
        "note": "Graphify AST edges have no validity window",
    }

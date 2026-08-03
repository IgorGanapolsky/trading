"""Hybrid graph + optional vector fusion retrieval."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from src.rag.graph.router import QueryIntent, RouteDecision, route_query
from src.rag.graph.store import FinancialGraphStore, GraphNode, GraphPath, adjacency_summary

logger = logging.getLogger(__name__)

VectorSearchFn = Callable[[str, int], list[dict[str, Any]]]


@dataclass
class HybridRetrievalResult:
    query: str
    route: RouteDecision
    seeds: list[str]
    paths: list[GraphPath]
    nodes: list[GraphNode]
    vector_hits: list[dict[str, Any]] = field(default_factory=list)
    latency_ms: float = 0.0
    graph_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "route": self.route.to_dict(),
            "seeds": self.seeds,
            "paths": [p.to_dict() for p in self.paths],
            "nodes": [n.to_dict() for n in self.nodes],
            "vector_hits": self.vector_hits,
            "latency_ms": self.latency_ms,
            "graph_only": self.graph_only,
        }


def _default_vector_search(query: str, top_k: int) -> list[dict[str, Any]]:
    """Best-effort fusion with existing LessonsLearnedRAG / pipeline."""
    try:
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        results = rag.search(query, top_k=top_k)
        hits: list[dict[str, Any]] = []
        for item in results or []:
            # Support (LessonResult, score) or LessonResult-like objects
            score = 0.0
            obj = item
            if isinstance(item, tuple) and len(item) >= 1:
                obj = item[0]
                if len(item) > 1:
                    try:
                        score = float(item[1])
                    except (TypeError, ValueError):
                        score = 0.0
            if isinstance(obj, dict):
                hits.append({**obj, "score": obj.get("score", score)})
                continue
            hits.append(
                {
                    "id": getattr(obj, "id", None) or getattr(obj, "lesson_id", None) or "",
                    "title": getattr(obj, "title", "") or "",
                    "snippet": getattr(obj, "snippet", "")
                    or getattr(obj, "content", "")
                    or "",
                    "prevention": getattr(obj, "prevention", "") or "",
                    "severity": getattr(obj, "severity", "") or "",
                    "file": getattr(obj, "file", "") or "",
                    "score": float(getattr(obj, "score", score) or score),
                }
            )
        return hits
    except Exception as exc:  # noqa: BLE001 — fusion is optional
        logger.debug("Vector fusion unavailable: %s", exc)
        return []


class GraphHybridRetriever:
    """Execute routed graph pathfinding + optional lesson vector fusion."""

    def __init__(
        self,
        store: FinancialGraphStore,
        vector_search: Optional[VectorSearchFn] = None,
    ):
        self.store = store
        self.vector_search = vector_search

    def retrieve(
        self,
        query: str,
        *,
        route: RouteDecision | None = None,
        top_k_paths: int = 20,
        top_k_vector: int = 5,
        as_of: str | None = None,
        force_graph_only: bool = False,
    ) -> HybridRetrievalResult:
        t0 = time.perf_counter()
        decision = route or route_query(query)
        seeds = self._resolve_seeds(decision.seed_hints, query)
        if not seeds:
            seeds = ["strategy:spy_put_credit"]

        paths = self.store.bfs_paths(
            seeds,
            max_hops=decision.max_hops,
            max_paths=top_k_paths,
            as_of=as_of,
            prefer_rels=decision.prefer_rels,
        )

        # Collect unique nodes from seeds + paths
        node_ids: list[str] = []
        seen: set[str] = set()
        for s in seeds:
            if s not in seen:
                seen.add(s)
                node_ids.append(s)
        for path in paths:
            for nid in path.node_ids:
                if nid not in seen:
                    seen.add(nid)
                    node_ids.append(nid)

        nodes: list[GraphNode] = []
        for nid in node_ids:
            n = self.store.get_node(nid)
            if n:
                nodes.append(n)
            else:
                # text search fallback for unresolved seeds
                for hit in self.store.search_nodes(nid.split(":")[-1], limit=3):
                    if hit.id not in seen:
                        seen.add(hit.id)
                        nodes.append(hit)

        vector_hits: list[dict[str, Any]] = []
        graph_only = force_graph_only or not decision.use_vector_fusion
        if not graph_only:
            search_fn = self.vector_search or _default_vector_search
            try:
                vector_hits = search_fn(query, top_k_vector) or []
            except Exception as exc:  # noqa: BLE001
                logger.warning("Vector search failed: %s", exc)
                vector_hits = []
                graph_only = True

        # For strategy status, boost adjacency of kill switch
        if decision.intent == QueryIntent.STRATEGY_STATUS:
            for extra in (
                "macro:strategy_kill_2026_07_22",
                "strategy:spy_put_credit",
                "strategy:iron_condor",
            ):
                if extra not in seen:
                    n = self.store.get_node(extra)
                    if n:
                        seen.add(extra)
                        nodes.append(n)

        latency_ms = (time.perf_counter() - t0) * 1000.0
        return HybridRetrievalResult(
            query=query,
            route=decision,
            seeds=seeds,
            paths=paths,
            nodes=nodes,
            vector_hits=vector_hits,
            latency_ms=latency_ms,
            graph_only=graph_only,
        )

    def _resolve_seeds(self, hints: list[str], query: str) -> list[str]:
        seeds: list[str] = []
        for h in hints:
            if self.store.get_node(h):
                seeds.append(h)
                continue
            # Try search on the bare token
            token = h.split(":")[-1]
            hits = self.store.search_nodes(token, limit=5)
            for hit in hits:
                seeds.append(hit.id)
        if not seeds:
            # Free-text search on the whole query
            for hit in self.store.search_nodes(query[:80], limit=8):
                seeds.append(hit.id)
        # de-dupe
        out: list[str] = []
        seen: set[str] = set()
        for s in seeds:
            if s not in seen:
                seen.add(s)
                out.append(s)
        return out

    def explain_node(self, node_id: str) -> dict[str, Any]:
        return adjacency_summary(self.store, node_id)

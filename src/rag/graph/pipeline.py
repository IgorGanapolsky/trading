"""Multi-stage Graph RAG execution workflow (deterministic agents).

Stages:
  1. Routing agent   — intent + seed hints
  2. Retrieval fusion — graph BFS + optional vector lessons
  3. TokenGuard      — hard context budget before synthesis
  4. Context pack    — ready for Hermes/Claude (no auto trade submit)

This never submits orders. It only produces evidence-bounded context.
"""

from __future__ import annotations

import logging
import os
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from src.rag.graph.builder import FinancialGraphBuilder
from src.rag.graph.retriever import GraphHybridRetriever, HybridRetrievalResult
from src.rag.graph.router import RouteDecision, route_query
from src.rag.graph.store import FinancialGraphStore
from src.rag.graph.token_gateway import apply_token_guard

logger = logging.getLogger(__name__)

_PIPELINE_LOCK = threading.RLock()
_PIPELINE_SINGLETON: Optional[GraphRAGPipeline] = None


@dataclass
class GraphRAGResult:
    """End-to-end Graph RAG response for a single query."""

    query: str
    allowed: bool
    context: str
    route: dict[str, Any]
    retrieval: dict[str, Any]
    token_guard: dict[str, Any]
    latency_ms: float
    graph_stats: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "query": self.query,
            "allowed": self.allowed,
            "context": self.context,
            "route": self.route,
            "retrieval": self.retrieval,
            "token_guard": self.token_guard,
            "latency_ms": self.latency_ms,
            "graph_stats": self.graph_stats,
            "warnings": self.warnings,
        }


class GraphRAGPipeline:
    """Routing → hybrid retrieval → TokenGuard context pack."""

    def __init__(
        self,
        store: FinancialGraphStore | None = None,
        repo_root: str | Path | None = None,
        *,
        auto_build_if_empty: bool = True,
        max_tokens: int = 1800,
        hard_max_tokens: int = 3200,
    ):
        self.repo_root = Path(repo_root or Path.cwd())
        self.store = store or FinancialGraphStore(
            db_path=self.repo_root / "data/rag/financial_graph.sqlite"
        )
        self.retriever = GraphHybridRetriever(self.store)
        self.auto_build_if_empty = auto_build_if_empty
        self.max_tokens = max_tokens
        self.hard_max_tokens = hard_max_tokens
        self._ensure_graph()

    def _ensure_graph(self) -> None:
        stats = self.store.stats()
        if stats.get("nodes", 0) == 0 and self.auto_build_if_empty:
            logger.info("Graph empty — running full rebuild from local ledgers")
            builder = FinancialGraphBuilder(self.store, repo_root=self.repo_root)
            builder.rebuild(clear=True)

    def rebuild(self, *, clear: bool = True) -> dict[str, Any]:
        builder = FinancialGraphBuilder(self.store, repo_root=self.repo_root)
        return builder.rebuild(clear=clear)

    def stats(self) -> dict[str, Any]:
        return self.store.stats()

    def route(self, query: str) -> RouteDecision:
        return route_query(query)

    def retrieve(self, query: str, **kwargs: Any) -> HybridRetrievalResult:
        return self.retriever.retrieve(query, **kwargs)

    def query(
        self,
        query: str,
        *,
        max_tokens: int | None = None,
        hard_max_tokens: int | None = None,
        top_k_paths: int = 20,
        top_k_vector: int = 5,
        force_graph_only: bool = False,
        as_of: str | None = None,
    ) -> GraphRAGResult:
        t0 = time.perf_counter()
        warnings: list[str] = []
        route = route_query(query)
        retrieval = self.retriever.retrieve(
            query,
            route=route,
            top_k_paths=top_k_paths,
            top_k_vector=top_k_vector,
            force_graph_only=force_graph_only,
            as_of=as_of,
        )
        if retrieval.graph_only and route.use_vector_fusion:
            warnings.append("vector_fusion_unavailable_graph_only")

        guard = apply_token_guard(
            query=query,
            intent=route.intent.value,
            route_reason=route.reason,
            paths=[p.to_dict() for p in retrieval.paths],
            nodes=[n.to_dict() for n in retrieval.nodes],
            vector_hits=retrieval.vector_hits,
            max_tokens=max_tokens or self.max_tokens,
            hard_max_tokens=hard_max_tokens or self.hard_max_tokens,
        )

        latency_ms = (time.perf_counter() - t0) * 1000.0
        # Prefer end-to-end latency; also record retrieval stage latency
        retrieval_dict = retrieval.to_dict()
        retrieval_dict["stage_latency_ms"] = retrieval.latency_ms

        return GraphRAGResult(
            query=query,
            allowed=guard.allowed,
            context=guard.context_text,
            route=route.to_dict(),
            retrieval=retrieval_dict,
            token_guard=guard.to_dict(),
            latency_ms=latency_ms,
            graph_stats=self.store.stats(),
            warnings=warnings,
        )

    def close(self) -> None:
        self.store.close()


def get_graph_rag_pipeline(
    repo_root: str | Path | None = None,
    *,
    refresh: bool = False,
) -> GraphRAGPipeline:
    """Process-wide singleton for operator scripts."""
    global _PIPELINE_SINGLETON
    with _PIPELINE_LOCK:
        if refresh and _PIPELINE_SINGLETON is not None:
            try:
                _PIPELINE_SINGLETON.close()
            except Exception as exc:  # noqa: BLE001 — best-effort singleton reset
                logger.debug("graph pipeline close during refresh failed: %s", exc)
            _PIPELINE_SINGLETON = None
        if _PIPELINE_SINGLETON is None:
            root = Path(repo_root or os.getenv("TRADING_REPO_ROOT") or Path.cwd())
            _PIPELINE_SINGLETON = GraphRAGPipeline(repo_root=root)
        return _PIPELINE_SINGLETON

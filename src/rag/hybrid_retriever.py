"""Hybrid RAG Retriever with Reciprocal Rank Fusion (RRF).

Combines Lexical Keyword Search (BM25/FTS), Dense Vector Search, and optional
managed ripgrep ranks using Reciprocal Rank Fusion (RRF).

zg (zvec-grep) process steal: one fusion layer for multi-route local search.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Mapping

from src.rag.query_rewriter import RAGQueryRewriter
from src.rag.rag_reranker import RAGReranker

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class HybridSearchResult:
    lesson_id: str
    title: str
    rrf_score: float
    vector_rank: int
    bm25_rank: int
    content_snippet: str
    rg_rank: int = 999
    path: str = ""
    line: int | None = None
    route: str = "hybrid"


class HybridRAGRetriever:
    """Combines BM25/FTS lexical ranking, vector search, and optional rg via RRF."""

    def __init__(self, k_rrf: float = 60.0):
        self.k_rrf = k_rrf
        self.rewriter = RAGQueryRewriter()
        self.reranker = RAGReranker()

    def rrf_merge(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        top_n: int = 5,
        rg_results: list[dict[str, Any]] | None = None,
    ) -> list[HybridSearchResult]:
        """Two/three-list merge kept for existing tests and callers."""
        out: list[HybridSearchResult] = []
        v_ranks = {
            str(item.get("id", item.get("lesson_id", f"vec_{i}"))): i
            for i, item in enumerate(vector_results, 1)
        }
        b_ranks = {
            str(item.get("id", item.get("lesson_id", f"bm25_{i}"))): i
            for i, item in enumerate(bm25_results, 1)
        }
        r_ranks = {
            str(item.get("id", item.get("lesson_id", f"rg_{i}"))): i
            for i, item in enumerate(rg_results or [], 1)
        }
        items: dict[str, dict[str, Any]] = {}
        scores: dict[str, float] = {}
        for rank, item in enumerate(vector_results, 1):
            lid = str(item.get("id", item.get("lesson_id", f"vec_{rank}")))
            scores[lid] = scores.get(lid, 0.0) + (1.0 / (self.k_rrf + rank))
            items[lid] = item
        for rank, item in enumerate(bm25_results, 1):
            lid = str(item.get("id", item.get("lesson_id", f"bm25_{rank}")))
            scores[lid] = scores.get(lid, 0.0) + (1.0 / (self.k_rrf + rank))
            if lid not in items:
                items[lid] = item
        for rank, item in enumerate(rg_results or [], 1):
            lid = str(item.get("id", item.get("lesson_id", f"rg_{rank}")))
            scores[lid] = scores.get(lid, 0.0) + (1.0 / (self.k_rrf + rank))
            if lid not in items:
                items[lid] = item

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
        for lid in sorted_ids:
            item = items[lid]
            out.append(
                HybridSearchResult(
                    lesson_id=lid,
                    title=str(item.get("title", "")),
                    rrf_score=round(scores[lid], 6),
                    vector_rank=v_ranks.get(lid, 999),
                    bm25_rank=b_ranks.get(lid, 999),
                    rg_rank=r_ranks.get(lid, 999),
                    content_snippet=str(
                        item.get("snippet", item.get("content", item.get("preview", "")))
                    )[:200],
                    path=str(item.get("path") or item.get("file") or ""),
                    line=item.get("line") if isinstance(item.get("line"), int) else None,
                    route="hybrid",
                )
            )
        return out

    def rrf_merge_multi(
        self,
        ranked_lists: Mapping[str, list[dict[str, Any]]],
        *,
        top_n: int = 10,
        weights: Mapping[str, float] | None = None,
    ) -> list[Any]:
        """Fuse arbitrary named ranked lists with RRF; returns EvidenceHit when available."""
        from src.rag.zg_local_search import EvidenceHit

        scores: dict[str, float] = {}
        items: dict[str, dict[str, Any]] = {}
        route_hits: dict[str, set[str]] = {}

        for route_name, results in ranked_lists.items():
            if not results:
                continue
            w = 1.0
            if weights and route_name in weights:
                w = float(weights[route_name]) or 1.0
            for rank, item in enumerate(results, 1):
                lid = str(item.get("id", item.get("lesson_id", f"{route_name}_{rank}")))
                scores[lid] = scores.get(lid, 0.0) + w / (self.k_rrf + rank)
                if lid not in items:
                    items[lid] = dict(item)
                    items[lid].setdefault("route", route_name)
                route_hits.setdefault(lid, set()).add(route_name)

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
        merged: list[EvidenceHit] = []
        for lid in sorted_ids:
            item = items[lid]
            routes = sorted(route_hits.get(lid, set()))
            route_label = "+".join(routes) if routes else "hybrid"
            line_raw = item.get("line")
            line = line_raw if isinstance(line_raw, int) else None
            merged.append(
                EvidenceHit(
                    id=lid,
                    path=str(item.get("path") or item.get("file") or lid),
                    line=line,
                    preview=str(
                        item.get("preview")
                        or item.get("snippet")
                        or item.get("content")
                        or ""
                    )[:500],
                    score=round(scores[lid], 6),
                    route=route_label,
                    title=str(item.get("title", "")),
                    metadata=dict(item.get("metadata") or {}),
                )
            )
        return merged

    @staticmethod
    def format_compact_evidence(results: list[HybridSearchResult]) -> str:
        """zg-style compact evidence lines for agent context."""
        if not results:
            return "(no hits)"
        lines: list[str] = []
        for r in results:
            loc = f"{r.path}:{r.line}" if r.path and r.line else (r.path or r.lesson_id)
            preview = r.content_snippet.replace("\n", " ").strip()
            if len(preview) > 160:
                preview = preview[:157] + "..."
            title = f" {r.title}" if r.title else ""
            lines.append(f"[hybrid {r.rrf_score:.4f}] {loc}{title} — {preview}")
        return "\n".join(lines)

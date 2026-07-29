"""Hybrid RAG Retriever with Reciprocal Rank Fusion (RRF).

Combines Lexical Keyword Search (BM25) and Dense Vector Search (LanceDB)
using Reciprocal Rank Fusion (RRF) to maximize recall and precision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

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


class HybridRAGRetriever:
    """Combines BM25 lexical keyword ranking and vector search via RRF."""

    def __init__(self, k_rrf: float = 60.0):
        self.k_rrf = k_rrf
        self.rewriter = RAGQueryRewriter()
        self.reranker = RAGReranker()

    def rrf_merge(
        self,
        vector_results: list[dict[str, Any]],
        bm25_results: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[HybridSearchResult]:
        scores: dict[str, float] = {}
        items: dict[str, dict[str, Any]] = {}
        v_ranks: dict[str, int] = {}
        b_ranks: dict[str, int] = {}

        for rank, item in enumerate(vector_results, 1):
            lid = str(item.get("id", item.get("lesson_id", f"vec_{rank}")))
            scores[lid] = scores.get(lid, 0.0) + (1.0 / (self.k_rrf + rank))
            items[lid] = item
            v_ranks[lid] = rank

        for rank, item in enumerate(bm25_results, 1):
            lid = str(item.get("id", item.get("lesson_id", f"bm25_{rank}")))
            scores[lid] = scores.get(lid, 0.0) + (1.0 / (self.k_rrf + rank))
            if lid not in items:
                items[lid] = item
            b_ranks[lid] = rank

        sorted_ids = sorted(scores.keys(), key=lambda x: scores[x], reverse=True)[:top_n]
        merged: list[HybridSearchResult] = []

        for lid in sorted_ids:
            item = items[lid]
            merged.append(
                HybridSearchResult(
                    lesson_id=lid,
                    title=str(item.get("title", "")),
                    rrf_score=round(scores[lid], 6),
                    vector_rank=v_ranks.get(lid, 999),
                    bm25_rank=b_ranks.get(lid, 999),
                    content_snippet=str(item.get("snippet", item.get("content", "")))[:200],
                )
            )

        return merged

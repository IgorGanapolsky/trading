"""Agentic RAG Reranker for High-Precision Lesson Retrieval.

Re-scores vector search candidate results using domain keyword weighting and term overlap scoring
to ensure trade safety rules and risk gates are retrieved with top precision.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankedLesson:
    lesson_id: str
    title: str
    original_score: float
    reranked_score: float
    content_snippet: str


class RAGReranker:
    """Re-ranks vector search candidate lessons to boost precision for agentic queries."""

    def __init__(self, high_priority_keywords: list[str] | None = None):
        self.high_priority_keywords = high_priority_keywords or [
            "drawdown",
            "circuit breaker",
            "bogleheads",
            "section 1256",
            "safety buffer",
            "200-dma",
            "stop loss",
        ]

    def rerank(
        self,
        query: str,
        candidates: list[dict[str, Any]],
        top_n: int = 5,
    ) -> list[RerankedLesson]:
        if not candidates:
            return []

        query_words = set(query.lower().split())
        reranked = []

        for item in candidates:
            lesson_id = str(item.get("id", item.get("lesson_id", "N/A")))
            title = str(item.get("title", ""))
            content = str(item.get("content", item.get("snippet", "")))
            orig_score = float(item.get("score", 0.5))

            text_lower = (title + " " + content).lower()
            overlap_score = sum(1 for w in query_words if w in text_lower) * 0.15

            priority_boost = 0.0
            for kw in self.high_priority_keywords:
                if kw in text_lower:
                    priority_boost += 0.2

            final_score = orig_score + overlap_score + priority_boost
            snippet = content[:300] if content else title

            reranked.append(
                RerankedLesson(
                    lesson_id=lesson_id,
                    title=title,
                    original_score=round(orig_score, 4),
                    reranked_score=round(final_score, 4),
                    content_snippet=snippet,
                )
            )

        reranked.sort(key=lambda x: x.reranked_score, reverse=True)
        return reranked[:top_n]

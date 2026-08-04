"""Dependency-light answer quality evaluation for generated RAG responses.

Retrieval metrics cannot detect a generator that ignores context or invents a
profit claim.  This module scores the answer layer separately and is suitable
for deterministic CI mutation tests.  Optional model-based judges can be added
as diagnostics, but these scores remain the fail-closed regression gate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Sequence

from src.rag.embedding_backend import EmbeddingBackend, cosine_similarity

_WORD_RE = re.compile(r"[a-z0-9]+(?:[.-][a-z0-9]+)?")
_CLAIM_SPLIT_RE = re.compile(r"(?<=[.!?])\s+|\n+")
_CITATION_RE = re.compile(r"\[(?P<citation>(?:LL[-_][A-Za-z0-9_-]+)|\d+)\]", re.IGNORECASE)
_STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "because",
    "by",
    "for",
    "from",
    "has",
    "have",
    "how",
    "if",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "our",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "we",
    "were",
    "what",
    "when",
    "which",
    "with",
    "would",
    "you",
    "your",
}


def _tokens(text: str) -> set[str]:
    return {
        token
        for token in _WORD_RE.findall(text.lower())
        if len(token) > 2 and token not in _STOPWORDS
    }


def _normalize_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _context_content(context: str | dict[str, Any]) -> str:
    if isinstance(context, str):
        return context
    return " ".join(
        str(context.get(key, ""))
        for key in ("title", "snippet", "content", "prevention")
        if context.get(key)
    )


def _context_id(context: str | dict[str, Any], index: int) -> str:
    if isinstance(context, dict):
        value = context.get("id") or context.get("lesson_id") or context.get("source")
        if value:
            return str(value)
    return str(index + 1)


@dataclass(frozen=True)
class ClaimSupport:
    claim: str
    best_context_id: str | None
    lexical_support: float
    dense_support: float
    support_score: float
    supported: bool


@dataclass(frozen=True)
class AnswerQualityScore:
    faithfulness: float
    groundedness: float
    answer_relevance: float
    citation_precision: float
    citation_coverage: float
    unsupported_claims: tuple[str, ...]
    claim_support: tuple[ClaimSupport, ...]
    passed: bool


class RAGAnswerEvaluator:
    """Score claim support, source grounding, and query relevance separately."""

    def __init__(
        self,
        embedding_backend: EmbeddingBackend | None = None,
        *,
        support_threshold: float = 0.48,
        quality_threshold: float = 0.80,
    ) -> None:
        self.embedding_backend = embedding_backend or EmbeddingBackend(backend="feature-hash")
        self.support_threshold = support_threshold
        self.quality_threshold = quality_threshold

    @staticmethod
    def _claims(answer: str) -> list[str]:
        claims = []
        for part in _CLAIM_SPLIT_RE.split(answer.strip()):
            cleaned = _CITATION_RE.sub("", part).strip(" -*\t")
            if len(_tokens(cleaned)) >= 2:
                claims.append(cleaned)
        return claims

    def _support_claim(
        self,
        claim: str,
        contexts: Sequence[str | dict[str, Any]],
    ) -> ClaimSupport:
        claim_tokens = _tokens(claim)
        claim_vector = self.embedding_backend.encode_query(claim)
        best_id: str | None = None
        best_lexical = 0.0
        best_dense = 0.0
        best_score = 0.0

        for index, context in enumerate(contexts):
            content = _context_content(context)
            context_tokens = _tokens(content)
            lexical = (
                len(claim_tokens & context_tokens) / len(claim_tokens) if claim_tokens else 0.0
            )
            context_vector = self.embedding_backend.encode_passages([content])[0]
            dense = cosine_similarity(claim_vector, context_vector)
            score = (0.72 * lexical) + (0.28 * dense)
            if score > best_score:
                best_id = _context_id(context, index)
                best_lexical = lexical
                best_dense = dense
                best_score = score

        return ClaimSupport(
            claim=claim,
            best_context_id=best_id,
            lexical_support=round(best_lexical, 4),
            dense_support=round(best_dense, 4),
            support_score=round(best_score, 4),
            supported=best_score >= self.support_threshold,
        )

    @staticmethod
    def _citation_scores(
        answer: str,
        contexts: Sequence[str | dict[str, Any]],
        claim_count: int,
    ) -> tuple[float, float]:
        citations = [match.group("citation") for match in _CITATION_RE.finditer(answer)]
        if not citations:
            return 0.0, 0.0
        valid_ids = {
            _normalize_id(_context_id(context, index)) for index, context in enumerate(contexts)
        }
        valid = sum(1 for citation in citations if _normalize_id(citation) in valid_ids)
        precision = valid / len(citations)
        coverage = min(valid / max(claim_count, 1), 1.0)
        return precision, coverage

    def evaluate(
        self,
        *,
        query: str,
        answer: str,
        contexts: Sequence[str | dict[str, Any]],
    ) -> AnswerQualityScore:
        claims = self._claims(answer)
        supports = tuple(self._support_claim(claim, contexts) for claim in claims)

        if supports:
            faithfulness = sum(1 for support in supports if support.supported) / len(supports)
            mean_support = sum(support.support_score for support in supports) / len(supports)
        else:
            faithfulness = 0.0
            mean_support = 0.0

        citation_precision, citation_coverage = self._citation_scores(answer, contexts, len(claims))
        # Groundedness demands both semantic/lexical support and attributable sources.
        # Missing citations are not fatal for internal gate text, but they cannot earn A+.
        groundedness = (
            (0.70 * mean_support) + (0.20 * citation_precision) + (0.10 * citation_coverage)
        )

        query_tokens = _tokens(query)
        answer_tokens = _tokens(answer)
        query_coverage = (
            len(query_tokens & answer_tokens) / len(query_tokens) if query_tokens else 0.0
        )
        query_vector = self.embedding_backend.encode_query(query)
        answer_vector = self.embedding_backend.encode_passages([answer])[0]
        dense_relevance = cosine_similarity(query_vector, answer_vector)
        answer_relevance = (0.65 * query_coverage) + (0.35 * dense_relevance)

        unsupported = tuple(support.claim for support in supports if not support.supported)
        passed = (
            faithfulness >= self.quality_threshold
            and groundedness >= self.quality_threshold
            and answer_relevance >= self.quality_threshold
        )
        return AnswerQualityScore(
            faithfulness=round(faithfulness, 4),
            groundedness=round(min(groundedness, 1.0), 4),
            answer_relevance=round(min(answer_relevance, 1.0), 4),
            citation_precision=round(citation_precision, 4),
            citation_coverage=round(citation_coverage, 4),
            unsupported_claims=unsupported,
            claim_support=supports,
            passed=passed,
        )

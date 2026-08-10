"""Answer-level RAG metrics: faithfulness, groundedness, answer relevance.

Closes the answer-evaluation gap. The existing evaluation suite grades
RETRIEVAL only (precision@k, recall@k, MRR, nDCG). This module adds metrics on
the GENERATED answer itself:

  * Faithfulness    - the answer must not contradict the retrieved context.
                      Measured as the fraction of the answer's claim-sentences
                      whose content tokens are substantively present in the
                      retrieved passages. This is the deterministic baseline.
  * Groundedness    - the answer should be attributable to the sources, i.e.
                      the fraction of the answer's content tokens that appear
                      in the context ("citation-ability"). An invented date is
                      punished because its tokens are absent from the sources.
  * Answer relevance - does the answer address the question? Measured as the
                      question's content tokens that also appear in the answer
                      (lexical proxy).

Why lexical proxies: dependency-free and deterministic, matching the repo's
"zero hard dependencies; degrade gracefully" rule. In production you upgrade
these to an LLM judge (ask a strong model to score each claim against each
source 0/1). Both paths are supported: functions accept an optional
`claim_splitter` so you can plug in an LLM claim splitter/hallucination judge
without changing this API. All scores are 0..1.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Callable, Optional

_STOP = {
    "the",
    "a",
    "an",
    "and",
    "or",
    "but",
    "in",
    "on",
    "at",
    "to",
    "for",
    "of",
    "with",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "it",
    "its",
    "that",
    "this",
    "these",
    "those",
    "we",
    "you",
    "i",
    "as",
    "by",
    "from",
    "into",
    "about",
    "than",
}

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


@dataclass
class AnswerScore:
    """Scores for one generated answer."""

    faithfulness: float = 0.0  # 0..1 supported-by-context
    groundedness: float = 0.0  # 0..1 attributable to retrieved sources
    answer_relevance: float = 0.0  # 0..1 addresses the question
    coverage: float = 0.0  # 0..1 context covers the answer's claims
    n_claims: int = 0
    n_supported_claims: int = 0

    def to_dict(self) -> dict:
        return {
            "faithfulness": round(self.faithfulness, 3),
            "groundedness": round(self.groundedness, 3),
            "answer_relevance": round(self.answer_relevance, 3),
            "coverage": round(self.coverage, 3),
            "n_claims": self.n_claims,
            "n_supported_claims": self.n_supported_claims,
        }


def _content_tokens(text: str) -> set[str]:
    if not text:
        return set()
    return {t.lower() for t in _TOKEN_RE.findall(text) if t.lower() not in _STOP and len(t) > 1}


def estimate_claims(answer: str) -> list[str]:
    """Deterministic sentence-level claim splitter (no LLM dependency)."""
    if not answer:
        return []
    parts = re.split(r"(?<=[.!?])\s+", answer.strip())
    return [p.rstrip(".!?").strip() for p in parts if p.strip()]


def recognize_supporting_facts(context: list[str]) -> set[str]:
    """Union of all content tokens across retrieved passages."""
    merged: set[str] = set()
    for c in context or []:
        merged |= _content_tokens(c)
    return merged


class RAGAnswerMetrics:
    """Compute answer-level RAG metrics via claims + lexical grounding."""

    def __init__(
        self,
        claim_splitter: Optional[Callable[[str], list[str]]] = None,
    ) -> None:
        self._split = claim_splitter or estimate_claims

    def measure(
        self,
        *,
        question: str,
        answer: str,
        context: list[str],
        reference_answer: Optional[str] = None,
    ) -> AnswerScore:
        claims = self._split(answer)
        claim_sets = [self._content(claim) for claim in claims if claim]
        support = recognize_supporting_facts(context)

        # Faithfulness: fraction of each claim's content tokens in context.
        supported_per_claim: list[float] = []
        for cs in claim_sets:
            if not cs:
                continue
            overlap = len(cs & support)
            supported_per_claim.append(overlap / max(1, len(cs)))
        faithfulness = (
            sum(supported_per_claim) / len(supported_per_claim) if supported_per_claim else 0.0
        )

        # Groundedness: fraction of answer content tokens present in context.
        ans_tok = self._content(answer)
        groundedness = len(ans_tok & support) / len(ans_tok) if ans_tok else 0.0

        # Answer relevance (lexical): how well the answer touches the question.
        q_tok = self._content(question)
        relevance = len(q_tok & ans_tok) / len(q_tok) if q_tok and ans_tok else 0.0

        n_supported = sum(1 for s in supported_per_claim if s >= 0.5)
        return AnswerScore(
            faithfulness=faithfulness,
            groundedness=groundedness,
            answer_relevance=relevance,
            coverage=faithfulness,
            n_claims=len(claims),
            n_supported_claims=n_supported,
        )

    @staticmethod
    def _content(text: str) -> set[str]:
        return _content_tokens(text)


def measure_answer_metrics(
    *,
    question: str,
    answer: str,
    context: list[str],
    reference_answer: Optional[str] = None,
) -> AnswerScore:
    """Module-level convenience: compute the three metrics in one call."""
    return RAGAnswerMetrics().measure(
        question=question,
        answer=answer,
        context=context,
        reference_answer=reference_answer,
    )

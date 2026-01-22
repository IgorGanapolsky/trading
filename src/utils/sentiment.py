"""Lightweight sentiment utilities used by ensemble gates.

Dec 12, 2025: Added fact-check layer with VADER + cosine similarity veto.
CEO Directive: Cut RAG noise with 0.7 similarity threshold.
"""

from __future__ import annotations

import logging
import math
from functools import lru_cache
from typing import Any

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

logger = logging.getLogger(__name__)

# Fact-check threshold for cosine similarity (CEO directive: 0.7)
COSINE_SIM_THRESHOLD = 0.7


@lru_cache(maxsize=1)
def _get_analyzer() -> SentimentIntensityAnalyzer:
    return SentimentIntensityAnalyzer()


def compute_lexical_sentiment(text: str | None) -> float:
    """
    Compute a deterministic sentiment score using VADER.

    Args:
        text: Arbitrary text snippet (can be None/empty).

    Returns:
        Compound polarity score clamped between -1 and 1.
    """
    if not text:
        return 0.0
    analyzer = _get_analyzer()
    try:
        compound = analyzer.polarity_scores(text)["compound"]
    except Exception:
        return 0.0
    compound = max(-1.0, min(1.0, float(compound)))
    return compound


def blend_sentiment_scores(
    primary: float,
    fallback: float,
    weight: float = 0.6,
) -> float:
    """
    Blend two sentiment scores with a configurable weight.

    Args:
        primary: Typically the LLM sentiment score (-1 to 1).
        fallback: Deterministic/lexical score (-1 to 1).
        weight: Weight for primary score (0-1). Remaining weight applied to fallback.

    Returns:
        Blended score rounded to 4 decimal places.
    """
    weight = max(0.0, min(1.0, float(weight)))
    blended = (primary * weight) + (fallback * (1 - weight))
    return round(blended, 4)


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    """
    Compute cosine similarity between two vectors.

    Args:
        vec_a: First vector
        vec_b: Second vector

    Returns:
        Cosine similarity score between -1 and 1
    """
    if len(vec_a) != len(vec_b) or len(vec_a) == 0:
        return 0.0

    dot_product = sum(a * b for a, b in zip(vec_a, vec_b))
    norm_a = math.sqrt(sum(a * a for a in vec_a))
    norm_b = math.sqrt(sum(b * b for b in vec_b))

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot_product / (norm_a * norm_b)


def text_to_sentiment_vector(text: str) -> list[float]:
    """
    Convert text to a sentiment feature vector using VADER components.

    Returns:
        4-element vector: [negative, neutral, positive, compound]
    """
    if not text:
        return [0.0, 1.0, 0.0, 0.0]  # Neutral baseline

    analyzer = _get_analyzer()
    try:
        scores = analyzer.polarity_scores(text)
        return [
            scores.get("neg", 0.0),
            scores.get("neu", 0.5),
            scores.get("pos", 0.0),
            scores.get("compound", 0.0),
        ]
    except Exception:
        return [0.0, 1.0, 0.0, 0.0]


def fact_check_sentiment(
    llm_sentiment: float,
    raw_text: str,
    _baseline_text: str | None = None,
    threshold: float = COSINE_SIM_THRESHOLD,
) -> dict[str, Any]:
    """
    Fact-check LLM sentiment against VADER baseline using cosine similarity.

    CEO Directive (Dec 12, 2025): Cut RAG noise with 0.7 similarity threshold.

    Args:
        llm_sentiment: Sentiment score from LLM (-1 to 1)
        raw_text: Original text that was analyzed
        baseline_text: Optional baseline text for comparison (uses raw_text if None)
        threshold: Minimum cosine similarity to pass (default 0.7)

    Returns:
        Dict with:
        - accepted: Whether the sentiment passes fact-check
        - llm_score: Original LLM sentiment
        - vader_score: VADER baseline score
        - cosine_sim: Similarity between LLM and VADER vectors
        - blended_score: Final blended score if accepted
        - veto_reason: Why it was rejected (if applicable)
    """
    # Compute VADER baseline
    vader_score = compute_lexical_sentiment(raw_text)

    # Create sentiment vectors for comparison
    # LLM vector: [negative proxy, neutral proxy, positive proxy, compound]
    llm_neg = max(0, -llm_sentiment)
    llm_pos = max(0, llm_sentiment)
    llm_neu = 1 - abs(llm_sentiment)
    llm_vec = [llm_neg, llm_neu, llm_pos, llm_sentiment]

    vader_vec = text_to_sentiment_vector(raw_text)

    # Compute cosine similarity
    sim = cosine_similarity(llm_vec, vader_vec)

    # Check if same direction (both positive or both negative)
    same_direction = (llm_sentiment >= 0 and vader_score >= 0) or (
        llm_sentiment < 0 and vader_score < 0
    )

    # Fact-check logic
    accepted = sim >= threshold and same_direction
    veto_reason = None

    if not accepted:
        if sim < threshold:
            veto_reason = f"cosine_sim {sim:.3f} < threshold {threshold}"
        elif not same_direction:
            veto_reason = f"direction_mismatch: LLM={llm_sentiment:.2f}, VADER={vader_score:.2f}"

    # Compute blended score (only used if accepted)
    blended = blend_sentiment_scores(llm_sentiment, vader_score, weight=0.6)

    result = {
        "accepted": accepted,
        "llm_score": round(llm_sentiment, 4),
        "vader_score": round(vader_score, 4),
        "cosine_sim": round(sim, 4),
        "blended_score": round(blended, 4) if accepted else 0.0,
        "same_direction": same_direction,
        "threshold": threshold,
        "veto_reason": veto_reason,
    }

    if not accepted:
        logger.info(
            "Sentiment fact-check VETO: llm=%.2f, vader=%.2f, sim=%.3f, reason=%s",
            llm_sentiment,
            vader_score,
            sim,
            veto_reason,
        )

    return result

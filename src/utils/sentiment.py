"""Lightweight sentiment utilities used by ensemble gates."""

from __future__ import annotations

from functools import lru_cache

from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer


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

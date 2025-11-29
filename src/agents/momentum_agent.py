"""Momentum screening agent (Gate 1)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any

from src.strategies.legacy_momentum import LegacyMomentumCalculator

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    is_buy: bool
    strength: float  # Normalised 0-1 confidence
    indicators: Dict[str, Any]


class MomentumAgent:
    """Adapts the legacy deterministic momentum logic to the new funnel."""

    def __init__(self, min_score: float = 0.0) -> None:
        self._calculator = LegacyMomentumCalculator()
        self._min_score = min_score

    def analyze(self, ticker: str) -> MomentumSignal:
        payload = self._calculator.evaluate(ticker)
        score = payload.score

        is_buy = score > self._min_score
        strength = self._normalise_score(score)

        logger.debug(
            "MomentumAgent | %s | score=%.4f | buy=%s | strength=%.3f",
            ticker,
            score,
            is_buy,
            strength,
        )

        return MomentumSignal(
            is_buy=is_buy,
            strength=strength,
            indicators=payload.indicators,
        )

    @staticmethod
    def _normalise_score(score: float) -> float:
        """Convert raw technical score to 0-1 band."""
        if score <= 0:
            return 0.0
        # Damp extremely large values (>100) to 1.0 asymptotically
        return min(1.0, score / (score + 100.0))


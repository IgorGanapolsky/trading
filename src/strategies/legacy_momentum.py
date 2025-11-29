"""Adapter around the legacy momentum calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any

from src.utils.market_data import get_market_data_provider
from src.utils.technical_indicators import calculate_technical_score

logger = logging.getLogger(__name__)


@dataclass
class MomentumPayload:
    score: float
    indicators: Dict[str, Any]


class LegacyMomentumCalculator:
    """
    Thin wrapper that fetches historical data and reuses the shared technical score.
    """

    def __init__(self, lookback_days: int = 120) -> None:
        self.lookback_days = lookback_days
        self._provider = get_market_data_provider()

    def evaluate(self, symbol: str) -> MomentumPayload:
        result = self._provider.get_daily_bars(
            symbol, lookback_days=self.lookback_days
        )
        hist = result.data
        score, indicators = calculate_technical_score(hist, symbol)

        indicators = indicators or {}
        indicators["data_source"] = result.source.value
        indicators["cache_age_hours"] = result.cache_age_hours
        indicators["rows"] = len(hist)

        logger.debug(
            "Momentum calculator | %s | score=%.4f | rows=%s | source=%s",
            symbol,
            score,
            indicators["rows"],
            indicators["data_source"],
        )
        return MomentumPayload(score=score, indicators=indicators)


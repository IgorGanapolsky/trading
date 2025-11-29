"""Adapter around the legacy momentum calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Dict, Any

from src.utils.market_data import get_market_data_provider
from src.utils.technical_indicators import calculate_technical_score, calculate_atr

logger = logging.getLogger(__name__)


@dataclass
class MomentumPayload:
    score: float
    indicators: Dict[str, Any]


def _coerce_scalar(value: Any) -> float:
    """Convert pandas objects (Series/DataFrame slices) to float."""
    try:
        if hasattr(value, "item"):
            return float(value.item())
    except Exception:  # pragma: no cover - fallback in case .item fails
        pass
    try:
        if hasattr(value, "iloc"):
            return float(value.iloc[-1])
    except Exception:
        pass
    return float(value)


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
        indicators["symbol"] = symbol

        try:
            price = _coerce_scalar(hist["Close"].iloc[-1])
            indicators["last_price"] = price
        except (KeyError, IndexError):
            price = 0.0

        # Derived features for downstream RL filter
        if len(hist) >= 50:
            sma_50 = _coerce_scalar(hist["Close"].rolling(50).mean().iloc[-1])
            if sma_50 != 0:
                indicators["sma_50_ratio"] = (price - float(sma_50)) / float(sma_50)

        if len(hist) >= 14:
            try:
                atr = calculate_atr(hist)
                indicators["atr_pct"] = atr / price if price else 0.0
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.debug("ATR calculation failed for %s: %s", symbol, exc)

        logger.debug(
            "Momentum calculator | %s | score=%.4f | rows=%s | source=%s",
            symbol,
            score,
            indicators["rows"],
            indicators["data_source"],
        )
        return MomentumPayload(score=score, indicators=indicators)


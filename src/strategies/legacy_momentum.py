"""Adapter around the legacy momentum calculations."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.utils.market_data import get_market_data_provider
from src.utils.technical_indicators import calculate_adx, calculate_atr, calculate_technical_score

logger = logging.getLogger(__name__)


@dataclass
class MomentumPayload:
    score: float
    indicators: dict[str, Any]


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
        import os

        self.lookback_days = lookback_days
        self._provider = get_market_data_provider()

        # Runtime tunables (env)
        # TIGHTENED THRESHOLDS (Dec 10, 2025): Fix 0% win rate by requiring confirmed signals
        # Previous (R&D data collection): macd=-0.1, rsi=75, volume=0.6, adx=5.0
        # Problem: 0% live win rate, negative Sharpe (-7 to -72), trades in ranging markets
        # New: Require confirmed bullish signals in trending markets only
        self.macd_threshold = float(os.getenv("MOMENTUM_MACD_THRESHOLD", "0.0"))  # Confirmed bullish
        self.rsi_overbought = float(os.getenv("MOMENTUM_RSI_OVERBOUGHT", "65.0"))  # Avoid overbought
        self.volume_min = float(os.getenv("MOMENTUM_VOLUME_MIN", "1.0"))  # Require avg+ volume

        # ADX REGIME FILTER (Dec 10, 2025): Only trade in trending markets
        # Research shows: ADX < 20 = ranging market with 50% whipsaw failure rate
        # ADX 20-40 = trending (55-65% win rate), ADX 40+ = strong trend (65-75% win rate)
        # Setting to 20.0 to filter out ranging markets that killed our win rate
        self.adx_min = float(os.getenv("MOMENTUM_ADX_MIN", "20.0"))

    def evaluate(self, symbol: str) -> MomentumPayload:
        result = self._provider.get_daily_bars(symbol, lookback_days=self.lookback_days)
        hist = result.data

        # ADX REGIME FILTER (Dec 5, 2025): Skip ranging markets to avoid whipsaws
        adx_value, plus_di, minus_di = calculate_adx(hist)
        if adx_value < self.adx_min:
            logger.info(
                f"{symbol}: REJECTED - ADX regime filter (ADX={adx_value:.1f} < {self.adx_min}). "
                "Market is ranging/trendless - high whipsaw risk."
            )
            return MomentumPayload(
                score=0.0,
                indicators={
                    "adx": adx_value,
                    "plus_di": plus_di,
                    "minus_di": minus_di,
                    "regime": "RANGING",
                    "rejection_reason": f"ADX {adx_value:.1f} < {self.adx_min} (no trend)",
                    "symbol": symbol,
                },
            )

        score, indicators = calculate_technical_score(
            hist,
            symbol,
            macd_threshold=self.macd_threshold,
            rsi_overbought=self.rsi_overbought,
            volume_min=self.volume_min,
        )

        indicators = indicators or {}
        indicators["data_source"] = result.source.value
        indicators["cache_age_hours"] = result.cache_age_hours
        indicators["rows"] = len(hist)
        indicators["symbol"] = symbol
        # Add ADX to indicators for downstream analysis
        indicators["adx"] = adx_value
        indicators["plus_di"] = plus_di
        indicators["minus_di"] = minus_di
        indicators["regime"] = "TRENDING" if adx_value >= 25 else "WEAK_TREND"

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

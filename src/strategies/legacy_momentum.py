"""
Legacy Momentum Calculator - Gate 1 Technical Screening

This module provides the LegacyMomentumCalculator used by MomentumAgent
for the first gate of the trading funnel.

Uses technical indicators (MACD, RSI, Volume, ADX) to generate momentum signals.

Created: Dec 23, 2025 - Fix missing module for CI/trading readiness
Reference: rag_knowledge/lessons_learned/ll_019_system_dead_2_days_overly_strict_filters_dec12.md
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import yfinance as yf

from src.utils.technical_indicators import (
    calculate_adx,
    calculate_macd,
    calculate_rsi,
    calculate_volume_ratio,
)

logger = logging.getLogger(__name__)


@dataclass
class MomentumPayload:
    """Result of momentum evaluation."""

    score: float
    indicators: dict[str, Any]


class LegacyMomentumCalculator:
    """
    Deterministic momentum calculator for Gate 1 screening.

    Calculates technical indicators (MACD, RSI, Volume, ADX) and produces
    a composite momentum score. Thresholds are intentionally permissive
    during R&D phase per ll_019 lesson learned.

    Attributes:
        macd_threshold: Minimum MACD histogram value (default: 0.0)
        rsi_overbought: Maximum RSI value before rejection (default: 85.0)
        volume_min: Minimum volume ratio vs 20-day average (default: 0.5)
        adx_threshold: Minimum ADX for trend strength (default: 0.0 = disabled)
    """

    def __init__(
        self,
        macd_threshold: float = 0.0,
        rsi_overbought: float = 85.0,
        volume_min: float = 0.5,
        adx_threshold: float = 0.0,
    ) -> None:
        """
        Initialize momentum calculator with R&D-friendly defaults.

        Per ll_019 lesson learned: During R&D phase, prioritize trade flow
        over filter precision. ADX disabled (0.0), RSI high (85.0).
        """
        self.macd_threshold = macd_threshold
        self.rsi_overbought = rsi_overbought
        self.volume_min = volume_min
        self.adx_threshold = adx_threshold
        # Alias for backwards compatibility with some code paths
        self.adx_min = adx_threshold

    def evaluate(self, ticker: str) -> MomentumPayload:
        """
        Evaluate momentum signals for a given ticker.

        Fetches recent price history and calculates technical indicators.
        Returns a composite score and indicator values.

        Args:
            ticker: Stock symbol to evaluate (e.g., 'AAPL', 'SPY')

        Returns:
            MomentumPayload with score and indicator dictionary
        """
        indicators: dict[str, Any] = {
            "symbol": ticker,
            "macd": 0.0,
            "macd_hist": 0.0,
            "rsi": 50.0,
            "volume_ratio": 1.0,
            "adx": 0.0,
        }

        try:
            # Lazy import yfinance (for CI compatibility)
            import yfinance as yf

            # Fetch 60 days of history for indicator calculations
            stock = yf.Ticker(ticker)
            hist = stock.history(period="60d")

            if hist.empty or len(hist) < 26:
                logger.warning(f"{ticker}: Insufficient data ({len(hist)} bars)")
                return MomentumPayload(score=0.0, indicators=indicators)

            close = hist["Close"]

            # Calculate indicators
            macd_value, macd_signal, macd_hist = calculate_macd(close)
            rsi = calculate_rsi(close)
            volume_ratio = calculate_volume_ratio(hist)
            adx, plus_di, minus_di = calculate_adx(hist)

            # Update indicators dict
            indicators["macd"] = macd_value
            indicators["macd_signal"] = macd_signal
            indicators["macd_hist"] = macd_hist
            indicators["rsi"] = rsi
            indicators["volume_ratio"] = volume_ratio
            indicators["adx"] = adx
            indicators["plus_di"] = plus_di
            indicators["minus_di"] = minus_di
            indicators["current_price"] = float(close.iloc[-1])

            # Apply filters (permissive during R&D per ll_019)
            if macd_hist < self.macd_threshold:
                logger.debug(f"{ticker}: Bearish MACD ({macd_hist:.3f})")
                return MomentumPayload(score=0.0, indicators=indicators)

            if rsi > self.rsi_overbought:
                logger.debug(f"{ticker}: Overbought RSI ({rsi:.1f})")
                return MomentumPayload(score=0.0, indicators=indicators)

            if volume_ratio < self.volume_min:
                logger.debug(f"{ticker}: Low volume ({volume_ratio:.2f}x)")
                return MomentumPayload(score=0.0, indicators=indicators)

            # ADX check (disabled when threshold is 0)
            if self.adx_threshold > 0 and adx < self.adx_threshold:
                logger.debug(f"{ticker}: Weak trend ADX ({adx:.1f})")
                return MomentumPayload(score=0.0, indicators=indicators)

            # Calculate composite score
            # Higher score = stronger momentum signal
            current_price = float(close.iloc[-1])
            score = (
                current_price
                * (1 + macd_hist / 10)
                * (1 + (70 - rsi) / 100)
                * volume_ratio
            )

            logger.info(
                f"{ticker}: Momentum score {score:.2f} | "
                f"MACD: {macd_hist:.3f} | RSI: {rsi:.1f} | "
                f"Vol: {volume_ratio:.2f}x | ADX: {adx:.1f}"
            )

            return MomentumPayload(score=score, indicators=indicators)

        except Exception as e:
            logger.error(f"{ticker}: Momentum evaluation failed: {e}")
            return MomentumPayload(score=0.0, indicators=indicators)

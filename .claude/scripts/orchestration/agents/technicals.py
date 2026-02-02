"""
Technical Analysis Agent

Analyzes technical indicators for SPY:
- RSI (Relative Strength Index)
- MACD (Moving Average Convergence Divergence)
- Bollinger Bands position
- Trend direction
"""

from typing import Any

from .base import BaseAgent


class TechnicalsAgent(BaseAgent):
    """Technical indicator analysis agent."""

    def __init__(self):
        super().__init__("technicals")

    async def analyze(self) -> dict[str, Any]:
        """Analyze technical indicators."""
        # In production, these would be calculated from price data
        # Using Alpaca or other market data APIs

        rsi = 48  # 30-70 is neutral, <30 oversold, >70 overbought
        macd_histogram = 0.15  # Positive = bullish, Negative = bearish
        macd_signal = "neutral"  # bullish_cross, bearish_cross, neutral
        bb_position = 0.5  # 0=lower band, 0.5=middle, 1=upper band
        sma_20_above_50 = True  # Short-term trend
        sma_50_above_200 = True  # Long-term trend

        # Calculate signals
        # RSI: Neutral zone is good for iron condors
        if 40 <= rsi <= 60:
            rsi_signal = 0.6  # Good - range-bound
        elif 30 <= rsi <= 70:
            rsi_signal = 0.5  # Neutral
        else:
            rsi_signal = 0.3  # Caution - potential reversal

        # MACD: Neutral/mild readings preferred
        if abs(macd_histogram) < 0.5:
            macd_value = 0.6  # Good - not trending strongly
        else:
            macd_value = 0.4  # Trending - more directional risk

        # Bollinger: Middle is best for iron condors
        bb_signal = 1 - abs(bb_position - 0.5) * 2
        bb_signal = max(0.3, bb_signal)

        # Trend: Consistent trend is slightly better
        trend_signal = 0.6 if sma_20_above_50 == sma_50_above_200 else 0.4

        # Composite signal
        signal = (
            rsi_signal * 0.30 +
            macd_value * 0.25 +
            bb_signal * 0.25 +
            trend_signal * 0.20
        )

        # Determine trend direction
        if sma_20_above_50 and sma_50_above_200:
            trend = "uptrend"
        elif not sma_20_above_50 and not sma_50_above_200:
            trend = "downtrend"
        else:
            trend = "sideways"

        return {
            "signal": round(signal, 3),
            "confidence": 0.8,  # Technical analysis is fairly reliable
            "data": {
                "rsi": rsi,
                "rsi_zone": self._rsi_zone(rsi),
                "macd_histogram": macd_histogram,
                "macd_signal": macd_signal,
                "bollinger_position": bb_position,
                "trend": trend,
                "sma_alignment": "bullish" if sma_20_above_50 and sma_50_above_200 else "mixed",
                "recommendation": self._get_recommendation(signal, trend),
            },
        }

    def _rsi_zone(self, rsi: float) -> str:
        """Determine RSI zone."""
        if rsi < 30:
            return "oversold"
        elif rsi > 70:
            return "overbought"
        elif 40 <= rsi <= 60:
            return "neutral_optimal"
        else:
            return "neutral"

    def _get_recommendation(self, signal: float, trend: str) -> str:
        """Generate trading recommendation."""
        if signal >= 0.6 and trend == "sideways":
            return "ideal_for_iron_condor"
        elif signal >= 0.5:
            return "acceptable_for_iron_condor"
        else:
            return "consider_directional_bias"

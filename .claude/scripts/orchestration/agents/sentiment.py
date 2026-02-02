"""
Sentiment Analysis Agent

Analyzes market sentiment from various sources:
- VIX (fear index)
- Put/Call ratio
- CNN Fear & Greed Index
"""

import os
from typing import Any

from .base import BaseAgent


class SentimentAgent(BaseAgent):
    """Market sentiment analysis agent."""

    def __init__(self):
        super().__init__("sentiment")

    async def analyze(self) -> dict[str, Any]:
        """Analyze market sentiment indicators."""
        # In production, these would be fetched from APIs
        # For now, return mock data that represents typical values

        vix = 18.5  # Normal VIX range 12-20
        put_call_ratio = 0.95  # <1 = bullish, >1 = bearish
        fear_greed = 52  # 0-100, 50 = neutral

        # Calculate composite signal
        # VIX: Lower is more bullish (normalize 10-40 range)
        vix_signal = 1 - ((vix - 10) / 30)
        vix_signal = max(0, min(1, vix_signal))

        # Put/Call: Lower is more bullish (normalize 0.5-1.5 range)
        pcr_signal = 1 - ((put_call_ratio - 0.5) / 1.0)
        pcr_signal = max(0, min(1, pcr_signal))

        # Fear/Greed: Direct mapping (0-100 -> 0-1)
        fg_signal = fear_greed / 100

        # Weighted average
        signal = (vix_signal * 0.4) + (pcr_signal * 0.3) + (fg_signal * 0.3)

        # Confidence based on indicator agreement
        signals = [vix_signal, pcr_signal, fg_signal]
        variance = sum((s - signal) ** 2 for s in signals) / len(signals)
        confidence = max(0.5, 1 - variance)

        return {
            "signal": round(signal, 3),
            "confidence": round(confidence, 3),
            "data": {
                "vix": vix,
                "vix_signal": round(vix_signal, 3),
                "put_call_ratio": put_call_ratio,
                "pcr_signal": round(pcr_signal, 3),
                "fear_greed_index": fear_greed,
                "fg_signal": round(fg_signal, 3),
                "interpretation": self._interpret_sentiment(signal),
            },
        }

    def _interpret_sentiment(self, signal: float) -> str:
        """Convert signal to human-readable interpretation."""
        if signal >= 0.7:
            return "bullish - favorable for iron condors"
        elif signal >= 0.5:
            return "neutral - good for range-bound strategies"
        elif signal >= 0.3:
            return "cautious - consider wider wings"
        else:
            return "bearish - high volatility expected"

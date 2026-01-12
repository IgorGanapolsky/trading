"""Stub file - FallbackStrategy for MCP trading fallback."""

from typing import Any


class FallbackStrategy:
    """Stub for FallbackStrategy - provides fallback analysis when LLM fails."""

    def __init__(self, *args, **kwargs):
        pass

    @staticmethod
    def analyze_without_llm(data: dict[str, Any]) -> dict[str, Any]:
        """
        Analyze market data without LLM when meta-agent fails.

        Args:
            data: Contains symbol and indicators (price, macd_histogram, rsi, etc.)

        Returns:
            Fallback trading decision
        """
        indicators = data.get("indicators", {})
        momentum_score = indicators.get("momentum_score", 50)
        rsi = indicators.get("rsi", 50)

        # Simple momentum-based fallback logic
        if momentum_score > 60 and rsi < 70:
            action = "BUY"
            confidence = min(0.6, (momentum_score - 50) / 50)
        elif momentum_score < 40 or rsi > 80:
            action = "SELL"
            confidence = min(0.6, (50 - momentum_score) / 50)
        else:
            action = "HOLD"
            confidence = 0.5

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": f"Fallback analysis: momentum={momentum_score:.1f}, RSI={rsi:.1f}",
        }

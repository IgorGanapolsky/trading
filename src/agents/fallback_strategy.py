"""
Fallback Strategy Stub

Placeholder for fallback trading strategy functionality.
TODO: Implement actual fallback logic when needed.
"""


class FallbackStrategy:
    """Fallback strategy when primary strategies fail."""

    def name(self) -> str:
        """Return strategy name."""
        return "FallbackStrategy"

    def should_activate(self, context: dict) -> bool:
        """
        Check if fallback should activate.

        Args:
            context: Trading context

        Returns:
            True if fallback should activate
        """
        return False

    def execute(self, context: dict) -> dict:
        """
        Execute fallback strategy.

        Args:
            context: Trading context

        Returns:
            Fallback action to take
        """
        return {
            "action": "hold",
            "reason": "Fallback strategy - no action",
        }

    @staticmethod
    def analyze_without_llm(data: dict) -> dict:
        """
        Analyze market data without LLM (fallback when meta_agent fails).

        Args:
            data: Market data with indicators

        Returns:
            Analysis result with action, confidence, reasoning
        """
        # Simple momentum-based fallback
        indicators = data.get("indicators", {})
        momentum_score = indicators.get("momentum_score", 50)

        if momentum_score > 60:
            action = "BUY"
            confidence = min((momentum_score - 50) / 50, 0.6)
        elif momentum_score < 40:
            action = "SELL"
            confidence = min((50 - momentum_score) / 50, 0.6)
        else:
            action = "HOLD"
            confidence = 0.3

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": f"Fallback analysis: momentum_score={momentum_score:.1f}",
        }

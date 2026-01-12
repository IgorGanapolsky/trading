"""Stub file - MacroeconomicAgent (original deleted in cleanup)."""


class MacroeconomicAgent:
    """Stub for MacroeconomicAgent - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def analyze(self, *args, **kwargs):
        return {"signal": "neutral", "confidence": 0.0}

    def get_macro_context(self) -> dict:
        """Return empty macro context - not used in Phil Town strategy."""
        return {
            "market_regime": "neutral",
            "vix_level": 15.0,
            "interest_rate_trend": "stable",
            "economic_outlook": "neutral",
            "recommendation": "proceed_normal",
        }

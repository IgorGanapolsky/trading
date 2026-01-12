"""Stub file - MomentumAgent (original deleted in cleanup)."""


class MomentumAgent:
    """Stub for MomentumAgent - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self._regime_config = {}

    def analyze(self, symbol: str = None, *args, **kwargs) -> dict:
        """Return neutral momentum signal."""
        return {"signal": "hold", "confidence": 0.0, "recommendation": "neutral"}

    def configure_regime(self, overrides: dict = None) -> None:
        """Configure momentum regime - stub does nothing."""
        self._regime_config = overrides or {}

    def _fetch_history(self, ticker: str) -> list:
        """Return empty history - stub."""
        return []

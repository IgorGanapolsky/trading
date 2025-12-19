"""
Core Strategy - Stub module for CI compatibility.

This is a stub created to fix CI failures after the original module was deleted.
The actual trading logic is in guaranteed_trader.py and other strategy files.

Created: Dec 19, 2025 - Fix CI import errors
"""

from typing import Any

from src.strategies.registry import StrategyInterface


class CoreStrategy(StrategyInterface):
    """
    Core trading strategy stub.

    This implements the StrategyInterface to satisfy import checks.
    Actual trading logic is handled by TradingOrchestrator and guaranteed_trader.py.
    """

    def __init__(self, **kwargs):
        """Initialize strategy with optional configuration."""
        self.config = kwargs

    @property
    def name(self) -> str:
        """Return strategy name."""
        return "CoreStrategy"

    def generate_signals(self, data: Any) -> list[dict[str, Any]]:
        """
        Generate trading signals from input data.

        This stub returns empty signals - actual logic is in guaranteed_trader.py
        """
        return []

    def get_config(self) -> dict[str, Any]:
        """Return strategy configuration."""
        return {
            "name": self.name,
            "version": "1.0.0",
            "status": "stub",
            "note": "Actual trading via guaranteed_trader.py",
        }

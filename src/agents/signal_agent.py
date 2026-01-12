"""Signal Agent stub - generates trading signals.

This stub enables mcp_trading orchestration.
Full implementation pending capital accumulation to $500.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class SignalAgent:
    """Signal agent for generating trading signals."""

    name: str = "signal_agent"
    role: str = "Trading signal generation"

    def generate_signal(self, symbol: str, data: dict[str, Any]) -> dict[str, Any]:
        """Generate a trading signal for a symbol."""
        return {
            "symbol": symbol,
            "signal": "NEUTRAL",
            "strength": 0.0,
            "reason": "Stub implementation",
        }

    def get_entry_points(self, symbol: str) -> list[float]:
        """Get potential entry points for a symbol."""
        return []

"""Fallback Strategy stub - provides safe default behavior.

This stub enables mcp_trading orchestration.
Full implementation pending capital accumulation to $500.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class FallbackStrategy:
    """Fallback strategy when primary strategies fail."""

    name: str = "fallback_strategy"
    role: str = "Safe default trading behavior"

    def execute(self, context: dict[str, Any]) -> dict[str, Any]:
        """Execute fallback strategy."""
        return {
            "action": "HOLD",
            "reason": "Fallback strategy - no action",
            "risk_level": "LOW",
        }

    def should_activate(self, error: Exception | None = None) -> bool:
        """Check if fallback strategy should activate."""
        return error is not None

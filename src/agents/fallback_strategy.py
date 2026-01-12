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

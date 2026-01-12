"""
Signal Agent Stub

Placeholder for trading signal agent functionality.
TODO: Implement actual signal generation when needed.
"""

from src.agents.base_agent import BaseAgent


class SignalAgent(BaseAgent):
    """Agent responsible for generating trading signals."""

    def name(self) -> str:
        """Return agent name."""
        return "SignalAgent"

    async def generate_signals(self, symbols: list) -> list:
        """
        Generate trading signals for given symbols.

        Args:
            symbols: List of symbols to analyze

        Returns:
            List of trading signals
        """
        return []

    async def evaluate_signal(self, signal: dict) -> float:
        """
        Evaluate signal strength.

        Args:
            signal: Trading signal to evaluate

        Returns:
            Signal strength score (0-1)
        """
        return 0.0

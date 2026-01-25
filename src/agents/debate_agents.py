"""Debate Agents - Multi-agent debate system for trading decisions."""

import logging

logger = logging.getLogger(__name__)


class DebateAgent:
    """An agent that participates in trading debates."""

    def __init__(self, name: str, bias: str = "neutral"):
        self.name = name
        self.bias = bias

    def argue(self, topic: dict) -> dict:
        """Present an argument on the topic."""
        return {
            "agent": self.name,
            "position": self.bias,
            "confidence": 0.5,
            "reasoning": "Stub reasoning",
        }


class DebateCoordinator:
    """Coordinates debates between multiple agents."""

    def __init__(self):
        self.agents: list[DebateAgent] = [
            DebateAgent("bull", "bullish"),
            DebateAgent("bear", "bearish"),
            DebateAgent("neutral", "neutral"),
        ]

    def run_debate(self, topic: dict) -> dict:
        """Run a debate and return consensus."""
        arguments = [agent.argue(topic) for agent in self.agents]

        return {
            "topic": topic,
            "arguments": arguments,
            "consensus": "hold",
            "confidence": 0.5,
        }


def get_debate_consensus(topic: dict) -> dict:
    """Run debate and get consensus."""
    coordinator = DebateCoordinator()
    return coordinator.run_debate(topic)


class DebateModerator:
    """Moderates bull/bear debates for trading decisions.

    Provides the interface expected by TradingOrchestrator.
    """

    def __init__(self):
        self.coordinator = DebateCoordinator()

    def conduct_debate(self, ticker: str, market_data: dict) -> dict:
        """Conduct a bull/bear debate on a ticker.

        Args:
            ticker: The stock symbol to debate
            market_data: Market data for the ticker

        Returns:
            Dict with debate outcome including consensus and confidence
        """
        topic = {
            "ticker": ticker,
            "market_data": market_data,
            "question": f"Should we trade {ticker}?",
        }
        result = self.coordinator.run_debate(topic)

        # Add fields expected by orchestrator
        result["ticker"] = ticker
        result["recommendation"] = result.get("consensus", "hold")

        return result

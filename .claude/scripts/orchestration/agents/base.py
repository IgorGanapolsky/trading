"""
Base Agent Class for Swarm Orchestration

All specialized agents inherit from this base class.
"""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any


class BaseAgent(ABC):
    """Base class for all swarm agents."""

    def __init__(self, agent_type: str):
        self.agent_type = agent_type
        self.started_at: datetime | None = None
        self.completed_at: datetime | None = None

    @abstractmethod
    async def analyze(self) -> dict[str, Any]:
        """
        Execute the agent's analysis.

        Returns:
            dict with:
                - signal: float 0-1 (0=bearish, 0.5=neutral, 1=bullish)
                - confidence: float 0-1
                - data: dict with analysis details
        """
        pass

    async def run(self) -> dict[str, Any]:
        """Execute the agent and return results."""
        self.started_at = datetime.now(timezone.utc)

        try:
            result = await self.analyze()
            result["agent_type"] = self.agent_type
            result["status"] = "completed"
        except Exception as e:
            result = {
                "agent_type": self.agent_type,
                "status": "failed",
                "error": str(e),
                "signal": 0.5,  # Neutral on failure
                "confidence": 0.0,
                "data": {},
            }

        self.completed_at = datetime.now(timezone.utc)
        result["duration_ms"] = (
            self.completed_at - self.started_at
        ).total_seconds() * 1000

        return result

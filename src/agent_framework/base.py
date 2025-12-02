"""
Abstract base classes for trading agents.

Agents follow a three-step lifecycle:
1. prepare(context)  -> optional warm-up / cache priming
2. execute(context)  -> mandatory core logic, returns AgentResult
3. cleanup(context)  -> optional resource release
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .context import RunContext

logger = logging.getLogger(__name__)


@dataclass
class AgentResult:
    """Standardized agent response payload."""

    name: str
    succeeded: bool
    payload: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    started_at: datetime = field(default_factory=datetime.utcnow)
    finished_at: datetime | None = None

    def mark_finished(self) -> None:
        self.finished_at = datetime.utcnow()


class TradingAgent(ABC):
    """Base interface all agents must implement."""

    def __init__(self, agent_name: str) -> None:
        self.agent_name = agent_name

    def prepare(self, context: RunContext) -> None:
        """
        Optional warmup hook.

        Executed before `execute` and can be used to hydrate caches or fetch metadata.
        """

    @abstractmethod
    def execute(self, context: RunContext) -> AgentResult:
        """
        Core agent logic.

        Implementations MUST create an AgentResult, populate payload/error fields,
        call `mark_finished`, and return the result.
        """

    def cleanup(self, context: RunContext) -> None:
        """
        Optional teardown hook.

        Called after `execute`, even if exceptions occur.
        """

    # Convenience helper -------------------------------------------------
    def run(self, context: RunContext) -> AgentResult:
        """Utility to execute the full lifecycle with consistent logging."""
        logger.info("Starting agent %s in %s mode", self.agent_name, context.mode.value)
        result: AgentResult
        try:
            self.prepare(context)
            result = self.execute(context)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Agent %s failed: %s", self.agent_name, exc)
            result = AgentResult(
                name=self.agent_name,
                succeeded=False,
                error=str(exc),
            )
        finally:
            try:
                self.cleanup(context)
            except Exception:  # pragma: no cover - defensive
                logger.exception("Agent %s cleanup raised an exception", self.agent_name)

        result.mark_finished()
        status = "succeeded" if result.succeeded else "failed"
        logger.info(
            "Agent %s %s in %ss",
            self.agent_name,
            status,
            (
                (result.finished_at - result.started_at).total_seconds()
                if result.finished_at
                else "N/A"
            ),
        )
        return result

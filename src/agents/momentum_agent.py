"""Momentum screening agent (Gate 1) — stub retained for interface compatibility.

MomentumStrategy was removed (dead code cleanup, 2026-03-23).
This agent is no longer actively used; all live trading uses IronCondorTrader.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.rag.lessons_learned_rag import LessonsLearnedRAG

logger = logging.getLogger(__name__)


@dataclass
class MomentumSignal:
    is_buy: bool
    strength: float  # Normalised 0-1 confidence
    indicators: dict[str, Any]


class MomentumAgent:
    """Stub: MomentumStrategy removed — agent returns a neutral signal."""

    def __init__(self, min_score: float = 0.0) -> None:
        self._min_score = min_score
        self.rag = LessonsLearnedRAG()

    def configure_regime(
        self,
        overrides: dict[str, float] | None = None,
    ) -> None:
        """No-op: momentum regime config removed with MomentumStrategy."""

    def analyze(self, ticker: str) -> MomentumSignal:
        """Return neutral signal — momentum analysis is not active."""
        logger.warning(
            "MomentumAgent.analyze(%s): MomentumStrategy removed; returning neutral signal.",
            ticker,
        )
        return MomentumSignal(
            is_buy=False,
            strength=0.0,
            indicators={"symbol": ticker, "note": "momentum_strategy_removed"},
        )

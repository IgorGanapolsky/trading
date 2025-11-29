"""LLM budget enforcement for Gate 3."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BudgetController:
    """
    Tracks estimated LLM spend for a single run.

    We assume Actions reset state each execution so a per-run counter is enough.
    """

    def __init__(self, max_run_spend: float = 1.50) -> None:
        self.max_run_spend = max_run_spend
        self.current_spend = 0.0

    def can_afford_execution(self, estimate: float = 0.02) -> bool:
        """Return True if we can spend at least `estimate` more dollars."""
        allowed = self.current_spend + estimate <= self.max_run_spend
        if not allowed:
            logger.warning(
                "LLM budget exhausted: spent %.2f / %.2f",
                self.current_spend,
                self.max_run_spend,
            )
        return allowed

    def log_spend(self, amount: float) -> None:
        """Record an actual spend after a successful API call."""
        if amount <= 0:
            return
        self.current_spend += amount
        logger.info(
            "LLM budget updated: +$%.4f (total this run: $%.4f)",
            amount,
            self.current_spend,
        )


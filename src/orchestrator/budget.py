"""LLM budget enforcement for Gate 3."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


class BudgetController:
    """
    Tracks estimated LLM spend for a single run.

    We assume Actions reset state each execution so a per-run counter is enough.
    """

    def __init__(
        self,
        max_run_spend: float = 1.50,
        default_estimate: float = 0.01,
        model_costs: dict[str, float] | None = None,
    ) -> None:
        self.max_run_spend = max_run_spend
        self.default_estimate = default_estimate
        self.model_costs = model_costs or {}
        self.current_spend = 0.0

    def can_afford_execution(
        self,
        *,
        model: str | None = None,
        estimate: float | None = None,
    ) -> bool:
        """Return True if we can spend at least `estimate` more dollars."""
        expected = estimate
        if expected is None:
            expected = self.model_costs.get(model or "", self.default_estimate)

        allowed = self.current_spend + expected <= self.max_run_spend
        if not allowed:
            logger.warning(
                "LLM budget exhausted: need %.2f but only %.2f remaining.",
                expected,
                self.remaining_budget,
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

    @property
    def remaining_budget(self) -> float:
        return max(0.0, self.max_run_spend - self.current_spend)



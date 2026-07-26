"""Dividend-growth buy-and-hold strategy (dividend_growth_income candidate).

Deliberately simple: buy-and-hold income does not need momentum or timing
signals - the entire point is dollar-cost-averaging into a small basket of
qualified-dividend growth ETFs and letting distributions compound. Complexity
here would just be a knob to overfit; see .claude/rules/karpathy-principles.md.

Does not inherit src.strategies.registry.StrategyInterface - that ABC's
analyze/execute contract does not fit a scheduled DCA buyer, and the sibling
ReitStrategy that tried to use it was broken and unused for that reason
(config/strategy_candidate_tournament.json, 2026-07-25).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Qualified-dividend growth ETF universe. Single-fund by default; kept as a
# list so a future paper-cohort could compare allocations without a rewrite.
DEFAULT_UNIVERSE = ["SCHD"]


@dataclass(frozen=True)
class DcaOrder:
    symbol: str
    notional_usd: float


class DividendGrowthStrategy:
    """Deterministic dollar-cost-averaging allocator, no market timing."""

    def __init__(self, universe: list[str] | None = None):
        self.universe = list(DEFAULT_UNIVERSE) if universe is None else universe
        if not self.universe:
            raise ValueError("universe must contain at least one symbol")

    def plan_purchase(self, available_cash_usd: float) -> list[DcaOrder]:
        """Split available cash evenly across the universe.

        Returns an empty list (not an error) when cash is too small to buy a
        meaningful position - callers should treat "nothing to do yet" as the
        normal case for a small, growing account.
        """
        if available_cash_usd <= 0:
            return []
        per_symbol = available_cash_usd / len(self.universe)
        if per_symbol < 1.0:
            logger.info(
                "Skipping DCA: $%.2f split across %d symbols is below the $1 minimum notional",
                available_cash_usd,
                len(self.universe),
            )
            return []
        return [DcaOrder(symbol=symbol, notional_usd=per_symbol) for symbol in self.universe]

"""Evidence-driven position sizing for the after-tax income objective.

No win rate, expectancy, trade cadence, or profitability is assumed. Real-money
sizing remains zero until a desk-grade realized cohort clears the configured
sample and confidence gates.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from src.analytics.statistical_edge import (
    calculate_edge_statistics,
    required_pretax_monthly,
)


@dataclass(frozen=True)
class PositionSizingPlan:
    account_equity: float
    max_risk_pct: float
    max_risk_usd: float
    spread_width: float
    max_loss_per_contract: float
    recommended_contracts: int
    observed_sample_size: int
    observed_expectancy_per_trade: float | None
    expectancy_lower_95: float | None
    expected_monthly_gross: float
    expected_monthly_after_tax: float
    required_monthly_gross: float
    target_attainable_at_observed_edge: bool
    readiness_reason: str


class DynamicPositionSizer:
    """Size only from verified realized outcomes and bounded account risk."""

    def __init__(
        self,
        target_after_tax_monthly: float = 1_000.0,
        estimated_tax_rate: float = 0.37,
        max_risk_per_trade_pct: float = 0.01,
        minimum_live_sample: int = 100,
    ):
        if not 0.0 < max_risk_per_trade_pct <= 0.02:
            raise ValueError("max_risk_per_trade_pct must be in (0, 0.02]")
        self.target_after_tax_monthly = float(target_after_tax_monthly)
        self.estimated_tax_rate = float(estimated_tax_rate)
        self.max_risk_per_trade_pct = float(max_risk_per_trade_pct)
        self.minimum_live_sample = max(100, int(minimum_live_sample))

    @property
    def target_gross_monthly(self) -> float:
        return required_pretax_monthly(
            self.target_after_tax_monthly,
            self.estimated_tax_rate,
        )

    def calculate_sizing(
        self,
        account_equity: float,
        spread_width: float = 5.0,
        credit_received: float = 0.75,
        *,
        realized_pnls: Sequence[float] = (),
        observed_trades_per_month: float | None = None,
    ) -> PositionSizingPlan:
        """Calculate a bounded live-size plan from a realized active cohort."""
        equity = max(0.0, float(account_equity))
        width = float(spread_width)
        credit = float(credit_received)
        if width <= 0.0 or credit < 0.0 or credit >= width:
            raise ValueError("spread_width must be positive and credit must be in [0, width)")
        max_loss = (width - credit) * 100.0
        max_risk_usd = equity * self.max_risk_per_trade_pct
        stats = calculate_edge_statistics(realized_pnls)
        cadence = float(observed_trades_per_month or 0.0)

        reason = "ready"
        if equity <= 0.0:
            reason = "account equity is not positive"
        elif stats.sample_size < self.minimum_live_sample:
            reason = (
                f"insufficient realized sample: {stats.sample_size} < {self.minimum_live_sample}"
            )
        elif stats.expectancy_lower_95 is None or stats.expectancy_lower_95 <= 0.0:
            reason = "95% lower confidence bound for expectancy is not positive"
        elif cadence <= 0.0:
            reason = "observed monthly trade cadence is unavailable"

        contracts = 0
        expected_gross = 0.0
        if reason == "ready":
            risk_cap = math.floor(max_risk_usd / max_loss)
            # Half-Kelly capped at the hard 1% account-risk budget.
            avg_win = float(stats.average_win or 0.0)
            avg_loss = abs(float(stats.average_loss or 0.0))
            win_probability = stats.wins / stats.sample_size if stats.sample_size else 0.0
            payoff_ratio = avg_win / avg_loss if avg_loss > 0.0 else 0.0
            full_kelly = (
                win_probability - ((1.0 - win_probability) / payoff_ratio)
                if payoff_ratio > 0.0
                else 0.0
            )
            kelly_risk_usd = equity * max(0.0, min(full_kelly * 0.5, self.max_risk_per_trade_pct))
            kelly_cap = math.floor(kelly_risk_usd / max_loss)
            contracts = max(0, min(risk_cap, kelly_cap))
            expected_gross = contracts * float(stats.expectancy_per_trade or 0.0) * cadence
            if contracts == 0:
                reason = "verified edge exists but one contract exceeds the risk/Kelly budget"

        expected_after_tax = (
            expected_gross * (1.0 - self.estimated_tax_rate)
            if expected_gross > 0.0
            else expected_gross
        )
        return PositionSizingPlan(
            account_equity=equity,
            max_risk_pct=self.max_risk_per_trade_pct,
            max_risk_usd=round(max_risk_usd, 2),
            spread_width=width,
            max_loss_per_contract=round(max_loss, 2),
            recommended_contracts=contracts,
            observed_sample_size=stats.sample_size,
            observed_expectancy_per_trade=stats.expectancy_per_trade,
            expectancy_lower_95=stats.expectancy_lower_95,
            expected_monthly_gross=round(expected_gross, 2),
            expected_monthly_after_tax=round(expected_after_tax, 2),
            required_monthly_gross=self.target_gross_monthly,
            target_attainable_at_observed_edge=bool(
                contracts > 0 and expected_after_tax >= self.target_after_tax_monthly
            ),
            readiness_reason=reason,
        )

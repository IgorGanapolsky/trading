"""Freedom Number & Income Milestone Acceleration Calculator.

Inspired by Rico Nasol's Freedom Builder Bootcamp frameworks:
Computes the exact 'Freedom Number' (net monthly passive income target including
healthcare, tax drag, and buffer), projects capital accumulation milestones to
the North Star deadline (Nov 14, 2029), and models combined cashflow from:
  1. Business/consulting net surplus deposits (Gurobi/ThumbGate)
  2. Defined-risk options alpha (SPY Put Credit / XSP)
  3. 3-Bucket passive distribution yield compounding (SPYI/QQQI/SCHD/SGOV)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any


@dataclass(frozen=True)
class FreedomBudget:
    base_living_expenses_usd: float
    healthcare_buffer_usd: float
    lifestyle_travel_buffer_usd: float
    tax_contingency_pct: float = 0.18  # Section 1256 blended effective rate

    @property
    def total_net_monthly_need(self) -> float:
        return (
            self.base_living_expenses_usd
            + self.healthcare_buffer_usd
            + self.lifestyle_travel_buffer_usd
        )

    @property
    def required_gross_monthly_distribution(self) -> float:
        return self.total_net_monthly_need / (1.0 - self.tax_contingency_pct)


@dataclass(frozen=True)
class MilestoneProjection:
    target_capital_usd: float
    current_capital_usd: float
    months_to_deadline: int
    target_deadline_date: str
    monthly_business_savings_usd: float
    annual_portfolio_yield_pct: float
    annual_trading_alpha_pct: float
    projected_capital_at_deadline: float
    monthly_passive_income_at_deadline: float
    shortfall_or_surplus_usd: float
    on_track_for_north_star: bool
    months_to_freedom_achieved: int
    milestone_timeline: list[dict[str, Any]] = field(default_factory=list)


class FreedomNumberCalculator:
    """Models multi-engine capital accumulation toward financial independence."""

    NORTH_STAR_DEADLINE = date(2029, 11, 14)  # 50th Birthday

    def __init__(self, budget: FreedomBudget | None = None):
        self.budget = budget or FreedomBudget(
            base_living_expenses_usd=4500.0,
            healthcare_buffer_usd=1000.0,
            lifestyle_travel_buffer_usd=500.0,
            tax_contingency_pct=0.18,
        )

    def calculate_months_remaining(self, current_date: date | None = None) -> int:
        now = current_date or date.today()
        if now >= self.NORTH_STAR_DEADLINE:
            return 0
        years = self.NORTH_STAR_DEADLINE.year - now.year
        months = self.NORTH_STAR_DEADLINE.month - now.month
        return max(0, years * 12 + months)

    def compute_projection(
        self,
        current_capital_usd: float = 100000.0,
        monthly_business_savings_usd: float = 4000.0,
        annual_portfolio_yield_pct: float = 0.095,  # 3-Bucket blended yield
        annual_trading_alpha_pct: float = 0.120,  # Defined-risk options alpha
        current_date: date | None = None,
    ) -> MilestoneProjection:
        """Project multi-engine compounding timeline to the North Star milestone."""
        months_remaining = self.calculate_months_remaining(current_date)
        net_monthly_need = self.budget.total_net_monthly_need

        # Target capital needed at blended portfolio net yield
        effective_net_yield = annual_portfolio_yield_pct * (1.0 - self.budget.tax_contingency_pct)
        target_capital = (net_monthly_need * 12.0) / max(0.01, effective_net_yield)

        # Monthly total growth rate: (Portfolio Yield + Trading Alpha) / 12
        monthly_growth_rate = (annual_portfolio_yield_pct + annual_trading_alpha_pct) / 12.0

        capital = current_capital_usd
        timeline: list[dict[str, Any]] = []
        months_to_freedom = 999

        for m in range(1, max(months_remaining, 60) + 1):
            # Compound capital and add monthly savings
            growth = capital * monthly_growth_rate
            capital += growth + monthly_business_savings_usd

            monthly_passive_income = (capital * effective_net_yield) / 12.0

            if capital >= target_capital and months_to_freedom == 999:
                months_to_freedom = m

            if m <= months_remaining or m == months_to_freedom or m % 12 == 0:
                timeline.append(
                    {
                        "month": m,
                        "capital_usd": round(capital, 2),
                        "monthly_passive_income_usd": round(monthly_passive_income, 2),
                        "freedom_goal_pct": round((capital / target_capital) * 100.0, 1),
                    }
                )

        capital_at_deadline = (
            timeline[min(len(timeline) - 1, months_remaining - 1)]["capital_usd"]
            if months_remaining > 0
            else current_capital_usd
        )
        monthly_income_at_deadline = (capital_at_deadline * effective_net_yield) / 12.0
        surplus = capital_at_deadline - target_capital

        return MilestoneProjection(
            target_capital_usd=round(target_capital, 2),
            current_capital_usd=round(current_capital_usd, 2),
            months_to_deadline=months_remaining,
            target_deadline_date=self.NORTH_STAR_DEADLINE.isoformat(),
            monthly_business_savings_usd=round(monthly_business_savings_usd, 2),
            annual_portfolio_yield_pct=annual_portfolio_yield_pct,
            annual_trading_alpha_pct=annual_trading_alpha_pct,
            projected_capital_at_deadline=round(capital_at_deadline, 2),
            monthly_passive_income_at_deadline=round(monthly_income_at_deadline, 2),
            shortfall_or_surplus_usd=round(surplus, 2),
            on_track_for_north_star=(capital_at_deadline >= target_capital),
            months_to_freedom_achieved=months_to_freedom,
            milestone_timeline=timeline,
        )

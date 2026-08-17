"""Three-Bucket Passive Income & Distribution Allocation Engine.

Inspired by modern income investing architecture (Freedom Builder / 3-Bucket Model):
Replaces traditional low-yield dividend assumptions (3% SCHD requiring $2.5M capital)
with an institutional 3-Bucket structure combining Section 1256 option-income ETFs,
dividend growth compounders, and short-duration treasury liquidity reserves.

Target Profile:
  - Bucket 1 (Liquidity & Buffer): SGOV / USFR (15% target, ~5.0% yield)
  - Bucket 2 (Cashflow Engine): SPYI / QQQI / JEPQ / DIVO (55% target, ~10.0% yield, Section 1256 tax treatment)
  - Bucket 3 (Dividend Compounder): SCHD / DGRO (30% target, ~3.4% yield, long-term dividend growth)

North Star Target: $6,000/month after-tax on $600,000 capital.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class BucketConfig:
    name: str
    target_weight: float  # 0.0 to 1.0
    expected_yield: float  # e.g. 0.10 for 10%
    tax_rate: float  # effective tax rate (e.g. 0.20 for Section 1256 60/40 blended rate)
    symbols: list[str]


DEFAULT_BUCKETS: dict[str, BucketConfig] = {
    "bucket_1_liquidity": BucketConfig(
        name="Bucket 1: Liquidity & Reserve",
        target_weight=0.15,
        expected_yield=0.050,
        tax_rate=0.24,  # ordinary interest
        symbols=["SGOV", "USFR"],
    ),
    "bucket_2_cashflow": BucketConfig(
        name="Bucket 2: High-Yield Option Income",
        target_weight=0.55,
        expected_yield=0.102,
        tax_rate=0.18,  # Section 1256 60/40 capital gains blend + ROC
        symbols=["SPYI", "QQQI", "JEPQ", "DIVO"],
    ),
    "bucket_3_compounder": BucketConfig(
        name="Bucket 3: Dividend Growth Compounder",
        target_weight=0.30,
        expected_yield=0.034,
        tax_rate=0.15,  # qualified dividend rate
        symbols=["SCHD", "DGRO"],
    ),
}


@dataclass(frozen=True)
class BucketAllocation:
    bucket_key: str
    name: str
    allocated_usd: float
    target_weight: float
    expected_annual_gross: float
    expected_annual_net: float
    expected_monthly_net: float
    symbols: list[str]


@dataclass(frozen=True)
class IncomePortfolioPlan:
    total_capital_usd: float
    target_monthly_income_usd: float
    gross_annual_income_usd: float
    net_annual_income_usd: float
    net_monthly_income_usd: float
    effective_blended_yield: float
    effective_blended_tax_rate: float
    income_shortfall_usd: float
    north_star_achieved: bool
    capital_needed_for_goal: float
    allocations: list[BucketAllocation] = field(default_factory=list)

    def summary(self) -> str:
        status = "ACHIEVED" if self.north_star_achieved else "IN_ACCUMULATION"
        return (
            f"IncomePlan({status}): Capital=${self.total_capital_usd:,.2f} -> "
            f"Net Monthly=${self.net_monthly_income_usd:,.2f} / Goal=${self.target_monthly_income_usd:,.2f} "
            f"(Blended Net Yield={self.net_annual_income_usd / max(1.0, self.total_capital_usd):.2%})"
        )


class IncomeBucketEngine:
    """Calculates allocations, cashflow projections, and stress-tests for the 3-Bucket system."""

    def __init__(self, buckets: Mapping[str, BucketConfig] | None = None):
        self.buckets = dict(DEFAULT_BUCKETS) if buckets is None else dict(buckets)
        # Validate weights sum to 1.0
        total_weight = sum(b.target_weight for b in self.buckets.values())
        if not (0.999 <= total_weight <= 1.001):
            raise ValueError(f"Bucket target weights must sum to 1.0, got {total_weight:.4f}")

    def evaluate_portfolio(
        self,
        capital_usd: float,
        target_monthly_income_usd: float = 6000.0,
    ) -> IncomePortfolioPlan:
        """Calculate complete distribution plan and milestone gap."""
        if capital_usd < 0:
            raise ValueError("capital_usd cannot be negative")

        allocations: list[BucketAllocation] = []
        total_gross = 0.0
        total_net = 0.0

        for key, bucket in self.buckets.items():
            allocated = capital_usd * bucket.target_weight
            annual_gross = allocated * bucket.expected_yield
            annual_net = annual_gross * (1.0 - bucket.tax_rate)
            monthly_net = annual_net / 12.0

            total_gross += annual_gross
            total_net += annual_net

            allocations.append(
                BucketAllocation(
                    bucket_key=key,
                    name=bucket.name,
                    allocated_usd=round(allocated, 2),
                    target_weight=bucket.target_weight,
                    expected_annual_gross=round(annual_gross, 2),
                    expected_annual_net=round(annual_net, 2),
                    expected_monthly_net=round(monthly_net, 2),
                    symbols=bucket.symbols,
                )
            )

        monthly_net = total_net / 12.0
        blended_yield = (total_gross / capital_usd) if capital_usd > 0 else 0.0
        blended_tax = (1.0 - (total_net / total_gross)) if total_gross > 0 else 0.0
        blended_net_rate = (total_net / capital_usd) if capital_usd > 0 else 0.0

        # Capital needed to produce target_monthly_income_usd at this blended net rate
        target_annual_net = target_monthly_income_usd * 12.0
        capital_needed = (target_annual_net / blended_net_rate) if blended_net_rate > 0 else 0.0
        shortfall = max(0.0, target_monthly_income_usd - monthly_net)

        return IncomePortfolioPlan(
            total_capital_usd=round(capital_usd, 2),
            target_monthly_income_usd=round(target_monthly_income_usd, 2),
            gross_annual_income_usd=round(total_gross, 2),
            net_annual_income_usd=round(total_net, 2),
            net_monthly_income_usd=round(monthly_net, 2),
            effective_blended_yield=round(blended_yield, 4),
            effective_blended_tax_rate=round(blended_tax, 4),
            income_shortfall_usd=round(shortfall, 2),
            north_star_achieved=(monthly_net >= target_monthly_income_usd),
            capital_needed_for_goal=round(capital_needed, 2),
            allocations=allocations,
        )

    def plan_rebalance_dca(
        self,
        current_holdings: Mapping[str, float],
        deposit_usd: float,
    ) -> dict[str, float]:
        """Direct new funds to the most underweight buckets first."""
        if deposit_usd <= 0:
            return {k: 0.0 for k in self.buckets}

        total_current = sum(current_holdings.get(k, 0.0) for k in self.buckets)
        new_total = total_current + deposit_usd

        # Calculate target dollar amounts for each bucket
        target_dollars = {k: new_total * b.target_weight for k, b in self.buckets.items()}
        deficits = {
            k: max(0.0, target_dollars[k] - current_holdings.get(k, 0.0)) for k in self.buckets
        }
        total_deficit = sum(deficits.values())

        if total_deficit <= 0:
            # Pro-rata if already perfectly balanced
            return {k: round(deposit_usd * b.target_weight, 2) for k, b in self.buckets.items()}

        # Allocate deposit proportional to deficit
        plan: dict[str, float] = {}
        for k in self.buckets:
            share = (deficits[k] / total_deficit) * deposit_usd
            plan[k] = round(share, 2)

        return plan

    def simulate_bear_market_survival(
        self,
        capital_usd: float,
        monthly_expense_usd: float = 6000.0,
        equity_drop_pct: float = 0.30,
        months: int = 12,
    ) -> dict[str, Any]:
        """Simulate portfolio survival without forced equity sales during a market crash."""
        b1_initial = capital_usd * self.buckets["bucket_1_liquidity"].target_weight
        b2_initial = (
            capital_usd * self.buckets["bucket_2_cashflow"].target_weight * (1.0 - equity_drop_pct)
        )
        b3_initial = (
            capital_usd
            * self.buckets["bucket_3_compounder"].target_weight
            * (1.0 - equity_drop_pct)
        )

        # Monthly income generated from crashed Bucket 2 and 3
        b2_net_monthly = (
            b2_initial
            * self.buckets["bucket_2_cashflow"].expected_yield
            * (1.0 - self.buckets["bucket_2_cashflow"].tax_rate)
        ) / 12.0
        b3_net_monthly = (
            b3_initial
            * self.buckets["bucket_3_compounder"].expected_yield
            * (1.0 - self.buckets["bucket_3_compounder"].tax_rate)
        ) / 12.0
        b1_net_monthly = (
            b1_initial
            * self.buckets["bucket_1_liquidity"].expected_yield
            * (1.0 - self.buckets["bucket_1_liquidity"].tax_rate)
        ) / 12.0

        monthly_cashflow_incoming = b2_net_monthly + b3_net_monthly + b1_net_monthly
        monthly_deficit = max(0.0, monthly_expense_usd - monthly_cashflow_incoming)

        # Bucket 1 cash drain
        b1_remaining = b1_initial - (monthly_deficit * months)
        survived = b1_remaining >= 0.0

        return {
            "initial_capital_usd": capital_usd,
            "equity_drop_pct": equity_drop_pct,
            "duration_months": months,
            "bucket_1_initial_cash": round(b1_initial, 2),
            "monthly_cashflow_during_crash": round(monthly_cashflow_incoming, 2),
            "monthly_deficit_drawn_from_b1": round(monthly_deficit, 2),
            "bucket_1_remaining_cash": round(max(0.0, b1_remaining), 2),
            "forced_equity_sale_required": not survived,
            "survival_months_runway": round(b1_initial / max(1.0, monthly_deficit), 1)
            if monthly_deficit > 0
            else 999.0,
        }

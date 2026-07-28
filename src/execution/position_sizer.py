"""Dynamic Position Sizer for Target Income Engine.

Calculates optimal contract sizing and risk allocation to target
$1,250/mo gross ($1,000/mo after-tax) income while capping drawdown risk per trade.
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class PositionSizingPlan:
    account_equity: float
    max_risk_pct: float
    max_risk_usd: float
    spread_width: float
    max_loss_per_contract: float
    recommended_contracts: int
    expected_monthly_gross: float
    expected_monthly_after_tax: float


class DynamicPositionSizer:
    """Calculates position sizing for target $1,000/mo after-tax income."""

    def __init__(
        self,
        target_after_tax_monthly: float = 1000.0,
        estimated_tax_rate: float = 0.20,
        max_risk_per_trade_pct: float = 0.05,
    ):
        self.target_after_tax_monthly = target_after_tax_monthly
        self.estimated_tax_rate = estimated_tax_rate
        self.max_risk_per_trade_pct = max_risk_per_trade_pct

    @property
    def target_gross_monthly(self) -> float:
        return self.target_after_tax_monthly / (1.0 - self.estimated_tax_rate)

    def calculate_sizing(
        self,
        account_equity: float,
        spread_width: float = 5.0,
        credit_received: float = 0.75,
    ) -> PositionSizingPlan:
        """Calculate optimal contract count based on account equity and spread parameters."""
        if account_equity <= 0.0:
            return PositionSizingPlan(
                account_equity=0.0,
                max_risk_pct=self.max_risk_per_trade_pct,
                max_risk_usd=0.0,
                spread_width=spread_width,
                max_loss_per_contract=(spread_width - credit_received) * 100.0,
                recommended_contracts=0,
                expected_monthly_gross=0.0,
                expected_monthly_after_tax=0.0,
            )

        max_loss_per_contract = max(1.0, (spread_width - credit_received) * 100.0)
        max_risk_usd = account_equity * self.max_risk_per_trade_pct

        # Recommended contract count capped by 5% risk per trade rule
        contracts = math.floor(max_risk_usd / max_loss_per_contract)
        contracts = max(1 if account_equity >= 1000.0 else 0, contracts)

        # Expected monthly return assuming 4 trades/month with 85% win rate
        expected_monthly_gross = contracts * (credit_received * 100.0) * 4 * 0.85
        expected_after_tax = expected_monthly_gross * (1.0 - self.estimated_tax_rate)

        return PositionSizingPlan(
            account_equity=account_equity,
            max_risk_pct=self.max_risk_per_trade_pct,
            max_risk_usd=max_risk_usd,
            spread_width=spread_width,
            max_loss_per_contract=max_loss_per_contract,
            recommended_contracts=contracts,
            expected_monthly_gross=round(expected_monthly_gross, 2),
            expected_monthly_after_tax=round(expected_after_tax, 2),
        )

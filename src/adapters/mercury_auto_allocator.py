"""Mercury Sub-Account Auto-Transfer & Revenue Allocation Engine.

Implements Mercury's 5-subaccount architecture (Payroll, Operating Expenses, Taxes, Savings, Profit)
to automatically route incoming revenue into tax reserves (20%), maintain safety buffers ($500),
and stream trading collateral to Alpaca Brokerage.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "data" / "mercury_subaccount_allocation_state.json"


@dataclass(frozen=True)
class SubAccountBalance:
    account_name: str  # e.g. "Taxes", "Operating Expenses", "Trading Collateral", "Profit"
    target_percentage: float
    current_balance_usd: float
    allocated_usd: float


@dataclass(frozen=True)
class MercuryAllocationPlan:
    incoming_revenue_usd: float
    tax_reserve_usd: float  # 20.0% tax rule
    safety_buffer_usd: float  # $500 minimum operating buffer
    trading_collateral_usd: float
    profit_sweep_usd: float
    allocations: list[SubAccountBalance]


class MercuryAutoAllocator:
    """Automates sub-account revenue routing and tax reserve transfers for Max Smith KDP LLC."""

    def __init__(
        self,
        tax_rate: float = 0.20,
        safety_buffer_usd: float = 500.0,
        trading_collateral_pct: float = 0.60,
    ):
        self.tax_rate = tax_rate
        self.safety_buffer_usd = safety_buffer_usd
        self.trading_collateral_pct = trading_collateral_pct

    def plan_allocation(self, incoming_revenue_usd: float, available_checking_usd: float) -> MercuryAllocationPlan:
        tax_reserve = round(incoming_revenue_usd * self.tax_rate, 2)
        remaining_revenue = max(0.0, incoming_revenue_usd - tax_reserve)

        # Calculate surplus above safety buffer
        total_available = available_checking_usd + remaining_revenue
        surplus = max(0.0, total_available - self.safety_buffer_usd)

        trading_collateral = round(surplus * self.trading_collateral_pct, 2)
        profit_sweep = round(surplus - trading_collateral, 2)

        allocations = [
            SubAccountBalance(
                account_name="Taxes (20%)",
                target_percentage=20.0,
                current_balance_usd=0.0,
                allocated_usd=tax_reserve,
            ),
            SubAccountBalance(
                account_name="Operating Expenses (Buffer)",
                target_percentage=0.0,
                current_balance_usd=available_checking_usd,
                allocated_usd=self.safety_buffer_usd,
            ),
            SubAccountBalance(
                account_name="Trading Collateral (Alpaca)",
                target_percentage=60.0,
                current_balance_usd=0.0,
                allocated_usd=trading_collateral,
            ),
            SubAccountBalance(
                account_name="Profit Sweep",
                target_percentage=20.0,
                current_balance_usd=0.0,
                allocated_usd=profit_sweep,
            ),
        ]

        return MercuryAllocationPlan(
            incoming_revenue_usd=incoming_revenue_usd,
            tax_reserve_usd=tax_reserve,
            safety_buffer_usd=self.safety_buffer_usd,
            trading_collateral_usd=trading_collateral,
            profit_sweep_usd=profit_sweep,
            allocations=allocations,
        )

    def save_allocation_state(self, plan: MercuryAllocationPlan) -> Path:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        data = asdict(plan)
        with STATE_PATH.open("w", encoding="utf-8") as h:
            json.dump(data, h, indent=2)
        logger.info("Saved Mercury auto-allocation state to %s", STATE_PATH)
        return STATE_PATH

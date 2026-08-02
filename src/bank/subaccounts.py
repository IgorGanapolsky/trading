"""Mercury Sub-Accounts & Automated Money Transfer Engine.

Implements Mercury account features from mercury.pdf:
1. Sub-accounts architecture (Operating Expenses, Taxes, Profit, Payroll, Savings).
2. Automated revenue/remittance transfer rules (e.g. 20% tax reserve, profit allocation).
3. IO Card 1.5% cashback reward routing.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
SUBACCOUNT_LOG_PATH = ROOT / "data" / "audit" / "mercury_subaccount_transfers.jsonl"


class SubAccountType(StrEnum):
    OPERATING_EXPENSES = "operating_expenses"
    TAXES = "taxes"
    PROFIT = "profit"
    PAYROLL = "payroll"
    SAVINGS = "savings"
    REVENUE_HOLDING = "revenue_holding"


@dataclass(frozen=True)
class SubAccountConfig:
    name: str
    subaccount_type: SubAccountType
    target_allocation_pct: float
    description: str


@dataclass(frozen=True)
class TransferSplitResult:
    total_amount_usd: float
    tax_reserve_usd: float
    profit_reserve_usd: float
    operating_expenses_usd: float
    tax_pct: float
    profit_pct: float
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class CashbackRewardResult:
    spend_amount_usd: float
    cashback_rate_pct: float
    cashback_earned_usd: float
    destination_subaccount: SubAccountType
    timestamp: str

    def as_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["destination_subaccount"] = self.destination_subaccount.value
        return data


class MercurySubAccountManager:
    """Manages sub-accounts, auto-transfer rules, and cashback rewards."""

    DEFAULT_SUBACCOUNTS = {
        SubAccountType.TAXES: SubAccountConfig(
            name="Taxes Reserve",
            subaccount_type=SubAccountType.TAXES,
            target_allocation_pct=20.0,  # 20% for Section 1256 index options
            description="Auto-reserved estimated tax liabilities",
        ),
        SubAccountType.PROFIT: SubAccountConfig(
            name="Profit Reserve",
            subaccount_type=SubAccountType.PROFIT,
            target_allocation_pct=10.0,
            description="Reserved for monthly $1,000/mo net after-tax target",
        ),
        SubAccountType.OPERATING_EXPENSES: SubAccountConfig(
            name="Operating Expenses",
            subaccount_type=SubAccountType.OPERATING_EXPENSES,
            target_allocation_pct=70.0,
            description="Trading capital reinvestment & operational costs",
        ),
    }

    def __init__(self, log_path: Path | None = None):
        self.log_path = log_path or SUBACCOUNT_LOG_PATH

    def calculate_auto_transfer_split(
        self,
        amount_usd: float,
        *,
        tax_pct: float = 20.0,
        profit_pct: float = 10.0,
    ) -> TransferSplitResult:
        """Calculate auto-transfer split across Taxes, Profit, and Operating Expenses."""
        if amount_usd <= 0:
            raise ValueError("Transfer amount must be positive")

        tax_reserve = round(amount_usd * (tax_pct / 100.0), 2)
        profit_reserve = round(amount_usd * (profit_pct / 100.0), 2)
        operating_exp = round(amount_usd - tax_reserve - profit_reserve, 2)

        result = TransferSplitResult(
            total_amount_usd=round(amount_usd, 2),
            tax_reserve_usd=tax_reserve,
            profit_reserve_usd=profit_reserve,
            operating_expenses_usd=operating_exp,
            tax_pct=tax_pct,
            profit_pct=profit_pct,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self._log_record("AUTO_TRANSFER_SPLIT", result.as_dict())
        return result

    def calculate_io_card_cashback(
        self,
        spend_usd: float,
        cashback_rate_pct: float = 1.5,
        destination_subaccount: SubAccountType = SubAccountType.PROFIT,
    ) -> CashbackRewardResult:
        """Calculate 1.5% IO Card cashback reward."""
        if spend_usd < 0:
            raise ValueError("Spend amount cannot be negative")

        cashback = round(spend_usd * (cashback_rate_pct / 100.0), 2)
        result = CashbackRewardResult(
            spend_amount_usd=round(spend_usd, 2),
            cashback_rate_pct=cashback_rate_pct,
            cashback_earned_usd=cashback,
            destination_subaccount=destination_subaccount,
            timestamp=datetime.now(UTC).isoformat(),
        )

        self._log_record("CASHBACK_REWARD", result.as_dict())
        return result

    def _log_record(self, event_type: str, data: dict[str, Any]) -> None:
        """Append record to audit log file."""
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            record = {"event_type": event_type, "data": data}
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record) + "\n")
        except Exception as exc:
            logger.warning("Failed to log subaccount record: %s", exc)

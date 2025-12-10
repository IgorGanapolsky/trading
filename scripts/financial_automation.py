#!/usr/bin/env python3
"""
Financial Automation Scripts

Handles automated financial operations:
1. Weekend crypto funding top-up
2. Quarterly tax withdrawal (28% of profits to high-yield savings)
3. Dynamic investment scaling based on floating P/L

Per CEO directive: No manual operations - everything automated.
"""

import json
import logging
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.alpaca_trader import AlpacaTrader

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WeekendFundingAutomation:
    """
    Automatic weekend funding top-up for crypto trading.

    Runs every Saturday 8 AM to ensure sufficient balance for weekend crypto trades.
    """

    MIN_WEEKEND_BALANCE = 150.0  # Minimum cash needed for weekend trading
    DEFAULT_TOP_UP_AMOUNT = 100.0

    def __init__(self, paper: bool = True):
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)
        self.state_file = Path("data/weekend_funding_state.json")

    def check_and_topup(self) -> dict:
        """
        Check if weekend funding is needed and initiate top-up.

        Returns:
            Dict with action taken and details
        """
        today = date.today()

        # Only run on Saturday
        if today.weekday() != 5:  # Saturday = 5
            return {
                "action": "SKIPPED",
                "reason": f"Not Saturday (today is {today.strftime('%A')})",
                "next_check": self._next_saturday().isoformat(),
            }

        # Check current balance
        try:
            account = self.trader.get_account()
            cash = float(account.get("cash", 0))
        except Exception as e:
            logger.error(f"Failed to get account balance: {e}")
            return {"action": "ERROR", "reason": str(e)}

        if cash >= self.MIN_WEEKEND_BALANCE:
            return {
                "action": "SUFFICIENT",
                "cash": cash,
                "threshold": self.MIN_WEEKEND_BALANCE,
                "message": f"Cash ${cash:.2f} >= ${self.MIN_WEEKEND_BALANCE:.2f} threshold",
            }

        # Need to top up
        top_up_needed = self.MIN_WEEKEND_BALANCE - cash + self.DEFAULT_TOP_UP_AMOUNT

        logger.info(f"Weekend top-up needed: ${top_up_needed:.2f}")

        # Log the top-up request (actual transfer would need Plaid integration)
        self._log_topup_request(cash, top_up_needed)

        return {
            "action": "TOPUP_REQUESTED",
            "current_cash": cash,
            "top_up_amount": top_up_needed,
            "target_balance": cash + top_up_needed,
            "message": f"Requested ${top_up_needed:.2f} top-up for weekend trading",
            "note": "Requires Plaid integration for automatic transfer",
        }

    def _next_saturday(self) -> date:
        """Get next Saturday's date."""
        today = date.today()
        days_until_saturday = (5 - today.weekday()) % 7
        if days_until_saturday == 0:
            days_until_saturday = 7
        return today + timedelta(days=days_until_saturday)

    def _log_topup_request(self, current_cash: float, amount: float) -> None:
        """Log top-up request for audit trail."""
        state = self._load_state()
        state["topup_requests"] = state.get("topup_requests", [])
        state["topup_requests"].append(
            {
                "date": date.today().isoformat(),
                "current_cash": current_cash,
                "amount_requested": amount,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save_state(state)

    def _load_state(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self, state: dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(state, f, indent=2)


class TaxWithdrawalAutomation:
    """
    Quarterly tax withdrawal automation.

    Every quarter, withdraws 28% of YTD profits to high-yield savings.
    Prevents the "made $50k, owe $18k, only have $15k left" nightmare.
    """

    TAX_RATE = 0.28  # 28% estimated tax rate for short-term gains
    QUARTERS = {
        1: (1, 3),  # Q1: Jan-Mar, withdraw April 1
        2: (4, 6),  # Q2: Apr-Jun, withdraw July 1
        3: (7, 9),  # Q3: Jul-Sep, withdraw October 1
        4: (10, 12),  # Q4: Oct-Dec, withdraw January 1
    }

    def __init__(self, paper: bool = True):
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)
        self.state_file = Path("data/tax_withdrawal_state.json")
        self.state = self._load_state()

    def check_quarterly_withdrawal(self) -> dict:
        """
        Check if it's time for quarterly tax withdrawal.

        Returns:
            Dict with withdrawal details
        """
        today = date.today()
        current_quarter = (today.month - 1) // 3 + 1

        # Check if already processed this quarter
        last_quarter = self.state.get("last_quarter_processed")
        if last_quarter == f"{today.year}Q{current_quarter}":
            return {
                "action": "ALREADY_PROCESSED",
                "quarter": f"{today.year}Q{current_quarter}",
                "message": "Tax withdrawal already processed this quarter",
            }

        # Only process on first day of quarter (or within first week)
        quarter_start_months = {1: 1, 2: 4, 3: 7, 4: 10}
        if today.day > 7 or today.month != quarter_start_months[current_quarter]:
            return {
                "action": "NOT_YET",
                "quarter": f"{today.year}Q{current_quarter}",
                "message": f"Not in quarterly processing window (day {today.day})",
            }

        # Calculate YTD profit
        ytd_profit = self._calculate_ytd_profit()

        if ytd_profit <= 0:
            return {
                "action": "NO_PROFIT",
                "ytd_profit": ytd_profit,
                "message": "No YTD profit - no tax withdrawal needed",
            }

        # Calculate tax withdrawal amount
        tax_amount = ytd_profit * self.TAX_RATE

        # Calculate remaining profit after previous withdrawals
        previous_withdrawals = self.state.get("ytd_withdrawals", 0)
        net_withdrawal = max(0, tax_amount - previous_withdrawals)

        if net_withdrawal <= 0:
            return {
                "action": "ALREADY_COVERED",
                "ytd_profit": ytd_profit,
                "tax_due": tax_amount,
                "previous_withdrawals": previous_withdrawals,
                "message": "Previous withdrawals already cover tax liability",
            }

        # Log withdrawal request
        self._log_withdrawal(today.year, current_quarter, ytd_profit, net_withdrawal)

        return {
            "action": "WITHDRAWAL_REQUESTED",
            "quarter": f"{today.year}Q{current_quarter}",
            "ytd_profit": ytd_profit,
            "tax_rate": self.TAX_RATE,
            "tax_due": tax_amount,
            "net_withdrawal": net_withdrawal,
            "message": f"Withdraw ${net_withdrawal:.2f} to high-yield savings for taxes",
            "note": "Transfer to Ally/Marcus HY savings at 4%+ APY",
        }

    def _calculate_ytd_profit(self) -> float:
        """Calculate Year-to-Date profit from trade history."""
        try:
            # Load system state
            state_file = Path("data/system_state.json")
            if not state_file.exists():
                return 0.0

            with open(state_file) as f:
                state = json.load(f)

            return state.get("account", {}).get("total_pl", 0.0)
        except Exception as e:
            logger.error(f"Failed to calculate YTD profit: {e}")
            return 0.0

    def _log_withdrawal(self, year: int, quarter: int, profit: float, amount: float) -> None:
        """Log tax withdrawal for audit trail."""
        self.state["last_quarter_processed"] = f"{year}Q{quarter}"
        self.state["ytd_withdrawals"] = self.state.get("ytd_withdrawals", 0) + amount
        self.state["withdrawal_history"] = self.state.get("withdrawal_history", [])
        self.state["withdrawal_history"].append(
            {
                "quarter": f"{year}Q{quarter}",
                "ytd_profit": profit,
                "amount": amount,
                "timestamp": datetime.now().isoformat(),
            }
        )
        self._save_state()

    def _load_state(self) -> dict:
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_state(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)

    def reset_ytd(self) -> None:
        """Reset YTD tracking (call on January 1)."""
        self.state["ytd_withdrawals"] = 0
        self.state["ytd_reset_date"] = date.today().isoformat()
        self._save_state()
        logger.info("YTD tax tracking reset for new year")


def run_all_automation():
    """Run all financial automation checks."""
    print("=" * 70)
    print("💰 FINANCIAL AUTOMATION")
    print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    # 1. Weekend funding check
    print("\n--- Weekend Funding Check ---")
    weekend_auto = WeekendFundingAutomation(paper=True)
    weekend_result = weekend_auto.check_and_topup()
    print(f"Action: {weekend_result['action']}")
    print(f"Details: {weekend_result.get('message', weekend_result.get('reason', 'N/A'))}")

    # 2. Tax withdrawal check
    print("\n--- Quarterly Tax Withdrawal Check ---")
    tax_auto = TaxWithdrawalAutomation(paper=True)
    tax_result = tax_auto.check_quarterly_withdrawal()
    print(f"Action: {tax_result['action']}")
    print(f"Details: {tax_result.get('message', 'N/A')}")

    # 3. Smart DCA snapshot (reference only)
    print("\n--- Smart DCA Allocation Snapshot ---")
    from src.orchestrator.smart_dca import SmartDCAAllocator

    allocator = SmartDCAAllocator()
    dca_snapshot = allocator.snapshot()
    for bucket, amount in dca_snapshot["targets"].items():
        print(f"{bucket}: ${amount:.2f}/day")
    print("ℹ️  Smart DCA enforcement now lives inside the TradingOrchestrator funnel.")

    print("\n" + "=" * 70)

    return {
        "weekend_funding": weekend_result,
        "tax_withdrawal": tax_result,
        "dca_targets": dca_snapshot["targets"],
    }


if __name__ == "__main__":
    run_all_automation()

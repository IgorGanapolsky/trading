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


class FibonacciScaler:
    """
    Auto-scale daily investment using Fibonacci sequence.

    Scale up when cumulative profit >= next Fibonacci level × 30 days

    Milestones:
    - $1/day base
    - $2/day when profit >= $60
    - $3/day when profit >= $90
    - $5/day when profit >= $150
    - $8/day when profit >= $240
    - $13/day when profit >= $390
    - $21/day when profit >= $630
    - $34/day when profit >= $1020
    - $55/day when profit >= $1650
    - $89/day when profit >= $2670
    - Cap at $100/day
    """

    # Fibonacci sequence for daily amounts (up to $100/day cap)
    FIBONACCI = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 100]
    FIBONACCI_SEQUENCE = FIBONACCI  # Backwards compatibility
    FUNDING_DAYS = 30  # Days of funding required before scale-up
    DAYS_PER_LEVEL = 30  # Backwards compatibility
    MAX_DAILY = 100.0
    MAX_DAILY_AMOUNT = 100.0  # Backwards compatibility

    def __init__(self, paper: bool = True, state_file: str = "data/fibonacci_scaling_state.json"):
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)
        self.state_file = Path(state_file)
        self.system_state_file = Path("data/system_state.json")
        self.state = self._load_state()

    def get_fibonacci_level(self, cumulative_profit: float) -> float:
        """
        Calculate current Fibonacci level based on cumulative profit.

        Args:
            cumulative_profit: Total realized + unrealized profit

        Returns:
            Current daily investment amount
        """
        # Start at level 0 ($1/day) if no profit
        if cumulative_profit <= 0:
            return self.FIBONACCI_SEQUENCE[0]

        # Find highest level we can afford
        current_level = self.FIBONACCI_SEQUENCE[0]
        for level_idx, fib_amount in enumerate(self.FIBONACCI_SEQUENCE):
            # Calculate milestone for THIS level
            milestone = fib_amount * self.DAYS_PER_LEVEL

            if cumulative_profit >= milestone:
                current_level = fib_amount
            else:
                # Can't afford this level yet
                break

        return float(current_level)

    def get_next_milestone(self, current_level: float) -> dict:
        """
        Get next Fibonacci milestone details.

        Args:
            current_level: Current daily amount

        Returns:
            Dict with next level, milestone profit needed, and progress
        """
        try:
            current_idx = self.FIBONACCI_SEQUENCE.index(int(current_level))
        except ValueError:
            # Not in sequence, start from beginning
            current_idx = 0

        # Check if at max level
        if current_idx >= len(self.FIBONACCI_SEQUENCE) - 1:
            return {
                "next_level": self.MAX_DAILY_AMOUNT,
                "milestone_profit": float('inf'),
                "current_level": current_level,
                "at_max": True,
                "message": "At maximum daily investment level",
            }

        next_level = self.FIBONACCI_SEQUENCE[current_idx + 1]
        milestone = next_level * self.DAYS_PER_LEVEL

        return {
            "next_level": float(next_level),
            "milestone_profit": float(milestone),
            "current_level": current_level,
            "at_max": False,
            "days_to_fund": self.DAYS_PER_LEVEL,
            "message": f"Need ${milestone:.2f} cumulative profit to scale to ${next_level}/day",
        }

    def should_scale_up(self, cumulative_profit: float, current_level: float) -> bool:
        """
        Check if we should scale up to next Fibonacci level.

        Args:
            cumulative_profit: Total profit to date
            current_level: Current daily investment amount

        Returns:
            True if should scale up, False otherwise
        """
        milestone_info = self.get_next_milestone(current_level)

        # Already at max?
        if milestone_info["at_max"]:
            return False

        # Have we hit the milestone?
        return cumulative_profit >= milestone_info["milestone_profit"]

    def calculate_daily_investment(self) -> dict:
        """
        Calculate today's investment using Fibonacci scaling.

        Returns:
            Dict with calculated amount, milestone info, and scaling details
        """
        try:
            # Get current account data
            account = self.trader.get_account()
            equity = float(account.get("equity", 100000))

            # Load system state for cumulative profit tracking
            state_file = Path("data/system_state.json")
            starting_balance = 100000.0
            cumulative_profit = 0.0

            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                    starting_balance = state.get("account", {}).get("starting_balance", 100000.0)
                    cumulative_profit = state.get("account", {}).get("total_pl", 0.0)

            # Get current and historical levels
            previous_level = self.state.get("current_level", 1.0)
            current_level = self.get_fibonacci_level(cumulative_profit)

            # Check if we scaled up
            scaled_up = current_level > previous_level
            if scaled_up:
                self._log_scale_up(previous_level, current_level, cumulative_profit)
                self.state["current_level"] = current_level
                self.state["last_scale_up"] = datetime.now().isoformat()
                self._save_state()

            # Get next milestone info
            milestone_info = self.get_next_milestone(current_level)
            profit_to_next = max(0, milestone_info["milestone_profit"] - cumulative_profit)
            progress_pct = (cumulative_profit / milestone_info["milestone_profit"] * 100) if not milestone_info["at_max"] else 100.0

            return {
                "daily_amount": current_level,
                "cumulative_profit": round(cumulative_profit, 2),
                "current_level": current_level,
                "previous_level": previous_level,
                "scaled_up": scaled_up,
                "next_level": milestone_info["next_level"],
                "next_milestone": milestone_info["milestone_profit"],
                "profit_to_next_level": round(profit_to_next, 2),
                "progress_to_next": round(progress_pct, 1),
                "at_max_level": milestone_info["at_max"],
                "fibonacci_sequence": self.FIBONACCI_SEQUENCE,
                "scaling_strategy": "Fibonacci Compounding (each level funded by previous profits)",
            }

        except Exception as e:
            logger.error(f"Fibonacci scaling calculation failed: {e}")
            return {
                "daily_amount": 1.0,  # Safe fallback to base level
                "error": str(e),
                "fallback_mode": True,
            }

    def _log_scale_up(self, old_level: float, new_level: float, profit: float) -> None:
        """Log scale-up event for audit trail."""
        logger.info(f"🚀 FIBONACCI SCALE-UP: ${old_level}/day → ${new_level}/day (profit: ${profit:.2f})")

        # Add to state history
        self.state["scale_up_history"] = self.state.get("scale_up_history", [])
        self.state["scale_up_history"].append({
            "timestamp": datetime.now().isoformat(),
            "old_level": old_level,
            "new_level": new_level,
            "cumulative_profit": profit,
            "milestone_hit": new_level * self.DAYS_PER_LEVEL,
        })

    # ==================== NEW CONVENIENCE API ====================
    # Simpler methods that read from state automatically
    # ============================================================

    def _get_cumulative_profit(self) -> float:
        """Get current cumulative profit from system state."""
        try:
            if self.system_state_file.exists():
                with open(self.system_state_file) as f:
                    state = json.load(f)
                    return state.get("account", {}).get("total_pl", 0.0)
        except Exception as e:
            logger.error(f"Failed to read cumulative profit: {e}")
        return 0.0

    def get_current_level(self) -> int:
        """
        Get current Fibonacci level index.

        Returns:
            Index in FIBONACCI sequence (0-10)
        """
        cumulative_profit = self._get_cumulative_profit()
        current_amount = self.get_fibonacci_level(cumulative_profit)

        try:
            return self.FIBONACCI.index(int(current_amount))
        except ValueError:
            return 0  # Default to first level

    def get_daily_amount(self) -> float:
        """
        Get current daily investment amount.

        Returns:
            Current daily investment in dollars
        """
        level = self.get_current_level()
        return float(self.FIBONACCI[level])

    def get_next_milestone(self) -> dict:
        """
        Get profit needed for next level (convenience method with no params).

        Returns:
            Dict with milestone details, reading from current state
        """
        cumulative_profit = self._get_cumulative_profit()
        level = self.get_current_level()

        # Check if at max level
        if level >= len(self.FIBONACCI) - 1:
            return {
                "at_max": True,
                "current": self.MAX_DAILY,
                "current_level": self.FIBONACCI[level],
                "current_profit": cumulative_profit,
            }

        next_fib = self.FIBONACCI[level + 1]
        required_profit = next_fib * self.FUNDING_DAYS
        remaining = max(0, required_profit - cumulative_profit)
        progress_pct = (cumulative_profit / required_profit * 100) if required_profit > 0 else 0

        return {
            "at_max": False,
            "current_level": self.FIBONACCI[level],
            "next_level": next_fib,
            "required_profit": required_profit,
            "current_profit": cumulative_profit,
            "remaining": remaining,
            "progress_pct": round(progress_pct, 1),
            "message": f"Need ${required_profit:.2f} profit to scale to ${next_fib}/day (${remaining:.2f} remaining)",
        }

    def should_scale_up(self) -> bool:
        """
        Check if ready to scale up (convenience method with no params).

        Returns:
            True if should scale up, False otherwise
        """
        milestone = self.get_next_milestone()
        if milestone.get("at_max"):
            return False
        return milestone["current_profit"] >= milestone["required_profit"]

    def scale_up(self) -> dict:
        """
        Execute scale-up and persist state.

        Returns:
            Dict with scale-up details or {scaled: False} if not ready
        """
        if not self.should_scale_up():
            milestone = self.get_next_milestone()
            return {
                "scaled": False,
                "reason": "Milestone not reached",
                "current_profit": milestone.get("current_profit", 0),
                "required_profit": milestone.get("required_profit", 0),
                "remaining": milestone.get("remaining", 0),
            }

        old_level = self.get_current_level()
        new_level = old_level + 1
        cumulative_profit = self._get_cumulative_profit()

        # Update state
        self.state["fibonacci_level"] = new_level
        self.state["current_level"] = float(self.FIBONACCI[new_level])
        self.state["last_scale_up"] = datetime.now().isoformat()

        # Log to history
        self._log_scale_up(
            float(self.FIBONACCI[old_level]),
            float(self.FIBONACCI[new_level]),
            cumulative_profit
        )

        self._save_state()

        logger.info(f"🚀 SCALED UP: ${self.FIBONACCI[old_level]}/day → ${self.FIBONACCI[new_level]}/day")

        return {
            "scaled": True,
            "old_amount": self.FIBONACCI[old_level],
            "new_amount": self.FIBONACCI[new_level],
            "old_level": old_level,
            "new_level": new_level,
            "profit_at_scale": cumulative_profit,
            "milestone_hit": self.FIBONACCI[new_level] * self.FUNDING_DAYS,
            "timestamp": datetime.now().isoformat(),
        }

    def get_projection(self, avg_daily_return_pct: float = 0.13) -> dict:
        """
        Project time to $100/day at current return rate.

        Args:
            avg_daily_return_pct: Average daily return percentage (default 0.13%)

        Returns:
            Dict with projection details including days/months to each milestone
        """
        cumulative_profit = self._get_cumulative_profit()
        current_level = self.get_current_level()
        current_amount = self.FIBONACCI[current_level]

        # Get account equity for compounding calculations
        try:
            account = self.trader.get_account()
            equity = float(account.get("equity", 100000))
        except Exception:
            equity = 100000.0  # Default fallback

        projections = []

        # Project each remaining level
        for i in range(current_level, len(self.FIBONACCI)):
            fib_amount = self.FIBONACCI[i]
            milestone_profit = fib_amount * self.FUNDING_DAYS

            # Calculate days to reach this milestone
            if i == current_level:
                days_to_milestone = 0  # Already at this level
            else:
                profit_needed = milestone_profit - cumulative_profit

                # Compound daily returns
                # P = cumulative_profit + sum(equity * daily_return for each day)
                # Simplified: assume linear growth for approximation
                avg_daily_profit = equity * (avg_daily_return_pct / 100)

                if avg_daily_profit <= 0:
                    days_to_milestone = float('inf')
                else:
                    days_to_milestone = int(profit_needed / avg_daily_profit)

            projections.append({
                "level_index": i,
                "daily_amount": fib_amount,
                "milestone_profit": milestone_profit,
                "days_from_now": days_to_milestone,
                "months_from_now": round(days_to_milestone / 30, 1),
                "date_estimate": (datetime.now() + timedelta(days=days_to_milestone)).strftime("%Y-%m-%d") if days_to_milestone < 3650 else "Beyond 10 years",
            })

        # Find $100/day milestone
        max_level_idx = len(self.FIBONACCI) - 1
        max_projection = projections[max_level_idx - current_level] if max_level_idx >= current_level else projections[-1]

        return {
            "current_level": current_amount,
            "current_profit": cumulative_profit,
            "avg_daily_return_pct": avg_daily_return_pct,
            "current_equity": equity,
            "days_to_max": max_projection["days_from_now"],
            "months_to_max": max_projection["months_from_now"],
            "date_at_max": max_projection["date_estimate"],
            "max_daily_amount": self.MAX_DAILY,
            "milestones": projections,
            "note": f"Assumes {avg_daily_return_pct}% daily return (compounding). Actual timeline may vary.",
        }

    # ==================== END CONVENIENCE API ====================

    def _load_state(self) -> dict:
        """Load Fibonacci scaling state."""
        if not self.state_file.exists():
            return {"current_level": 1.0, "scale_up_history": []}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception:
            return {"current_level": 1.0, "scale_up_history": []}

    def _save_state(self) -> None:
        """Save Fibonacci scaling state."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.state, f, indent=2)


class DynamicInvestmentScaler:
    """
    LEGACY: Linear scaling based on floating P/L.

    DEPRECATED: Use FibonacciScaler for profit-based compounding strategy.
    Kept for backward compatibility only.
    """

    BASE_DAILY_AMOUNT = 10.0
    PNL_SCALING_FACTOR = 0.30  # 30% of floating P/L added to base
    MAX_DAILY_AMOUNT = 50.0
    MIN_DAILY_AMOUNT = 5.0  # Floor even in drawdown

    def __init__(self, paper: bool = True):
        self.paper = paper
        self.trader = AlpacaTrader(paper=paper)
        logger.warning("DynamicInvestmentScaler is DEPRECATED. Use FibonacciScaler instead.")

    def calculate_daily_investment(self) -> dict:
        """
        Calculate today's investment amount based on floating P/L.

        Returns:
            Dict with calculated amount and breakdown
        """
        try:
            account = self.trader.get_account()
            equity = float(account.get("equity", 100000))

            # Load starting balance from system state
            state_file = Path("data/system_state.json")
            starting_balance = 100000.0
            if state_file.exists():
                with open(state_file) as f:
                    state = json.load(f)
                    starting_balance = state.get("account", {}).get("starting_balance", 100000.0)

            floating_pnl = equity - starting_balance

        except Exception as e:
            logger.error(f"Failed to get account data: {e}")
            return {
                "daily_amount": self.BASE_DAILY_AMOUNT,
                "error": str(e),
            }

        # Calculate scaled amount
        # daily = min(10 + 0.3 * floating_pnl, 50)
        scaled_amount = self.BASE_DAILY_AMOUNT + (self.PNL_SCALING_FACTOR * floating_pnl)

        # Apply floor and ceiling
        daily_amount = max(self.MIN_DAILY_AMOUNT, min(scaled_amount, self.MAX_DAILY_AMOUNT))

        return {
            "daily_amount": round(daily_amount, 2),
            "base_amount": self.BASE_DAILY_AMOUNT,
            "floating_pnl": round(floating_pnl, 2),
            "scaling_factor": self.PNL_SCALING_FACTOR,
            "pre_cap_amount": round(scaled_amount, 2),
            "min_amount": self.MIN_DAILY_AMOUNT,
            "max_amount": self.MAX_DAILY_AMOUNT,
            "formula": f"min(${self.BASE_DAILY_AMOUNT} + 0.3 × ${floating_pnl:.2f}, ${self.MAX_DAILY_AMOUNT})",
            "deprecated": True,
            "use_instead": "FibonacciScaler",
        }


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

    # 3. Fibonacci-based daily investment scaling
    print("\n--- Daily Investment Calculation (Fibonacci Scaling) ---")
    fib_scaler = FibonacciScaler(paper=True)

    # Use new convenience API
    current_level = fib_scaler.get_current_level()
    daily_amount = fib_scaler.get_daily_amount()
    milestone = fib_scaler.get_next_milestone()
    should_scale = fib_scaler.should_scale_up()

    print(f"💎 Today's Investment: ${daily_amount:.2f}/day")
    print(f"📊 Current Profit: ${milestone.get('current_profit', 0):.2f}")
    print(f"📈 Current Level: Level {current_level} (${daily_amount:.0f}/day)")

    if not milestone.get('at_max'):
        print(f"🎯 Next Level: ${milestone['next_level']:.0f}/day")
        print(f"🏆 Next Milestone: ${milestone['required_profit']:.2f} profit")
        print(f"🚀 Progress: {milestone['progress_pct']:.1f}% (${milestone['remaining']:.2f} to go)")
        print(f"✅ Ready to Scale: {'YES' if should_scale else 'NO'}")

        if should_scale:
            print("\n⚡ AUTO-SCALING TRIGGERED!")
            scale_result = fib_scaler.scale_up()
            if scale_result['scaled']:
                print(f"✨ SCALED UP: ${scale_result['old_amount']:.0f} → ${scale_result['new_amount']:.0f}/day")
                print(f"🎉 Milestone Hit: ${scale_result['milestone_hit']:.2f} profit")
    else:
        print("🏁 AT MAXIMUM LEVEL: $100/day (safety cap)")

    # Show projection to $100/day
    print("\n--- Projection to $100/day Goal ---")
    try:
        projection = fib_scaler.get_projection(avg_daily_return_pct=0.13)
        print(f"📅 Days to $100/day: {projection['days_to_max']}")
        print(f"📆 Months to $100/day: {projection['months_to_max']:.1f}")
        print(f"🗓️  Estimated Date: {projection['date_at_max']}")
        print(f"💡 Assumption: {projection['avg_daily_return_pct']:.2f}% daily return")
    except Exception as e:
        print(f"⚠️  Projection unavailable: {e}")

    # 4. Legacy comparison (optional)
    print("\n--- Legacy Linear Scaling (for comparison) ---")
    legacy_scaler = DynamicInvestmentScaler(paper=True)
    legacy_result = legacy_scaler.calculate_daily_investment()
    print(f"Legacy Method: ${legacy_result['daily_amount']:.2f}/day")
    print(f"Floating P/L: ${legacy_result.get('floating_pnl', 0):.2f}")
    print(f"⚠️  Note: This method is DEPRECATED. Use Fibonacci scaling above.")

    print("\n" + "=" * 70)

    return {
        "weekend_funding": weekend_result,
        "tax_withdrawal": tax_result,
        "fibonacci_investment": fib_result,
        "legacy_investment": legacy_result,
    }


if __name__ == "__main__":
    run_all_automation()

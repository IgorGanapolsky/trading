"""
Stock Lending Income Module - Alpaca Fully Paid Securities Lending (FPSL)

Tracks and monitors stock lending income from Alpaca's FPSL program.
Users earn passive income by lending their shares to institutions.

Key Features:
- Check enrollment status
- Estimate potential lending income
- Track actual lending income
- Monitor which securities are on loan

References:
- https://alpaca.markets/blog/unlock-passive-income-with-alpacas-stock-lending-program-for-trading-api/
- https://docs.alpaca.markets/docs/fully-paid-securities-lending

Author: Trading System CTO
Created: 2025-12-09
"""

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# Load environment variables
try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

ALPACA_API_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET_KEY = os.getenv("ALPACA_SECRET_KEY")

# Common high-demand stocks for lending (typically hard-to-borrow stocks)
HIGH_DEMAND_TICKERS = {
    "GME",
    "AMC",
    "TSLA",
    "RIVN",
    "LCID",
    "NVDA",
    "PLTR",
    "SOFI",
    "COIN",
    "HOOD",
    "MARA",
    "RIOT",
    "BITO",
    "ARKK",
    "SQQQ",
    "TQQQ",
}

# Estimated lending rates by demand tier (annual %)
LENDING_RATES = {
    "high_demand": 15.0,  # Hard-to-borrow stocks
    "medium_demand": 5.0,  # Popular but available
    "low_demand": 1.0,  # General stocks
}

# Alpaca revenue share (Elite: 50%, Standard: 20%)
ALPACA_ELITE_SHARE = 0.50
ALPACA_STANDARD_SHARE = 0.20


@dataclass
class LendingPosition:
    """Represents a position available or currently on loan."""

    symbol: str
    quantity: float
    market_value: float
    estimated_rate: float  # Annual rate %
    is_on_loan: bool
    estimated_daily_income: float
    estimated_annual_income: float


@dataclass
class LendingIncomeSummary:
    """Summary of stock lending income potential and actuals."""

    total_lendable_value: float
    total_estimated_daily_income: float
    total_estimated_annual_income: float
    positions_count: int
    high_demand_count: int
    is_enrolled: bool
    enrollment_date: Optional[datetime]
    total_earned_to_date: float
    last_payment_date: Optional[datetime]
    last_payment_amount: float


class StockLendingTracker:
    """
    Tracks stock lending income from Alpaca's FPSL program.

    Usage:
        tracker = StockLendingTracker()
        summary = tracker.get_income_summary()
        print(f"Estimated annual income: ${summary.total_estimated_annual_income:.2f}")
    """

    def __init__(self, is_elite: bool = False, paper_trading: bool = True):
        """
        Initialize the stock lending tracker.

        Args:
            is_elite: Whether user has Alpaca Elite status (50% vs 20% share)
            paper_trading: Whether using paper trading (lending not available)
        """
        self.is_elite = is_elite
        self.revenue_share = ALPACA_ELITE_SHARE if is_elite else ALPACA_STANDARD_SHARE
        self.paper_trading = paper_trading
        self.client = None
        self._init_client()

        # State tracking
        self.state_file = Path(__file__).parent.parent.parent / "data" / "lending_state.json"
        self.lending_state = self._load_state()

    def _init_client(self) -> None:
        """Initialize Alpaca trading client."""
        if not ALPACA_API_KEY or not ALPACA_SECRET_KEY:
            print("Warning: Alpaca credentials not found")
            return

        try:
            from alpaca.trading.client import TradingClient

            self.client = TradingClient(ALPACA_API_KEY, ALPACA_SECRET_KEY, paper=self.paper_trading)
        except ImportError:
            print("Warning: alpaca-py not installed")
        except Exception as e:
            print(f"Warning: Failed to init Alpaca client: {e}")

    def _load_state(self) -> dict:
        """Load lending state from file."""
        if self.state_file.exists():
            try:
                with open(self.state_file) as f:
                    return json.load(f)
            except Exception:
                pass
        return {
            "is_enrolled": False,
            "enrollment_date": None,
            "total_earned": 0.0,
            "payments": [],
            "last_updated": None,
        }

    def _save_state(self) -> None:
        """Save lending state to file."""
        self.lending_state["last_updated"] = datetime.now().isoformat()
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.state_file, "w") as f:
            json.dump(self.lending_state, f, indent=2)

    def _estimate_lending_rate(self, symbol: str) -> float:
        """
        Estimate the lending rate for a symbol based on demand.

        High-demand stocks (hard-to-borrow) can command 15%+ rates.
        Regular stocks typically earn 1-5%.
        """
        if symbol.upper() in HIGH_DEMAND_TICKERS:
            return LENDING_RATES["high_demand"]
        # Could add more sophisticated logic here based on:
        # - Short interest data
        # - Borrow availability
        # - Market conditions
        return LENDING_RATES["low_demand"]

    def get_lendable_positions(self) -> list[LendingPosition]:
        """
        Get all positions that could potentially be lent.

        Returns list of positions with estimated lending income.
        """
        if not self.client:
            return []

        try:
            positions = self.client.get_all_positions()
        except Exception as e:
            print(f"Error fetching positions: {e}")
            return []

        lendable = []
        for pos in positions:
            symbol = pos.symbol
            quantity = float(pos.qty)
            market_value = float(pos.market_value)

            # Estimate lending rate
            annual_rate = self._estimate_lending_rate(symbol)

            # Apply revenue share
            effective_rate = annual_rate * self.revenue_share

            # Calculate estimated income
            estimated_annual = market_value * (effective_rate / 100)
            estimated_daily = estimated_annual / 365

            lendable.append(
                LendingPosition(
                    symbol=symbol,
                    quantity=quantity,
                    market_value=market_value,
                    estimated_rate=effective_rate,
                    is_on_loan=False,  # Would need actual loan status from API
                    estimated_daily_income=estimated_daily,
                    estimated_annual_income=estimated_annual,
                )
            )

        return lendable

    def get_income_summary(self) -> LendingIncomeSummary:
        """
        Get a summary of stock lending income potential.

        Returns comprehensive summary including:
        - Total lendable value
        - Estimated daily/annual income
        - Enrollment status
        - Historical earnings
        """
        positions = self.get_lendable_positions()

        total_value = sum(p.market_value for p in positions)
        total_daily = sum(p.estimated_daily_income for p in positions)
        total_annual = sum(p.estimated_annual_income for p in positions)
        high_demand = sum(1 for p in positions if p.symbol in HIGH_DEMAND_TICKERS)

        # Parse enrollment date
        enrollment_date = None
        if self.lending_state.get("enrollment_date"):
            try:
                enrollment_date = datetime.fromisoformat(self.lending_state["enrollment_date"])
            except ValueError:
                pass

        # Get last payment info
        last_payment_date = None
        last_payment_amount = 0.0
        if self.lending_state.get("payments"):
            last_payment = self.lending_state["payments"][-1]
            try:
                last_payment_date = datetime.fromisoformat(last_payment.get("date", ""))
                last_payment_amount = float(last_payment.get("amount", 0))
            except (ValueError, TypeError):
                pass

        return LendingIncomeSummary(
            total_lendable_value=total_value,
            total_estimated_daily_income=total_daily,
            total_estimated_annual_income=total_annual,
            positions_count=len(positions),
            high_demand_count=high_demand,
            is_enrolled=self.lending_state.get("is_enrolled", False),
            enrollment_date=enrollment_date,
            total_earned_to_date=self.lending_state.get("total_earned", 0.0),
            last_payment_date=last_payment_date,
            last_payment_amount=last_payment_amount,
        )

    def enroll_in_program(self) -> bool:
        """
        Enroll in Alpaca's stock lending program.

        Note: This is a placeholder - actual enrollment requires:
        1. Account to be live (not paper trading)
        2. Agreement acceptance through Alpaca dashboard
        3. API enrollment endpoint (if available)

        Returns True if enrollment was successful/recorded.
        """
        if self.paper_trading:
            print("Stock lending not available in paper trading mode")
            print("Switch to live trading to enable stock lending income")
            return False

        # Record enrollment intent - actual enrollment through Alpaca dashboard
        self.lending_state["is_enrolled"] = True
        self.lending_state["enrollment_date"] = datetime.now().isoformat()
        self._save_state()

        print("Enrollment recorded. Complete enrollment at:")
        print("https://app.alpaca.markets/paper/dashboard/overview")
        return True

    def record_payment(self, amount: float, date: Optional[datetime] = None) -> None:
        """
        Record a lending income payment (for manual tracking until API available).

        Args:
            amount: Payment amount in USD
            date: Payment date (defaults to now)
        """
        if date is None:
            date = datetime.now()

        payment = {"date": date.isoformat(), "amount": amount}

        if "payments" not in self.lending_state:
            self.lending_state["payments"] = []

        self.lending_state["payments"].append(payment)
        self.lending_state["total_earned"] = sum(
            p.get("amount", 0) for p in self.lending_state["payments"]
        )
        self._save_state()

        print(f"Recorded lending payment: ${amount:.2f}")
        print(f"Total earned to date: ${self.lending_state['total_earned']:.2f}")

    def generate_report(self) -> str:
        """
        Generate a human-readable stock lending income report.

        Returns formatted string report.
        """
        summary = self.get_income_summary()
        positions = self.get_lendable_positions()

        lines = [
            "=" * 60,
            "STOCK LENDING INCOME REPORT",
            "=" * 60,
            f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"Account Type: {'Paper Trading' if self.paper_trading else 'Live'}",
            f"Revenue Share: {self.revenue_share * 100:.0f}% ({'Elite' if self.is_elite else 'Standard'})",
            "",
            "ENROLLMENT STATUS",
            "-" * 40,
            f"  Enrolled: {'Yes' if summary.is_enrolled else 'No'}",
        ]

        if summary.enrollment_date:
            lines.append(f"  Enrollment Date: {summary.enrollment_date.strftime('%Y-%m-%d')}")

        lines.extend(
            [
                "",
                "INCOME SUMMARY",
                "-" * 40,
                f"  Total Lendable Value: ${summary.total_lendable_value:,.2f}",
                f"  Positions: {summary.positions_count}",
                f"  High-Demand Stocks: {summary.high_demand_count}",
                "",
                f"  Estimated Daily Income: ${summary.total_estimated_daily_income:.2f}",
                f"  Estimated Monthly Income: ${summary.total_estimated_daily_income * 30:.2f}",
                f"  Estimated Annual Income: ${summary.total_estimated_annual_income:.2f}",
                "",
                f"  Total Earned to Date: ${summary.total_earned_to_date:.2f}",
            ]
        )

        if summary.last_payment_date:
            lines.append(
                f"  Last Payment: ${summary.last_payment_amount:.2f} on {summary.last_payment_date.strftime('%Y-%m-%d')}"
            )

        if positions:
            lines.extend(
                [
                    "",
                    "LENDABLE POSITIONS",
                    "-" * 40,
                    f"  {'Symbol':<8} {'Qty':>10} {'Value':>12} {'Rate':>8} {'Est. Annual':>12}",
                ]
            )

            for pos in sorted(positions, key=lambda p: p.estimated_annual_income, reverse=True)[
                :10
            ]:
                demand = "HD" if pos.symbol in HIGH_DEMAND_TICKERS else ""
                lines.append(
                    f"  {pos.symbol:<8} {pos.quantity:>10.2f} ${pos.market_value:>10,.2f} "
                    f"{pos.estimated_rate:>6.2f}% ${pos.estimated_annual_income:>10,.2f} {demand}"
                )

        if self.paper_trading:
            lines.extend(
                [
                    "",
                    "NOTE: Stock lending requires a live trading account.",
                    "Switch to live trading to earn passive income from your holdings.",
                ]
            )

        lines.append("=" * 60)

        return "\n".join(lines)


def get_lending_income_for_report() -> dict:
    """
    Get lending income data for inclusion in daily trading report.

    Returns dict with key metrics for the report.
    """
    tracker = StockLendingTracker(is_elite=False, paper_trading=True)
    summary = tracker.get_income_summary()

    return {
        "enrolled": summary.is_enrolled,
        "lendable_value": summary.total_lendable_value,
        "estimated_daily_income": summary.total_estimated_daily_income,
        "estimated_annual_income": summary.total_estimated_annual_income,
        "total_earned": summary.total_earned_to_date,
        "positions_count": summary.positions_count,
        "high_demand_count": summary.high_demand_count,
        "note": "Stock lending available when live trading enabled",
    }


if __name__ == "__main__":
    # Demo usage
    tracker = StockLendingTracker(is_elite=False, paper_trading=True)
    print(tracker.generate_report())

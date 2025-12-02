#!/usr/bin/env python3
"""
Demo Fibonacci Scaling with Current System State

Shows how the Fibonacci scaling would work with current profit levels.
"""

import json
from pathlib import Path


class FibonacciScalerDemo:
    """Demo version of FibonacciScaler using system_state.json data."""

    FIBONACCI_SEQUENCE = [1, 2, 3, 5, 8, 13, 21, 34, 55, 89, 100]
    DAYS_PER_LEVEL = 30
    MAX_DAILY_AMOUNT = 100.0

    def __init__(self):
        self.state_file = Path("data/system_state.json")

    def get_fibonacci_level(self, cumulative_profit: float) -> float:
        """Calculate current Fibonacci level based on cumulative profit."""
        if cumulative_profit <= 0:
            return self.FIBONACCI_SEQUENCE[0]

        current_level = self.FIBONACCI_SEQUENCE[0]
        for fib_amount in self.FIBONACCI_SEQUENCE:
            milestone = fib_amount * self.DAYS_PER_LEVEL
            if cumulative_profit >= milestone:
                current_level = fib_amount
            else:
                break

        return float(current_level)

    def get_next_milestone(self, current_level: float) -> dict:
        """Get next Fibonacci milestone details."""
        try:
            current_idx = self.FIBONACCI_SEQUENCE.index(int(current_level))
        except ValueError:
            current_idx = 0

        if current_idx >= len(self.FIBONACCI_SEQUENCE) - 1:
            return {
                "next_level": self.MAX_DAILY_AMOUNT,
                "milestone_profit": float('inf'),
                "current_level": current_level,
                "at_max": True,
            }

        next_level = self.FIBONACCI_SEQUENCE[current_idx + 1]
        milestone = next_level * self.DAYS_PER_LEVEL

        return {
            "next_level": float(next_level),
            "milestone_profit": float(milestone),
            "current_level": current_level,
            "at_max": False,
        }

    def run_demo(self):
        """Run demo with current system state."""
        print("=" * 70)
        print("FIBONACCI SCALING - CURRENT STATE DEMO")
        print("=" * 70)

        # Load system state
        if not self.state_file.exists():
            print(f"\n⚠️  Error: {self.state_file} not found")
            return

        with open(self.state_file) as f:
            state = json.load(f)

        # Get current profit
        cumulative_profit = state.get("account", {}).get("total_pl", 0.0)
        current_equity = state.get("account", {}).get("current_equity", 0.0)
        starting_balance = state.get("account", {}).get("starting_balance", 100000.0)

        print(f"\n📊 Current Account Status:")
        print(f"  Starting Balance: ${starting_balance:,.2f}")
        print(f"  Current Equity: ${current_equity:,.2f}")
        print(f"  Cumulative P/L: ${cumulative_profit:,.2f}")

        # Calculate Fibonacci level
        current_level = self.get_fibonacci_level(cumulative_profit)
        milestone_info = self.get_next_milestone(current_level)

        print(f"\n💎 Fibonacci Scaling Analysis:")
        print(f"  Current Level: ${current_level:.0f}/day")
        print(f"  Next Level: ${milestone_info['next_level']:.0f}/day")
        print(f"  Next Milestone: ${milestone_info['milestone_profit']:.2f} profit needed")

        if not milestone_info['at_max']:
            profit_needed = milestone_info['milestone_profit'] - cumulative_profit
            progress_pct = (cumulative_profit / milestone_info['milestone_profit']) * 100 if cumulative_profit > 0 else 0

            print(f"  Progress: {progress_pct:.1f}%")
            print(f"  Profit Needed: ${profit_needed:.2f}")
        else:
            print(f"  Status: 🏁 AT MAXIMUM LEVEL")

        # Show roadmap
        print(f"\n🗺️  Fibonacci Roadmap (from current level):")
        print(f"{'Level':<8} {'Daily $':<12} {'Milestone $':<15} {'Status':<20}")
        print("-" * 60)

        for i, fib in enumerate(self.FIBONACCI_SEQUENCE):
            milestone = fib * self.DAYS_PER_LEVEL

            if fib < current_level:
                status = "✅ Completed"
            elif fib == current_level:
                status = "📍 Current Level"
            else:
                status = f"🎯 Need ${milestone:.2f}"

            print(f"{i+1:<8} ${fib:<11.0f} ${milestone:<14.2f} {status:<20}")

        # Show example scaling projection
        print(f"\n📈 Scaling Projection (if 10% monthly returns):")
        print(f"{'Month':<8} {'Profit $':<12} {'Daily Amount':<15} {'Monthly Invest':<15}")
        print("-" * 60)

        starting = starting_balance
        monthly_return = 0.10  # 10% monthly return assumption

        for month in range(1, 13):
            profit = (starting * monthly_return) * month  # Simplified cumulative
            level = self.get_fibonacci_level(profit)
            monthly_invest = level * 21  # ~21 trading days/month

            print(f"{month:<8} ${profit:<11.2f} ${level:<14.0f} ${monthly_invest:<14.2f}")

        print("\n" + "=" * 70)
        print("Note: This is based on Fibonacci compounding strategy.")
        print("Each level is funded ONLY by actual profits from previous levels.")
        print("=" * 70)


if __name__ == "__main__":
    demo = FibonacciScalerDemo()
    demo.run_demo()

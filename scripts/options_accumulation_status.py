#!/usr/bin/env python3
"""
Options Accumulation Status Report

Shows current progress toward options trading threshold.
"""

import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))

from src.strategies.options_accumulation_strategy import OptionsAccumulationStrategy

load_dotenv()


def main():
    print("=" * 80)
    print("📊 OPTIONS ACCUMULATION STATUS REPORT")
    print("=" * 80)
    print()

    try:
        # Initialize strategy
        strategy = OptionsAccumulationStrategy(paper=True)

        # Get status
        status = strategy.get_current_status()

        if status.get("status") == "error":
            print(f"❌ Error: {status.get('error')}")
            return

        # Display status
        print(f"🎯 Target Symbol: {status['target_symbol']}")
        print(f"📈 Target Shares: {status['target_shares']}")
        print(f"💰 Daily Investment: ${status['daily_amount']:.2f}")
        print()

        print("📊 CURRENT STATUS:")
        print(f"   Current Shares: {status['current_shares']:.4f}")
        print(f"   Current Price: ${status['current_price']:.2f}")
        print(f"   Position Value: ${status['position_value']:.2f}")
        print()

        if status["status"] == "complete":
            print("✅ TARGET REACHED!")
            print(f"   You have {status['current_shares']:.2f} shares")
            print("   Covered calls can now be activated")
        else:
            print("⏳ ACCUMULATING:")
            print(f"   Shares Needed: {status['shares_needed']:.4f}")
            print(f"   Cost to Target: ${status['cost_to_target']:,.2f}")
            print(
                f"   Days to Target: {status['days_to_target']:.0f} days ({status['days_to_target'] / 365:.1f} years)"
            )
            print(f"   Progress: {status['progress_pct']:.1f}%")
            print()

            # Calculate milestones
            milestones = [10, 25, 50, 75, 90]
            print("🎯 MILESTONES:")
            for milestone in milestones:
                if status["progress_pct"] < milestone:
                    shares_at_milestone = (milestone / 100) * status["target_shares"]
                    shares_needed = max(0, shares_at_milestone - status["current_shares"])
                    cost = shares_needed * status["current_price"]
                    days = cost / status["daily_amount"] if status["daily_amount"] > 0 else 0
                    print(
                        f"   {milestone}% ({shares_at_milestone:.1f} shares): {days:.0f} days (${cost:,.2f})"
                    )

        print()
        print("=" * 80)

        # Show expected income once active
        if status["status"] == "complete" or status["progress_pct"] > 50:
            print()
            print("💰 EXPECTED INCOME (Once Active):")
            position_value = (
                status["position_value"]
                if status["status"] == "complete"
                else status["target_shares"] * status["current_price"]
            )
            monthly_premium = position_value * 0.01  # 1% monthly estimate
            annual_yield = (monthly_premium * 12) / position_value * 100
            print(f"   Position Value: ${position_value:,.2f}")
            print(f"   Monthly Premium: ~${monthly_premium:.2f}")
            print(f"   Annual Yield: ~{annual_yield:.1f}%")
            print(f"   Daily Income: ~${monthly_premium / 30:.2f}/day")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

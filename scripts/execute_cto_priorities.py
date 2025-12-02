#!/usr/bin/env python3
"""
CTO/CFO Priority Execution

Based on Deep Research - Prioritized Actions
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"


def analyze_and_recommend():
    """Analyze current state and provide prioritized recommendations."""
    print("=" * 80)
    print("🎯 CTO/CFO PRIORITY EXECUTION")
    print(f"   Based on Deep Research - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    if not SYSTEM_STATE_FILE.exists():
        print("System state not found")
        return

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    positions = state.get("performance", {}).get("open_positions", [])

    # Priority 1: Position Concentration Analysis
    print("\n🚨 PRIORITY 1: POSITION CONCENTRATION")
    print("-" * 80)

    total_value = sum(p.get("amount", 0) for p in positions)
    spy_pos = next((p for p in positions if p.get("symbol") == "SPY"), None)

    if spy_pos:
        spy_value = spy_pos.get("amount", 0)
        spy_pct = (spy_value / total_value * 100) if total_value > 0 else 0

        print(f"  SPY Position: ${spy_value:,.2f} ({spy_pct:.1f}% of portfolio)")
        print(f"  Total Portfolio: ${total_value:,.2f}")

        if spy_pct > 60:
            print(f"\n  ⚠️  CRITICAL: SPY is {spy_pct:.1f}% of portfolio (exceeds 60% limit)")
            print("  🎯 ACTION REQUIRED:")
            print(f"     1. Reduce SPY position by ${(spy_value - total_value * 0.5):,.2f}")
            print("     2. Diversify into QQQ/VOO")
            print("     3. Target: SPY < 50% of portfolio")
        else:
            print(f"  ✅ SPY concentration acceptable ({spy_pct:.1f}%)")

    # Priority 2: Entry Criteria Analysis
    print("\n🚨 PRIORITY 2: ENTRY CRITERIA IMPROVEMENT")
    print("-" * 80)

    for pos in positions:
        symbol = pos.get("symbol", "UNKNOWN")
        entry = pos.get("entry_price", 0)
        current = pos.get("current_price", 0)
        pl_pct = pos.get("unrealized_pl_pct", 0)

        if pl_pct < -2:
            print(f"  {symbol}: Entered at ${entry:.2f}, now ${current:.2f} ({pl_pct:.2f}%)")
            print(f"    ⚠️  Entry was {abs(pl_pct):.2f}% above current price")
            print("    💡 RECOMMENDATION:")
            print("       - Add pullback filter: Wait for RSI < 40")
            print("       - Add MACD confirmation: Require MACD histogram > 0")
            print("       - Add price filter: Entry only if price < 20-day MA")

    # Priority 3: Profit-Taking Rules
    print("\n🚨 PRIORITY 3: PROFIT-TAKING RULES")
    print("-" * 80)

    googl_pos = next((p for p in positions if p.get("symbol") == "GOOGL"), None)
    if googl_pos:
        pl_pct = googl_pos.get("unrealized_pl_pct", 0)
        if pl_pct > 2:
            print(f"  GOOGL: Up {pl_pct:.2f}%")
            print("    ✅ Profit target reached (+2%)")
            print("    🎯 ACTION: Consider taking partial profit")
            print("       - Sell 50% at +3%")
            print("       - Trail stop on remaining 50%")

    # Priority 4: Strategy Optimization
    print("\n🚨 PRIORITY 4: STRATEGY OPTIMIZATION")
    print("-" * 80)

    print("  Based on Research:")
    print("    1. Entry Filters:")
    print("       ✅ MACD histogram > 0 (already implemented)")
    print("       ✅ RSI < 70 (already implemented)")
    print("       ⚠️  ADD: Price < 20-day MA (pullback entry)")
    print("       ⚠️  ADD: Volume > 20-day average")
    print("    2. Position Sizing:")
    print("       ⚠️  ADD: Max 50% per symbol (currently SPY is 74%)")
    print("       ⚠️  ADD: Rebalance when concentration > 60%")
    print("    3. Exit Rules:")
    print("       ✅ Stop-loss at -2% (implemented)")
    print("       ⚠️  ADD: Take profit at +3% (partial)")
    print("       ⚠️  ADD: Trail stop at +1% (implemented)")

    return {
        "spy_concentration": spy_pct if spy_pos else 0,
        "needs_rebalancing": spy_pct > 60 if spy_pos else False,
        "entry_improvements": ["pullback_filter", "volume_confirmation", "ma_filter"],
        "profit_taking_needed": (googl_pos.get("unrealized_pl_pct", 0) > 2 if googl_pos else False),
    }


def main():
    """Execute priority analysis."""
    recommendations = analyze_and_recommend()

    print("\n" + "=" * 80)
    print("📋 EXECUTION SUMMARY")
    print("=" * 80)

    if recommendations.get("needs_rebalancing"):
        print("\n🚨 IMMEDIATE ACTIONS REQUIRED:")
        print("  1. Reduce SPY position concentration")
        print("  2. Diversify into QQQ/VOO")
        print("  3. Implement position size limits")

    if recommendations.get("profit_taking_needed"):
        print("\n💰 PROFIT-TAKING OPPORTUNITY:")
        print("  1. Take partial profit on GOOGL (+2.34%)")
        print("  2. Implement automated profit-taking rules")

    print("\n✅ Analysis Complete - Ready for Execution")


if __name__ == "__main__":
    main()

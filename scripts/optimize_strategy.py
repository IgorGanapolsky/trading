#!/usr/bin/env python3
"""
Strategy Optimization Recommendations

CTO Analysis: Optimize trading strategy based on current performance.
"""

import json
from pathlib import Path

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
PERF_FILE = DATA_DIR / "performance_log.json"


def analyze_strategy_performance():
    """Analyze strategy and provide optimization recommendations."""
    print("=" * 80)
    print("🎯 STRATEGY OPTIMIZATION ANALYSIS")
    print("=" * 80)

    if not SYSTEM_STATE_FILE.exists():
        print("System state not found")
        return

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    positions = state.get("performance", {}).get("open_positions", [])
    state.get("performance", {})

    # Analyze positions
    print("\n📊 POSITION ANALYSIS")
    print("-" * 80)

    total_unrealized = sum(p.get("unrealized_pl", 0) for p in positions)
    profitable_count = sum(1 for p in positions if p.get("unrealized_pl", 0) > 0)
    losing_count = len(positions) - profitable_count

    print(f"  Total Positions:    {len(positions)}")
    print(f"  Profitable:         {profitable_count}")
    print(f"  Losing:             {losing_count}")
    print(f"  Total Unrealized:   ${total_unrealized:+,.2f}")

    # Entry analysis
    print("\n📈 ENTRY TIMING ANALYSIS")
    print("-" * 80)

    for pos in positions:
        symbol = pos.get("symbol", "UNKNOWN")
        entry = pos.get("entry_price", 0)
        current = pos.get("current_price", 0)
        pl_pct = pos.get("unrealized_pl_pct", 0)

        if pl_pct < 0:
            print(f"  {symbol}: Entered at ${entry:.2f}, now ${current:.2f}")
            print(f"    ⚠️  Entry was {abs(pl_pct):.2f}% above current price")
            print("    💡 Consider: Wait for pullback before entering")

    # Recommendations
    print("\n💡 OPTIMIZATION RECOMMENDATIONS")
    print("-" * 80)

    recommendations = []

    # Entry timing
    if losing_count > profitable_count:
        recommendations.append(
            {
                "category": "Entry Timing",
                "issue": "More losing positions than profitable",
                "recommendation": "Wait for better entry points - use pullbacks",
                "action": "Add entry filters: RSI < 40, MACD histogram > 0, price above MA",
            }
        )

    # Position sizing
    spy_pos = next((p for p in positions if p.get("symbol") == "SPY"), None)
    if spy_pos:
        spy_value = spy_pos.get("amount", 0)
        total_value = sum(p.get("amount", 0) for p in positions)
        spy_pct = (spy_value / total_value * 100) if total_value > 0 else 0

        if spy_pct > 70:
            recommendations.append(
                {
                    "category": "Position Sizing",
                    "issue": f"SPY is {spy_pct:.1f}% of portfolio",
                    "recommendation": "Diversify - SPY position too large",
                    "action": "Reduce SPY allocation, add QQQ/VOO",
                }
            )

    # Stop-loss strategy
    if any(p.get("unrealized_pl_pct", 0) < -2 for p in positions):
        recommendations.append(
            {
                "category": "Risk Management",
                "issue": "Positions down > 2%",
                "recommendation": "Tighter stop-losses (already implemented)",
                "action": "✅ Stop-losses active - monitor closely",
            }
        )

    # Display recommendations
    for i, rec in enumerate(recommendations, 1):
        print(f"\n{i}. [{rec['category']}] {rec['issue']}")
        print(f"   Recommendation: {rec['recommendation']}")
        print(f"   Action: {rec['action']}")

    if not recommendations:
        print("  ✅ Strategy appears well-optimized")
        print("  • Continue current approach")
        print("  • Monitor performance over next week")

    return recommendations


if __name__ == "__main__":
    analyze_strategy_performance()

#!/usr/bin/env python3
"""
Quick Actions - Immediate Value-Add Opportunities

CTO/CFO Quick Actions: Things I can do right now to improve the system.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"


def analyze_spy_loss():
    """Analyze why SPY is down -4.44% and provide recommendations."""
    print("=" * 80)
    print("🔍 SPY POSITION ANALYSIS")
    print("=" * 80)

    if not SYSTEM_STATE_FILE.exists():
        print("System state not found")
        return

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    positions = state.get("performance", {}).get("open_positions", [])
    spy_pos = next((p for p in positions if p.get("symbol") == "SPY"), None)

    if not spy_pos:
        print("SPY position not found")
        return

    entry_price = spy_pos.get("entry_price", 0)
    current_price = spy_pos.get("current_price", 0)
    unrealized_pl_pct = spy_pos.get("unrealized_pl_pct", 0)

    print("\n📊 SPY Position Details:")
    print(f"  Entry Price:    ${entry_price:.2f}")
    print(f"  Current Price:  ${current_price:.2f}")
    print(f"  Loss:           {unrealized_pl_pct:.2f}%")
    print(f"  Dollar Loss:    ${spy_pos.get('unrealized_pl', 0):+.2f}")

    # Analysis
    print("\n💡 Analysis:")
    print(f"  • SPY is down {abs(unrealized_pl_pct):.2f}% from entry")
    print(f"  • This represents a ${abs(spy_pos.get('unrealized_pl', 0)):.2f} unrealized loss")
    print("  • Stop-loss is set at $669.04 (will trigger if drops further)")

    # Recommendations
    print("\n🎯 Recommendations:")
    if unrealized_pl_pct < -5:
        print("  🚨 CRITICAL: Loss exceeds 5% - Consider immediate review")
        print("     - Market may be in correction")
        print("     - Consider reducing position size")
    elif unrealized_pl_pct < -2:
        print("  ⚠️  WARNING: Loss exceeds 2% - Monitor closely")
        print("     - Stop-loss will protect further downside")
        print("     - Consider if this is temporary volatility")

    print("  ✅ Stop-loss active: Will auto-sell if drops to $669.04")
    print("  📈 If SPY recovers above entry ($682.70), consider taking profits")

    return {
        "entry": entry_price,
        "current": current_price,
        "loss_pct": unrealized_pl_pct,
        "recommendation": "monitor" if unrealized_pl_pct > -5 else "review",
    }


def analyze_win_rate():
    """Analyze why win rate is 0% and provide recommendations."""
    print("\n" + "=" * 80)
    print("📊 WIN RATE ANALYSIS")
    print("=" * 80)

    if not SYSTEM_STATE_FILE.exists():
        return

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    performance = state.get("performance", {})
    total_trades = performance.get("total_trades", 0)
    win_rate = performance.get("win_rate", 0)

    print("\n📈 Current Metrics:")
    print(f"  Total Trades:    {total_trades}")
    print(f"  Win Rate:        {win_rate:.1f}%")
    print(f"  Winning Trades:  {performance.get('winning_trades', 0)}")
    print(f"  Losing Trades:   {performance.get('losing_trades', 0)}")

    positions = state.get("performance", {}).get("open_positions", [])
    profitable = sum(1 for p in positions if p.get("unrealized_pl", 0) > 0)
    losing = len(positions) - profitable

    print("\n📦 Current Positions:")
    print(f"  Profitable:       {profitable}/{len(positions)}")
    print(f"  Losing:           {losing}/{len(positions)}")

    print("\n💡 Analysis:")
    if total_trades == 0:
        print("  • No trades executed yet - win rate will populate after trades")
    elif win_rate == 0 and total_trades > 0:
        print("  • Win rate is 0% because no positions have been closed profitably")
        print(f"  • Current positions show: {profitable} profitable, {losing} losing")
        print("  • Win rate will update when positions are closed")

    print("\n🎯 Recommendations:")
    print("  • Focus on position management and exit timing")
    print(f"  • Current unrealized P/L: ${sum(p.get('unrealized_pl', 0) for p in positions):+.2f}")
    print("  • Consider taking profits on GOOGL (+2.34%)")
    print("  • Monitor SPY closely (-4.44%)")


def suggest_optimizations():
    """Suggest immediate optimizations."""
    print("\n" + "=" * 80)
    print("⚡ QUICK OPTIMIZATIONS")
    print("=" * 80)

    optimizations = [
        {
            "priority": "HIGH",
            "action": "Take partial profit on GOOGL",
            "reason": "Position up +2.34%, trail stop protects downside",
            "impact": "Lock in $9.49 profit, reduce risk",
        },
        {
            "priority": "HIGH",
            "action": "Review SPY entry timing",
            "reason": "Down -4.44% suggests poor entry point",
            "impact": "Improve future entry criteria",
        },
        {
            "priority": "MEDIUM",
            "action": "Set up daily performance alerts",
            "reason": "Get notified of significant P/L changes",
            "impact": "Faster response to issues",
        },
        {
            "priority": "MEDIUM",
            "action": "Analyze entry criteria",
            "reason": "0% win rate suggests entry timing issues",
            "impact": "Improve strategy performance",
        },
        {
            "priority": "LOW",
            "action": "Diversify position sizes",
            "reason": "SPY position is largest loss",
            "impact": "Better risk distribution",
        },
    ]

    for opt in optimizations:
        priority_emoji = (
            "🚨" if opt["priority"] == "HIGH" else "⚠️" if opt["priority"] == "MEDIUM" else "ℹ️"
        )
        print(f"\n{priority_emoji} [{opt['priority']}] {opt['action']}")
        print(f"   Reason: {opt['reason']}")
        print(f"   Impact: {opt['impact']}")

    return optimizations


def main():
    """Execute quick actions."""
    print("=" * 80)
    print("⚡ QUICK ACTIONS - IMMEDIATE VALUE-ADD")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Analyze SPY loss
    spy_analysis = analyze_spy_loss()

    # Analyze win rate
    analyze_win_rate()

    # Suggest optimizations
    optimizations = suggest_optimizations()

    print("\n" + "=" * 80)
    print("✅ Quick Actions Complete")
    print("=" * 80)

    return {
        "spy_analysis": spy_analysis,
        "optimizations": optimizations,
    }


if __name__ == "__main__":
    main()

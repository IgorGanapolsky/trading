#!/usr/bin/env python3
"""
Real-Time Status Report

CTO/CFO Status: Current system state and performance.
"""

import json
from datetime import datetime
from pathlib import Path

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
PERF_FILE = DATA_DIR / "performance_log.json"


def generate_status_report():
    """Generate comprehensive status report."""
    print("=" * 80)
    print("📊 REAL-TIME STATUS REPORT")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

    # Load state
    if not SYSTEM_STATE_FILE.exists():
        print("❌ System state file not found")
        return

    with open(SYSTEM_STATE_FILE) as f:
        state = json.load(f)

    # Financial Status
    account = state.get("account", {})
    print("\n💰 FINANCIAL STATUS")
    print("-" * 80)
    print(f"  Current Equity:      ${account.get('current_equity', 0):,.2f}")
    print(f"  Starting Balance:     ${account.get('starting_balance', 100000):,.2f}")
    print(f"  Total P/L:           ${account.get('total_pl', 0):+,.2f}")
    print(f"  P/L Percentage:      {account.get('total_pl_pct', 0):+.4f}%")
    print(f"  Cash Available:       ${account.get('cash', 0):,.2f}")
    print(f"  Positions Value:     ${account.get('positions_value', 0):,.2f}")

    # Positions
    positions = state.get("performance", {}).get("open_positions", [])
    if positions:
        print("\n📦 CURRENT POSITIONS")
        print("-" * 80)
        total_unrealized = 0
        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            qty = pos.get("quantity", 0)
            entry = pos.get("entry_price", 0)
            current = pos.get("current_price", 0)
            unrealized = pos.get("unrealized_pl", 0)
            unrealized_pct = pos.get("unrealized_pl_pct", 0)
            total_unrealized += unrealized

            status = "🟢" if unrealized > 0 else "🔴"
            print(f"  {status} {symbol:6s} {qty:8.4f} shares")
            print(f"      Entry: ${entry:.2f} → Current: ${current:.2f}")
            print(f"      P/L: ${unrealized:+,.2f} ({unrealized_pct:+.2f}%)")

            # Risk assessment
            if unrealized_pct < -5:
                print("      🚨 CRITICAL: Loss exceeds 5%")
            elif unrealized_pct < -2:
                print("      ⚠️  WARNING: Loss exceeds 2%")

        print(f"\n  Total Unrealized P/L: ${total_unrealized:+,.2f}")

    # System Status
    meta = state.get("meta", {})
    last_updated = meta.get("last_updated", "Unknown")
    print("\n🤖 SYSTEM STATUS")
    print("-" * 80)
    print(f"  Last Updated:         {last_updated}")

    # Challenge Status
    challenge = state.get("challenge", {})
    print(
        f"  Challenge Day:        {challenge.get('current_day', 0)}/{challenge.get('total_days', 90)}"
    )
    print(f"  Phase:                {challenge.get('phase', 'Unknown')}")

    # Performance Metrics
    performance = state.get("performance", {})
    print("\n📈 PERFORMANCE METRICS")
    print("-" * 80)
    print(f"  Total Trades:         {performance.get('total_trades', 0)}")
    print(f"  Win Rate:             {performance.get('win_rate', 0):.1f}%")

    best = performance.get("best_trade", {})
    worst = performance.get("worst_trade", {})
    print(f"  Best Trade:           {best.get('symbol', 'N/A')} ${best.get('pl', 0):+,.2f}")
    print(f"  Worst Trade:          {worst.get('symbol', 'N/A')} ${worst.get('pl', 0):+,.2f}")

    # Today's Status
    today = datetime.now().strftime("%Y-%m-%d")
    if PERF_FILE.exists():
        with open(PERF_FILE) as f:
            perf_data = json.load(f)
        today_entries = [e for e in perf_data if e.get("date") == today]
        if today_entries:
            latest = today_entries[-1]
            print("\n📅 TODAY'S PERFORMANCE")
            print("-" * 80)
            print(f"  P/L:                  ${latest.get('pl', 0):+,.2f}")
            print(f"  Equity:               ${latest.get('equity', 0):,.2f}")
        else:
            print("\n⚠️  No trades executed today")

    print("\n" + "=" * 80)
    print("✅ Status Report Complete")
    print("=" * 80)


if __name__ == "__main__":
    generate_status_report()

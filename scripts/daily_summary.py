#!/usr/bin/env python3
"""
Daily Trading Summary - Quick performance check

Shows:
- Today's P/L
- Current positions
- Overall performance
- Next actions
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# Load data
DATA_DIR = Path("data")
PERF_FILE = DATA_DIR / "performance_log.json"
STATE_FILE = DATA_DIR / "system_state.json"


def get_today_summary():
    """Get today's trading summary."""
    today = datetime.now().strftime("%Y-%m-%d")

    # Load performance log
    perf_data = []
    if PERF_FILE.exists():
        with open(PERF_FILE) as f:
            perf_data = json.load(f)

    # Load system state
    state = {}
    if STATE_FILE.exists():
        with open(STATE_FILE) as f:
            state = json.load(f)

    # Find today's entries
    today_entries = [e for e in perf_data if e.get("date") == today]

    print("=" * 60)
    print("📊 DAILY TRADING SUMMARY")
    print("=" * 60)
    print(f"Date: {today}")
    print()

    if today_entries:
        latest = today_entries[-1]
        print("💰 TODAY'S PERFORMANCE")
        print(f"  Equity:      ${latest['equity']:,.2f}")
        print(f"  Cash:        ${latest['cash']:,.2f}")
        print(f"  P/L:         ${latest['pl']:+,.2f} ({latest['pl_pct']:+.4f}%)")
        print(f"  Buying Power: ${latest['buying_power']:,.2f}")
    else:
        print("⚠️  No entries for today yet")
        if perf_data:
            latest = perf_data[-1]
            print(f"  Last entry: {latest.get('date')} - P/L: ${latest.get('pl', 0):+,.2f}")

    print()

    # Overall performance
    starting = 100000.0
    if today_entries:
        current = today_entries[-1]["equity"]
    elif state.get("account"):
        current = state["account"].get("current_equity", starting)
    else:
        current = starting

    total_pnl = current - starting
    print("📈 OVERALL PERFORMANCE")
    print(f"  Starting:    ${starting:,.2f}")
    print(f"  Current:     ${current:,.2f}")
    print(f"  Total P/L:   ${total_pnl:+,.2f} ({total_pnl / starting * 100:+.4f}%)")
    print()

    # Current positions
    if state.get("performance", {}).get("open_positions"):
        positions = state["performance"]["open_positions"]
        print("📦 CURRENT POSITIONS")
        total_unrealized = 0
        for pos in positions:
            symbol = pos.get("symbol", "UNKNOWN")
            qty = pos.get("quantity", 0)
            unrealized = pos.get("unrealized_pl", 0)
            unrealized_pct = pos.get("unrealized_pl_pct", 0)
            total_unrealized += unrealized

            emoji = "🟢" if unrealized > 0 else "🔴"
            print(
                f"  {emoji} {symbol:6s} {qty:8.4f} shares  P/L: ${unrealized:+8.2f} ({unrealized_pct:+.2f}%)"
            )

        print(f"\n  Total Unrealized P/L: ${total_unrealized:+,.2f}")
        print()

    # Performance metrics
    if state.get("performance"):
        perf = state["performance"]
        print("📊 PERFORMANCE METRICS")
        print(f"  Total Trades: {perf.get('total_trades', 0)}")
        print(f"  Win Rate:     {perf.get('win_rate', 0):.1f}%")
        print(
            f"  Best Trade:   {perf.get('best_trade', {}).get('symbol', 'N/A')} ${perf.get('best_trade', {}).get('pl', 0):+,.2f}"
        )
        print(
            f"  Worst Trade:  {perf.get('worst_trade', {}).get('symbol', 'N/A')} ${perf.get('worst_trade', {}).get('pl', 0):+,.2f}"
        )
        print()

    # Challenge status
    if state.get("challenge"):
        challenge = state["challenge"]
        print("🎯 CHALLENGE STATUS")
        print(f"  Day: {challenge.get('current_day', 0)}/{challenge.get('total_days', 90)}")
        print(f"  Phase: {challenge.get('phase', 'Unknown')}")
        print()

    print("=" * 60)


if __name__ == "__main__":
    get_today_summary()

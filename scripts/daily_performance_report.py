#!/usr/bin/env python3
"""
Daily Performance Report

Generates a comprehensive daily performance report.
FREE - No API costs, local processing only.
"""

import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = Path("data")
PERF_LOG_FILE = DATA_DIR / "performance_log.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
EVAL_DIR = DATA_DIR / "evaluations"


def load_performance_log():
    """Load performance log."""
    if not PERF_LOG_FILE.exists():
        return []
    with open(PERF_LOG_FILE) as f:
        return json.load(f)


def load_system_state():
    """Load system state."""
    if not SYSTEM_STATE_FILE.exists():
        return {}
    with open(SYSTEM_STATE_FILE) as f:
        return json.load(f)


def get_today_evaluations():
    """Get today's evaluations."""
    today = date.today().isoformat()
    eval_file = EVAL_DIR / f"evaluations_{today}.json"

    if not eval_file.exists():
        return []

    with open(eval_file) as f:
        return json.load(f)


def calculate_reliability(perf_log):
    """Calculate system reliability."""
    if not perf_log:
        return 0.0, 0, 0

    dates = [entry.get("date") for entry in perf_log if entry.get("date")]
    dates.sort()

    if not dates:
        return 0.0, 0, 0

    first_date = datetime.fromisoformat(dates[0]).date()
    last_date = datetime.fromisoformat(dates[-1]).date()

    # Calculate expected trading days (weekdays only)
    expected_dates = []
    current = first_date
    while current <= last_date:
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            expected_dates.append(current.isoformat())
        current += timedelta(days=1)

    trading_days = len(dates)
    total_expected = len(expected_dates)
    gaps = total_expected - trading_days
    reliability = (trading_days / total_expected * 100) if total_expected > 0 else 0

    return reliability, trading_days, gaps


def main():
    """Generate daily performance report."""
    print("=" * 70)
    print("DAILY PERFORMANCE REPORT")
    print("=" * 70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    # Load data
    perf_log = load_performance_log()
    system_state = load_system_state()
    today_evaluations = get_today_evaluations()

    # Today's performance
    today = date.today().isoformat()
    today_entry = None
    for entry in reversed(perf_log):
        if entry.get("date") == today:
            today_entry = entry
            break

    print("📊 TODAY'S PERFORMANCE:")
    if today_entry:
        equity = today_entry.get("equity", 0)
        pl = today_entry.get("pl", 0)
        pl_pct = today_entry.get("pl_pct", 0)
        print(f"   Equity: ${equity:,.2f}")
        print(f"   P/L: ${pl:+,.2f} ({pl_pct:+.2f}%)")
    else:
        print("   ⚠️  No trades executed today")
    print()

    # Overall performance
    if perf_log:
        latest = perf_log[-1]
        starting_balance = system_state.get("account", {}).get("starting_balance", 100000)
        total_pl = latest.get("equity", 0) - starting_balance
        total_pl_pct = (total_pl / starting_balance * 100) if starting_balance > 0 else 0

        print("📈 OVERALL PERFORMANCE:")
        print(f"   Starting Balance: ${starting_balance:,.2f}")
        print(f"   Current Equity: ${latest.get('equity', 0):,.2f}")
        print(f"   Total P/L: ${total_pl:+,.2f} ({total_pl_pct:+.2f}%)")
        print()

    # System reliability
    reliability, trading_days, gaps = calculate_reliability(perf_log)
    print("🔧 SYSTEM RELIABILITY:")
    print(f"   Reliability: {reliability:.1f}%")
    print(f"   Trading Days: {trading_days}")
    print(f"   Data Gaps: {gaps}")
    print()

    # Evaluations
    print("✅ EVALUATIONS:")
    print(f"   Today's Evaluations: {len(today_evaluations)}")
    if today_evaluations:
        passed = sum(1 for e in today_evaluations if e.get("passed", False))
        failed = len(today_evaluations) - passed
        print(f"   Passed: {passed} ✅")
        print(f"   Failed: {failed} ❌")
    else:
        print("   ⚠️  No evaluations today")
    print()

    # System state
    last_updated = system_state.get("meta", {}).get("last_updated", "Unknown")
    print("📊 SYSTEM STATE:")
    print(f"   Last Updated: {last_updated}")
    try:
        last_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        age_hours = (datetime.now() - last_dt.replace(tzinfo=None)).total_seconds() / 3600
        if age_hours > 24:
            print(f"   ⚠️  WARNING: System state is {age_hours:.1f} hours old")
        else:
            print(f"   ✅ System state is fresh ({age_hours:.1f} hours old)")
    except Exception:
        pass
    print()

    print("=" * 70)
    print("💡 TIP: Run this script daily to track performance")
    print("=" * 70)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
System Reliability Improvement Script

Identifies and fixes data gaps to improve system reliability.
FREE - No API costs, local processing only.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DATA_DIR = Path("data")
PERF_LOG_FILE = DATA_DIR / "performance_log.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"


def analyze_reliability():
    """Analyze current system reliability."""
    if not PERF_LOG_FILE.exists():
        print("⚠️  Performance log not found")
        return None

    with open(PERF_LOG_FILE) as f:
        perf_log = json.load(f)

    if not perf_log:
        print("⚠️  Performance log is empty")
        return None

    dates = [entry.get("date") for entry in perf_log if entry.get("date")]
    dates.sort()

    if not dates:
        return None

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

    missing_dates = [d for d in expected_dates if d not in dates]

    return {
        "first_date": first_date.isoformat(),
        "last_date": last_date.isoformat(),
        "total_expected": total_expected,
        "trading_days": trading_days,
        "gaps": gaps,
        "reliability": reliability,
        "missing_dates": missing_dates,
    }


def suggest_recovery_actions(analysis):
    """Suggest recovery actions for missing trading days."""
    if not analysis or not analysis["missing_dates"]:
        return []

    suggestions = []

    # Group consecutive missing dates
    consecutive_groups = []
    current_group = []

    for missing_date in sorted(analysis["missing_dates"]):
        if not current_group:
            current_group = [missing_date]
        else:
            last_date = datetime.fromisoformat(current_group[-1]).date()
            current_date = datetime.fromisoformat(missing_date).date()

            if (current_date - last_date).days == 1:
                current_group.append(missing_date)
            else:
                consecutive_groups.append(current_group)
                current_group = [missing_date]

    if current_group:
        consecutive_groups.append(current_group)

    for group in consecutive_groups:
        if len(group) == 1:
            suggestions.append(
                {
                    "date": group[0],
                    "action": "single_missing",
                    "description": f"Single missing trading day: {group[0]}",
                }
            )
        else:
            suggestions.append(
                {
                    "start_date": group[0],
                    "end_date": group[-1],
                    "action": "consecutive_missing",
                    "description": f"Consecutive missing days: {group[0]} to {group[-1]} ({len(group)} days)",
                }
            )

    return suggestions


def main():
    """Main function."""
    print("=" * 70)
    print("SYSTEM RELIABILITY IMPROVEMENT")
    print("=" * 70)
    print()

    # Analyze current reliability
    analysis = analyze_reliability()

    if not analysis:
        print("⚠️  Could not analyze reliability")
        return

    print(f"📅 Period: {analysis['first_date']} to {analysis['last_date']}")
    print(f"📊 Expected Trading Days: {analysis['total_expected']}")
    print(f"✅ Actual Trading Days: {analysis['trading_days']}")
    print(f"❌ Data Gaps: {analysis['gaps']}")
    print(f"📈 Current Reliability: {analysis['reliability']:.1f}%")
    print()

    if analysis["gaps"] > 0:
        print(f"🔍 Missing Trading Days ({len(analysis['missing_dates'])}):")
        for missing in analysis["missing_dates"][:10]:
            print(f"   • {missing}")
        if len(analysis["missing_dates"]) > 10:
            print(f"   ... and {len(analysis['missing_dates']) - 10} more")
        print()

        # Suggest recovery actions
        suggestions = suggest_recovery_actions(analysis)
        if suggestions:
            print("💡 RECOVERY SUGGESTIONS:")
            for i, suggestion in enumerate(suggestions[:5], 1):
                print(f"   {i}. {suggestion['description']}")
            print()
            print("   Note: These are historical gaps. Future gaps can be prevented by:")
            print("   • Ensuring workflow runs daily")
            print("   • Adding retry logic for failed executions")
            print("   • Monitoring workflow status")
    else:
        print("✅ No data gaps detected - system reliability is 100%!")

    print()
    print("=" * 70)
    print("RECOMMENDATIONS:")
    print("   1. Ensure GitHub Actions workflow runs daily")
    print("   2. Add retry logic for failed executions")
    print("   3. Monitor workflow status and alert on failures")
    print("   4. Add automatic recovery for missed days")
    print("=" * 70)


if __name__ == "__main__":
    main()

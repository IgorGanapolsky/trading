#!/usr/bin/env python3
"""
Daily Automation Check

Verifies that automation is working and system is healthy.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
PERF_FILE = DATA_DIR / "performance_log.json"


def check_automation_health():
    """Check if automation is working properly."""
    print("=" * 80)
    print("🤖 AUTOMATION HEALTH CHECK")
    print("=" * 80)

    issues = []
    warnings = []

    # Check system state freshness
    if SYSTEM_STATE_FILE.exists():
        with open(SYSTEM_STATE_FILE) as f:
            state = json.load(f)

        last_updated = state.get("meta", {}).get("last_updated", "")
        if last_updated:
            try:
                last_update_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
                age_hours = (
                    datetime.now(last_update_dt.tzinfo) - last_update_dt
                ).total_seconds() / 3600

                if age_hours > 48:
                    issues.append(f"System state is {age_hours:.1f} hours old (CRITICAL)")
                elif age_hours > 24:
                    warnings.append(f"System state is {age_hours:.1f} hours old")
                else:
                    print(f"✅ System state fresh: {age_hours:.1f} hours old")
            except Exception:
                warnings.append("Could not parse last update time")

    # Check for today's trades
    today = datetime.now().strftime("%Y-%m-%d")
    if PERF_FILE.exists():
        with open(PERF_FILE) as f:
            perf_data = json.load(f)

        today_entries = [e for e in perf_data if e.get("date") == today]
        if today_entries:
            print(f"✅ Today's performance data exists: {len(today_entries)} entries")
        else:
            # Check if market is open
            now = datetime.now()
            if now.weekday() < 5 and 9 <= now.hour < 16:  # Weekday, market hours
                warnings.append("No performance data for today (market may be open)")
            else:
                print("ℹ️  No trades today (market closed or before execution)")

    # Check positions
    if SYSTEM_STATE_FILE.exists():
        with open(SYSTEM_STATE_FILE) as f:
            state = json.load(f)

        positions = state.get("performance", {}).get("open_positions", [])
        losing_positions = [p for p in positions if p.get("unrealized_pl_pct", 0) < -5]

        if losing_positions:
            for pos in losing_positions:
                issues.append(f"{pos['symbol']} down {pos['unrealized_pl_pct']:.2f}% (CRITICAL)")

        print(f"✅ Positions monitored: {len(positions)} open")

    # Summary
    print("\n" + "=" * 80)
    print("📋 HEALTH CHECK SUMMARY")
    print("=" * 80)

    if issues:
        print(f"\n🚨 CRITICAL ISSUES: {len(issues)}")
        for issue in issues:
            print(f"  • {issue}")
    else:
        print("\n✅ No critical issues")

    if warnings:
        print(f"\n⚠️  WARNINGS: {len(warnings)}")
        for warning in warnings:
            print(f"  • {warning}")
    else:
        print("\n✅ No warnings")

    if not issues and not warnings:
        print("\n✅ System healthy - automation working properly")

    return {
        "healthy": len(issues) == 0,
        "issues": issues,
        "warnings": warnings,
    }


if __name__ == "__main__":
    check_automation_health()

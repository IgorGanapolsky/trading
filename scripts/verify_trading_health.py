#!/usr/bin/env python3
"""
Trading Health Verification Script
Per RAG Lesson LL-019: Check trading health FIRST before any task.

This script is meant to run in GitHub Actions where credentials are available.
"""
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path


def check_trades_file():
    """Check if today's trades file exists."""
    today = date.today().isoformat()
    trades_file = Path(f"data/trades_{today}.json")
    if trades_file.exists():
        trades = json.loads(trades_file.read_text())
        return True, f"✅ {len(trades)} trades today"
    return False, f"❌ No trades file: {trades_file}"


def check_performance_log():
    """Check if performance log was updated today."""
    log_file = Path("data/performance_log.json")
    if not log_file.exists():
        return False, "❌ No performance_log.json"
    
    try:
        data = json.loads(log_file.read_text())
        if data:
            last_entry = data[-1] if isinstance(data, list) else data
            last_date = last_entry.get("date", "unknown")
            today = date.today().isoformat()
            if last_date == today:
                return True, f"✅ Performance log updated today"
            return False, f"⚠️ Performance log stale: {last_date}"
    except Exception as e:
        return False, f"❌ Error reading log: {e}"


def check_system_state():
    """Check system state freshness."""
    state_file = Path("data/system_state.json")
    if not state_file.exists():
        return False, "❌ No system_state.json"
    
    try:
        data = json.loads(state_file.read_text())
        last_sync = data.get("meta", {}).get("last_sync", "unknown")
        return True, f"Last sync: {last_sync}"
    except Exception as e:
        return False, f"❌ Error: {e}"


def main():
    print("=" * 60)
    print("🔍 TRADING HEALTH CHECK (per RAG Lesson LL-019)")
    print("=" * 60)
    print(f"📅 Date: {datetime.now().isoformat()}")
    print()

    all_ok = True
    
    # Check 1: Trades file
    ok, msg = check_trades_file()
    print(f"1. Trades File: {msg}")
    if not ok:
        all_ok = False
    
    # Check 2: Performance log
    ok, msg = check_performance_log()
    print(f"2. Performance Log: {msg}")
    if not ok:
        all_ok = False
    
    # Check 3: System state
    ok, msg = check_system_state()
    print(f"3. System State: {msg}")
    
    print()
    if all_ok:
        print("✅ Trading system is HEALTHY")
        return 0
    else:
        print("🚨 CRITICAL: Trading system may be DEAD!")
        print("   Per LL-019: Trigger daily-trading workflow manually")
        return 1


if __name__ == "__main__":
    sys.exit(main())

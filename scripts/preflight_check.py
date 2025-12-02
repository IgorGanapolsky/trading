#!/usr/bin/env python3
"""
Pre-Flight Check for Trading System
Verifies all systems are ready for tomorrow's workflow execution.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def check_mark():
    return "✅"


def fail_mark():
    return "❌"


def warn_mark():
    return "⚠️"


def check_environment_variables():
    """Check required environment variables are set"""
    print("\n" + "=" * 70)
    print("1. ENVIRONMENT VARIABLES")
    print("=" * 70)

    required = {
        "ALPACA_API_KEY": "Alpaca API key",
        "ALPACA_SECRET_KEY": "Alpaca secret key",
    }

    recommended = {
        "POLYGON_API_KEY": "Polygon.io API key (reliable data source)",
        "FINNHUB_API_KEY": "Finnhub API key (economic calendar)",
    }

    optional = {
        "SENTRY_DSN": "Sentry error monitoring",
        "ALPHA_VANTAGE_API_KEY": "Alpha Vantage API (fallback)",
    }

    all_ok = True

    for var, desc in required.items():
        value = os.getenv(var)
        if value:
            print(f"{check_mark()} {var}: Set ({desc})")
        else:
            print(f"{fail_mark()} {var}: MISSING ({desc})")
            all_ok = False

    for var, desc in recommended.items():
        value = os.getenv(var)
        if value:
            print(f"{check_mark()} {var}: Set ({desc})")
        else:
            print(f"{warn_mark()} {var}: Not set ({desc}) - Recommended")

    for var, desc in optional.items():
        value = os.getenv(var)
        if value:
            print(f"{check_mark()} {var}: Set ({desc})")
        else:
            print(f"   {var}: Not set ({desc}) - Optional")

    return all_ok


def check_code_fixes():
    """Verify infrastructure fixes are in place"""
    print("\n" + "=" * 70)
    print("2. CODE FIXES VERIFICATION")
    print("=" * 70)

    checks = []

    # Check data source priority order
    market_data_file = Path("src/utils/market_data.py")
    if market_data_file.exists():
        content = market_data_file.read_text()
        if "PRIORITY 2: Try Alpaca API FIRST" in content:
            print(f"{check_mark()} Data source priority: Alpaca first")
            checks.append(True)
        else:
            print(f"{fail_mark()} Data source priority: Old order (yfinance first)")
            checks.append(False)

        if "ALPHAVANTAGE_MAX_TOTAL_SECONDS" in content:
            print(f"{check_mark()} Alpha Vantage timeout: 90s max configured")
            checks.append(True)
        else:
            print(f"{fail_mark()} Alpha Vantage timeout: Not configured")
            checks.append(False)

    # Check workflow timeout
    workflow_file = Path(".github/workflows/daily-trading.yml")
    if workflow_file.exists():
        content = workflow_file.read_text()
        if "timeout-minutes: 30" in content:
            print(f"{check_mark()} Workflow timeout: 30 minutes")
            checks.append(True)
        else:
            print(f"{warn_mark()} Workflow timeout: Check value")
            checks.append(False)

    # Check error monitoring
    error_monitoring_file = Path("src/utils/error_monitoring.py")
    if error_monitoring_file.exists():
        print(f"{check_mark()} Error monitoring: Sentry integration exists")
        checks.append(True)
    else:
        print(f"{fail_mark()} Error monitoring: Not configured")
        checks.append(False)

    return all(checks)


def check_performance_log():
    """Check performance log is up to date"""
    print("\n" + "=" * 70)
    print("3. PERFORMANCE LOG")
    print("=" * 70)

    perf_log = Path("data/performance_log.json")
    if not perf_log.exists():
        print(f"{warn_mark()} Performance log: File doesn't exist")
        return False

    try:
        with open(perf_log) as f:
            data = json.load(f)

        if not data:
            print(f"{warn_mark()} Performance log: Empty")
            return False

        last_entry = data[-1]
        last_date = datetime.fromisoformat(last_entry.get("date", ""))
        today = datetime.now().date()

        if last_date.date() == today:
            print(f"{check_mark()} Performance log: Updated today")
            return True
        elif last_date.date() == today - timedelta(days=1):
            print(
                f"{warn_mark()} Performance log: Last updated yesterday (expected if workflow hasn't run today)"
            )
            return True
        else:
            print(f"{fail_mark()} Performance log: Last updated {last_date.date()} (stale)")
            return False
    except Exception as e:
        print(f"{fail_mark()} Performance log: Error reading - {e}")
        return False


def check_system_state():
    """Check system state is valid"""
    print("\n" + "=" * 70)
    print("4. SYSTEM STATE")
    print("=" * 70)

    state_file = Path("data/system_state.json")
    if not state_file.exists():
        print(f"{warn_mark()} System state: File doesn't exist")
        return True  # Not critical

    try:
        with open(state_file) as f:
            state = json.load(f)

        last_updated = state.get("last_updated")
        if last_updated:
            print(f"{check_mark()} System state: Last updated {last_updated}")
        else:
            print(f"{warn_mark()} System state: No timestamp")

        return True
    except Exception as e:
        print(f"{warn_mark()} System state: Error reading - {e}")
        return True  # Not critical


def check_workflow_config():
    """Check GitHub Actions workflow configuration"""
    print("\n" + "=" * 70)
    print("5. WORKFLOW CONFIGURATION")
    print("=" * 70)

    workflow_file = Path(".github/workflows/daily-trading.yml")
    if not workflow_file.exists():
        print(f"{fail_mark()} Workflow file: Not found")
        return False

    content = workflow_file.read_text()

    checks = []

    # Check schedule
    if "cron: '35 14 * * 1-5'" in content:
        print(f"{check_mark()} Schedule: 9:35 AM ET weekdays")
        checks.append(True)
    else:
        print(f"{warn_mark()} Schedule: Check cron expression")
        checks.append(False)

    # Check timeout
    if "timeout-minutes: 30" in content:
        print(f"{check_mark()} Timeout: 30 minutes")
        checks.append(True)
    else:
        print(f"{warn_mark()} Timeout: Check value")
        checks.append(False)

    # Check Python version
    if "python-version: '3.11'" in content:
        print(f"{check_mark()} Python version: 3.11")
        checks.append(True)
    else:
        print(f"{warn_mark()} Python version: Check value")
        checks.append(False)

    return all(checks)


def main():
    print("=" * 70)
    print("PRE-FLIGHT CHECK: Trading System Readiness")
    print("=" * 70)
    print(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    results = []

    results.append(("Environment Variables", check_environment_variables()))
    results.append(("Code Fixes", check_code_fixes()))
    results.append(("Performance Log", check_performance_log()))
    results.append(("System State", check_system_state()))
    results.append(("Workflow Config", check_workflow_config()))

    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    all_passed = True
    for name, passed in results:
        status = check_mark() if passed else fail_mark()
        print(f"{status} {name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 70)
    if all_passed:
        print("✅ ALL CHECKS PASSED - System ready for tomorrow!")
    else:
        print("⚠️  SOME CHECKS FAILED - Review issues above")
    print("=" * 70)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Diagnose paper trading system issues.
Checks workflow status, secrets, and trading execution.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_trade_files():
    """Check if trade files exist for recent days."""
    print("📁 Checking for recent trade files...")
    print("-" * 50)

    data_dir = Path("data")
    missing_days = []

    # Check last 7 days
    for i in range(7):
        date = datetime.now() - timedelta(days=i)
        if date.weekday() >= 5:  # Skip weekends
            continue

        date_str = date.strftime("%Y-%m-%d")
        trade_file = data_dir / f"trades_{date_str}.json"

        if trade_file.exists():
            with open(trade_file) as f:
                trades = json.load(f)
            print(f"✅ {date_str} ({date.strftime('%A')}): {len(trades)} trades")
        else:
            print(f"❌ {date_str} ({date.strftime('%A')}): NO TRADES FILE")
            missing_days.append(date_str)

    print()

    if missing_days:
        print(f"⚠️  Missing {len(missing_days)} trading days:")
        for day in missing_days:
            print(f"   - {day}")
        return False
    else:
        print("✅ All recent trading days have trade files")
        return True


def check_system_state():
    """Check system_state.json for automation status."""
    print("📊 Checking system state...")
    print("-" * 50)

    state_file = Path("data/system_state.json")

    if not state_file.exists():
        print("❌ system_state.json not found!")
        return False

    with open(state_file) as f:
        state = json.load(f)

    # Check automation status
    automation = state.get("automation", {})
    print(f"GitHub Actions Enabled: {automation.get('github_actions_enabled', 'unknown')}")
    print(f"Workflow Status: {automation.get('workflow_status', 'unknown')}")
    print(f"Reason: {automation.get('workflow_status_reason', 'none')}")
    print()

    # Check paper account
    paper = state.get("paper_account", {})
    print(f"Paper Account Equity: ${paper.get('current_equity', 0):,.2f}")
    print(f"Last Sync: {paper.get('last_sync', 'unknown')}")
    print(f"Win Rate: {paper.get('win_rate', 0)}% (n={paper.get('win_rate_sample_size', 0)})")
    print()

    # Check last trading date
    trades = state.get("trades", {})
    last_trade = trades.get("last_trade_date", "unknown")
    print(f"Last Trade Date: {last_trade}")

    # Calculate days since last trade
    if last_trade != "unknown":
        try:
            last_date = datetime.strptime(last_trade, "%Y-%m-%d")
            days_since = (datetime.now() - last_date).days

            if days_since > 3:
                print(f"⚠️  WARNING: {days_since} days since last trade!")
            else:
                print(f"   ({days_since} days ago)")
        except ValueError:
            pass

    print()
    return automation.get("github_actions_enabled", False)


def check_secrets():
    """Check if required secrets are set (only checks local env)."""
    print("🔑 Checking secrets (local environment only)...")
    print("-" * 50)

    required = [
        "ALPACA_API_KEY",
        "ALPACA_SECRET_KEY",
    ]

    optional = [
        "ANTHROPIC_API_KEY",
        "OPENROUTER_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "POLYGON_API_KEY",
        "FINNHUB_API_KEY",
        "GOOGLE_API_KEY",
    ]

    all_good = True

    for secret in required:
        value = os.getenv(secret)
        if value and len(value) > 10:
            print(f"✅ {secret}: configured")
        else:
            print(f"❌ {secret}: MISSING")
            all_good = False

    print()

    for secret in optional:
        value = os.getenv(secret)
        if value and len(value) > 10:
            print(f"✅ {secret}: configured")
        else:
            print(f"⚠️  {secret}: missing (optional)")

    print()
    print("⚠️  NOTE: This only checks local environment.")
    print("   GitHub Actions uses repository secrets, not local env.")
    print("   Verify at: https://github.com/IgorGanapolsky/trading/settings/secrets/actions")
    print()

    return all_good


def main():
    """Run all diagnostic checks."""
    print()
    print("=" * 50)
    print("PAPER TRADING SYSTEM DIAGNOSTICS")
    print("=" * 50)
    print()

    checks = {
        "Trade Files": check_trade_files(),
        "System State": check_system_state(),
        "Secrets (Local)": check_secrets(),
    }

    print()
    print("=" * 50)
    print("SUMMARY")
    print("=" * 50)

    for check, passed in checks.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {check}")

    print()

    if not all(checks.values()):
        print("⚠️  ISSUES DETECTED")
        print()
        print("Next steps:")
        print("1. Check GitHub Actions: https://github.com/IgorGanapolsky/trading/actions")
        print("2. Verify secrets are configured in GitHub repository settings")
        print("3. Try manual workflow trigger to test execution")
        print("4. Review diagnostic document: PAPER_TRADING_DIAGNOSIS_JAN09.md")
        return 1
    else:
        print("✅ ALL CHECKS PASSED")
        print()
        print("If trading still not working, check GitHub Actions workflow logs.")
        return 0


if __name__ == "__main__":
    sys.exit(main())

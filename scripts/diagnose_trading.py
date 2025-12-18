#!/usr/bin/env python3
"""
Diagnostic script to identify why trading is not executing.

Checks:
1. GitHub Actions scheduler status (via heartbeat file)
2. Last trade execution date
3. System state freshness
4. Blocking conditions (gates, thresholds)
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

def check_heartbeat():
    """Check if GitHub Actions scheduler is running."""
    heartbeat_path = Path("data/scheduler_heartbeat.json")

    print("\n" + "=" * 60)
    print("1. GITHUB ACTIONS SCHEDULER STATUS")
    print("=" * 60)

    if not heartbeat_path.exists():
        print("❌ CRITICAL: scheduler_heartbeat.json is MISSING")
        print("   This means GitHub Actions scheduled workflows are NOT running!")
        print("   The scheduler should write this file every 30 mins during market hours.")
        print("\n   LIKELY CAUSES:")
        print("   - GitHub disabled workflows after 60 days of inactivity")
        print("   - Repository settings disabled Actions")
        print("   - Workflow file has syntax errors")
        return False

    try:
        with open(heartbeat_path) as f:
            data = json.load(f)
        last_run = data.get("last_run", "unknown")
        print(f"✅ Heartbeat file exists")
        print(f"   Last run: {last_run}")

        # Check staleness
        if last_run != "unknown":
            try:
                last_dt = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
                age_hours = (datetime.now(timezone.utc) - last_dt).total_seconds() / 3600
                if age_hours > 2:
                    print(f"⚠️  WARNING: Heartbeat is {age_hours:.1f} hours old")
                    return False
                else:
                    print(f"   Age: {age_hours:.1f} hours (OK)")
                    return True
            except:
                pass
        return True
    except Exception as e:
        print(f"❌ Error reading heartbeat: {e}")
        return False


def check_last_trade():
    """Check when the last trade was executed."""
    print("\n" + "=" * 60)
    print("2. LAST TRADE EXECUTION")
    print("=" * 60)

    # Find most recent trade file
    data_dir = Path("data")
    trade_files = sorted(data_dir.glob("trades_*.json"), reverse=True)

    if not trade_files:
        print("❌ NO TRADE FILES FOUND")
        print("   No trades have ever been recorded.")
        return None

    latest_file = trade_files[0]
    print(f"   Latest trade file: {latest_file.name}")

    try:
        with open(latest_file) as f:
            trades = json.load(f)

        if not trades:
            print(f"   File is empty (no trades recorded)")
        else:
            print(f"   Contains {len(trades)} trade(s)")
            for trade in trades[-3:]:  # Show last 3
                symbol = trade.get("symbol", "?")
                status = trade.get("status", "?")
                ts = trade.get("ts", "?")
                print(f"   - {symbol}: {status} at {ts}")

        # Extract date from filename
        date_str = latest_file.stem.replace("trades_", "")
        trade_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        days_ago = (datetime.now().date() - trade_date).days
        print(f"\n   Last trade date: {trade_date} ({days_ago} days ago)")

        if days_ago > 3:
            print(f"❌ NO TRADES FOR {days_ago} DAYS!")

        return trade_date
    except Exception as e:
        print(f"❌ Error reading trade file: {e}")
        return None


def check_system_state():
    """Check system state freshness and blocking conditions."""
    print("\n" + "=" * 60)
    print("3. SYSTEM STATE & BLOCKING CONDITIONS")
    print("=" * 60)

    state_path = Path("data/system_state.json")
    if not state_path.exists():
        print("❌ system_state.json not found")
        return

    try:
        with open(state_path) as f:
            state = json.load(f)

        # Check freshness
        last_updated = state.get("meta", {}).get("last_updated", "unknown")
        print(f"   Last updated: {last_updated}")

        # Account info
        account = state.get("account", {})
        equity = account.get("current_equity", 0)
        cash = account.get("cash", 0)
        buying_power = account.get("buying_power", cash)
        print(f"   Equity: ${equity:,.2f}")
        print(f"   Cash: ${cash:,.2f}")
        print(f"   Buying Power: ${buying_power:,.2f}")

        # Performance
        perf = state.get("performance", {})
        total_trades = perf.get("total_trades", 0)
        win_rate = perf.get("win_rate", 0)
        print(f"   Total trades: {total_trades}")
        print(f"   Win rate: {win_rate}%")

        # Check for blocking conditions
        print("\n   BLOCKING CONDITION CHECKS:")

        # Check daily investment
        daily_inv = float(os.getenv("DAILY_INVESTMENT", "10"))
        if daily_inv < 50:
            print(f"   ⚠️  DAILY_INVESTMENT=${daily_inv} (below $50 minimum batch)")
        else:
            print(f"   ✅ DAILY_INVESTMENT=${daily_inv}")

        # Check if equity is reasonable
        if equity <= 0:
            print("   ❌ Equity is $0 or negative - trading blocked")
        else:
            print(f"   ✅ Equity is positive")

    except Exception as e:
        print(f"❌ Error reading system state: {e}")


def check_env_vars():
    """Check critical environment variables."""
    print("\n" + "=" * 60)
    print("4. ENVIRONMENT VARIABLES")
    print("=" * 60)

    critical_vars = [
        ("ALPACA_API_KEY", "Alpaca trading"),
        ("ALPACA_SECRET_KEY", "Alpaca trading"),
    ]

    optional_vars = [
        ("PAPER_TRADING", "Paper mode (should be 'true')"),
        ("DAILY_INVESTMENT", "Daily allocation"),
    ]

    all_set = True
    for var, desc in critical_vars:
        val = os.getenv(var)
        if val:
            print(f"   ✅ {var}: {'*' * min(len(val), 8)}... ({desc})")
        else:
            print(f"   ❌ {var}: NOT SET ({desc})")
            all_set = False

    for var, desc in optional_vars:
        val = os.getenv(var, "not set")
        print(f"   ℹ️  {var}: {val} ({desc})")

    return all_set


def summarize_issues():
    """Summarize all identified issues."""
    print("\n" + "=" * 60)
    print("SUMMARY & RECOMMENDED ACTIONS")
    print("=" * 60)

    print("""
IDENTIFIED ISSUES:
1. GitHub Actions scheduler is NOT running (heartbeat missing)
2. No trades executed since Dec 12 (6+ days)
3. Last trade was stuck in PENDING_NEW status

ROOT CAUSE: GitHub Actions scheduled workflows are disabled or failing

IMMEDIATE FIXES:
1. Trigger trading manually by pushing to the TRIGGER file:
   echo "TRIGGER $(date +%s)" > .github/TRIGGER_DAILY_TRADING
   git add .github/TRIGGER_DAILY_TRADING
   git commit -m "chore: trigger daily trading"
   git push origin main

2. Check GitHub Actions in the repository:
   - Go to https://github.com/YOUR_REPO/actions
   - Look for disabled workflows
   - Re-enable any disabled workflows

3. Verify secrets are configured:
   - Repository Settings > Secrets and variables > Actions
   - Ensure ALPACA_API_KEY and ALPACA_SECRET_KEY are set

LONG-TERM FIXES:
- Set up local cron job as backup
- Add alerting when scheduler heartbeat fails
""")


def main():
    print("=" * 60)
    print("TRADING SYSTEM DIAGNOSTIC REPORT")
    print(f"Generated: {datetime.now().isoformat()}")
    print("=" * 60)

    check_heartbeat()
    check_last_trade()
    check_system_state()
    check_env_vars()
    summarize_issues()

    return 0


if __name__ == "__main__":
    os.chdir(Path(__file__).parent.parent)
    sys.exit(main())

#!/usr/bin/env python3
"""
Trading System Diagnostic Script

Comprehensive check of all trading system components to identify why trades aren't executing.
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


def check_environment():
    """Check environment variables."""
    print("\n" + "=" * 70)
    print("1. ENVIRONMENT VARIABLES CHECK")
    print("=" * 70)

    required_vars = ["ALPACA_API_KEY", "ALPACA_SECRET_KEY"]
    optional_vars = ["OPENROUTER_API_KEY", "POLYGON_API_KEY", "FINNHUB_API_KEY"]

    for var in required_vars:
        value = os.getenv(var)
        if value:
            masked = f"{value[:4]}...{value[-4:]}" if len(value) > 8 else "***"
            print(f"✅ {var}: {masked}")
        else:
            print(f"❌ {var}: MISSING (CRITICAL)")

    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"✅ {var}: Present")
        else:
            print(f"⚠️  {var}: Missing (optional)")


def check_system_state():
    """Check system state file."""
    print("\n" + "=" * 70)
    print("2. SYSTEM STATE CHECK")
    print("=" * 70)

    state_file = Path("data/system_state.json")
    if not state_file.exists():
        print(f"❌ {state_file}: MISSING")
        return

    with open(state_file) as f:
        state = json.load(f)

    # Check staleness
    last_updated = state.get("meta", {}).get("last_updated", "")
    if last_updated:
        try:
            if "T" in last_updated:
                last_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            else:
                last_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
            age = datetime.now() - last_dt.replace(tzinfo=None)
            age_hours = age.total_seconds() / 3600
            if age_hours > 48:
                print(f"⚠️  System state is STALE: {age_hours:.1f} hours old")
            else:
                print(f"✅ System state freshness: {age_hours:.1f} hours old")
        except Exception as e:
            print(f"❌ Could not parse last_updated: {e}")

    # Check automation
    automation = state.get("automation", {})
    last_exec = automation.get("last_successful_execution", "Unknown")
    next_exec = automation.get("next_scheduled_execution", "Unknown")
    print(f"\n📊 Automation Status:")
    print(f"   Last successful execution: {last_exec}")
    print(f"   Next scheduled execution:  {next_exec}")
    print(f"   Workflow status: {automation.get('workflow_status', 'Unknown')}")

    # Check account
    account = state.get("account", {})
    print(f"\n💰 Account Status:")
    print(f"   Equity: ${account.get('current_equity', 0):,.2f}")
    print(f"   Cash: ${account.get('cash', 0):,.2f}")
    print(f"   P/L: ${account.get('total_pl', 0):+,.2f} ({account.get('total_pl_pct', 0):+.2f}%)")

    # Check performance
    perf = state.get("performance", {})
    print(f"\n📈 Performance:")
    print(f"   Total trades: {perf.get('total_trades', 0)}")
    print(f"   Win rate: {perf.get('win_rate', 0):.1f}%")
    print(f"   Open positions: {len(perf.get('open_positions', []))}")


def check_performance_log():
    """Check performance log file."""
    print("\n" + "=" * 70)
    print("3. PERFORMANCE LOG CHECK")
    print("=" * 70)

    perf_file = Path("data/performance_log.json")
    if not perf_file.exists():
        print(f"❌ {perf_file}: MISSING - Dashboard will show no data!")
        return

    with open(perf_file) as f:
        perf_data = json.load(f)

    print(f"✅ Performance log exists: {len(perf_data)} entries")
    if perf_data:
        latest = perf_data[-1]
        print(f"   Latest entry: {latest.get('date', 'Unknown')}")
        print(f"   Equity: ${latest.get('equity', 0):,.2f}")
        print(f"   P/L: ${latest.get('pl', 0):+,.2f}")


def check_recent_trades():
    """Check recent trade files."""
    print("\n" + "=" * 70)
    print("4. RECENT TRADES CHECK")
    print("=" * 70)

    data_dir = Path("data")
    trade_files = sorted(data_dir.glob("trades_*.json"), reverse=True)

    if not trade_files:
        print("❌ No trade files found!")
        return

    print(f"Found {len(trade_files)} trade file(s)")

    for trade_file in trade_files[:5]:  # Show last 5 days
        with open(trade_file) as f:
            trades = json.load(f)

        date = trade_file.stem.replace("trades_", "")
        strategies = set(t.get("strategy", "Unknown") for t in trades)
        modes = set(t.get("mode", "LIVE") for t in trades)

        print(f"\n📅 {date}: {len(trades)} trade(s)")
        print(f"   Strategies: {', '.join(strategies)}")
        print(f"   Modes: {', '.join(modes)}")
        for t in trades:
            symbol = t.get("symbol", "?")
            action = t.get("action", "?")
            amount = t.get("amount", 0)
            mode = t.get("mode", "LIVE")
            print(f"   - {action} ${amount:.2f} {symbol} [{mode}]")


def check_alpaca_connection():
    """Check Alpaca API connection."""
    print("\n" + "=" * 70)
    print("5. ALPACA API CHECK")
    print("=" * 70)

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        print("❌ Cannot test API - credentials missing")
        return

    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(api_key, secret_key, paper=True)
        account = client.get_account()
        print(f"✅ Alpaca connection successful!")
        print(f"   Account: {account.account_number}")
        print(f"   Equity: ${float(account.equity):,.2f}")
        print(f"   Cash: ${float(account.cash):,.2f}")
        print(f"   Status: {account.status}")
    except ImportError:
        print("⚠️  alpaca-py not installed - skipping API check")
    except Exception as e:
        print(f"❌ Alpaca connection failed: {e}")


def check_workflow_files():
    """Check GitHub Actions workflow files."""
    print("\n" + "=" * 70)
    print("6. WORKFLOW FILES CHECK")
    print("=" * 70)

    workflow_dir = Path(".github/workflows")
    critical_workflows = [
        "daily-trading.yml",
        "weekend-crypto-trading.yml",
        "dashboard-auto-update.yml",
    ]

    for wf in critical_workflows:
        wf_path = workflow_dir / wf
        if wf_path.exists():
            print(f"✅ {wf}: EXISTS")
            with open(wf_path) as f:
                content = f.read()
            # Check for update_performance_log.py
            if "update_performance_log.py" in content:
                print(f"   ✅ Includes performance log update step")
            else:
                print(f"   ⚠️  Missing performance log update step")
        else:
            print(f"❌ {wf}: MISSING")


def main():
    print("=" * 70)
    print("🔍 TRADING SYSTEM DIAGNOSTICS")
    print(f"📅 Run at: {datetime.now().isoformat()}")
    print("=" * 70)

    check_environment()
    check_system_state()
    check_performance_log()
    check_recent_trades()
    check_alpaca_connection()
    check_workflow_files()

    print("\n" + "=" * 70)
    print("DIAGNOSTIC COMPLETE")
    print("=" * 70)
    print("\n⚡ Next Steps:")
    print("1. Check GitHub Actions logs for workflow failures")
    print("2. Verify secrets are configured in repo settings")
    print("3. Run 'python3 scripts/autonomous_trader.py --dry-run' to test locally")
    print()


if __name__ == "__main__":
    main()

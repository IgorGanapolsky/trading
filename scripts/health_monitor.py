#!/usr/bin/env python3
"""Monitor trading system health and alert on failures.

Detects:
1. Missing trades (no execution in last N days)
2. Workflow failures (>60% of recent runs failed)
3. Stale system state (not updated in >48 hours)
4. Account connectivity issues

Part of P1: Health Monitoring & Alerts from SYSTEMIC_FAILURE_PREVENTION_PLAN.md
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path


def check_recent_trades(days=2) -> tuple[bool, str]:
    """Check if trades executed in last N days.

    Returns:
        (is_healthy, status_message)
    """
    datetime.now() - timedelta(days=days)

    trades_found = []
    for day in range(days + 1):
        date = (datetime.now() - timedelta(days=day)).strftime("%Y-%m-%d")
        trade_file = Path(f"data/trades_{date}.json")

        if trade_file.exists():
            try:
                trades = json.loads(trade_file.read_text())
                if not isinstance(trades, list):
                    trades = [trades]

                if trades:
                    trades_found.append(f"{date}: {len(trades)} trades")
            except json.JSONDecodeError:
                continue

    if trades_found:
        status = "\n".join([f"  ✅ {t}" for t in trades_found])
        return True, f"Recent trades found:\n{status}"
    else:
        return False, f"❌ CRITICAL: No trades in last {days} days - SYSTEM NOT TRADING"


def check_workflow_health() -> tuple[bool, str]:
    """Check recent workflow runs via gh CLI.

    Returns:
        (is_healthy, status_message)
    """
    try:
        result = subprocess.run(
            ["gh", "run", "list", "--limit", "10", "--json", "conclusion,name,createdAt"],
            capture_output=True,
            text=True,
            timeout=10,
        )

        if result.returncode != 0:
            return False, f"⚠️  Could not fetch workflow status: {result.stderr}"

        runs = json.loads(result.stdout)
        if not runs:
            return True, "ℹ️  No recent workflow runs found"

        failures = [r for r in runs if r.get("conclusion") == "failure"]
        success_count = len(runs) - len(failures)

        # Alert if >60% of recent runs failed
        failure_rate = len(failures) / len(runs)

        if failure_rate >= 0.6:
            failed_workflows = "\n".join([f"  - {r['name']}" for r in failures[:3]])
            return (
                False,
                f"❌ CRITICAL: {len(failures)}/{len(runs)} recent workflows failed ({failure_rate:.0%}):\n{failed_workflows}",
            )
        else:
            return (
                True,
                f"✅ Workflows healthy: {success_count}/{len(runs)} succeeded ({100 - failure_rate * 100:.0f}% success)",
            )

    except subprocess.TimeoutExpired:
        return False, "⚠️  Workflow health check timed out"
    except json.JSONDecodeError:
        return False, "⚠️  Could not parse workflow status"
    except Exception as e:
        return False, f"⚠️  Error checking workflows: {e}"


def check_system_state() -> tuple[bool, str]:
    """Check if system_state.json is up to date.

    Returns:
        (is_healthy, status_message)
    """
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        return False, "⚠️  system_state.json not found (will be created on first run)"

    try:
        state = json.loads(state_file.read_text())
        last_updated = state.get("meta", {}).get("last_updated", "")

        if not last_updated:
            return True, "ℹ️  system_state.json has no last_updated timestamp"

        # Parse timestamp
        if "T" in last_updated:
            updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
        else:
            updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")

        age_hours = (datetime.now() - updated_dt.replace(tzinfo=None)).total_seconds() / 3600

        if age_hours > 48:
            return (
                False,
                f"❌ system_state.json is stale ({age_hours:.1f} hours old, last: {last_updated})",
            )
        else:
            return True, f"✅ System state current (updated {age_hours:.1f} hours ago)"

    except Exception as e:
        return False, f"⚠️  Could not validate system_state.json: {e}"


def check_alpaca_connectivity() -> tuple[bool, str]:
    """Check if we can connect to Alpaca API.

    Returns:
        (is_healthy, status_message)
    """
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")

    if not api_key or not secret_key:
        return True, "ℹ️  Alpaca credentials not in environment (expected in CI)"

    try:
        from alpaca.trading.client import TradingClient

        client = TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
        account = client.get_account()

        equity = float(account.equity)
        return True, f"✅ Alpaca connected: ${equity:,.2f} equity"

    except ImportError:
        return True, "ℹ️  Alpaca SDK not installed (expected in CI)"
    except Exception as e:
        return False, f"❌ Alpaca connection failed: {e}"


def main():
    """Run all health checks and report status."""
    print("=" * 70)
    print("TRADING SYSTEM HEALTH MONITOR")
    print("=" * 70)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    checks = [
        ("Recent Trades", check_recent_trades),
        ("Workflow Health", check_workflow_health),
        ("System State", check_system_state),
        ("Alpaca Connectivity", check_alpaca_connectivity),
    ]

    results = []
    all_healthy = True

    for name, check_fn in checks:
        print(f"Check: {name}")
        print("-" * 70)

        is_healthy, message = check_fn()
        results.append((name, is_healthy, message))

        print(message)
        print()

        if not is_healthy:
            all_healthy = False

    # Summary
    print("=" * 70)
    if all_healthy:
        print("✅ SYSTEM HEALTHY - All checks passed")
        print("=" * 70)
        return 0
    else:
        print("❌ SYSTEM UNHEALTHY - Issues detected")
        print()
        print("Failed checks:")
        for name, is_healthy, message in results:
            if not is_healthy:
                print(f"  - {name}")
        print("=" * 70)
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

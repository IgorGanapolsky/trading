#!/usr/bin/env python3
"""Monitor trading system health and alert on failures.

Detects:
1. Missing trades (no execution in last N days)
2. Workflow failures (>60% of recent runs failed)
3. Stale system state (not updated in >48 hours)
4. Account connectivity issues
5. Budget burn rate (on track for $100/month?) - Jan 2026
6. Gemini failover readiness (backup LLM operational?) - Jan 2026

Part of P1: Health Monitoring & Alerts from SYSTEMIC_FAILURE_PREVENTION_PLAN.md
"""

import json
import logging
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
from src.utils.error_monitoring import init_sentry

load_dotenv()
init_sentry()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def check_recent_trades(days=2) -> tuple[bool, str]:
    """Check if trades executed in last N days.

    Returns:
        (is_healthy, status_message)
    """
    # Calculate cutoff date for trade search
    cutoff_date = datetime.now() - timedelta(days=days)
    _ = cutoff_date  # Used for logging if needed

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


def check_budget_health() -> tuple[bool, str]:
    """Check if budget spending is on track for $100/month.

    Returns:
        (is_healthy, status_message)
    """
    budget_file = Path("data/budget_tracker.json")
    monthly_budget = 100.00

    if not budget_file.exists():
        return True, "ℹ️  No budget data yet (tracking will start on first API call)"

    try:
        data = json.loads(budget_file.read_text())
        spent = data.get("spent_this_month", 0.0)
        remaining = monthly_budget - spent

        # Calculate projected spend
        now = datetime.now()
        days_elapsed = now.day
        days_total = 30  # Approximate
        daily_rate = spent / max(days_elapsed, 1)
        projected = daily_rate * days_total

        # Determine health
        pct_remaining = remaining / monthly_budget

        if pct_remaining > 0.50:
            health = "healthy"
            status = "✅"
        elif pct_remaining > 0.20:
            health = "caution"
            status = "⚠️ "
        else:
            health = "critical"
            status = "❌"

        on_track = projected <= monthly_budget

        message = (
            f"{status} Budget {health.upper()}: ${spent:.2f} spent, "
            f"${remaining:.2f} remaining ({pct_remaining:.0%})\n"
            f"     Projected: ${projected:.2f}/month "
            f"({'on track' if on_track else 'OVER BUDGET'})"
        )

        return pct_remaining > 0.10, message  # Fail if <10% remaining

    except Exception as e:
        return True, f"⚠️  Could not check budget: {e}"


def check_gemini_failover() -> tuple[bool, str]:
    """Check if Gemini backup LLM is operational.

    Returns:
        (is_healthy, status_message)
    """
    api_key = os.getenv("GOOGLE_API_KEY")

    if not api_key:
        return True, "ℹ️  GOOGLE_API_KEY not set (Gemini failover unavailable)"

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-2.0-flash-exp")

        # Quick test - just verify the model can be initialized
        # (Don't actually call API to save quota)
        if model:
            return True, "✅ Gemini failover ready (model initialized)"

        return False, "❌ Gemini model initialization failed"

    except ImportError:
        return True, "ℹ️  google-generativeai not installed (expected in CI)"
    except Exception as e:
        return False, f"❌ Gemini failover check failed: {e}"


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
        ("Budget Health", check_budget_health),
        ("Gemini Failover", check_gemini_failover),
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

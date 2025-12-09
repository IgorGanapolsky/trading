#!/usr/bin/env python3
"""
TRADE EXECUTION VERIFICATION TESTS

These tests verify that trading actually executes, not just that workflows run.

The problem: Workflows can show "success" while trading is silently skipped.
The solution: Verify actual trade execution by checking Alpaca API.

This test should be run:
1. After daily-trading workflow completes
2. As part of post-market verification
3. When debugging why P/L isn't changing
"""

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TradeExecutionVerifier:
    """Verifies that trades are actually being executed."""

    def __init__(self):
        self.data_dir = Path(__file__).parent.parent / "data"
        self.alpaca_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_secret = os.getenv("ALPACA_SECRET_KEY")

    def test_system_state_updated_recently(self) -> tuple[bool, str]:
        """
        Test that system_state.json was updated in the last 24 hours.

        If it wasn't, trading likely isn't running.
        """
        state_file = self.data_dir / "system_state.json"

        if not state_file.exists():
            return False, "system_state.json does not exist"

        try:
            with open(state_file) as f:
                data = json.load(f)

            last_updated = data.get("meta", {}).get("last_updated")
            if not last_updated:
                return False, "system_state.json has no last_updated timestamp"

            # Parse timestamp
            if "T" in last_updated:
                updated_dt = datetime.fromisoformat(last_updated.replace("Z", "+00:00"))
            else:
                updated_dt = datetime.strptime(last_updated, "%Y-%m-%d %H:%M:%S")
                updated_dt = updated_dt.replace(tzinfo=timezone.utc)

            age_hours = (datetime.now(timezone.utc) - updated_dt).total_seconds() / 3600

            if age_hours > 24:
                return (
                    False,
                    f"system_state.json is {age_hours:.1f} hours old - trading may not be running",
                )

            return True, f"system_state.json updated {age_hours:.1f} hours ago"

        except Exception as e:
            return False, f"Error checking system_state.json: {e}"

    def test_trades_logged_today(self) -> tuple[bool, str]:
        """
        Test that trades are being logged.

        On trading days, there should be trade logs.
        """
        today = datetime.now().strftime("%Y-%m-%d")
        trades_file = self.data_dir / f"trades_{today}.json"

        # Also check audit trail
        audit_file = self.data_dir / "audit_trail" / "hybrid_funnel_runs.jsonl"

        has_trades = trades_file.exists()
        has_audit = audit_file.exists()

        if has_trades:
            try:
                with open(trades_file) as f:
                    trades = json.load(f)
                if isinstance(trades, list) and len(trades) > 0:
                    return True, f"Found {len(trades)} trades logged today"
            except Exception:
                pass

        if has_audit:
            try:
                # Check if audit has entries from today
                with open(audit_file) as f:
                    lines = f.readlines()
                    today_entries = sum(1 for line in lines if today in line)
                    if today_entries > 0:
                        return True, f"Found {today_entries} audit entries today"
            except Exception:
                pass

        # Check if today is a trading day
        weekday = datetime.now().weekday()
        if weekday >= 5:  # Weekend
            return True, "Weekend - no equity trades expected"

        return False, f"No trades or audit entries found for {today}"

    def test_alpaca_has_recent_orders(self) -> tuple[bool, str]:
        """
        Test that Alpaca has received orders recently.

        This is the ground truth - if Alpaca has no orders, trading isn't working.
        """
        if not self.alpaca_key or not self.alpaca_secret:
            return True, "Alpaca credentials not set (skipping in CI)"

        try:
            from alpaca.trading.client import TradingClient
            from alpaca.trading.enums import QueryOrderStatus
            from alpaca.trading.requests import GetOrdersRequest

            client = TradingClient(self.alpaca_key, self.alpaca_secret, paper=True)

            # Get orders from last 7 days
            request = GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                after=datetime.now(timezone.utc) - timedelta(days=7),
            )
            orders = client.get_orders(filter=request)

            if not orders:
                return (
                    False,
                    "No Alpaca orders in the last 7 days - trading is NOT working",
                )

            # Check for orders in last 24 hours (on trading days)
            recent_orders = [
                o for o in orders if o.created_at > datetime.now(timezone.utc) - timedelta(hours=24)
            ]

            weekday = datetime.now().weekday()
            if weekday < 5 and not recent_orders:  # Weekday, no recent orders
                return (
                    False,
                    f"No Alpaca orders in last 24 hours (found {len(orders)} older orders)",
                )

            return (
                True,
                f"Found {len(orders)} orders in last 7 days ({len(recent_orders)} in last 24h)",
            )

        except ImportError:
            return True, "alpaca-py not installed (skipping)"
        except Exception as e:
            return False, f"Alpaca API error: {e}"

    def test_equity_changed_recently(self) -> tuple[bool, str]:
        """
        Test that portfolio equity has changed in the last 7 days.

        If equity is flat, either:
        1. Trading isn't happening
        2. All trades are being cancelled
        3. System is stuck
        """
        state_file = self.data_dir / "system_state.json"
        perf_file = self.data_dir / "performance_log.json"

        if not state_file.exists():
            return False, "No system_state.json"

        try:
            with open(state_file) as f:
                state = json.load(f)

            current_equity = state.get("account", {}).get("current_equity", 0)
            starting_equity = state.get("account", {}).get("starting_balance", 100000)

            if current_equity == 0:
                return False, "Current equity is 0 - check Alpaca connection"

            pl = current_equity - starting_equity
            pl_pct = (pl / starting_equity) * 100 if starting_equity else 0

            # Check performance log for equity changes
            if perf_file.exists():
                with open(perf_file) as f:
                    perf_log = json.load(f)

                if len(perf_log) > 1:
                    # Check if equity has changed in last entries
                    recent = perf_log[-5:] if len(perf_log) >= 5 else perf_log
                    equities = [e.get("equity", 0) for e in recent]
                    unique_equities = len(set(equities))

                    if unique_equities == 1 and len(recent) >= 3:
                        return (
                            False,
                            f"Equity unchanged across {len(recent)} log entries - trading may be stuck",
                        )

            return True, f"Equity: ${current_equity:,.2f} (P/L: {pl_pct:+.4f}%)"

        except Exception as e:
            return False, f"Error checking equity: {e}"

    def test_workflow_actually_executed_trading(self) -> tuple[bool, str]:
        """
        Test that the workflow actually executed the trading step.

        This checks the last run status to see if trading was skipped.
        """
        status_file = self.data_dir / "last_run_status.json"

        if not status_file.exists():
            return True, "No last_run_status.json (first run or CI)"

        try:
            with open(status_file) as f:
                status = json.load(f)

            run_status = status.get("status", "UNKNOWN")
            step = status.get("step", "unknown")
            error = status.get("error")

            if run_status == "SUCCESS" and step == "complete":
                return True, "Last workflow run completed successfully"

            if run_status == "FAILURE":
                return False, f"Last workflow FAILED at step: {step}. Error: {error}"

            if "skip" in str(step).lower():
                return False, f"Last workflow SKIPPED trading: {step}"

            return True, f"Last run status: {run_status} ({step})"

        except Exception as e:
            return False, f"Error reading last_run_status.json: {e}"

    def run_all(self) -> list[tuple[str, bool, str]]:
        """Run all verification tests."""
        tests = [
            ("System State Updated Recently", self.test_system_state_updated_recently),
            ("Trades Logged Today", self.test_trades_logged_today),
            ("Alpaca Has Recent Orders", self.test_alpaca_has_recent_orders),
            ("Equity Changed Recently", self.test_equity_changed_recently),
            ("Workflow Executed Trading", self.test_workflow_actually_executed_trading),
        ]

        results = []
        for test_name, test_func in tests:
            try:
                passed, message = test_func()
                results.append((test_name, passed, message))
            except Exception as e:
                results.append((test_name, False, f"Test exception: {e}"))

        return results


def main():
    """Run trade execution verification."""
    print("=" * 70)
    print("TRADE EXECUTION VERIFICATION")
    print("Verifies that trading is ACTUALLY happening, not just workflows running")
    print("=" * 70)
    print()

    verifier = TradeExecutionVerifier()
    results = verifier.run_all()

    passed = 0
    failed = 0
    warnings = 0

    for test_name, passed_test, message in results:
        if passed_test:
            status = "✅ PASS"
            passed += 1
        else:
            # Some tests are warnings, not failures (e.g., weekend)
            if "Weekend" in message or "skipping" in message.lower():
                status = "⚠️  SKIP"
                warnings += 1
            else:
                status = "❌ FAIL"
                failed += 1

        print(f"{status}: {test_name}")
        print(f"   └─ {message}")

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed, {warnings} skipped")
    print("=" * 70)

    if failed > 0:
        print()
        print("❌ TRADING VERIFICATION FAILED")
        print("   Trades are NOT being executed as expected!")
        print("   Check workflow logs and Alpaca dashboard.")
        return 1

    print()
    print("✅ TRADE EXECUTION VERIFIED")
    return 0


if __name__ == "__main__":
    sys.exit(main())

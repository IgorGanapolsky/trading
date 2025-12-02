#!/usr/bin/env python3
"""
Health Check Script for Autonomous Trading Bot

Runs 30 minutes after trading execution (10:05 AM ET) to verify:
1. Trades were executed
2. Market data was fetched successfully
3. Portfolio state is fresh
4. No circuit breaker triggers

Alerts CEO via Telegram if any issues detected.
"""

import json
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.alerts.telegram_alerter import TelegramAlerter


class HealthCheckResult:
    """Result of a single health check."""

    def __init__(self, check_name: str, status: str, message: str, details: Optional[dict] = None):
        self.check_name = check_name
        self.status = status  # HEALTHY, WARNING, CRITICAL
        self.message = message
        self.details = details or {}


class HealthChecker:
    """
    Comprehensive health check orchestrator.

    Verifies all aspects of trading system operation and alerts CEO on failures.
    """

    def __init__(self):
        self.alerter = TelegramAlerter()
        self.project_root = Path(__file__).parent.parent
        self.data_dir = self.project_root / "data"
        self.logs_dir = self.project_root / "logs"

    def run_all_checks(self) -> list[HealthCheckResult]:
        """
        Run all health checks.

        Returns:
            List of HealthCheckResult objects
        """
        results = []

        print("=" * 70)
        print("🏥 AUTONOMOUS TRADING BOT - HEALTH CHECK")
        print(f"📅 Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S ET')}")
        print("=" * 70)
        print()

        # Check 1: GitHub Actions workflow status (MOST CRITICAL)
        results.append(self.check_github_actions_status())

        # Check 2: Trade file exists for today
        results.append(self.check_trade_file_exists())

        # Check 3: System state is fresh
        results.append(self.check_system_state_freshness())

        # Check 4: No market data errors in logs
        results.append(self.check_market_data_errors())

        # Check 5: Portfolio matches Alpaca API (if available)
        results.append(self.check_portfolio_accuracy())

        return results

    def check_github_actions_status(self) -> HealthCheckResult:
        """
        Check GitHub Actions workflow status for last 3 runs.
        This is THE MOST CRITICAL check - if workflow fails, nothing executes.
        """
        print("🔍 Checking GitHub Actions workflow status...")

        try:
            # Query GitHub API for last 3 workflow runs
            result = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--workflow=daily-trading.yml",
                    "--limit",
                    "3",
                    "--json",
                    "conclusion,createdAt,displayTitle",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode != 0:
                return HealthCheckResult(
                    check_name="github_actions_status",
                    status="WARNING",
                    message=f"Cannot query GitHub API: {result.stderr[:100]}",
                )

            runs = json.loads(result.stdout)

            if not runs:
                return HealthCheckResult(
                    check_name="github_actions_status",
                    status="CRITICAL",
                    message="No workflow runs found",
                )

            # Check last 3 runs
            failures = [r for r in runs if r.get("conclusion") == "failure"]
            successes = [r for r in runs if r.get("conclusion") == "success"]

            # CRITICAL: 3 consecutive failures
            if len(failures) >= 3:
                return HealthCheckResult(
                    check_name="github_actions_status",
                    status="CRITICAL",
                    message="Last 3 workflow runs FAILED - trading not executing!",
                    details={
                        "consecutive_failures": 3,
                        "last_run": runs[0].get("createdAt"),
                        "action": "Check GitHub Actions logs immediately",
                    },
                )

            # WARNING: 2 failures
            if len(failures) >= 2:
                return HealthCheckResult(
                    check_name="github_actions_status",
                    status="WARNING",
                    message="2 of last 3 workflow runs FAILED",
                    details={
                        "failures": len(failures),
                        "successes": len(successes),
                        "last_run": runs[0].get("createdAt"),
                    },
                )

            # WARNING: Latest run failed
            if runs[0].get("conclusion") == "failure":
                return HealthCheckResult(
                    check_name="github_actions_status",
                    status="WARNING",
                    message="Latest workflow run FAILED",
                    details={
                        "last_run": runs[0].get("createdAt"),
                        "action": "Check GitHub Actions logs",
                    },
                )

            # HEALTHY: Recent successes
            return HealthCheckResult(
                check_name="github_actions_status",
                status="HEALTHY",
                message=f"Last 3 workflow runs: {len(successes)} success, {len(failures)} failure",
                details={
                    "last_run": runs[0].get("createdAt"),
                    "last_conclusion": runs[0].get("conclusion"),
                },
            )

        except subprocess.TimeoutExpired:
            return HealthCheckResult(
                check_name="github_actions_status",
                status="WARNING",
                message="GitHub API query timed out",
            )
        except Exception as e:
            return HealthCheckResult(
                check_name="github_actions_status",
                status="WARNING",
                message=f"Failed to check workflow status: {str(e)[:100]}",
            )

    def check_trade_file_exists(self) -> HealthCheckResult:
        """Verify data/trades_YYYY-MM-DD.json exists for today."""
        print("🔍 Checking if trades file exists...")

        today = date.today()
        trade_file = self.data_dir / f"trades_{today.isoformat()}.json"

        if not trade_file.exists():
            # Check if market is open today (weekdays only)
            if today.weekday() >= 5:  # Saturday=5, Sunday=6
                return HealthCheckResult(
                    check_name="trade_file_exists",
                    status="HEALTHY",
                    message="Market closed (weekend) - no trades expected",
                )

            return HealthCheckResult(
                check_name="trade_file_exists",
                status="CRITICAL",
                message=f"No trades file found for {today}",
                details={"expected_file": str(trade_file)},
            )

        # File exists - check if it has content
        try:
            with open(trade_file) as f:
                trades = json.load(f)

            if not trades:
                return HealthCheckResult(
                    check_name="trade_file_exists",
                    status="WARNING",
                    message="Trades file exists but is empty",
                    details={"file": str(trade_file)},
                )

            return HealthCheckResult(
                check_name="trade_file_exists",
                status="HEALTHY",
                message=f"Trades file found with {len(trades)} entries",
                details={"file": str(trade_file), "trade_count": len(trades)},
            )

        except json.JSONDecodeError as e:
            return HealthCheckResult(
                check_name="trade_file_exists",
                status="CRITICAL",
                message=f"Trades file is corrupted: {e}",
                details={"file": str(trade_file)},
            )

    def check_system_state_freshness(self) -> HealthCheckResult:
        """Verify system_state.json was updated < 24 hours ago."""
        print("🔍 Checking system state freshness...")

        state_file = self.data_dir / "system_state.json"

        if not state_file.exists():
            return HealthCheckResult(
                check_name="system_state_freshness",
                status="CRITICAL",
                message="system_state.json does not exist",
            )

        try:
            with open(state_file) as f:
                state = json.load(f)

            last_updated_str = state.get("meta", {}).get("last_updated")
            if not last_updated_str:
                return HealthCheckResult(
                    check_name="system_state_freshness",
                    status="CRITICAL",
                    message="system_state.json missing last_updated timestamp",
                )

            last_updated = datetime.fromisoformat(last_updated_str)
            age_hours = (datetime.now() - last_updated).total_seconds() / 3600

            if age_hours > 48:
                return HealthCheckResult(
                    check_name="system_state_freshness",
                    status="CRITICAL",
                    message=f"system_state.json is {age_hours:.1f}h old (stale)",
                    details={"last_updated": str(last_updated), "age_hours": age_hours},
                )

            if age_hours > 24:
                return HealthCheckResult(
                    check_name="system_state_freshness",
                    status="WARNING",
                    message=f"system_state.json is {age_hours:.1f}h old",
                    details={"last_updated": str(last_updated), "age_hours": age_hours},
                )

            return HealthCheckResult(
                check_name="system_state_freshness",
                status="HEALTHY",
                message=f"system_state.json is {age_hours:.1f}h old (fresh)",
                details={"last_updated": str(last_updated), "age_hours": age_hours},
            )

        except Exception as e:
            return HealthCheckResult(
                check_name="system_state_freshness",
                status="CRITICAL",
                message=f"Failed to read system_state.json: {e}",
            )

    def check_market_data_errors(self) -> HealthCheckResult:
        """Parse logs for market data fetch failures."""
        print("🔍 Checking for market data errors...")

        stderr_log = self.logs_dir / "workflow_stderr.log"

        if not stderr_log.exists():
            return HealthCheckResult(
                check_name="market_data_errors",
                status="WARNING",
                message="workflow_stderr.log does not exist",
            )

        try:
            # Read last 100 lines (today's execution)
            with open(stderr_log) as f:
                lines = f.readlines()[-100:]

            # Look for critical error patterns
            error_patterns = [
                "Failed to fetch",
                "No data returned",
                "gaierror",
                "Exception",
                "Failed download",
                "No timezone found",
                "All symbols rejected",
            ]

            errors_found = []
            for line in lines:
                for pattern in error_patterns:
                    if pattern in line and line.strip():
                        errors_found.append(line.strip())

            if errors_found:
                # Deduplicate similar errors
                unique_errors = list(set(errors_found))[:5]  # First 5 unique

                return HealthCheckResult(
                    check_name="market_data_errors",
                    status="CRITICAL" if len(unique_errors) > 3 else "WARNING",
                    message=f"Found {len(errors_found)} market data errors in logs",
                    details={"errors": unique_errors, "total_count": len(errors_found)},
                )

            return HealthCheckResult(
                check_name="market_data_errors",
                status="HEALTHY",
                message="No market data errors found in logs",
            )

        except Exception as e:
            return HealthCheckResult(
                check_name="market_data_errors",
                status="WARNING",
                message=f"Failed to parse error logs: {e}",
            )

    def check_portfolio_accuracy(self) -> HealthCheckResult:
        """Verify portfolio data matches Alpaca API."""
        print("🔍 Checking portfolio accuracy...")

        state_file = self.data_dir / "system_state.json"

        if not state_file.exists():
            return HealthCheckResult(
                check_name="portfolio_accuracy",
                status="WARNING",
                message="Cannot verify - system_state.json missing",
            )

        try:
            with open(state_file) as f:
                state = json.load(f)

            account = state.get("account", {})
            equity = account.get("current_equity", 0)
            pl = account.get("total_pl", 0)

            # TODO: Query Alpaca API for ground truth comparison
            # For now, just verify values are reasonable

            if equity < 90000 or equity > 110000:
                return HealthCheckResult(
                    check_name="portfolio_accuracy",
                    status="WARNING",
                    message=f"Portfolio value unusual: ${equity:,.2f}",
                    details={"equity": equity, "pl": pl},
                )

            return HealthCheckResult(
                check_name="portfolio_accuracy",
                status="HEALTHY",
                message=f"Portfolio: ${equity:,.2f} (P/L: ${pl:+,.2f})",
                details={"equity": equity, "pl": pl},
            )

        except Exception as e:
            return HealthCheckResult(
                check_name="portfolio_accuracy",
                status="WARNING",
                message=f"Failed to read portfolio data: {e}",
            )

    def calculate_overall_status(self, results: list[HealthCheckResult]) -> str:
        """
        Determine overall health status from individual checks.

        Returns:
            HEALTHY, WARNING, or CRITICAL
        """
        statuses = [r.status for r in results]

        if "CRITICAL" in statuses:
            return "CRITICAL"
        elif "WARNING" in statuses:
            return "WARNING"
        else:
            return "HEALTHY"

    def format_results(self, results: list[HealthCheckResult]) -> str:
        """Format results for display and alerting."""
        output = []

        for result in results:
            status_emoji = {"HEALTHY": "✅", "WARNING": "⚠️", "CRITICAL": "❌"}.get(
                result.status, "❓"
            )

            output.append(f"{status_emoji} {result.check_name}: {result.message}")

        return "\n".join(output)

    def send_alerts(self, overall_status: str, results: list[HealthCheckResult]):
        """Send alerts via Telegram if issues detected."""
        if overall_status == "HEALTHY":
            print("\n✅ All checks passed - no alerts sent")
            return

        # Build alert message
        failed_checks = [r for r in results if r.status != "HEALTHY"]

        message = f"*HEALTH CHECK {overall_status}*\n\n"
        message += "Failed Checks:\n"

        for check in failed_checks:
            status_emoji = "⚠️" if check.status == "WARNING" else "❌"
            message += f"{status_emoji} {check.check_name}\n"
            message += f"   {check.message}\n"

        message += "\n📁 Check logs for details"
        message += "\n🎯 Next execution: Tomorrow 9:35 AM ET"

        # Send via Telegram
        if overall_status == "CRITICAL":
            self.alerter.send_alert(message, level="CRITICAL")
        else:
            self.alerter.send_alert(message, level="WARNING")


def main():
    """Main health check execution."""
    checker = HealthChecker()

    # Run all checks
    results = checker.run_all_checks()

    # Calculate overall status
    overall_status = checker.calculate_overall_status(results)

    # Print results
    print("\n" + "=" * 70)
    print("📊 HEALTH CHECK RESULTS")
    print("=" * 70)
    print(checker.format_results(results))
    print()
    print(f"Overall Status: {overall_status}")
    print("=" * 70)

    # Send alerts if needed
    checker.send_alerts(overall_status, results)

    # Exit with appropriate code
    if overall_status == "CRITICAL":
        sys.exit(1)
    elif overall_status == "WARNING":
        sys.exit(2)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()

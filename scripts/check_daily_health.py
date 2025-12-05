#!/usr/bin/env python3
"""
Daily Trading Health Check Script.

Validates system health over the past N days:
- SLO: "Daily trading job success rate >= 99% over 30 days"
- Checks for missing trading days
- Categorizes failures by type
- Reports on data integrity, broker connectivity, risk violations, bugs

Exit codes:
    0: Health check passed
    1: Health check failed (below threshold)
    2: Warning (some issues but above threshold)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import NamedTuple


# Error taxonomy for failure classification
class ErrorType(Enum):
    DATA_INTEGRITY_ERROR = "data_integrity"
    BROKER_CONNECTIVITY_ERROR = "broker_connectivity"
    RISK_VIOLATION_ABORT = "risk_violation"
    API_AUTH_ERROR = "api_auth"
    BUG_UNEXPECTED_EXCEPTION = "bug"
    UNKNOWN = "unknown"


class DayStatus(NamedTuple):
    date: str
    executed: bool
    success: bool
    error_type: ErrorType | None
    error_message: str | None


def classify_error(error_msg: str | None) -> ErrorType:
    """Classify an error message into a standard error type."""
    if not error_msg:
        return ErrorType.UNKNOWN

    error_lower = error_msg.lower()

    if any(
        term in error_lower for term in ["authentication", "api_key", "auth_token", "401", "403"]
    ):
        return ErrorType.API_AUTH_ERROR

    if any(
        term in error_lower for term in ["connection", "timeout", "network", "dns", "unreachable"]
    ):
        return ErrorType.BROKER_CONNECTIVITY_ERROR

    if any(
        term in error_lower for term in ["json", "parse", "invalid data", "corrupt", "missing file"]
    ):
        return ErrorType.DATA_INTEGRITY_ERROR

    if any(
        term in error_lower
        for term in ["risk", "circuit breaker", "max drawdown", "position limit"]
    ):
        return ErrorType.RISK_VIOLATION_ABORT

    if any(term in error_lower for term in ["exception", "error", "traceback", "failed"]):
        return ErrorType.BUG_UNEXPECTED_EXCEPTION

    return ErrorType.UNKNOWN


def get_market_days(start_date: datetime, end_date: datetime) -> list[str]:
    """Get list of market days (weekdays, excluding US holidays) between dates."""
    try:
        import holidays

        us_holidays = holidays.US(years=[start_date.year, end_date.year])
    except ImportError:
        us_holidays = {}

    market_days = []
    current = start_date
    while current <= end_date:
        # Skip weekends
        if current.weekday() < 5:  # Monday = 0, Friday = 4
            # Skip US holidays
            if current.date() not in us_holidays:
                market_days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)

    return market_days


def load_audit_trail(data_dir: Path) -> dict[str, dict]:
    """Load all audit trail files and index by date."""
    audit_dir = data_dir / "audit_trail"
    if not audit_dir.exists():
        return {}

    audits_by_date = {}
    for audit_file in audit_dir.glob("*.json"):
        try:
            with open(audit_file) as f:
                audit = json.load(f)

            # Extract date from timestamp or filename
            timestamp = audit.get("timestamp", "")
            if timestamp:
                date_str = timestamp.split("T")[0]
            else:
                # Try to extract from filename like plan_20251128_094831_audit.json
                parts = audit_file.stem.split("_")
                if len(parts) >= 2 and len(parts[1]) == 8:
                    date_str = f"{parts[1][:4]}-{parts[1][4:6]}-{parts[1][6:8]}"
                else:
                    continue

            # Store most recent audit for each date
            if date_str not in audits_by_date or timestamp > audits_by_date[date_str].get(
                "timestamp", ""
            ):
                audits_by_date[date_str] = audit
        except Exception:
            continue

    return audits_by_date


def load_system_state(data_dir: Path) -> dict:
    """Load system state file."""
    state_file = data_dir / "system_state.json"
    if not state_file.exists():
        return {}

    try:
        with open(state_file) as f:
            return json.load(f)
    except Exception:
        return {}


def analyze_audit(audit: dict) -> tuple[bool, ErrorType | None, str | None]:
    """Analyze an audit record for success/failure status."""
    execution_results = audit.get("execution_results", {})

    # Check for errors in any phase
    errors = execution_results.get("errors", [])

    # Check phase statuses
    phases = execution_results.get("phases", {})
    for phase_name, phase_data in phases.items():
        if isinstance(phase_data, dict):
            # Check for phase-level errors
            if phase_data.get("error"):
                errors.append(phase_data["error"])

            # Check task-level errors
            tasks = phase_data.get("tasks", {})
            for task_name, task_data in tasks.items():
                if isinstance(task_data, dict) and not task_data.get("success", True):
                    errors.append(f"{task_name}: {task_data.get('error', 'failed')}")

    # Determine overall success
    final_decision = execution_results.get("final_decision", "")
    success = final_decision in ["TRADE_EXECUTED", "NO_TRADE_NEEDED", "HOLD"] or not errors

    if errors:
        error_msg = "; ".join(str(e) for e in errors[:3])  # Limit to first 3
        error_type = classify_error(error_msg)
        return success, error_type, error_msg

    return success, None, None


def check_health(
    data_dir: Path,
    lookback_days: int = 30,
    success_threshold: float = 0.99,
) -> tuple[bool, list[DayStatus], dict]:
    """
    Check trading health over the lookback period.

    Returns:
        (health_ok, day_statuses, summary_stats)
    """
    today = datetime.now()
    start_date = today - timedelta(days=lookback_days)

    # Get expected market days
    expected_days = get_market_days(start_date, today)

    # Load audit trail
    audits = load_audit_trail(data_dir)

    # Analyze each expected market day
    day_statuses = []
    for day in expected_days:
        if day in audits:
            success, error_type, error_msg = analyze_audit(audits[day])
            day_statuses.append(
                DayStatus(
                    date=day,
                    executed=True,
                    success=success,
                    error_type=error_type,
                    error_message=error_msg,
                )
            )
        else:
            day_statuses.append(
                DayStatus(
                    date=day,
                    executed=False,
                    success=False,
                    error_type=ErrorType.UNKNOWN,
                    error_message="No audit trail found",
                )
            )

    # Calculate statistics
    total_days = len(day_statuses)
    executed_days = sum(1 for s in day_statuses if s.executed)
    successful_days = sum(1 for s in day_statuses if s.success)

    # Count error types
    error_counts = Counter(s.error_type for s in day_statuses if s.error_type)

    success_rate = successful_days / total_days if total_days > 0 else 0.0
    execution_rate = executed_days / total_days if total_days > 0 else 0.0

    summary = {
        "lookback_days": lookback_days,
        "total_market_days": total_days,
        "executed_days": executed_days,
        "successful_days": successful_days,
        "missing_days": total_days - executed_days,
        "failed_days": executed_days - successful_days,
        "success_rate": success_rate,
        "execution_rate": execution_rate,
        "error_breakdown": {e.value: c for e, c in error_counts.items() if e},
        "threshold": success_threshold,
        "health_ok": success_rate >= success_threshold,
    }

    return success_rate >= success_threshold, day_statuses, summary


def print_report(day_statuses: list[DayStatus], summary: dict, verbose: bool = False):
    """Print the health check report."""
    print("\n" + "=" * 70)
    print("DAILY TRADING HEALTH CHECK")
    print(f"Report Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

    print(f"\n📊 SUMMARY (Last {summary['lookback_days']} days)")
    print("-" * 40)
    print(f"   Total Market Days:    {summary['total_market_days']}")
    print(f"   Executed Days:        {summary['executed_days']}")
    print(f"   Successful Days:      {summary['successful_days']}")
    print(f"   Missing Days:         {summary['missing_days']}")
    print(f"   Failed Days:          {summary['failed_days']}")
    print(f"   Success Rate:         {summary['success_rate']:.1%}")
    print(f"   Execution Rate:       {summary['execution_rate']:.1%}")
    print(f"   Required Threshold:   {summary['threshold']:.1%}")

    if summary["error_breakdown"]:
        print("\n🚨 ERROR BREAKDOWN")
        print("-" * 40)
        for error_type, count in sorted(summary["error_breakdown"].items(), key=lambda x: -x[1]):
            print(f"   {error_type}: {count}")

    # Show recent failures
    failures = [s for s in day_statuses if not s.success]
    if failures:
        print(f"\n⚠️  RECENT ISSUES ({len(failures)} days)")
        print("-" * 40)
        for status in failures[-5:]:  # Show last 5
            error_type = status.error_type.value if status.error_type else "unknown"
            msg = (
                status.error_message[:60] + "..."
                if status.error_message and len(status.error_message) > 60
                else status.error_message
            )
            if status.executed:
                print(f"   {status.date}: [{error_type}] {msg}")
            else:
                print(f"   {status.date}: MISSING - no execution recorded")

    if verbose:
        print("\n📅 DAILY BREAKDOWN")
        print("-" * 40)
        for status in day_statuses:
            icon = "✅" if status.success else ("⚠️" if status.executed else "❌")
            print(f"   {status.date}: {icon}")

    print("\n" + "=" * 70)
    if summary["health_ok"]:
        print("✅ HEALTH CHECK PASSED")
    else:
        print("❌ HEALTH CHECK FAILED")
        print(
            f"   Success rate {summary['success_rate']:.1%} is below threshold {summary['threshold']:.1%}"
        )
    print("=" * 70 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Check daily trading health")
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data"),
        help="Path to data directory",
    )
    parser.add_argument(
        "--lookback",
        type=int,
        default=30,
        help="Number of days to look back (default: 30)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.99,
        help="Success rate threshold (default: 0.99)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Show detailed daily breakdown",
    )
    parser.add_argument(
        "--ci",
        action="store_true",
        help="Exit with error code if health check fails",
    )
    args = parser.parse_args()

    health_ok, day_statuses, summary = check_health(
        data_dir=args.data_dir,
        lookback_days=args.lookback,
        success_threshold=args.threshold,
    )

    print_report(day_statuses, summary, verbose=args.verbose)

    # Write to GitHub Actions output if available
    github_output = os.getenv("GITHUB_OUTPUT")
    if github_output:
        try:
            with open(github_output, "a") as f:
                f.write(f"health_ok={'true' if health_ok else 'false'}\n")
                f.write(f"success_rate={summary['success_rate']:.4f}\n")
                f.write(f"missing_days={summary['missing_days']}\n")
        except Exception:
            pass

    if args.ci and not health_ok:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

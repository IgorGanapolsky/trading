#!/usr/bin/env python3
"""
Workflow Health Monitor - Detects Silent Failures in Automated Trading

This script monitors whether scheduled GitHub Actions workflows are actually running.
It tracks expected executions vs actual executions and alerts on gaps.

Problem Solved:
- Crypto trading was supposed to run every weekend for 3 weeks but had 0 executions
- No one noticed because there was no monitoring of workflow execution

How it works:
1. Maintains execution log of all scheduled workflows
2. Calculates expected executions based on schedule
3. Compares expected vs actual
4. Alerts if executions are missed

Usage:
    python scripts/workflow_health_monitor.py --check
    python scripts/workflow_health_monitor.py --record daily-trading
    python scripts/workflow_health_monitor.py --report
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Workflow schedules (expected execution times)
WORKFLOW_SCHEDULES = {
    "daily-trading": {
        "name": "Daily Trading Execution",
        "schedule": "weekdays",  # Mon-Fri
        "time_et": "09:35",
        "critical": True,
    },
    "dashboard-update": {
        "name": "Dashboard Update",
        "schedule": "daily",
        "time_et": "10:00",
        "critical": False,
    },
}


class WorkflowHealthMonitor:
    """Monitors health of automated trading workflows."""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.execution_log_path = self.data_dir / "workflow_executions.json"
        self.health_report_path = self.data_dir / "workflow_health.json"
        self.executions = self._load_executions()

    def _load_executions(self) -> dict[str, list[dict]]:
        """Load execution log from disk."""
        if self.execution_log_path.exists():
            try:
                with open(self.execution_log_path) as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load execution log: {e}")
        return {}

    def _save_executions(self) -> None:
        """Save execution log to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        with open(self.execution_log_path, "w") as f:
            json.dump(self.executions, f, indent=2, default=str)

    def record_execution(
        self,
        workflow_id: str,
        status: str = "success",
        details: dict[str, Any] | None = None,
    ) -> None:
        """
        Record a workflow execution.

        Args:
            workflow_id: Workflow identifier (e.g., "daily-trading")
            status: Execution status ("success", "failure", "skipped")
            details: Additional execution details
        """
        if workflow_id not in self.executions:
            self.executions[workflow_id] = []

        execution = {
            "timestamp": datetime.now().isoformat(),
            "status": status,
            "details": details or {},
        }

        self.executions[workflow_id].append(execution)

        # Keep only last 100 executions per workflow
        if len(self.executions[workflow_id]) > 100:
            self.executions[workflow_id] = self.executions[workflow_id][-100:]

        self._save_executions()
        logger.info(f"Recorded {workflow_id} execution: {status}")

    def get_expected_executions(self, workflow_id: str, days: int = 7) -> list[datetime]:
        """Calculate expected execution times for a workflow."""
        schedule = WORKFLOW_SCHEDULES.get(workflow_id, {})
        schedule_type = schedule.get("schedule", "")
        time_et = schedule.get("time_et", "09:35")

        hour, minute = map(int, time_et.split(":"))
        expected = []
        today = datetime.now().replace(hour=hour, minute=minute, second=0, microsecond=0)

        for i in range(days):
            check_date = today - timedelta(days=i)
            weekday = check_date.weekday()  # 0=Mon, 6=Sun

            should_run = False
            if (
                schedule_type == "weekdays"
                and weekday < 5
                or schedule_type == "weekends"
                and weekday >= 5
                or schedule_type == "daily"
            ):
                should_run = True

            if should_run:
                expected.append(check_date)

        return expected

    def get_actual_executions(self, workflow_id: str, days: int = 7) -> list[datetime]:
        """Get actual execution times from log."""
        cutoff = datetime.now() - timedelta(days=days)
        actual = []

        for execution in self.executions.get(workflow_id, []):
            try:
                exec_time = datetime.fromisoformat(execution["timestamp"])
                if exec_time >= cutoff and execution.get("status") == "success":
                    actual.append(exec_time)
            except Exception:
                continue

        return actual

    def check_health(self, days: int = 7) -> dict[str, Any]:
        """
        Check health of all workflows.

        Returns:
            Health report with status for each workflow
        """
        report = {
            "timestamp": datetime.now().isoformat(),
            "period_days": days,
            "workflows": {},
            "alerts": [],
            "overall_health": "HEALTHY",
        }

        for workflow_id, schedule in WORKFLOW_SCHEDULES.items():
            expected = self.get_expected_executions(workflow_id, days)
            actual = self.get_actual_executions(workflow_id, days)

            expected_count = len(expected)
            actual_count = len(actual)
            execution_rate = actual_count / expected_count if expected_count > 0 else 0

            # Determine status
            if execution_rate >= 0.9:
                status = "HEALTHY"
            elif execution_rate >= 0.5:
                status = "DEGRADED"
            else:
                status = "CRITICAL"

            workflow_health = {
                "name": schedule["name"],
                "status": status,
                "expected_executions": expected_count,
                "actual_executions": actual_count,
                "execution_rate": round(execution_rate * 100, 1),
                "last_execution": None,
                "missed_dates": [],
            }

            # Get last execution
            if actual:
                workflow_health["last_execution"] = max(actual).isoformat()

            # Calculate missed dates
            actual_dates = {a.date() for a in actual}
            for exp in expected:
                if exp.date() not in actual_dates:
                    workflow_health["missed_dates"].append(exp.date().isoformat())

            report["workflows"][workflow_id] = workflow_health

            # Generate alerts for critical issues
            if status == "CRITICAL" and schedule.get("critical", False):
                alert = {
                    "severity": "CRITICAL",
                    "workflow": workflow_id,
                    "message": f"{schedule['name']} has only {actual_count}/{expected_count} executions ({execution_rate * 100:.0f}%)",
                    "missed_dates": workflow_health["missed_dates"][:5],
                }
                report["alerts"].append(alert)
                report["overall_health"] = "CRITICAL"
            elif status == "DEGRADED":
                if report["overall_health"] != "CRITICAL":
                    report["overall_health"] = "DEGRADED"

        # Save report
        with open(self.health_report_path, "w") as f:
            json.dump(report, f, indent=2)

        return report

    def print_report(self, report: dict[str, Any]) -> None:
        """Print formatted health report."""
        print("\n" + "=" * 70)
        print("WORKFLOW HEALTH REPORT")
        print("=" * 70)
        print(f"Generated: {report['timestamp']}")
        print(f"Period: Last {report['period_days']} days")
        print(f"Overall Health: {report['overall_health']}")
        print("-" * 70)

        for workflow_id, health in report["workflows"].items():
            status_icon = {
                "HEALTHY": "✅",
                "DEGRADED": "⚠️",
                "CRITICAL": "❌",
            }.get(health["status"], "❓")

            print(f"\n{status_icon} {health['name']} ({workflow_id})")
            print(f"   Status: {health['status']}")
            print(
                f"   Executions: {health['actual_executions']}/{health['expected_executions']} ({health['execution_rate']}%)"
            )
            if health["last_execution"]:
                print(f"   Last Run: {health['last_execution']}")
            if health["missed_dates"]:
                print(f"   Missed: {', '.join(health['missed_dates'][:3])}")
                if len(health["missed_dates"]) > 3:
                    print(f"           ...and {len(health['missed_dates']) - 3} more")

        if report["alerts"]:
            print("\n" + "-" * 70)
            print("🚨 ALERTS:")
            for alert in report["alerts"]:
                print(f"   [{alert['severity']}] {alert['message']}")

        print("\n" + "=" * 70)


def main():
    parser = argparse.ArgumentParser(description="Workflow Health Monitor")
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check health of all workflows",
    )
    parser.add_argument(
        "--record",
        type=str,
        metavar="WORKFLOW",
        help="Record successful execution of a workflow",
    )
    parser.add_argument(
        "--status",
        type=str,
        default="success",
        choices=["success", "failure", "skipped"],
        help="Status of recorded execution",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days to check (default: 7)",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="Generate and print health report",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output report as JSON",
    )

    args = parser.parse_args()
    monitor = WorkflowHealthMonitor()

    if args.record:
        monitor.record_execution(args.record, status=args.status)
        print(f"✅ Recorded {args.record} execution: {args.status}")
        return 0

    if args.check or args.report:
        report = monitor.check_health(days=args.days)

        if args.json:
            print(json.dumps(report, indent=2))
        else:
            monitor.print_report(report)

        # Exit with error code if critical
        if report["overall_health"] == "CRITICAL":
            return 1
        return 0

    # Default: show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Workflow Health Monitor - Detects Silent Failures in Automated Trading

This script monitors whether scheduled GitHub Actions workflows are actually running.
It tracks expected executions vs actual executions and alerts on gaps.

Problem Solved:
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

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)
ET = ZoneInfo("America/New_York")

# Workflow schedules (expected execution times)
WORKFLOW_SCHEDULES = {
    "ci": {
        "name": "Main CI",
        "schedule": "weekdays",  # Expected on active development days
        "time_et": "12:00",
        "critical": True,
    },
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
            "timestamp": datetime.now(tz=ET).isoformat(),
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
        now_et = datetime.now(tz=ET)
        today = now_et.replace(hour=hour, minute=minute, second=0, microsecond=0)

        for i in range(days):
            check_date = today - timedelta(days=i)
            weekday = check_date.weekday()  # 0=Mon, 6=Sun

            should_run = False
            if (
                (schedule_type == "weekdays" and weekday < 5)
                or (schedule_type == "weekends" and weekday >= 5)
                or schedule_type == "daily"
            ):
                should_run = True

            if should_run:
                if check_date > now_et:
                    continue
                expected.append(check_date)

        return expected

    def get_execution_records(self, workflow_id: str, days: int = 7) -> list[dict[str, Any]]:
        """Get execution records from log."""
        cutoff = datetime.now(tz=ET) - timedelta(days=days)
        records: list[dict[str, Any]] = []

        for execution in self.executions.get(workflow_id, []):
            try:
                exec_time = datetime.fromisoformat(execution["timestamp"])
                if exec_time.tzinfo is None:
                    exec_time = exec_time.replace(tzinfo=ET)
                else:
                    exec_time = exec_time.astimezone(ET)
                if exec_time >= cutoff:
                    records.append({"timestamp": exec_time, "status": execution.get("status", "unknown")})
            except Exception:
                continue

        return records

    def check_health(self, days: int = 7) -> dict[str, Any]:
        """
        Check health of all workflows.

        Returns:
            Health report with status for each workflow
        """
        report = {
            "timestamp": datetime.now(tz=ET).isoformat(),
            "period_days": days,
            "workflows": {},
            "alerts": [],
            "overall_health": "HEALTHY",
        }

        for workflow_id, schedule in WORKFLOW_SCHEDULES.items():
            expected = self.get_expected_executions(workflow_id, days)
            records = self.get_execution_records(workflow_id, days)
            actual = [row["timestamp"] for row in records if row.get("status") != "skipped"]
            success_count = sum(1 for row in records if row.get("status") == "success")
            failed_count = sum(
                1
                for row in records
                if row.get("status") in {"failure", "cancelled", "timed_out"}
            )

            expected_count = len(expected)
            actual_count = len(actual)
            execution_rate = actual_count / expected_count if expected_count > 0 else 0
            success_rate = success_count / max(1, actual_count)

            # Determine status
            if execution_rate >= 0.9 and success_rate >= 0.85:
                status = "HEALTHY"
            elif execution_rate >= 0.5 and success_rate >= 0.6:
                status = "DEGRADED"
            else:
                status = "CRITICAL"

            workflow_health = {
                "name": schedule["name"],
                "status": status,
                "expected_executions": expected_count,
                "actual_executions": actual_count,
                "success_executions": success_count,
                "failed_executions": failed_count,
                "execution_rate": round(execution_rate * 100, 1),
                "success_rate": round(success_rate * 100, 1),
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
            elif status == "CRITICAL":
                if report["overall_health"] == "HEALTHY":
                    report["overall_health"] = "DEGRADED"
            elif status == "DEGRADED":
                if report["overall_health"] != "CRITICAL":
                    report["overall_health"] = "DEGRADED"

        # Save report
        self.data_dir.mkdir(parents=True, exist_ok=True)
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
            print(
                f"   Outcomes: {health.get('success_executions', 0)} success / "
                f"{health.get('failed_executions', 0)} failed "
                f"(success rate {health.get('success_rate', 0)}%)"
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
        choices=["success", "failure", "cancelled", "timed_out", "queued", "in_progress", "skipped"],
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

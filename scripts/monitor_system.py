#!/usr/bin/env python3
"""
Real-time System Monitoring and Alerts

Monitors trading system health and sends alerts for critical issues.
Can be run continuously or as a one-time check.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv

load_dotenv()

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Configuration
DATA_DIR = Path("data")
PERF_LOG_FILE = DATA_DIR / "performance_log.json"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
ALERT_THRESHOLDS = {
    "max_perf_log_age_hours": 25,  # Alert if performance log > 25 hours old
    "max_system_state_age_hours": 25,  # Alert if system state > 25 hours old
    "min_equity": 95000,  # Alert if equity drops below $95k
    "max_daily_loss": 100,  # Alert if daily loss > $100
}


class SystemMonitor:
    """Monitors trading system health and generates alerts."""

    def __init__(self):
        self.alerts: list[dict] = []
        self.metrics: dict = {}

    def check_performance_log_freshness(self) -> bool:
        """Check if performance log was updated recently."""
        if not PERF_LOG_FILE.exists():
            self.alerts.append(
                {
                    "level": "CRITICAL",
                    "component": "Performance Log",
                    "message": "Performance log file does not exist",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False

        try:
            with open(PERF_LOG_FILE) as f:
                perf_data = json.load(f)

            if not perf_data:
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "Performance Log",
                        "message": "Performance log is empty",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return False

            last_entry = perf_data[-1]
            last_date = datetime.fromisoformat(
                last_entry.get("timestamp", last_entry.get("date", ""))
            )
            age_hours = (datetime.now() - last_date.replace(tzinfo=None)).total_seconds() / 3600

            self.metrics["perf_log_age_hours"] = age_hours

            if age_hours > ALERT_THRESHOLDS["max_perf_log_age_hours"]:
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "Performance Log",
                        "message": f"Performance log is {age_hours:.1f} hours old (threshold: {ALERT_THRESHOLDS['max_perf_log_age_hours']}h)",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return False

            return True
        except Exception as e:
            self.alerts.append(
                {
                    "level": "ERROR",
                    "component": "Performance Log",
                    "message": f"Error reading performance log: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False

    def check_system_state_freshness(self) -> bool:
        """Check if system state was updated recently."""
        if not SYSTEM_STATE_FILE.exists():
            self.alerts.append(
                {
                    "level": "WARNING",
                    "component": "System State",
                    "message": "System state file does not exist",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False

        try:
            with open(SYSTEM_STATE_FILE) as f:
                system_state = json.load(f)

            # Check both root level and meta.last_updated (backwards compatibility)
            last_updated_str = system_state.get("last_updated") or system_state.get("meta", {}).get(
                "last_updated"
            )
            if not last_updated_str:
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "System State",
                        "message": "System state has no timestamp",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return False

            last_updated = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            age_hours = (datetime.now() - last_updated.replace(tzinfo=None)).total_seconds() / 3600

            self.metrics["system_state_age_hours"] = age_hours

            if age_hours > ALERT_THRESHOLDS["max_system_state_age_hours"]:
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "System State",
                        "message": f"System state is {age_hours:.1f} hours old (threshold: {ALERT_THRESHOLDS['max_system_state_age_hours']}h)",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return False

            return True
        except Exception as e:
            self.alerts.append(
                {
                    "level": "ERROR",
                    "component": "System State",
                    "message": f"Error reading system state: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False

    def check_portfolio_health(self) -> bool:
        """Check portfolio equity and P/L."""
        try:
            with open(PERF_LOG_FILE) as f:
                perf_data = json.load(f)

            if not perf_data:
                return False

            last_entry = perf_data[-1]
            equity = last_entry.get("equity", 0)
            pl = last_entry.get("pl", 0)

            self.metrics["equity"] = equity
            self.metrics["pl"] = pl

            # Check equity threshold
            if equity < ALERT_THRESHOLDS["min_equity"]:
                self.alerts.append(
                    {
                        "level": "CRITICAL",
                        "component": "Portfolio",
                        "message": f"Equity dropped below ${ALERT_THRESHOLDS['min_equity']:,} (current: ${equity:,.2f})",
                        "timestamp": datetime.now().isoformat(),
                    }
                )
                return False

            # Check daily loss threshold
            if pl < -ALERT_THRESHOLDS["max_daily_loss"]:
                self.alerts.append(
                    {
                        "level": "WARNING",
                        "component": "Portfolio",
                        "message": f"Daily loss exceeds ${ALERT_THRESHOLDS['max_daily_loss']} (current: ${pl:,.2f})",
                        "timestamp": datetime.now().isoformat(),
                    }
                )

            return True
        except Exception as e:
            self.alerts.append(
                {
                    "level": "ERROR",
                    "component": "Portfolio",
                    "message": f"Error checking portfolio health: {e}",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False

    def check_workflow_status(self) -> bool:
        """Check GitHub Actions workflow status."""
        # This would require GitHub API access
        # For now, we'll check if workflow files exist
        workflow_file = Path(".github/workflows/daily-trading.yml")
        if not workflow_file.exists():
            self.alerts.append(
                {
                    "level": "ERROR",
                    "component": "Workflow",
                    "message": "Workflow file not found",
                    "timestamp": datetime.now().isoformat(),
                }
            )
            return False
        return True

    def run_all_checks(self) -> dict:
        """Run all health checks."""
        logger.info("Running system health checks...")

        self.check_performance_log_freshness()
        self.check_system_state_freshness()
        self.check_portfolio_health()
        self.check_workflow_status()

        # Categorize alerts by severity
        critical = [a for a in self.alerts if a["level"] == "CRITICAL"]
        warnings = [a for a in self.alerts if a["level"] == "WARNING"]
        errors = [a for a in self.alerts if a["level"] == "ERROR"]

        return {
            "timestamp": datetime.now().isoformat(),
            "status": "HEALTHY" if not critical and not errors else "UNHEALTHY",
            "metrics": self.metrics,
            "alerts": {
                "critical": critical,
                "warnings": warnings,
                "errors": errors,
                "total": len(self.alerts),
            },
        }

    def print_report(self, report: dict):
        """Print formatted monitoring report."""
        print("\n" + "=" * 70)
        print("SYSTEM MONITORING REPORT")
        print("=" * 70)
        print(f"Timestamp: {report['timestamp']}")
        print(f"Status: {report['status']}")
        print()

        print("📊 METRICS:")
        for key, value in report["metrics"].items():
            print(f"   {key}: {value}")
        print()

        alerts = report["alerts"]
        if alerts["total"] == 0:
            print("✅ No alerts - System is healthy")
        else:
            if alerts["critical"]:
                print("🚨 CRITICAL ALERTS:")
                for alert in alerts["critical"]:
                    print(f"   [{alert['component']}] {alert['message']}")
                print()

            if alerts["errors"]:
                print("❌ ERRORS:")
                for alert in alerts["errors"]:
                    print(f"   [{alert['component']}] {alert['message']}")
                print()

            if alerts["warnings"]:
                print("⚠️  WARNINGS:")
                for alert in alerts["warnings"]:
                    print(f"   [{alert['component']}] {alert['message']}")
                print()

        print("=" * 70)


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Monitor trading system health")
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuously (check every 5 minutes)",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=300,
        help="Check interval in seconds (default: 300 = 5 minutes)",
    )
    args = parser.parse_args()

    monitor = SystemMonitor()

    if args.continuous:
        logger.info(f"Starting continuous monitoring (interval: {args.interval}s)")
        try:
            while True:
                report = monitor.run_all_checks()
                monitor.print_report(report)
                monitor.alerts.clear()  # Clear for next iteration
                time.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
    else:
        report = monitor.run_all_checks()
        monitor.print_report(report)
        sys.exit(0 if report["status"] == "HEALTHY" else 1)


if __name__ == "__main__":
    main()

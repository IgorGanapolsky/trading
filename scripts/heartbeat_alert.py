#!/usr/bin/env python3
"""
Heartbeat Alerting System - Monitor scheduler health and alert on failures.

Monitors scheduler_heartbeat.json to ensure the trading scheduler is running.
Alerts when heartbeat is missing or stale during market hours.

Requirements:
1. Check if scheduler_heartbeat.json exists and is recent (< 2 hours during market hours)
2. Send alerts on failure (log file, webhook, email)
3. Can run as cron job or GitHub Action

Usage:
    # Check and alert if heartbeat is stale
    python3 scripts/heartbeat_alert.py

    # Check with custom threshold (in minutes)
    python3 scripts/heartbeat_alert.py --threshold 90

    # Dry run (check only, no alerts)
    python3 scripts/heartbeat_alert.py --dry-run

    # Force check even outside market hours
    python3 scripts/heartbeat_alert.py --force

Author: Trading System
Created: 2025-12-18
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Import after path setup
from src.utils.market_hours import get_market_status, MarketSession
from src.safety.emergency_alerts import EmergencyAlerts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


class HeartbeatMonitor:
    """Monitor scheduler heartbeat and alert on failures."""

    def __init__(
        self,
        heartbeat_file: str = "data/scheduler_heartbeat.json",
        threshold_minutes: int = 120,
        alert_log_file: str = "data/heartbeat_alerts.json",
        force_check: bool = False,
    ):
        """
        Initialize heartbeat monitor.

        Args:
            heartbeat_file: Path to scheduler heartbeat file
            threshold_minutes: Maximum age of heartbeat before alerting (default: 2 hours)
            alert_log_file: Path to alert log file
            force_check: Force check even outside market hours
        """
        self.heartbeat_file = PROJECT_ROOT / heartbeat_file
        self.threshold_minutes = threshold_minutes
        self.alert_log_file = PROJECT_ROOT / alert_log_file
        self.force_check = force_check
        self.alerts = EmergencyAlerts()

        # Ensure alert log directory exists
        self.alert_log_file.parent.mkdir(parents=True, exist_ok=True)

    def check_heartbeat(self) -> dict:
        """
        Check heartbeat status.

        Returns:
            dict with status, message, and metadata
        """
        result = {
            "timestamp": datetime.now().isoformat(),
            "status": "HEALTHY",
            "message": "",
            "details": {},
        }

        # Check market status
        market_status = get_market_status()
        result["details"]["market_status"] = {
            "session": market_status.session.value,
            "can_trade": market_status.can_trade,
            "reason": market_status.reason,
            "current_time_et": market_status.current_time_et.isoformat(),
        }

        # Only check during market hours unless forced
        is_market_hours = market_status.session == MarketSession.REGULAR
        if not is_market_hours and not self.force_check:
            result["status"] = "SKIPPED"
            result["message"] = f"Outside market hours ({market_status.session.value}). Skipping check."
            logger.info(result["message"])
            return result

        # Check if heartbeat file exists
        if not self.heartbeat_file.exists():
            result["status"] = "CRITICAL"
            result["message"] = (
                f"Heartbeat file not found: {self.heartbeat_file}. "
                f"Scheduler may not be running!"
            )
            result["details"]["file_exists"] = False
            logger.error(result["message"])
            return result

        # Read heartbeat file
        try:
            with open(self.heartbeat_file) as f:
                heartbeat_data = json.load(f)
            result["details"]["heartbeat_data"] = heartbeat_data
        except json.JSONDecodeError as e:
            result["status"] = "ERROR"
            result["message"] = f"Failed to parse heartbeat file: {e}"
            logger.error(result["message"])
            return result
        except Exception as e:
            result["status"] = "ERROR"
            result["message"] = f"Error reading heartbeat file: {e}"
            logger.error(result["message"])
            return result

        # Parse last_run timestamp
        last_run_str = heartbeat_data.get("last_run", "")
        if not last_run_str:
            result["status"] = "ERROR"
            result["message"] = "Heartbeat file missing 'last_run' timestamp"
            logger.error(result["message"])
            return result

        try:
            # Parse ISO format timestamp (e.g., "2025-12-18T14:30:00Z")
            last_run = datetime.fromisoformat(last_run_str.replace("Z", "+00:00"))
            # Convert to naive datetime for comparison
            last_run_naive = last_run.replace(tzinfo=None)
        except ValueError as e:
            result["status"] = "ERROR"
            result["message"] = f"Invalid timestamp format in heartbeat: {last_run_str} ({e})"
            logger.error(result["message"])
            return result

        # Calculate age of heartbeat
        now = datetime.utcnow()
        age_delta = now - last_run_naive
        age_minutes = age_delta.total_seconds() / 60

        result["details"]["last_run"] = last_run_str
        result["details"]["age_minutes"] = round(age_minutes, 2)
        result["details"]["threshold_minutes"] = self.threshold_minutes

        # Check if heartbeat is stale
        if age_minutes > self.threshold_minutes:
            result["status"] = "CRITICAL"
            result["message"] = (
                f"Scheduler heartbeat is STALE! "
                f"Last run: {last_run_str} ({age_minutes:.1f} minutes ago). "
                f"Threshold: {self.threshold_minutes} minutes. "
                f"Scheduler may be stuck or crashed!"
            )
            logger.error(result["message"])
        else:
            result["status"] = "HEALTHY"
            result["message"] = (
                f"Scheduler heartbeat is current. "
                f"Last run: {last_run_str} ({age_minutes:.1f} minutes ago)."
            )
            logger.info(result["message"])

        return result

    def send_alerts(self, status: dict) -> dict:
        """
        Send alerts based on status.

        Args:
            status: Status dict from check_heartbeat()

        Returns:
            dict with alert results
        """
        alert_results = {
            "timestamp": datetime.now().isoformat(),
            "alerts_sent": [],
            "errors": [],
        }

        # Only alert on CRITICAL or ERROR status
        if status["status"] not in ["CRITICAL", "ERROR"]:
            logger.info("Status is healthy, no alerts needed")
            return alert_results

        # Determine alert priority
        if status["status"] == "CRITICAL":
            priority = EmergencyAlerts.PRIORITY_CRITICAL
        else:
            priority = EmergencyAlerts.PRIORITY_HIGH

        # Send alert
        title = f"Scheduler Heartbeat {status['status']}"
        message = status["message"]
        data = {
            "status": status["status"],
            "age_minutes": status["details"].get("age_minutes"),
            "threshold_minutes": status["details"].get("threshold_minutes"),
            "last_run": status["details"].get("last_run"),
            "market_status": status["details"].get("market_status", {}).get("session"),
        }

        try:
            results = self.alerts.send_alert(
                title=title,
                message=message,
                priority=priority,
                data=data,
            )
            alert_results["alerts_sent"] = results
            logger.info(f"Alerts sent: {results}")
        except Exception as e:
            error_msg = f"Failed to send alerts: {e}"
            logger.error(error_msg)
            alert_results["errors"].append(error_msg)

        # Log alert to file
        self._log_alert(status, alert_results)

        return alert_results

    def _log_alert(self, status: dict, alert_results: dict) -> None:
        """
        Log alert to file for audit trail.

        Args:
            status: Status dict from check_heartbeat()
            alert_results: Alert results dict
        """
        try:
            # Load existing alerts
            alerts = []
            if self.alert_log_file.exists():
                with open(self.alert_log_file) as f:
                    alerts = json.load(f)

            # Add new alert
            alerts.append(
                {
                    "timestamp": datetime.now().isoformat(),
                    "status": status,
                    "alert_results": alert_results,
                }
            )

            # Keep last 500 alerts
            alerts = alerts[-500:]

            # Save
            with open(self.alert_log_file, "w") as f:
                json.dump(alerts, f, indent=2)

            logger.info(f"Alert logged to {self.alert_log_file}")

        except Exception as e:
            logger.error(f"Failed to log alert to file: {e}")

    def run(self, dry_run: bool = False) -> int:
        """
        Run heartbeat check and send alerts.

        Args:
            dry_run: If True, check only without sending alerts

        Returns:
            Exit code (0 = healthy, 1 = critical/error)
        """
        logger.info("=" * 70)
        logger.info("SCHEDULER HEARTBEAT MONITOR")
        logger.info("=" * 70)
        logger.info(f"Heartbeat file: {self.heartbeat_file}")
        logger.info(f"Threshold: {self.threshold_minutes} minutes")
        logger.info(f"Dry run: {dry_run}")
        logger.info(f"Force check: {self.force_check}")
        logger.info("")

        # Check heartbeat
        status = self.check_heartbeat()

        # Print status
        logger.info("=" * 70)
        logger.info(f"STATUS: {status['status']}")
        logger.info("=" * 70)
        logger.info(f"Message: {status['message']}")
        logger.info("")

        if status["details"]:
            logger.info("Details:")
            for key, value in status["details"].items():
                if key == "heartbeat_data":
                    logger.info(f"  {key}:")
                    for hb_key, hb_value in value.items():
                        logger.info(f"    {hb_key}: {hb_value}")
                elif key == "market_status":
                    logger.info(f"  {key}:")
                    for ms_key, ms_value in value.items():
                        logger.info(f"    {ms_key}: {ms_value}")
                else:
                    logger.info(f"  {key}: {value}")
            logger.info("")

        # Send alerts if not dry run
        if not dry_run and status["status"] in ["CRITICAL", "ERROR"]:
            logger.info("Sending alerts...")
            alert_results = self.send_alerts(status)

            logger.info("=" * 70)
            logger.info("ALERT RESULTS")
            logger.info("=" * 70)
            logger.info(f"Alerts sent: {alert_results['alerts_sent']}")
            if alert_results["errors"]:
                logger.info(f"Errors: {alert_results['errors']}")
            logger.info("")
        elif dry_run and status["status"] in ["CRITICAL", "ERROR"]:
            logger.info("DRY RUN: Would send alerts, but skipping")
            logger.info("")

        # Return exit code
        logger.info("=" * 70)
        if status["status"] in ["CRITICAL", "ERROR"]:
            logger.info("❌ HEARTBEAT CHECK FAILED")
            logger.info("=" * 70)
            return 1
        elif status["status"] == "SKIPPED":
            logger.info("ℹ️  HEARTBEAT CHECK SKIPPED (outside market hours)")
            logger.info("=" * 70)
            return 0
        else:
            logger.info("✅ HEARTBEAT CHECK PASSED")
            logger.info("=" * 70)
            return 0


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Monitor scheduler heartbeat and alert on failures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Check heartbeat with default settings (2 hour threshold)
  python3 scripts/heartbeat_alert.py

  # Check with custom threshold (90 minutes)
  python3 scripts/heartbeat_alert.py --threshold 90

  # Dry run (check only, no alerts)
  python3 scripts/heartbeat_alert.py --dry-run

  # Force check even outside market hours
  python3 scripts/heartbeat_alert.py --force

  # Custom heartbeat file location
  python3 scripts/heartbeat_alert.py --heartbeat-file data/custom_heartbeat.json
        """,
    )

    parser.add_argument(
        "--heartbeat-file",
        default="data/scheduler_heartbeat.json",
        help="Path to scheduler heartbeat file (default: data/scheduler_heartbeat.json)",
    )

    parser.add_argument(
        "--threshold",
        type=int,
        default=120,
        help="Maximum age of heartbeat in minutes before alerting (default: 120)",
    )

    parser.add_argument(
        "--alert-log",
        default="data/heartbeat_alerts.json",
        help="Path to alert log file (default: data/heartbeat_alerts.json)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Check only, do not send alerts",
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Force check even outside market hours",
    )

    args = parser.parse_args()

    # Create monitor
    monitor = HeartbeatMonitor(
        heartbeat_file=args.heartbeat_file,
        threshold_minutes=args.threshold,
        alert_log_file=args.alert_log,
        force_check=args.force,
    )

    # Run check
    exit_code = monitor.run(dry_run=args.dry_run)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()

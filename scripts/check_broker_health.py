#!/usr/bin/env python3
"""
Broker Health Check Script

Autonomous health monitoring for broker connectivity.
Run as part of pre-market checks or continuous monitoring.

Usage:
    python3 scripts/check_broker_health.py
    python3 scripts/check_broker_health.py --alert  # Send alerts if unhealthy
"""

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

import logging

from src.alerts.telegram_alerter import TelegramAlerter
from src.core.broker_health import BrokerHealthMonitor

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Check broker health")
    parser.add_argument("--alert", action="store_true", help="Send alerts if broker is unhealthy")
    parser.add_argument("--broker", default="alpaca", help="Broker name to check (default: alpaca)")
    args = parser.parse_args()

    print("=" * 70)
    print("🔍 BROKER HEALTH CHECK")
    print("=" * 70)
    print()

    # Initialize monitor
    monitor = BrokerHealthMonitor(broker_name=args.broker)

    # Run health check
    monitor.check_health()
    summary = monitor.get_health_summary()

    # Display results
    print(f"Broker: {summary['broker'].upper()}")
    print(f"Status: {summary['status'].upper()}")
    print(f"Healthy: {'✅ YES' if summary['is_healthy'] else '❌ NO'}")
    print()

    print("Metrics:")
    print(f"  Success Rate: {summary['success_rate']:.1f}%")
    print(f"  Total Checks: {summary['total_checks']}")
    print(f"  Successful: {summary['successful_checks']}")
    print(f"  Failed: {summary['failed_checks']}")
    print(f"  Consecutive Failures: {summary['consecutive_failures']}")
    print(f"  Avg Response Time: {summary['avg_response_time_ms']:.2f}ms")
    print()

    if summary["account_status"]:
        print("Account Info:")
        print(f"  Status: {summary['account_status']}")
        if summary["buying_power"]:
            print(f"  Buying Power: ${summary['buying_power']:,.2f}")
        print()

    if summary["last_error"]:
        print(f"Last Error: {summary['last_error']}")
        print()

    # Check if alert needed
    if monitor.should_alert():
        alert_msg = monitor.get_alert_message()
        if alert_msg:
            print("🚨 ALERT TRIGGERED:")
            print(alert_msg)
            print()

            if args.alert:
                try:
                    alerter = TelegramAlerter()
                    alerter.send_alert(
                        title="Broker Health Alert",
                        message=alert_msg,
                        severity=(
                            "CRITICAL" if summary["consecutive_failures"] >= 3 else "WARNING"
                        ),
                    )
                    print("✅ Alert sent via Telegram")
                except Exception as e:
                    logger.error(f"Failed to send alert: {e}")
                    print(f"❌ Failed to send alert: {e}")

    print("=" * 70)

    # Exit with error code if unhealthy
    sys.exit(0 if summary["is_healthy"] else 1)


if __name__ == "__main__":
    main()

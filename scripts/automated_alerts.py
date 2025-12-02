#!/usr/bin/env python3
"""
Automated Alert System

Implements CTO/CFO Decision #4: Automated alerts for:
- P/L thresholds (>3% loss, >5% profit)
- Position concentration (>60%)
- System health issues
- Stop-loss triggers
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"

# Alert thresholds (unrealized_pl_pct is stored as percentage, e.g., 2.33 for 2.33%)
LOSS_THRESHOLD = -3.0  # -3%
PROFIT_THRESHOLD = 5.0  # +5%
CONCENTRATION_THRESHOLD = 0.60  # 60%
STALE_THRESHOLD_HOURS = 24  # 24 hours


def load_system_state() -> dict:
    """Load system state."""
    if not SYSTEM_STATE_FILE.exists():
        return {}

    with open(SYSTEM_STATE_FILE) as f:
        return json.load(f)


def check_pl_alerts(positions: list[dict]) -> list[str]:
    """Check for P/L threshold alerts."""
    alerts = []

    for position in positions:
        symbol = position.get("symbol")
        unrealized_pl_pct = position.get("unrealized_pl_pct", 0)

        # unrealized_pl_pct is stored as percentage (e.g., 2.33 for 2.33%, -4.44 for -4.44%)
        if unrealized_pl_pct <= LOSS_THRESHOLD:
            alerts.append(
                f"🚨 {symbol}: Loss exceeds {abs(LOSS_THRESHOLD):.0f}% threshold "
                f"({unrealized_pl_pct:.2f}% loss)"
            )
        elif unrealized_pl_pct >= PROFIT_THRESHOLD:
            alerts.append(
                f"✅ {symbol}: Profit exceeds {PROFIT_THRESHOLD:.0f}% threshold "
                f"({unrealized_pl_pct:.2f}% profit) - Consider profit-taking"
            )

    return alerts


def check_concentration_alerts(positions: list[dict], total_value: float) -> list[str]:
    """Check for position concentration alerts."""
    alerts = []

    if total_value == 0:
        return alerts

    for position in positions:
        symbol = position.get("symbol")
        position_value = position.get("amount", 0)
        concentration = position_value / total_value if total_value > 0 else 0

        if concentration > CONCENTRATION_THRESHOLD:
            alerts.append(
                f"⚠️ {symbol}: Position concentration {concentration * 100:.1f}% "
                f"exceeds {CONCENTRATION_THRESHOLD * 100:.0f}% threshold"
            )

    return alerts


def check_system_health(state: dict) -> list[str]:
    """Check for system health issues."""
    alerts = []

    # Check state freshness
    last_updated_str = state.get("meta", {}).get("last_updated")
    if last_updated_str:
        try:
            last_updated = datetime.fromisoformat(last_updated_str)
            hours_old = (datetime.now() - last_updated).total_seconds() / 3600

            if hours_old > STALE_THRESHOLD_HOURS:
                alerts.append(
                    f"⚠️ System state is {hours_old:.1f} hours old "
                    f"(threshold: {STALE_THRESHOLD_HOURS} hours)"
                )
        except Exception as e:
            logger.debug(f"Failed to parse last_updated: {e}")

    # Check automation status
    automation = state.get("automation", {})
    if not automation.get("github_actions_enabled", False):
        alerts.append("⚠️ GitHub Actions automation is disabled")

    # Check for recent failures
    failures = automation.get("failures", 0)
    if failures > 0:
        alerts.append(f"⚠️ Automation has {failures} failure(s)")

    return alerts


def check_stop_loss_alerts(positions: list[dict]) -> list[str]:
    """Check for stop-loss proximity alerts."""
    alerts = []

    for position in positions:
        symbol = position.get("symbol")
        entry_price = position.get("entry_price", 0)
        current_price = position.get("current_price", 0)
        unrealized_pl_pct = position.get("unrealized_pl_pct", 0)

        if entry_price == 0 or current_price == 0:
            continue

        # Calculate stop-loss price (assuming 2% trailing stop)
        stop_loss_price = entry_price * 0.98
        distance_to_stop = ((current_price - stop_loss_price) / entry_price) * 100

        # Alert if within 0.5% of stop-loss
        if 0 < distance_to_stop < 0.5:
            alerts.append(
                f"⚠️ {symbol}: Price ${current_price:.2f} is within 0.5% of stop-loss "
                f"${stop_loss_price:.2f} (P/L: {unrealized_pl_pct * 100:.2f}%)"
            )

    return alerts


def check_tlt_gate_status() -> list[str]:
    """Check TLT momentum gate status and return alerts if gate opened."""
    alerts = []
    try:
        from scripts.monitor_tlt_momentum import (
            check_tlt_gate_change,
            get_tlt_momentum_status,
        )

        gate_open, status = get_tlt_momentum_status()

        if "error" not in status:
            gate_change = check_tlt_gate_change()

            if gate_change:
                if gate_change["gate_opened"]:
                    alerts.append(
                        f"🟢 TLT Momentum Gate OPENED - Treasuries trading now enabled "
                        f"(SMA20=${status['sma20']:.2f} >= SMA50=${status['sma50']:.2f})"
                    )
                else:
                    alerts.append(
                        f"🔴 TLT Momentum Gate CLOSED - Treasuries trading paused "
                        f"(SMA20=${status['sma20']:.2f} < SMA50=${status['sma50']:.2f})"
                    )
            elif not gate_open:
                # Gate is closed but no change - just informational
                alerts.append(
                    f"⏸️  TLT Gate CLOSED - No trades until SMA20 crosses above SMA50 "
                    f"(Current: SMA20=${status['sma20']:.2f}, SMA50=${status['sma50']:.2f})"
                )
    except Exception as e:
        logger.warning(f"Could not check TLT gate status: {e}")

    return alerts


def generate_alerts(suppress_known: bool = False):
    """
    Generate all alerts.

    Args:
        suppress_known: If True, only show new alerts or changes (not implemented yet)
    """
    print("=" * 80)
    print("🔔 AUTOMATED ALERTS")
    print(f"   Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if suppress_known:
        print("   Mode: Suppressing known alerts")
    print("=" * 80)

    state = load_system_state()

    if not state:
        print("\n❌ System state not found")
        return

    positions = state.get("performance", {}).get("open_positions", [])
    account = state.get("account", {})
    total_value = account.get("positions_value", 0)

    all_alerts = []

    # Check P/L alerts
    pl_alerts = check_pl_alerts(positions)
    all_alerts.extend(pl_alerts)

    # Check concentration alerts
    concentration_alerts = check_concentration_alerts(positions, total_value)
    all_alerts.extend(concentration_alerts)

    # Check system health
    health_alerts = check_system_health(state)
    all_alerts.extend(health_alerts)

    # Check stop-loss proximity
    stop_loss_alerts = check_stop_loss_alerts(positions)
    all_alerts.extend(stop_loss_alerts)

    # Check TLT momentum gate status
    tlt_alerts = check_tlt_gate_status()
    all_alerts.extend(tlt_alerts)

    # Display alerts
    if all_alerts:
        print("\n📋 ALERTS:")
        for alert in all_alerts:
            print(f"  {alert}")
    else:
        print("\n✅ No alerts - System healthy")

    print("\n" + "=" * 80)

    if all_alerts:
        print("\n💡 NOTE: Alerts will persist until underlying conditions change.")
        print("   - SPY loss alert: Will stop when position recovers or is closed")
        print("   - Concentration alert: Will stop when portfolio rebalances")
        print("   - These are informational, not errors")

    # Return exit code based on alert severity
    critical_alerts = [a for a in all_alerts if "🚨" in a]
    if critical_alerts:
        return 1  # Exit code 1 = critical alerts

    return 0  # Exit code 0 = no critical alerts


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Generate automated trading alerts")
    parser.add_argument(
        "--suppress-known",
        action="store_true",
        help="Suppress known/persistent alerts (not implemented yet)",
    )
    args = parser.parse_args()

    try:
        exit_code = generate_alerts(suppress_known=args.suppress_known)
        sys.exit(exit_code)
    except Exception:
        logger.exception("Alert generation failed")
        sys.exit(1)

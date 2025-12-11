#!/usr/bin/env python3
"""
Independent Kill Switch Monitor

A standalone script that runs independently of the main trading bot.
Monitors portfolio P/L and triggers emergency stop if thresholds are breached.

This script is designed to be run as a cron job every minute to provide
redundant protection even if the main trading bot crashes.

Usage:
    # Run once
    python3 scripts/independent_kill_switch_monitor.py

    # Cron job (every minute during market hours)
    * 9-16 * * 1-5 cd /path/to/trading && python3 scripts/independent_kill_switch_monitor.py

Configuration (via environment variables):
    KILL_SWITCH_MAX_DAILY_LOSS: Maximum daily loss in dollars (default: $100)
    KILL_SWITCH_MAX_LOSS_PCT: Maximum daily loss percentage (default: 2%)
    KILL_SWITCH_CHECK_INTERVAL: Interval between checks in seconds (default: 60)

Author: Trading System
Created: 2025-12-11
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/kill_switch_monitor.log"),
    ],
)
logger = logging.getLogger(__name__)

# Configuration with environment variable overrides
MAX_DAILY_LOSS_DOLLARS = float(os.getenv("KILL_SWITCH_MAX_DAILY_LOSS", "100"))
MAX_DAILY_LOSS_PCT = float(os.getenv("KILL_SWITCH_MAX_LOSS_PCT", "2.0")) / 100
STATE_FILE = Path("data/kill_switch_monitor_state.json")
KILL_SWITCH_FILE = Path("data/KILL_SWITCH")


def get_alpaca_client():
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.error("Missing Alpaca API credentials")
            return None

        return TradingClient(api_key=api_key, secret_key=secret_key, paper=True)
    except Exception as e:
        logger.error(f"Failed to create Alpaca client: {e}")
        return None


def get_account_data(client) -> dict[str, Any] | None:
    """Fetch current account data from Alpaca."""
    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
            "last_equity": float(account.last_equity),
            "portfolio_value": float(account.portfolio_value),
            "status": str(account.status),
        }
    except Exception as e:
        logger.error(f"Failed to fetch account data: {e}")
        return None


def load_state() -> dict[str, Any]:
    """Load monitor state from disk."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {
        "start_of_day_equity": None,
        "start_date": None,
        "alerts_sent": 0,
        "last_check": None,
    }


def save_state(state: dict[str, Any]) -> None:
    """Save monitor state to disk."""
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.error(f"Failed to save state: {e}")


def activate_kill_switch(reason: str, details: dict[str, Any]) -> None:
    """Activate the kill switch by creating the trigger file."""
    KILL_SWITCH_FILE.parent.mkdir(parents=True, exist_ok=True)

    content = f"""KILL SWITCH ACTIVATED - INDEPENDENT MONITOR
============================================
Time: {datetime.now().isoformat()}
Reason: {reason}

Details:
{json.dumps(details, indent=2)}

This file was created by the independent kill switch monitor.
To resume trading, delete this file and reset the circuit breakers.
"""
    with open(KILL_SWITCH_FILE, "w") as f:
        f.write(content)

    logger.critical(f"🚨 KILL SWITCH ACTIVATED: {reason}")


def close_all_positions(client) -> bool:
    """Emergency close all positions."""
    try:
        client.close_all_positions(cancel_orders=True)
        logger.warning("All positions closed by kill switch")
        return True
    except Exception as e:
        logger.error(f"Failed to close positions: {e}")
        return False


def send_alert(title: str, message: str) -> None:
    """Send emergency alert via available channels."""
    try:
        from src.safety.emergency_alerts import get_alerts

        alerts = get_alerts()
        alerts.send_alert(title=title, message=message, priority="critical")
    except Exception as e:
        logger.warning(f"Could not send alert: {e}")


def check_and_enforce() -> dict[str, Any]:
    """
    Main monitoring function. Checks P/L and enforces kill switch if needed.

    Returns:
        Dict with check results
    """
    result = {
        "timestamp": datetime.now().isoformat(),
        "action_taken": None,
        "status": "ok",
    }

    # Check if kill switch already active
    if KILL_SWITCH_FILE.exists():
        result["status"] = "kill_switch_already_active"
        logger.info("Kill switch already active, skipping check")
        return result

    # Get Alpaca client
    client = get_alpaca_client()
    if not client:
        result["status"] = "no_client"
        result["error"] = "Failed to create Alpaca client"
        return result

    # Get account data
    account_data = get_account_data(client)
    if not account_data:
        result["status"] = "no_account_data"
        result["error"] = "Failed to fetch account data"
        return result

    result["account"] = account_data
    current_equity = account_data["equity"]

    # Load state and update start of day equity if needed
    state = load_state()
    today = datetime.now().strftime("%Y-%m-%d")

    if state["start_date"] != today:
        # New day - reset start of day equity
        state["start_of_day_equity"] = current_equity
        state["start_date"] = today
        state["alerts_sent"] = 0
        logger.info(f"New day detected. Start of day equity: ${current_equity:,.2f}")

    start_equity = state["start_of_day_equity"]
    if start_equity is None:
        start_equity = current_equity
        state["start_of_day_equity"] = start_equity

    # Calculate daily P/L
    daily_pnl = current_equity - start_equity
    daily_pnl_pct = daily_pnl / start_equity if start_equity > 0 else 0

    result["daily_pnl"] = daily_pnl
    result["daily_pnl_pct"] = daily_pnl_pct * 100
    result["start_equity"] = start_equity

    logger.info(
        f"P/L Check: ${daily_pnl:,.2f} ({daily_pnl_pct:.2%}) | "
        f"Equity: ${current_equity:,.2f} | Start: ${start_equity:,.2f}"
    )

    # Check 1: Absolute dollar loss threshold
    if daily_pnl < -MAX_DAILY_LOSS_DOLLARS:
        reason = f"Daily loss ${abs(daily_pnl):.2f} exceeds ${MAX_DAILY_LOSS_DOLLARS} limit"
        details = {
            "daily_pnl": daily_pnl,
            "threshold_dollars": -MAX_DAILY_LOSS_DOLLARS,
            "current_equity": current_equity,
            "start_equity": start_equity,
        }
        activate_kill_switch(reason, details)
        close_all_positions(client)
        send_alert("🚨 KILL SWITCH: Daily Loss Limit", reason)
        result["status"] = "kill_switch_triggered"
        result["action_taken"] = "positions_closed"
        result["trigger_reason"] = reason
        state["last_trigger"] = datetime.now().isoformat()
        save_state(state)
        return result

    # Check 2: Percentage loss threshold
    if daily_pnl_pct < -MAX_DAILY_LOSS_PCT:
        reason = f"Daily loss {abs(daily_pnl_pct):.2%} exceeds {MAX_DAILY_LOSS_PCT:.0%} limit"
        details = {
            "daily_pnl_pct": daily_pnl_pct * 100,
            "threshold_pct": -MAX_DAILY_LOSS_PCT * 100,
            "current_equity": current_equity,
            "start_equity": start_equity,
        }
        activate_kill_switch(reason, details)
        close_all_positions(client)
        send_alert("🚨 KILL SWITCH: Percentage Loss Limit", reason)
        result["status"] = "kill_switch_triggered"
        result["action_taken"] = "positions_closed"
        result["trigger_reason"] = reason
        state["last_trigger"] = datetime.now().isoformat()
        save_state(state)
        return result

    # Warning at 50% of threshold
    warning_threshold = -MAX_DAILY_LOSS_DOLLARS * 0.5
    if daily_pnl < warning_threshold and state["alerts_sent"] == 0:
        send_alert(
            "⚠️ Loss Warning",
            f"Daily P/L is ${daily_pnl:.2f} - approaching kill switch threshold",
        )
        state["alerts_sent"] = 1
        logger.warning(f"Warning: P/L approaching threshold at ${daily_pnl:.2f}")

    # Update state
    state["last_check"] = datetime.now().isoformat()
    state["last_pnl"] = daily_pnl
    save_state(state)

    return result


def main():
    """Main entry point."""
    # Ensure logs directory exists
    Path("logs").mkdir(exist_ok=True)

    logger.info("=" * 60)
    logger.info("INDEPENDENT KILL SWITCH MONITOR")
    logger.info(f"Max Daily Loss: ${MAX_DAILY_LOSS_DOLLARS} or {MAX_DAILY_LOSS_PCT:.0%}")
    logger.info("=" * 60)

    result = check_and_enforce()

    if result["status"] == "ok":
        logger.info(
            f"✅ All clear - Daily P/L: ${result.get('daily_pnl', 0):,.2f} "
            f"({result.get('daily_pnl_pct', 0):.2f}%)"
        )
    elif result["status"] == "kill_switch_triggered":
        logger.critical(f"🚨 KILL SWITCH TRIGGERED: {result.get('trigger_reason')}")
        sys.exit(1)  # Non-zero exit for cron alerting
    else:
        logger.warning(f"Check status: {result['status']}")

    return result


if __name__ == "__main__":
    main()

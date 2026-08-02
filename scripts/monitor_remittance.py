#!/usr/bin/env python3
"""Monitor remittance progress toward $1000/mo after-tax target and send alerts.

Checks the transfer ledger for confirmed broker→Mercury deposits this month,
estimates after-tax profit from realized P/L, and sends an alert if:
  - The target is met (congratulations)
  - The target is at risk (not enough days left in month)
  - The target is significantly behind (below 50% of monthly pace)

Alerts can be sent via:
  - Telegram (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
  - Webhook URL (ALERT_WEBHOOK_URL)
  - Email (ALERT_EMAIL via local mail)

Default: print to stdout only (no network calls).

Cron example (weekday 11:00 AM ET):
  0 15 * * 1-5  .venv/bin/python scripts/monitor_remittance.py --alert
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_LEDGER_PATH = ROOT / "data" / "audit" / "mercury_broker_transfers.jsonl"


def _days_remaining_in_month() -> int:
    """Days remaining (inclusive of today) in the current UTC month."""
    now = datetime.now(UTC)
    # Last day of month
    if now.month == 12:
        last = now.replace(year=now.year + 1, month=1, day=1)
    else:
        last = now.replace(month=now.month + 1, day=1)
    from datetime import timedelta

    last_day = (last - timedelta(days=1)).day
    return last_day - now.day + 1


def _send_telegram_alert(message: str) -> bool:
    """Send alert via Telegram. Returns True on success."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return False
    try:
        import requests

        resp = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _send_webhook_alert(message: str) -> bool:
    """Send alert via webhook URL. Returns True on success."""
    url = os.environ.get("ALERT_WEBHOOK_URL")
    if not url:
        return False
    try:
        import requests

        resp = requests.post(
            url,
            json={"text": message, "source": "remittance_monitor"},
            timeout=10,
        )
        return resp.status_code == 200
    except Exception:  # noqa: BLE001
        return False


def _send_email_alert(message: str) -> bool:
    """Send alert via local mail. Returns True on success."""
    email = os.environ.get("ALERT_EMAIL")
    if not email:
        return False
    try:
        import subprocess  # nosec B404

        proc = subprocess.run(  # nosec
            ["mail", "-s", "Remittance Monitor Alert", email],
            input=message,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return proc.returncode == 0
    except Exception:  # noqa: BLE001
        return False


def check_remittance(
    *,
    ledger_path: Path | None = None,
    month: str | None = None,
    realized_pnl: float | None = None,
    tax_rate: float = 0.15,
    target_usd: float = 1000.0,
) -> dict[str, Any]:
    """Check remittance progress and return a status dict."""
    from src.bank.live_gate import evaluate_live_bank_gate
    from src.bank.remittance import compute_remittance_progress
    from src.bank.transfer_ledger import load_transfer_ledger

    records = load_transfer_ledger(ledger_path=ledger_path)
    progress = compute_remittance_progress(
        records,
        month_yyyy_mm=month,
        target_usd=target_usd,
        realized_pre_tax_pnl_usd=realized_pnl,
        tax_rate=tax_rate,
    )
    gate = evaluate_live_bank_gate()

    days_left = _days_remaining_in_month()
    current_day = datetime.now(UTC).day
    days_in_month = current_day + days_left - 1

    # Calculate required daily pace to hit target
    required_daily_pace = target_usd / max(days_in_month, 1)
    current_daily_pace = progress.remitted_to_bank_usd / max(current_day, 1)
    pace_ratio = current_daily_pace / required_daily_pace if required_daily_pace > 0 else 0.0

    # Determine alert level
    if progress.target_met:
        alert_level = "SUCCESS"
        alert_message = (
            f"✅ Remittance target MET for {progress.month_yyyy_mm}: "
            f"${progress.remitted_to_bank_usd:.2f} confirmed to bank "
            f"(>= ${target_usd:.0f} target)"
        )
    elif progress.remitted_to_bank_usd == 0 and progress.remittance_event_count == 0:
        # No confirmed deposits yet — too early to warn, just info
        alert_level = "INFO"
        alert_message = (
            f"ℹ️ No confirmed remittances yet for {progress.month_yyyy_mm}: "
            f"${progress.remitted_to_bank_usd:.2f} of ${target_usd:.0f} target. "
            f"{days_left} days left."
        )
    elif pace_ratio < 0.5 and current_day >= 10:
        alert_level = "WARNING"
        alert_message = (
            f"⚠️ Remittance BEHIND for {progress.month_yyyy_mm}: "
            f"${progress.remitted_to_bank_usd:.2f} of ${target_usd:.0f} target "
            f"({progress.pct_of_target or 0:.0f}%). "
            f"Pace: ${current_daily_pace:.2f}/day vs ${required_daily_pace:.2f}/day needed. "
            f"{days_left} days left."
        )
    elif days_left <= 3 and not progress.target_met:
        alert_level = "URGENT"
        alert_message = (
            f"🚨 Remittance AT RISK for {progress.month_yyyy_mm}: "
            f"${progress.remitted_to_bank_usd:.2f} of ${target_usd:.0f} target. "
            f"Only {days_left} days left!"
        )
    else:
        alert_level = "INFO"
        alert_message = (
            f"ℹ️ Remittance on track for {progress.month_yyyy_mm}: "
            f"${progress.remitted_to_bank_usd:.2f} of ${target_usd:.0f} target "
            f"({progress.pct_of_target or 0:.0f}%). "
            f"{days_left} days left."
        )

    return {
        "alert_level": alert_level,
        "alert_message": alert_message,
        "progress": progress.as_dict(),
        "live_bank_gate": {
            "allowed": gate.allowed,
            "blockers": list(gate.blockers),
            "strategy_mode": gate.strategy_mode,
        },
        "days_remaining": days_left,
        "current_daily_pace": round(current_daily_pace, 2),
        "required_daily_pace": round(required_daily_pace, 2),
        "pace_ratio": round(pace_ratio, 2),
        "target_usd": target_usd,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--ledger-path", type=Path, default=DEFAULT_LEDGER_PATH)
    p.add_argument("--month", default=None, help="YYYY-MM (default: current UTC month)")
    p.add_argument(
        "--realized-pnl",
        type=float,
        default=None,
        help="Optional realized pre-tax P/L for after-tax estimate",
    )
    p.add_argument("--tax-rate", type=float, default=0.15)
    p.add_argument("--target-usd", type=float, default=1000.0)
    p.add_argument("--alert", action="store_true", help="Send alerts via Telegram/webhook/email")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    status = check_remittance(
        ledger_path=args.ledger_path,
        month=args.month,
        realized_pnl=args.realized_pnl,
        tax_rate=args.tax_rate,
        target_usd=args.target_usd,
    )

    if args.json:
        print(json.dumps(status, indent=2))
    else:
        print("=== REMITTANCE MONITOR ===")
        print(f"month: {status['progress']['month_yyyy_mm']}")
        print(f"alert: {status['alert_level']}")
        print(status["alert_message"])
        print(f"remitted_to_bank (confirmed): ${status['progress']['remitted_to_bank_usd']:.2f}")
        print(f"in_flight (submitted): ${status['progress']['in_flight_usd']:.2f}")
        print(f"target: ${status['target_usd']:.0f}")
        print(f"days_remaining: {status['days_remaining']}")
        print(
            f"pace: ${status['current_daily_pace']:.2f}/day vs ${status['required_daily_pace']:.2f}/day needed"
        )
        print(f"live_bank_gate.allowed: {status['live_bank_gate']['allowed']}")

    # Send alerts if requested
    if args.alert and status["alert_level"] in ("SUCCESS", "WARNING", "URGENT"):
        message = (
            f"{status['alert_message']}\n\n"
            f"Month: {status['progress']['month_yyyy_mm']}\n"
            f"Confirmed: ${status['progress']['remitted_to_bank_usd']:.2f}\n"
            f"Target: ${status['target_usd']:.0f}\n"
            f"Days left: {status['days_remaining']}"
        )
        sent = False
        if _send_telegram_alert(message):
            sent = True
            print("Alert sent via Telegram")
        elif _send_webhook_alert(message):
            sent = True
            print("Alert sent via webhook")
        elif _send_email_alert(message):
            sent = True
            print("Alert sent via email")
        if not sent:
            print("No alert channel configured (set TELEGRAM_BOT_TOKEN or ALERT_WEBHOOK_URL)")

    # Exit 0 for INFO/SUCCESS, 1 for WARNING, 2 for URGENT
    if status["alert_level"] == "URGENT":
        return 2
    if status["alert_level"] == "WARNING":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

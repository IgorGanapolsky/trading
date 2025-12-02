#!/usr/bin/env python3
"""
Risk Alerts - Warn before big losses or unusual activity
"""

import json
import os
from datetime import datetime
from pathlib import Path

import alpaca_trade_api as tradeapi

DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)

# Load from .env or environment
from dotenv import load_dotenv

load_dotenv()

api = tradeapi.REST(
    os.getenv("APCA_API_KEY_ID") or os.getenv("ALPACA_API_KEY"),
    os.getenv("APCA_SECRET_KEY") or os.getenv("ALPACA_SECRET_KEY"),
    os.getenv("APCA_API_BASE_URL")
    or os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets"),
    api_version="v2",
)


def check_position_risks():
    """Check for risky positions and return alerts."""
    alerts = []

    try:
        positions = api.list_positions()
        account = api.get_account()
        portfolio_value = float(account.portfolio_value)

        for pos in positions:
            symbol = pos.symbol
            unrealized_plpc = float(pos.unrealized_plpc) * 100
            unrealized_pl = float(pos.unrealized_pl)
            position_value = float(pos.market_value)
            position_pct = (position_value / portfolio_value) * 100

            # Alert: Large loss
            if unrealized_plpc <= -5:
                alerts.append(
                    {
                        "level": "CRITICAL",
                        "type": "large_loss",
                        "symbol": symbol,
                        "message": f"{symbol} down {unrealized_plpc:.2f}% (${unrealized_pl:,.2f})",
                        "unrealized_plpc": unrealized_plpc,
                        "unrealized_pl": unrealized_pl,
                    }
                )

            # Alert: Approaching stop-loss (Tier 2)
            elif symbol in ["NVDA", "GOOGL", "AMZN"] and unrealized_plpc <= -2.5:
                alerts.append(
                    {
                        "level": "WARNING",
                        "type": "approaching_stop_loss",
                        "symbol": symbol,
                        "message": f"{symbol} approaching stop-loss ({unrealized_plpc:.2f}% / -3%)",
                        "unrealized_plpc": unrealized_plpc,
                    }
                )

            # Alert: Over-concentration
            if position_pct > 10:
                alerts.append(
                    {
                        "level": "WARNING",
                        "type": "over_concentration",
                        "symbol": symbol,
                        "message": f"{symbol} is {position_pct:.1f}% of portfolio (limit: 10%)",
                        "position_pct": position_pct,
                    }
                )

        # Alert: Large portfolio loss
        total_unrealized = sum(float(p.unrealized_pl) for p in positions)
        if total_unrealized < -50:
            alerts.append(
                {
                    "level": "CRITICAL",
                    "type": "large_portfolio_loss",
                    "message": f"Portfolio down ${total_unrealized:,.2f}",
                    "total_unrealized": total_unrealized,
                }
            )

    except Exception as e:
        alerts.append(
            {
                "level": "ERROR",
                "type": "check_failed",
                "message": f"Failed to check risks: {e}",
            }
        )

    return alerts


def send_alerts(alerts):
    """Send alerts (print for now, can integrate with email/Slack later)."""
    if not alerts:
        return

    print("=" * 60)
    print("🚨 RISK ALERTS")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    critical = [a for a in alerts if a["level"] == "CRITICAL"]
    warnings = [a for a in alerts if a["level"] == "WARNING"]

    if critical:
        print("🔴 CRITICAL:")
        for alert in critical:
            print(f"  ⚠️  {alert['message']}")
        print()

    if warnings:
        print("🟡 WARNINGS:")
        for alert in warnings:
            print(f"  ⚠️  {alert['message']}")
        print()

    # Save to file
    alert_file = DATA_DIR / "risk_alerts.json"
    alert_data = {
        "timestamp": datetime.now().isoformat(),
        "alerts": alerts,
    }

    if alert_file.exists():
        with open(alert_file) as f:
            log = json.load(f)
    else:
        log = {"entries": []}

    log["entries"].append(alert_data)
    log["entries"] = log["entries"][-100:]  # Keep last 100

    with open(alert_file, "w") as f:
        json.dump(log, f, indent=2)


def main():
    """Run risk check."""
    alerts = check_position_risks()
    send_alerts(alerts)

    if alerts:
        return 1  # Exit code 1 if alerts found
    else:
        print("✅ No risk alerts")
        return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

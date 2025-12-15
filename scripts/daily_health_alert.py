#!/usr/bin/env python3
"""
Daily Trading Health Alert - The ONE Thing for Operational Reliability

Runs after trading and alerts on any issues.
Never be surprised by failures again.

Created: Dec 15, 2025
"""

import json
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent


def check_health() -> dict:
    """Run all health checks."""
    health = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "overall": "HEALTHY",
        "alerts": [],
        "summary": {}
    }
    
    # 1. Load system state
    state_file = PROJECT_ROOT / "data" / "system_state.json"
    if state_file.exists():
        with open(state_file) as f:
            state = json.load(f)
        health["summary"]["equity"] = state.get("account", {}).get("current_equity", 0)
        health["summary"]["total_pl"] = state.get("account", {}).get("total_pl", 0)
        
        # Check options performance
        closed = state.get("performance", {}).get("closed_trades", [])
        options = [t for t in closed if "P0" in t.get("symbol", "") or "C0" in t.get("symbol", "")]
        if options:
            health["summary"]["options_pl"] = sum(t.get("pl", 0) for t in options)
            wins = len([t for t in options if t.get("pl", 0) > 0])
            health["summary"]["options_wr"] = (wins / len(options) * 100) if options else 0
    else:
        health["alerts"].append("System state not found!")
        health["overall"] = "UNHEALTHY"
    
    # 2. Check today's trades
    today = datetime.now().strftime("%Y-%m-%d")
    trade_file = PROJECT_ROOT / "data" / f"trades_{today}.json"
    if trade_file.exists():
        with open(trade_file) as f:
            trades = json.load(f)
        health["summary"]["trades_today"] = len(trades)
        
        if trades:
            first_val = trades[0].get("account_value", 0)
            last_val = trades[-1].get("account_value", 0)
            health["summary"]["daily_pl"] = last_val - first_val if first_val else 0
    else:
        health["summary"]["trades_today"] = 0
        if datetime.now().weekday() < 5:
            health["alerts"].append("No trades file for today (weekday)")
    
    # 3. Set overall status
    if health["alerts"]:
        health["overall"] = "WARNING" if health["overall"] == "HEALTHY" else health["overall"]
    
    return health


def print_report(health: dict):
    """Print health report."""
    emoji = {"HEALTHY": "✅", "WARNING": "⚠️", "UNHEALTHY": "🔴"}
    s = health["summary"]
    
    print("=" * 50)
    print(f"📊 DAILY HEALTH: {emoji.get(health['overall'])} {health['overall']}")
    print("=" * 50)
    print(f"Date:         {health['date']}")
    print(f"Equity:       ${s.get('equity', 0):,.2f}")
    print(f"Total P/L:    ${s.get('total_pl', 0):,.2f}")
    print(f"Today's P/L:  ${s.get('daily_pl', 0):,.2f}")
    print(f"Options WR:   {s.get('options_wr', 0):.0f}%")
    print(f"Options P/L:  ${s.get('options_pl', 0):,.2f}")
    print(f"Trades Today: {s.get('trades_today', 0)}")
    
    if health["alerts"]:
        print("\n🚨 ALERTS:")
        for alert in health["alerts"]:
            print(f"  ⚠️ {alert}")
    
    print("=" * 50)


def main():
    health = check_health()
    print_report(health)
    
    # Save report
    reports_dir = PROJECT_ROOT / "reports"
    reports_dir.mkdir(exist_ok=True)
    with open(reports_dir / f"health_{health['date']}.json", "w") as f:
        json.dump(health, f, indent=2)
    
    return 1 if health["overall"] == "UNHEALTHY" else 0


if __name__ == "__main__":
    sys.exit(main())

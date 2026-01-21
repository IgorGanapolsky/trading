#!/usr/bin/env python3
"""
Earnings Position Monitor - Automated Position Risk Check

This script checks all existing positions against upcoming earnings dates
and outputs actionable alerts. Run via CI or locally.

Usage:
    python scripts/check_earnings_positions.py
"""

import json
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(__file__).rsplit("/scripts", 1)[0])

from src.risk.trade_gateway import get_trade_gateway


def main():
    """Check positions for earnings conflicts and output alerts."""
    print("=" * 60)
    print(f"EARNINGS POSITION MONITOR - {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    gateway = get_trade_gateway(paper=True)
    alerts = gateway.check_positions_for_earnings()

    if not alerts:
        print("\n✅ No positions at risk from upcoming earnings.")
        return 0

    print(f"\n⚠️ {len(alerts)} POSITION(S) REQUIRE ATTENTION:\n")

    for i, alert in enumerate(alerts, 1):
        print(f"--- Alert {i}: {alert['symbol']} ---")
        print(f"  Underlying:      {alert['underlying']}")
        print(f"  Quantity:        {alert['qty']}")
        print(f"  Unrealized P/L:  ${alert['unrealized_pl']:.2f}")
        print(f"  Earnings Date:   {alert['earnings_date']}")
        print(f"  Blackout Period: {alert['blackout_start']} to {alert['blackout_end']}")
        print(f"  Days to Blackout: {alert['days_to_blackout']}")
        print(f"  Days to Earnings: {alert['days_to_earnings']}")
        print(f"  Status:          {alert['status']}")
        print(f"  🎯 ACTION:       {alert['action']}")
        print()

    # Output JSON for CI consumption
    print("\n--- JSON Output ---")
    print(json.dumps(alerts, indent=2))

    # Return non-zero if urgent action needed
    urgent = any(a["days_to_blackout"] <= 7 for a in alerts)
    if urgent:
        print("\n🚨 URGENT: Position(s) within 7 days of blackout!")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

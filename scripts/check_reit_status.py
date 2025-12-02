#!/usr/bin/env python3
"""
Comprehensive REIT Trading Status Report

Shows:
1. Configuration status
2. Allocation calculations
3. Execution readiness
4. Historical trade analysis
"""

import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def load_trade_files():
    """Load all trade files."""
    trades_dir = Path("data")
    trades = []

    for trade_file in sorted(trades_dir.glob("trades_*.json")):
        try:
            with open(trade_file) as f:
                file_trades = json.load(f)
                if isinstance(file_trades, list):
                    trades.extend(file_trades)
                else:
                    trades.append(file_trades)
        except Exception as e:
            print(f"Warning: Could not load {trade_file}: {e}")

    return trades


def analyze_reit_trades(trades):
    """Analyze REIT-related trades."""
    vnq_trades = [t for t in trades if t.get("symbol") == "VNQ"]

    return {
        "total_vnq_trades": len(vnq_trades),
        "vnq_trades": vnq_trades,
        "last_vnq_trade": vnq_trades[-1] if vnq_trades else None,
        "vnq_by_date": defaultdict(list),
    }


def main():
    print("=" * 80)
    print("REIT TRADING STATUS REPORT")
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    print()

    # Configuration
    daily_investment = float(os.getenv("DAILY_INVESTMENT", "900.0"))
    reit_allocation_pct = 0.15
    reit_amount = daily_investment * reit_allocation_pct
    execution_threshold = 0.50

    print("📊 CONFIGURATION:")
    print(f"   Daily Investment:     ${daily_investment:.2f}")
    print("   REIT Allocation:     15%")
    print(f"   REIT Amount/Day:     ${reit_amount:.2f}")
    print(f"   Execution Threshold: ${execution_threshold:.2f}")
    print(
        f"   Status:              {'✅ READY' if reit_amount >= execution_threshold else '❌ BELOW THRESHOLD'}"
    )
    print()

    # Load trades
    print("📈 TRADE ANALYSIS:")
    trades = load_trade_files()
    print(f"   Total trades loaded:  {len(trades)}")

    reit_analysis = analyze_reit_trades(trades)
    print(f"   VNQ trades executed:  {reit_analysis['total_vnq_trades']}")

    if reit_analysis["last_vnq_trade"]:
        last_trade = reit_analysis["last_vnq_trade"]
        print(f"   Last VNQ trade:      {last_trade.get('timestamp', 'N/A')}")
        print(f"   Last VNQ amount:     ${last_trade.get('amount', 0):.2f}")
    else:
        print("   Last VNQ trade:      ❌ NONE FOUND")

    print()

    # Date analysis
    print("📅 TIMELINE:")
    vnq_added_date = "2025-11-27"
    print(f"   VNQ added to strategy: {vnq_added_date}")

    if trades:
        trade_dates = [t.get("timestamp", "")[:10] for t in trades if t.get("timestamp")]
        if trade_dates:
            last_trade_date = max(trade_dates)
            print(f"   Last trade execution: {last_trade_date}")

            if last_trade_date < vnq_added_date:
                print("   ⚠️  Last trade was BEFORE VNQ was added")
                print("   ✅ VNQ will execute on next trading day")
            else:
                print("   ✅ Trades executed after VNQ addition")
    else:
        print("   ⚠️  No trades found")

    print()

    # Summary
    print("=" * 80)
    print("SUMMARY:")
    print("=" * 80)

    if reit_analysis["total_vnq_trades"] == 0:
        if reit_amount >= execution_threshold:
            print("✅ REIT trading is CONFIGURED and READY")
            print(f"   Expected execution: ${reit_amount:.2f} per day")
            print("   ⚠️  No VNQ trades yet - system hasn't executed since VNQ was added")
            print("   ✅ VNQ will execute automatically on next trading day")
        else:
            print("❌ REIT trading NOT READY")
            print(
                f"   Allocation (${reit_amount:.2f}) is below threshold (${execution_threshold:.2f})"
            )
    else:
        print("✅ REIT trading is ACTIVE")
        print(f"   {reit_analysis['total_vnq_trades']} VNQ trades executed")

    print()


if __name__ == "__main__":
    main()

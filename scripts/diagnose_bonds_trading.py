#!/usr/bin/env python3
"""
Bonds Trading Diagnostic Script
Checks why BND/TLT orders aren't executing
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

load_dotenv()


def check_configuration():
    """Check current configuration settings"""
    print("=" * 80)
    print("BONDS TRADING DIAGNOSTIC")
    print("=" * 80)
    print()

    # Check environment variables
    daily_investment = float(os.getenv("DAILY_INVESTMENT", "1500.0"))
    tier1_allocation = float(os.getenv("TIER1_ALLOCATION", "0.60"))

    print("📊 CONFIGURATION CHECK")
    print("-" * 80)
    print(f"DAILY_INVESTMENT: ${daily_investment:.2f}")
    print(f"TIER1_ALLOCATION: {tier1_allocation * 100:.1f}%")
    print()

    # Calculate allocations
    tier1_daily = daily_investment * tier1_allocation

    # CoreStrategy allocation breakdown
    EQUITY_ALLOCATION_PCT = 0.60
    BOND_ALLOCATION_PCT = 0.15
    REIT_ALLOCATION_PCT = 0.15
    TREASURY_ALLOCATION_PCT = 0.10

    equity_amount = tier1_daily * EQUITY_ALLOCATION_PCT
    bond_amount = tier1_daily * BOND_ALLOCATION_PCT
    reit_amount = tier1_daily * REIT_ALLOCATION_PCT
    treasury_amount = tier1_daily * TREASURY_ALLOCATION_PCT

    print("💰 TIER 1 ALLOCATION BREAKDOWN")
    print("-" * 80)
    print(f"Tier 1 Daily Total: ${tier1_daily:.2f}")
    print(f"  Equity (60%):    ${equity_amount:.2f}")
    print(f"  Bonds (15%):     ${bond_amount:.2f}")
    print(f"  REITs (15%):     ${reit_amount:.2f}")
    print(f"  Treasuries (10%): ${treasury_amount:.2f}")
    print()

    # Check thresholds
    MIN_THRESHOLD = 0.50
    print("🎯 EXECUTION THRESHOLDS")
    print("-" * 80)
    print(f"Minimum Order Size: ${MIN_THRESHOLD:.2f}")
    print(
        f"Bond orders will execute: {'✅ YES' if bond_amount >= MIN_THRESHOLD else '❌ NO (too small)'}"
    )
    print(
        f"REIT orders will execute: {'✅ YES' if reit_amount >= MIN_THRESHOLD else '❌ NO (too small)'}"
    )
    print(
        f"Treasury orders will execute: {'✅ YES' if treasury_amount >= MIN_THRESHOLD else '❌ NO (too small)'}"
    )
    print()

    # Check system state
    system_state_file = Path("data/system_state.json")
    if system_state_file.exists():
        import json

        with open(system_state_file) as f:
            state = json.load(f)

        print("📈 SYSTEM STATE")
        print("-" * 80)
        tier1_state = state.get("strategies", {}).get("tier1", {})
        print(f"Tier 1 Daily Amount (from state): ${tier1_state.get('daily_amount', 'N/A')}")
        print(f"Tier 1 Trades Executed: {tier1_state.get('trades_executed', 0)}")
        print(f"Tier 1 Total Invested: ${tier1_state.get('total_invested', 0):.2f}")
        print()

    # Check recent trades
    print("📝 RECENT TRADE CHECK")
    print("-" * 80)
    trades_dir = Path("data/trades")
    if trades_dir.exists():
        trade_files = sorted(trades_dir.glob("trades_*.json"), reverse=True)[:5]
        bond_trades = 0
        total_trades = 0

        for trade_file in trade_files:
            try:
                with open(trade_file) as f:
                    trades = json.load(f)
                    for trade in trades:
                        total_trades += 1
                        if trade.get("symbol") in ["BND", "TLT"]:
                            bond_trades += 1
                            print(
                                f"✅ Found bond trade: {trade.get('symbol')} ${trade.get('amount', 0):.2f} on {trade_file.stem}"
                            )
            except Exception:
                pass

        if bond_trades == 0:
            print(f"❌ No bond trades found in last {len(trade_files)} trade files")
            print(f"   Total trades checked: {total_trades}")
        else:
            print(f"✅ Found {bond_trades} bond trade(s)")
        print()

    # Recommendations
    print("💡 RECOMMENDATIONS")
    print("-" * 80)
    if bond_amount < MIN_THRESHOLD:
        print(
            f"⚠️  Bond allocation (${bond_amount:.2f}) is below minimum threshold (${MIN_THRESHOLD:.2f})"
        )
        print("   Increase DAILY_INVESTMENT or TIER1_ALLOCATION to enable bond trading")
    elif bond_amount >= MIN_THRESHOLD:
        print(f"✅ Bond allocation (${bond_amount:.2f}) is sufficient for execution")
        print("   If bonds aren't executing, check:")
        print("   1. Execution logs for errors")
        print("   2. Market hours (bonds trade during market hours)")
        print("   3. Account buying power")
        print("   4. Order validation failures")
    print()

    print("=" * 80)


if __name__ == "__main__":
    check_configuration()

#!/usr/bin/env python3
"""
Verify trading execution success.

Checks 3 critical files to verify trades actually executed:
1. trades_YYYY-MM-DD.json exists and has filled orders
2. system_state.json shows updated account value
3. GitHub Actions workflows succeeded

Run this after any trading window to verify success/failure.
NO BULLSHIT. Just facts.
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Tuple


def check_trades_file(date_str: str) -> Tuple[bool, str]:
    """Check if today's trades file exists and has filled orders."""
    trades_file = Path(f"data/trades_{date_str}.json")
    
    if not trades_file.exists():
        return False, f"❌ trades_{date_str}.json does NOT exist"
    
    try:
        with open(trades_file) as f:
            trades = json.load(f)
    except Exception as e:
        return False, f"❌ trades_{date_str}.json is CORRUPT: {e}"
    
    if not trades:
        return False, f"❌ trades_{date_str}.json is EMPTY (no trades)"
    
    filled_trades = [t for t in trades if t.get('status') in ['FILLED', 'OrderStatus.FILLED']]
    
    if not filled_trades:
        return False, f"❌ NO FILLED trades in {len(trades)} total orders"
    
    total_pl = sum(t.get('pnl', 0) for t in filled_trades if 'pnl' in t)
    
    return True, f"✅ {len(filled_trades)} FILLED trades, P/L: ${total_pl:.2f}"


def check_system_state(date_str: str) -> Tuple[bool, str]:
    """Check if system_state.json was updated today."""
    state_file = Path("data/system_state.json")
    
    if not state_file.exists():
        return False, "❌ system_state.json does NOT exist"
    
    try:
        with open(state_file) as f:
            state = json.load(f)
    except Exception as e:
        return False, f"❌ system_state.json is CORRUPT: {e}"
    
    last_trade = state.get('last_trade_date', 'NEVER')
    account_value = state.get('account_value', 0)
    
    if last_trade != date_str:
        return False, f"❌ last_trade_date is {last_trade}, expected {date_str}"
    
    return True, f"✅ last_trade_date: {last_trade}, account: ${account_value:.2f}"


def verify_trading_success(date_str: str = None) -> bool:
    """
    Verify trading execution succeeded.
    
    Returns True if all checks pass, False otherwise.
    """
    if date_str is None:
        date_str = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    
    print("=" * 70)
    print(f"TRADING VERIFICATION - {date_str}")
    print("=" * 70)
    print()
    
    # Check 1: Trades file
    trades_ok, trades_msg = check_trades_file(date_str)
    print(f"1. Trades File:     {trades_msg}")
    
    # Check 2: System state
    state_ok, state_msg = check_system_state(date_str)
    print(f"2. System State:    {state_msg}")
    
    # Check 3: Manual workflow check (can't automate from here)
    print(f"3. GitHub Actions:  ⚠️  CHECK MANUALLY:")
    print(f"   https://github.com/IgorGanapolsky/trading/actions/workflows/daily-trading.yml")
    print(f"   https://github.com/IgorGanapolsky/trading/actions/workflows/combined-trading.yml")
    
    print()
    print("=" * 70)
    
    if trades_ok and state_ok:
        print("VERDICT: ✅ TRADING SUCCEEDED")
        print("=" * 70)
        return True
    else:
        print("VERDICT: ❌ TRADING FAILED")
        print("=" * 70)
        print()
        print("REASONS:")
        if not trades_ok:
            print(f"  - {trades_msg}")
        if not state_ok:
            print(f"  - {state_msg}")
        print()
        return False


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Verify trading execution success")
    parser.add_argument(
        "--date",
        help="Date to check (YYYY-MM-DD). Default: today",
        default=None
    )
    
    args = parser.parse_args()
    
    success = verify_trading_success(args.date)
    sys.exit(0 if success else 1)

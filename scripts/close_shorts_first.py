#!/usr/bin/env python3
"""
Close SHORT positions first to free up margin, then close longs.

CRISIS FIX: Alpaca is treating SELL orders on LONG puts as opening shorts,
which requires $56K+ margin we don't have.

Strategy:
1. Close SHORT positions first (buy to close) - this frees up margin
2. Then close LONG positions (sell to close) - should have margin now
"""

import os
import sys
from datetime import datetime

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
    "ALPACA_PAPER_TRADING_5K_API_SECRET"
)

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import ClosePositionRequest

print("=" * 60)
print(f"CLOSE SHORTS FIRST STRATEGY - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)
account = client.get_account()
print(f"\nEquity: ${float(account.equity):,.2f}")
print(f"Options Buying Power: ${float(account.options_buying_power):,.2f}")

# Get all positions
positions = client.get_all_positions()

shorts = []
longs = []

print("\nCurrent Positions:")
for pos in positions:
    qty = float(pos.qty)
    symbol = pos.symbol
    pnl = float(pos.unrealized_pl)

    # Only SPY options
    if not symbol.startswith("SPY") or len(symbol) <= 5:
        print(f"  [SKIP] {symbol}: qty={qty}")
        continue

    if qty < 0:
        shorts.append((symbol, qty, pnl))
        print(f"  [SHORT] {symbol}: qty={qty}, P/L=${pnl:+.2f}")
    else:
        longs.append((symbol, qty, pnl))
        print(f"  [LONG]  {symbol}: qty={qty}, P/L=${pnl:+.2f}")

# Step 1: Close all SHORT positions first
print("\n" + "=" * 60)
print("STEP 1: CLOSE SHORT POSITIONS (buy to close)")
print("=" * 60)

for symbol, qty, pnl in shorts:
    print(f"\nClosing {symbol} ({qty} contracts)...")
    try:
        result = client.close_position(symbol)
        print(f"  ✅ SUCCESS! Order ID: {result.id if hasattr(result, 'id') else result}")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")

# Refresh account after closing shorts
print("\n--- Refreshing account data ---")
account = client.get_account()
print(f"Options Buying Power now: ${float(account.options_buying_power):,.2f}")

# Step 2: Close all LONG positions
print("\n" + "=" * 60)
print("STEP 2: CLOSE LONG POSITIONS (sell to close)")
print("=" * 60)

for symbol, qty, pnl in longs:
    print(f"\nClosing {symbol} ({qty} contracts)...")
    try:
        result = client.close_position(symbol)
        print(f"  ✅ SUCCESS! Order ID: {result.id if hasattr(result, 'id') else result}")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")

        # Try partial close
        print(f"  Trying partial close (1 contract)...")
        try:
            close_req = ClosePositionRequest(qty="1")
            result = client.close_position(symbol, close_options=close_req)
            print(f"  ✅ Closed 1 contract! Order ID: {result.id if hasattr(result, 'id') else result}")
        except Exception as e2:
            print(f"  ❌ Partial also failed: {e2}")

print("\n" + "=" * 60)
print("CLOSE SHORTS FIRST STRATEGY COMPLETE")
print("=" * 60)

#!/usr/bin/env python3
"""
EMERGENCY: Close ALL option positions to stop losses.
Phil Town Rule #1: Don't lose money.
"""

import os
import sys

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_30K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
    "ALPACA_PAPER_TRADING_30K_API_SECRET"
)

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient

print("=" * 60)
print("CLOSE ALL OPTIONS - Phil Town Rule #1")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account status
account = client.get_account()
print(f"\nEquity: ${float(account.equity):,.2f}")
print(f"Cash: ${float(account.cash):,.2f}")

# Get all positions
positions = client.get_all_positions()
option_positions = [p for p in positions if len(p.symbol) > 10]  # Options have long symbols

print(f"\nFound {len(option_positions)} option positions:")
total_pl = 0
for pos in option_positions:
    pl = float(pos.unrealized_pl)
    total_pl += pl
    qty = float(pos.qty)
    print(f"  {pos.symbol}: qty={qty:+.0f}, P/L=${pl:+.2f}")

print(f"\nTotal Unrealized P/L: ${total_pl:+.2f}")

if not option_positions:
    print("\n✅ No option positions to close!")
    sys.exit(0)

print("\n" + "=" * 60)
print("CLOSING ALL POSITIONS")
print("=" * 60)

closed = 0
failed = 0

for pos in option_positions:
    symbol = pos.symbol
    print(f"\nClosing {symbol}...")
    try:
        result = client.close_position(symbol)
        print(f"  ✅ SUCCESS - Order ID: {result.id if hasattr(result, 'id') else 'N/A'}")
        closed += 1
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        failed += 1

print("\n" + "=" * 60)
print(f"RESULT: {closed} closed, {failed} failed")
print("=" * 60)

if failed > 0:
    sys.exit(1)

#!/usr/bin/env python3
"""EMERGENCY: Close exactly 7 contracts of SPY260220P00658000.

Based on analysis: 2 contracts bought TODAY (Jan 22), 7 bought BEFORE.
Closing 7 contracts is PDT-safe.
"""

import os
import sys

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get(
    "ALPACA_PAPER_TRADING_5K_API_SECRET"
)

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from datetime import datetime

print("=" * 60)
print(f"EMERGENCY CLOSE 7 - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account info
account = client.get_account()
print(f"\nAccount equity: ${float(account.equity):,.2f}")
print(f"Day trade count: {account.daytrade_count}")

# Check market status
clock = client.get_clock()
print(f"\nMarket open: {clock.is_open}")
if not clock.is_open:
    print("⚠️ Market is CLOSED - orders may not fill until market opens")

TARGET = "SPY260220P00658000"
CLOSE_QTY = 7  # PDT-safe: 7 bought before today

# Check position exists
positions = client.get_all_positions()
found = False
for p in positions:
    if p.symbol == TARGET:
        found = True
        qty = int(float(p.qty))
        pl = float(p.unrealized_pl)
        print(f"\nFound position: {TARGET}")
        print(f"  Current qty: {qty}")
        print(f"  P/L: ${pl:+,.2f}")
        break

if not found:
    print(f"\n✅ {TARGET} not found - already closed!")
    sys.exit(0)

# Attempt close
print(f"\n🔧 Attempting to close {CLOSE_QTY} contracts...")

# Method 1: close_position with qty
print("\n[1] Trying close_position(qty=7)...")
try:
    result = client.close_position(TARGET, qty=str(CLOSE_QTY))
    print(f"✅ SUCCESS: {result}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 2: Market order SELL
print("\n[2] Trying market order SELL...")
try:
    order = client.submit_order(MarketOrderRequest(
        symbol=TARGET,
        qty=CLOSE_QTY,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    print(f"✅ Order submitted: {order.id}")
    print(f"   Status: {order.status}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 3: Try smaller qty
print("\n[3] Trying smaller quantity (6)...")
try:
    order = client.submit_order(MarketOrderRequest(
        symbol=TARGET,
        qty=6,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    print(f"✅ Order submitted: {order.id}")
    print(f"   Status: {order.status}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 4: Close 1 at a time
print("\n[4] Trying to close 1 contract at a time...")
closed = 0
for i in range(CLOSE_QTY):
    try:
        order = client.submit_order(MarketOrderRequest(
            symbol=TARGET,
            qty=1,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        ))
        closed += 1
        print(f"  Closed contract {i+1}: {order.id}")
    except Exception as e:
        print(f"  Failed contract {i+1}: {e}")
        break

if closed > 0:
    print(f"\n✅ Closed {closed} contracts")
else:
    print("\n❌ ALL METHODS FAILED")
    print("   This may be a PDT restriction or broker issue")
    sys.exit(1)

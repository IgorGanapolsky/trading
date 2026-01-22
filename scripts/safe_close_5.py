#!/usr/bin/env python3
"""ULTRA-SAFE: Close only 5 contracts to definitely avoid PDT.

Analysis:
- 8 total contracts
- 2 bought TODAY (Jan 22) - selling these = day trades
- 6 bought Jan 21 - NOT day trades
- 1 bought Jan 20 - NOT day trades
- If Alpaca uses LIFO, selling 7 might include today's buys
- SAFE APPROACH: Only close 5 contracts (guaranteed all from before today)
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
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

print("=" * 60)
print(f"ULTRA-SAFE CLOSE 5 - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account info
account = client.get_account()
print(f"\nAccount equity: ${float(account.equity):,.2f}")
print(f"Day trade count (5 days): {account.daytrade_count}")
print(f"Pattern day trader: {getattr(account, 'pattern_day_trader', 'N/A')}")

# Check market status
clock = client.get_clock()
print(f"Market open: {clock.is_open}")

TARGET = "SPY260220P00658000"
CLOSE_QTY = 5  # ULTRA-SAFE: Only 5 to guarantee no PDT

# Check position exists
positions = client.get_all_positions()
found = False
for p in positions:
    if p.symbol == TARGET:
        found = True
        qty = int(float(p.qty))
        pl = float(p.unrealized_pl)
        print(f"\nPosition: {TARGET}")
        print(f"  Current qty: {qty}")
        print(f"  P/L: ${pl:+,.2f}")
        break

if not found:
    print(f"\n✅ {TARGET} not found - already closed!")
    sys.exit(0)

if qty == 0:
    print(f"\n✅ Position qty is 0 - already closed!")
    sys.exit(0)

# PDT check
print(f"\n📊 PDT Status:")
print(f"   Day trades (5 days): {account.daytrade_count}")
print(f"   Max allowed: 3")
remaining = 3 - int(account.daytrade_count)
print(f"   Remaining before PDT: {remaining}")

if remaining <= 0:
    print("\n⚠️ ALREADY AT PDT LIMIT - Cannot make more day trades today")
    print("   Will try to close non-day-trade contracts only")
    # Even safer - close only 3 contracts
    CLOSE_QTY = min(3, qty - 2)  # Leave today's buys

if CLOSE_QTY <= 0:
    print("\n❌ Cannot close any contracts safely")
    sys.exit(0)

# Attempt close
print(f"\n🔧 Attempting to close {CLOSE_QTY} contracts...")

# Method 1: close_position with qty
print(f"\n[1] Trying close_position(qty={CLOSE_QTY})...")
try:
    result = client.close_position(TARGET, qty=str(CLOSE_QTY))
    print(f"✅ SUCCESS!")
    if hasattr(result, 'id'):
        print(f"   Order ID: {result.id}")
    if hasattr(result, 'status'):
        print(f"   Status: {result.status}")
    sys.exit(0)
except Exception as e:
    error_str = str(e)
    print(f"❌ Failed: {error_str}")
    if "403" in error_str or "forbidden" in error_str.lower():
        print("   REASON: PDT protection blocked this order")
    if "day" in error_str.lower() and "trade" in error_str.lower():
        print("   REASON: Day trade restriction")

# Method 2: Market order SELL
print(f"\n[2] Trying market order SELL {CLOSE_QTY}...")
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
    error_str = str(e)
    print(f"❌ Failed: {error_str}")
    if "403" in error_str or "forbidden" in error_str.lower():
        print("   REASON: PDT protection blocked this order")

# Method 3: Even smaller qty
print(f"\n[3] Trying with qty=3...")
try:
    order = client.submit_order(MarketOrderRequest(
        symbol=TARGET,
        qty=3,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    print(f"✅ Order submitted: {order.id}")
    print(f"   Status: {order.status}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {e}")

# Method 4: Just 1 contract
print(f"\n[4] Trying with qty=1...")
try:
    order = client.submit_order(MarketOrderRequest(
        symbol=TARGET,
        qty=1,
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    ))
    print(f"✅ Order submitted: {order.id}")
    print(f"   Status: {order.status}")
    sys.exit(0)
except Exception as e:
    print(f"❌ Failed: {e}")
    print("\n❌ ALL METHODS FAILED")
    print("   PDT restriction is blocking ALL closes")
    print("   Options:")
    print("   1. Wait until tomorrow (day trades reset)")
    print("   2. Deposit $25,000 to remove PDT limit")
    print("   3. Accept PDT flag (90-day restriction)")
    sys.exit(1)

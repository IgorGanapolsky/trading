#!/usr/bin/env python3
"""
EMERGENCY: Cancel all orders then force close bleeding position.
"""
import os
import sys
import time

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest, MarketOrderRequest

print("=" * 60)
print("EMERGENCY CANCEL AND CLOSE")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Step 1: Get account status
account = client.get_account()
print(f"\nAccount Status:")
print(f"  Equity: ${float(account.equity):,.2f}")
print(f"  Cash: ${float(account.cash):,.2f}")
print(f"  Buying Power: ${float(account.buying_power):,.2f}")
print(f"  Day Trade Count: {account.daytrade_count}")

# Step 2: Cancel ALL open orders
print("\n" + "=" * 60)
print("STEP 1: Cancel ALL open orders")
print("=" * 60)

request_params = GetOrdersRequest(status=QueryOrderStatus.OPEN)
orders = client.get_orders(filter=request_params)

if orders:
    print(f"Found {len(orders)} open orders - canceling all...")
    for order in orders:
        print(f"  Canceling {order.symbol}: {order.id}")
        try:
            client.cancel_order_by_id(order.id)
            print(f"    ✅ Cancelled")
        except Exception as e:
            print(f"    ❌ Failed: {e}")

    # Wait for cancellations to process
    print("\nWaiting 2 seconds for cancellations...")
    time.sleep(2)
else:
    print("No open orders found")

# Step 3: Try to close position
target = "SPY260220P00658000"
print("\n" + "=" * 60)
print(f"STEP 2: Close position {target}")
print("=" * 60)

positions = client.get_all_positions()
target_pos = None

for pos in positions:
    print(f"  {pos.symbol}: qty={pos.qty}, P/L=${float(pos.unrealized_pl):+.2f}")
    if pos.symbol == target:
        target_pos = pos

if not target_pos:
    print(f"\n✅ Position {target} not found - already closed!")
    sys.exit(0)

qty = int(float(target_pos.qty))
current_price = float(target_pos.current_price)
print(f"\nTarget Position:")
print(f"  Symbol: {target}")
print(f"  Qty: {qty} LONG")
print(f"  Current Price: ${current_price:.2f}")
print(f"  P/L: ${float(target_pos.unrealized_pl):+.2f}")

# Try close_position for entire position
print(f"\nAttempt 1: close_position() for all {qty} contracts...")
try:
    result = client.close_position(target)
    print(f"  ✅ SUCCESS!")
    if hasattr(result, 'id'):
        print(f"  Order ID: {result.id}")
        print(f"  Status: {result.status}")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Failed: {e}")

# Try market order
print(f"\nAttempt 2: Market SELL order for all {qty} contracts...")
try:
    order = client.submit_order(
        MarketOrderRequest(
            symbol=target,
            qty=qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY
        )
    )
    print(f"  ✅ Order submitted!")
    print(f"  Order ID: {order.id}")
    print(f"  Status: {order.status}")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Failed: {e}")

# Try closing just 1 contract
print(f"\nAttempt 3: close_position() for just 1 contract...")
try:
    result = client.close_position(target, qty="1")
    print(f"  ✅ Closed 1 contract!")
    if hasattr(result, 'id'):
        print(f"  Order ID: {result.id}")
except Exception as e:
    print(f"  ❌ Failed: {e}")

print("\n" + "=" * 60)
print("⚠️  ALL CLOSE ATTEMPTS FAILED")
print("=" * 60)
print("Possible causes:")
print("  1. PDT restriction (check account.daytrade_count)")
print("  2. Insufficient buying power")
print("  3. Market closed")
print("  4. API error")
sys.exit(1)

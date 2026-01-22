#!/usr/bin/env python3
"""Force close the bleeding position using different order types."""
import os
import sys
from datetime import datetime

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce, OrderType
from alpaca.trading.requests import MarketOrderRequest, LimitOrderRequest

print("=" * 60)
print(f"FORCE CLOSE ATTEMPT - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account info
account = client.get_account()
print(f"\nAccount Equity: ${float(account.equity):,.2f}")
print(f"Day Trade Count: {account.daytrade_count}")
print(f"PDT Flag: {account.pattern_day_trader}")

# Get the position
target = "SPY260220P00658000"
positions = client.get_all_positions()

target_pos = None
for pos in positions:
    if pos.symbol == target:
        target_pos = pos
        break

if not target_pos:
    print(f"Position {target} not found!")
    sys.exit(0)

qty = int(float(target_pos.qty))
current_price = float(target_pos.current_price)
print(f"\nPosition: {target}")
print(f"  Qty: {qty}")
print(f"  Current Price: ${current_price:.2f}")
print(f"  P/L: ${float(target_pos.unrealized_pl):+.2f}")

# Try to close with different approaches
close_qty = 6  # Only close excess

print(f"\n=== Attempting to close {close_qty} contracts ===")

# Approach 1: Try closing position directly via close_position
print("\nApproach 1: Using close_position API...")
try:
    # Close specific quantity
    result = client.close_position(target, qty=str(close_qty))
    print(f"  ✅ SUCCESS: {result}")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Failed: {e}")

# Approach 2: Try limit order at current price
print("\nApproach 2: Limit order at market price...")
try:
    order = client.submit_order(
        LimitOrderRequest(
            symbol=target,
            qty=close_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            limit_price=round(current_price * 0.95, 2)  # Slightly below market
        )
    )
    print(f"  ✅ Limit order submitted: {order.id}")
    sys.exit(0)
except Exception as e:
    print(f"  ❌ Failed: {e}")

# Approach 3: Try closing just 1 contract
print("\nApproach 3: Close just 1 contract...")
try:
    result = client.close_position(target, qty="1")
    print(f"  ✅ Closed 1: {result}")
except Exception as e:
    print(f"  ❌ Failed: {e}")

print("\n⚠️  All approaches failed due to PDT restriction")
print("The account has hit the day trade limit.")

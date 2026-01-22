#!/usr/bin/env python3
"""
Close positions that were NOT opened today - bypass PDT.

PDT only applies to same-day round trips. If we close positions
opened yesterday, it's not a day trade.
"""
import os
import sys
from datetime import datetime, timezone

api_key = os.environ.get("ALPACA_API_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
api_secret = os.environ.get("ALPACA_SECRET_KEY") or os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")

if not api_key or not api_secret:
    print("ERROR: Missing Alpaca API credentials")
    sys.exit(1)

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

print("=" * 60)
print(f"CLOSE NON-DAYTRADE POSITIONS - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account
account = client.get_account()
print(f"\nAccount Equity: ${float(account.equity):,.2f}")
print(f"Day Trade Count: {account.daytrade_count}")

# Get orders to check when positions were opened
orders = list(client.get_orders(status='all', limit=100))
print(f"Recent Orders: {len(orders)}")

# Find when SPY260220P00658000 was bought
target = "SPY260220P00658000"
today = datetime.now(timezone.utc).date()

buys_today = 0
buys_yesterday = 0

for order in orders:
    if order.symbol == target and order.side.name == 'BUY' and order.filled_at:
        order_date = order.filled_at.date()
        if order_date == today:
            buys_today += int(float(order.filled_qty or 0))
        else:
            buys_yesterday += int(float(order.filled_qty or 0))

print(f"\n{target}:")
print(f"  Bought TODAY: {buys_today} contracts (would be day trade)")
print(f"  Bought BEFORE today: {buys_yesterday} contracts (NOT day trade)")

# We can safely close contracts that were not opened today
safe_to_close = buys_yesterday
print(f"\n  Safe to close: {safe_to_close} contracts")

if safe_to_close <= 0:
    print("\n⚠️  No contracts safe to close without day trade")
    sys.exit(0)

# Try to close just the non-day-trade contracts
print(f"\n=== Attempting to close {safe_to_close} contracts ===")

try:
    order = client.submit_order(
        MarketOrderRequest(
            symbol=target,
            qty=safe_to_close,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"  ✅ Order submitted: {order.id}")
    print(f"  Status: {order.status}")
except Exception as e:
    print(f"  ❌ Failed: {e}")
    
    # Try smaller qty
    print(f"\n  Trying {safe_to_close - 1} contracts...")
    try:
        order = client.submit_order(
            MarketOrderRequest(
                symbol=target,
                qty=safe_to_close - 1,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
        print(f"  ✅ Order submitted: {order.id}")
    except Exception as e2:
        print(f"  ❌ Failed: {e2}")
        sys.exit(1)

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)

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
print(f"CLOSE NON-DAYTRADE POSITIONS - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)

# Get account
account = client.get_account()
print(f"\nAccount Equity: ${float(account.equity):,.2f}")
print(f"Day Trade Count: {account.daytrade_count}")

# Get orders to check when positions were opened
from alpaca.trading.requests import GetOrdersRequest
from alpaca.trading.enums import QueryOrderStatus
orders_request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100)
orders = list(client.get_orders(filter=orders_request))
print(f"Recent Orders: {len(orders)}")

# Find when SPY260220P00658000 was bought
target = "SPY260220P00658000"
today = datetime.now(timezone.utc).date()

buys_today = 0
buys_yesterday = 0

for order in orders:
    if order.symbol == target and order.side.name == "BUY" and order.filled_at:
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

# Try to close using close_position with percentage
# This is more reliable than submit_order for closing existing positions
print(f"\n=== Attempting to close {safe_to_close} contracts using close_position API ===")

# Get current position qty
positions = client.get_all_positions()
current_qty = 0
for pos in positions:
    if pos.symbol == target:
        current_qty = int(float(pos.qty))
        break

print(f"  Current position qty: {current_qty}")

if current_qty <= 0:
    print("  No long position found")
    sys.exit(0)

# Calculate percentage to close (safe_to_close out of current_qty)
# But max out at what we can close without day trade
close_qty = min(safe_to_close, current_qty)
percentage = (close_qty / current_qty) * 100

print(f"  Closing {close_qty} contracts ({percentage:.1f}% of position)")

try:
    # Use close_position with qty parameter
    from alpaca.trading.requests import ClosePositionRequest
    close_request = ClosePositionRequest(qty=str(close_qty))
    result = client.close_position(target, close_options=close_request)

    if isinstance(result, list):
        for order in result:
            print(f"  ✅ Order: {order.id} - {order.status}")
    else:
        print(f"  ✅ Order: {result.id} - {result.status}")
except Exception as e:
    print(f"  ❌ close_position failed: {e}")

    # Fallback: try submit_order with explicit options
    print("\n  Trying submit_order fallback...")
    try:
        # For options, we need to be explicit about the order type
        from alpaca.trading.requests import MarketOrderRequest
        order = client.submit_order(
            MarketOrderRequest(
                symbol=target,
                qty=close_qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
        print(f"  ✅ Fallback order: {order.id}")
    except Exception as e2:
        print(f"  ❌ Fallback also failed: {e2}")

        # Try closing just 1 contract at a time
        print("\n  Trying one contract at a time...")
        for i in range(close_qty):
            try:
                order = client.submit_order(
                    MarketOrderRequest(
                        symbol=target,
                        qty=1,
                        side=OrderSide.SELL,
                        time_in_force=TimeInForce.DAY,
                    )
                )
                print(f"  ✅ Contract {i+1}: {order.id}")
            except Exception as e3:
                print(f"  ❌ Contract {i+1} failed: {e3}")
                break
        sys.exit(1)

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)

#!/usr/bin/env python3
"""Close ONLY contracts bought BEFORE today to bypass PDT."""

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
from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
from alpaca.trading.requests import MarketOrderRequest, GetOrdersRequest

print("=" * 60)
print(f"PDT BYPASS - CLOSE NON-DAYTRADE ONLY - {datetime.now()}")
print("=" * 60)

client = TradingClient(api_key, api_secret, paper=True)
account = client.get_account()
print(f"\nEquity: ${float(account.equity):,.2f}")
print(f"Day Trade Count: {account.daytrade_count}")

target = "SPY260220P00658000"
today = datetime.now(timezone.utc).date()

# Get position
positions = client.get_all_positions()
target_pos = None
for p in positions:
    if p.symbol == target:
        target_pos = p
        total_qty = int(float(p.qty))
        price = float(p.current_price)
        print(f"\nPosition: {target}")
        print(f"  Total Qty: {total_qty}")
        print(f"  Price: ${price:.2f}")
        print(f"  P/L: ${float(p.unrealized_pl):+,.2f}")
        break

if not target_pos:
    print(f"\n✅ {target} not found - may be closed already")
    sys.exit(0)

# Calculate PDT-safe quantity
print("\nCalculating PDT-safe quantity...")
try:
    orders = client.get_orders(filter=GetOrdersRequest(status=QueryOrderStatus.ALL, limit=100))
    buys_today = 0
    buys_before = 0
    for order in orders:
        if order.symbol == target and order.side.name == 'BUY' and order.filled_at:
            filled_qty = int(float(order.filled_qty or 0))
            if order.filled_at.date() == today:
                buys_today += filled_qty
            else:
                buys_before += filled_qty
    print(f"  Bought TODAY (day trade if sold): {buys_today}")
    print(f"  Bought BEFORE today (SAFE to sell): {buys_before}")

    safe_qty = min(buys_before, total_qty)
except Exception as e:
    print(f"  Warning: Could not calculate - {e}")
    safe_qty = total_qty - 1  # Conservative: assume 1 bought today

if safe_qty <= 0:
    print("\n⚠️ No PDT-safe contracts to close")
    sys.exit(0)

print(f"\n🔧 Will close {safe_qty} of {total_qty} contracts (PDT bypass)")

# Try market order for PDT-safe quantity
print(f"\nSubmitting SELL order for {safe_qty} contracts...")
try:
    order = client.submit_order(
        MarketOrderRequest(
            symbol=target,
            qty=safe_qty,
            side=OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
        )
    )
    print(f"✅ Order submitted: {order.id}")
    print(f"   Status: {order.status}")
    print(f"   Qty: {order.qty}")
except Exception as e:
    print(f"❌ Market order failed: {e}")

    # Try close_position with specific qty
    print(f"\nTrying close_position({safe_qty})...")
    try:
        result = client.close_position(target, qty=str(safe_qty))
        print(f"✅ close_position succeeded!")
        if hasattr(result, 'id'):
            print(f"   Order ID: {result.id}")
    except Exception as e2:
        print(f"❌ close_position failed: {e2}")
        sys.exit(1)

print("\n" + "=" * 60)
print("✅ PDT BYPASS COMPLETE")
print("=" * 60)

#!/usr/bin/env python3
"""
Check your current positions and orders
"""

import os

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import QueryOrderStatus
from alpaca.trading.requests import GetOrdersRequest

ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")

api = TradingClient(
    api_key=ALPACA_KEY,
    secret_key=ALPACA_SECRET,
    paper=True,
)

print("=" * 70)
print("📊 YOUR TRADING ACCOUNT STATUS")
print("=" * 70)

# Account Info
print("\n💰 ACCOUNT BALANCE")
print("-" * 70)
account = api.get_account()
print(f"Buying Power: ${float(account.buying_power):,.2f}")
print(f"Cash: ${float(account.cash):,.2f}")
print(f"Equity: ${float(account.equity):,.2f}")
print(f"P/L: ${float(account.equity) - 100000:.2f}")

# Positions
print("\n📈 CURRENT POSITIONS")
print("-" * 70)
positions = api.get_all_positions()

if positions:
    for pos in positions:
        pl_dollars = float(pos.unrealized_pl)
        pl_percent = float(pos.unrealized_plpc) * 100
        print(f"\n{pos.symbol}:")
        print(f"  Shares: {pos.qty}")
        print(f"  Entry Price: ${float(pos.avg_entry_price):.2f}")
        print(f"  Current Price: ${float(pos.current_price):.2f}")
        print(f"  Value: ${float(pos.market_value):.2f}")
        print(f"  P/L: ${pl_dollars:+.2f} ({pl_percent:+.2f}%)")
else:
    print("No positions yet")

# Recent Orders
print("\n📝 RECENT ORDERS (Last 10)")
print("-" * 70)
request = GetOrdersRequest(status=QueryOrderStatus.ALL, limit=10)
orders = api.get_orders(filter=request)

if orders:
    for order in orders:
        print(f"\n{order.symbol} - {order.side.upper()}")
        print(f"  Amount: ${order.notional if order.notional else 'N/A'}")
        print(f"  Status: {order.status}")
        print(f"  Time: {order.submitted_at}")
else:
    print("No orders yet")

print("\n" + "=" * 70)

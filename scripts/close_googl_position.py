#!/usr/bin/env python3
"""Close GOOGL position that has exceeded take-profit threshold."""

import os
import sys

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest

# Get API credentials
api_key = os.getenv("ALPACA_API_KEY")
api_secret = os.getenv("ALPACA_SECRET_KEY")

if not api_key or not api_secret:
    print("❌ Missing API credentials")
    sys.exit(1)

# Initialize client
client = TradingClient(api_key, api_secret, paper=True)

# Get positions
positions = client.get_all_positions()
print(f"📊 Found {len(positions)} positions:")

googl_position = None
for pos in positions:
    print(
        f"  {pos.symbol}: {pos.qty} shares @ ${pos.avg_entry_price:.2f}, Current: ${pos.current_price:.2f}, P/L: {pos.unrealized_plpc * 100:.2f}%"
    )
    if pos.symbol == "GOOGL":
        googl_position = pos

if not googl_position:
    print("❌ GOOGL position not found")
    sys.exit(1)

# Check if take-profit should trigger
unrealized_pct = googl_position.unrealized_plpc * 100
print("\n🔍 GOOGL Analysis:")
print(f"   Entry: ${googl_position.avg_entry_price:.2f}")
print(f"   Current: ${googl_position.current_price:.2f}")
print(f"   P/L: {unrealized_pct:.2f}%")
print("   Take-profit threshold: 10.0%")

if unrealized_pct >= 10.0:
    print(f"\n✅ TAKE-PROFIT TRIGGERED! ({unrealized_pct:.2f}% >= 10.0%)")
    print("🚀 Closing GOOGL position...")

    try:
        order = client.submit_order(
            order_data=MarketOrderRequest(
                symbol="GOOGL",
                qty=float(googl_position.qty),
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
        )
        print("✅ CLOSED GOOGL position!")
        print(f"   Order ID: {order.id}")
        print(f"   Quantity: {googl_position.qty} shares")
        print(
            f"   Estimated proceeds: ${float(googl_position.qty) * googl_position.current_price:.2f}"
        )
        print(f"   Realized profit: ${googl_position.unrealized_pl:.2f} ({unrealized_pct:.2f}%)")
    except Exception as e:
        print(f"❌ Failed to close position: {e}")
        sys.exit(1)
else:
    print(f"⚠️  Take-profit not triggered yet ({unrealized_pct:.2f}% < 10.0%)")

#!/usr/bin/env python3
"""Force close GOOGL position that has exceeded take-profit threshold."""

import os
import sys

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import alpaca_trade_api as tradeapi
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize Alpaca API
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")
ALPACA_BASE_URL = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

if not ALPACA_KEY or not ALPACA_SECRET:
    print("❌ Missing API credentials")
    sys.exit(1)

api = tradeapi.REST(ALPACA_KEY, ALPACA_SECRET, ALPACA_BASE_URL, api_version="v2")

# Get positions
positions = api.list_positions()
print(f"📊 Found {len(positions)} positions:")

googl_position = None
for pos in positions:
    entry_price = float(pos.avg_entry_price)
    current_price = float(pos.current_price)
    unrealized_pct = float(pos.unrealized_plpc) * 100
    print(
        f"  {pos.symbol}: {pos.qty} shares @ ${entry_price:.2f}, Current: ${current_price:.2f}, P/L: {unrealized_pct:.2f}%"
    )
    if pos.symbol == "GOOGL":
        googl_position = pos

if not googl_position:
    print("❌ GOOGL position not found")
    sys.exit(1)

# Check if take-profit should trigger
entry_price = float(googl_position.avg_entry_price)
current_price = float(googl_position.current_price)
unrealized_pct = float(googl_position.unrealized_plpc) * 100
unrealized_pl = float(googl_position.unrealized_pl)

print("\n🔍 GOOGL Analysis:")
print(f"   Entry: ${entry_price:.2f}")
print(f"   Current: ${current_price:.2f}")
print(f"   P/L: {unrealized_pct:.2f}%")
print("   Take-profit threshold: 10.0%")

if unrealized_pct >= 10.0:
    print(f"\n✅ TAKE-PROFIT TRIGGERED! ({unrealized_pct:.2f}% >= 10.0%)")
    print("🚀 Closing GOOGL position...")

    try:
        # Close the position
        order = api.submit_order(
            symbol="GOOGL",
            qty=float(googl_position.qty),
            side="sell",
            type="market",
            time_in_force="day",
        )
        print("✅ CLOSED GOOGL position!")
        print(f"   Order ID: {order.id}")
        print(f"   Quantity: {googl_position.qty} shares")
        print(f"   Estimated proceeds: ${float(googl_position.qty) * current_price:.2f}")
        print(f"   Realized profit: ${unrealized_pl:.2f} ({unrealized_pct:.2f}%)")
    except Exception as e:
        print(f"❌ Failed to close position: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
else:
    print(f"⚠️  Take-profit not triggered yet ({unrealized_pct:.2f}% < 10.0%)")

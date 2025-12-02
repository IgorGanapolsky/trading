#!/usr/bin/env python3
"""
DEMO: First Paper Trade Without AI
Shows how the system executes a trade using technical analysis only
"""

import os
from datetime import datetime, timedelta

import alpaca_trade_api as tradeapi

print("=" * 70)
print("🎯 DEMO: YOUR FIRST PAPER TRADE")
print("=" * 70)

# Load credentials from environment
ALPACA_KEY = os.getenv("ALPACA_API_KEY")
ALPACA_SECRET = os.getenv("ALPACA_SECRET_KEY")

if not ALPACA_KEY or not ALPACA_SECRET:
    raise ValueError("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables must be set")

# Connect to Alpaca
api = tradeapi.REST(
    ALPACA_KEY,
    ALPACA_SECRET,
    "https://paper-api.alpaca.markets",
)

# Step 1: Check Account
print("\n📊 STEP 1: Checking Your Paper Trading Account")
print("-" * 70)
account = api.get_account()
print(f"Account Status: {account.status}")
print(f"Buying Power: ${float(account.buying_power):,.2f}")
print(f"Cash Available: ${float(account.cash):,.2f}")
print(f"Current Equity: ${float(account.equity):,.2f}")

# Step 2: Analyze ETFs (Simple Momentum)
print("\n📈 STEP 2: Analyzing Index ETFs (Technical Analysis)")
print("-" * 70)

etfs = ["SPY", "QQQ", "VOO"]
momentum_scores = {}

for symbol in etfs:
    try:
        # Get 30 days of price data
        end = datetime.now()
        start = end - timedelta(days=30)

        bars = api.get_bars(
            symbol,
            "1Day",
            start=start.strftime("%Y-%m-%d"),
            end=end.strftime("%Y-%m-%d"),
        ).df

        if len(bars) > 0:
            # Calculate simple momentum (% change over period)
            first_price = bars["close"].iloc[0]
            last_price = bars["close"].iloc[-1]
            momentum = ((last_price - first_price) / first_price) * 100

            momentum_scores[symbol] = momentum
            print(f"{symbol}: {momentum:+.2f}% (30-day return)")
    except Exception as e:
        print(f"{symbol}: Error - {e}")
        momentum_scores[symbol] = 0

# Step 3: Select Best ETF
print("\n🎯 STEP 3: Selecting Best Performer")
print("-" * 70)

if momentum_scores:
    best_etf = max(momentum_scores, key=momentum_scores.get)
    best_score = momentum_scores[best_etf]

    print(f"Winner: {best_etf} with {best_score:+.2f}% momentum")
    print(f"Strategy: Buy ${6.00} worth (Tier 1 - 60% allocation)")
else:
    print("Error: Could not calculate momentum")
    exit(1)

# Step 4: Check Current Price
print("\n💵 STEP 4: Getting Current Price")
print("-" * 70)

try:
    latest_trade = api.get_latest_trade(best_etf)
    current_price = latest_trade.price
    shares_to_buy = 6.00 / current_price

    print(f"{best_etf} Current Price: ${current_price:.2f}")
    print(f"Shares to Buy: {shares_to_buy:.4f} (fractional shares)")
except Exception as e:
    print(f"Error getting price: {e}")
    exit(1)

# Step 5: Execute Trade (LIVE PAPER TRADE!)
print("\n🚀 STEP 5: Executing Paper Trade")
print("-" * 70)

try:
    # Place market order
    order = api.submit_order(
        symbol=best_etf,
        notional=6.00,  # $6 worth
        side="buy",
        type="market",
        time_in_force="day",
    )

    print("✅ ORDER PLACED!")
    print(f"Order ID: {order.id}")
    print(f"Symbol: {order.symbol}")
    print(f"Amount: ${6.00}")
    print(f"Status: {order.status}")
    print(f"Submitted At: {order.submitted_at}")

except Exception as e:
    print(f"❌ Order Failed: {e}")
    exit(1)

# Step 6: Summary
print("\n" + "=" * 70)
print("✅ PAPER TRADE COMPLETE!")
print("=" * 70)
print("\n📋 TRADE SUMMARY:")
print("   Strategy: Core (Tier 1 - Index ETFs)")
print(f"   Symbol: {best_etf}")
print("   Investment: $6.00")
print("   Method: Technical Momentum Analysis")
print("   Risk: LOW")
print("   Target: 8-12% annual return")
print("\n💡 NEXT STEPS:")
print("   1. Check order status: python3 scripts/check_positions.py")
print("   2. Check Alpaca web dashboard for real-time positions")
print("   3. Review tomorrow's trade at 9:35 AM ET")
print("\n🎯 THIS IS YOUR SYSTEM IN ACTION!")
print("=" * 70)

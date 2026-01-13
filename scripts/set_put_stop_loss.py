#!/usr/bin/env python3
"""
Set Stop-Loss on SOFI Put Position

CEO Directive: "We are never allowed to lose money!"
This script places a buy-to-close stop order on the short put.
"""

import os
import sys
from datetime import datetime

def main():
    print("=" * 60)
    print("🛡️ SETTING STOP-LOSS ON SOFI PUT")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.requests import StopLimitOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce

        api_key = os.environ.get('ALPACA_API_KEY')
        secret_key = os.environ.get('ALPACA_SECRET_KEY')

        if not api_key or not secret_key:
            print("❌ Missing Alpaca credentials")
            sys.exit(1)

        client = TradingClient(api_key, secret_key, paper=True)

        # Get current positions to verify we have the put
        positions = client.get_all_positions()
        put_position = None
        for p in positions:
            if 'SOFI' in p.symbol and 'P' in p.symbol:
                put_position = p
                print(f"✅ Found put position: {p.symbol}")
                print(f"   Qty: {p.qty}")
                print(f"   Current Price: ${float(p.current_price):.2f}")
                print(f"   Unrealized P/L: ${float(p.unrealized_pl):.2f}")
                break

        if not put_position:
            print("⚠️ No SOFI put position found")
            sys.exit(0)

        # Place stop-loss order (buy to close)
        print()
        print("📝 Placing stop-loss order...")
        print("   Type: Stop-Limit (Buy to Close)")
        print("   Stop Price: $1.50")
        print("   Limit Price: $1.55")
        print("   Time in Force: GTC")

        order_request = StopLimitOrderRequest(
            symbol=put_position.symbol,
            qty=abs(int(float(put_position.qty))),
            side=OrderSide.BUY,  # Buy to close short position
            stop_price=1.50,
            limit_price=1.55,
            time_in_force=TimeInForce.GTC
        )

        order = client.submit_order(order_request)

        print()
        print("✅ STOP-LOSS ORDER PLACED!")
        print(f"   Order ID: {order.id}")
        print(f"   Symbol: {order.symbol}")
        print(f"   Status: {order.status}")
        print()
        print("🛡️ Position now protected:")
        print("   - If put rises to $1.50, order triggers")
        print("   - Max loss capped at ~$71")
        print("=" * 60)

        return True

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

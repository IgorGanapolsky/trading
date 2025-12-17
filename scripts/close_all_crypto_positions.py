#!/usr/bin/env python3
"""
Emergency Script: Close ALL Crypto Positions

Per CEO mandate: ZERO crypto in this system.
This script closes any remaining BTCUSD, ETHUSD, SOLUSD positions.
"""
import os
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from alpaca.trading.client import TradingClient
from alpaca.trading.requests import MarketOrderRequest
from alpaca.trading.enums import OrderSide, TimeInForce

def main():
    """Close all crypto positions immediately."""
    api_key = os.getenv("APCA_API_KEY_ID")
    api_secret = os.getenv("APCA_API_SECRET_KEY")
    
    if not api_key or not api_secret:
        print("❌ Missing Alpaca credentials")
        return 1
    
    client = TradingClient(api_key, api_secret, paper=True)
    
    # Get all positions
    positions = client.get_all_positions()
    
    crypto_symbols = ["BTCUSD", "ETHUSD", "SOLUSD", "BTC/USD", "ETH/USD", "SOL/USD"]
    closed = []
    
    for position in positions:
        symbol = position.symbol
        
        # Check if this is a crypto position
        if any(crypto in symbol for crypto in crypto_symbols):
            qty = abs(float(position.qty))
            
            print(f"🔥 CLOSING CRYPTO POSITION: {symbol}")
            print(f"   Quantity: {qty}")
            print(f"   Unrealized P/L: ${position.unrealized_pl}")
            
            try:
                # Close position with market order
                order_data = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL if float(position.qty) > 0 else OrderSide.BUY,
                    time_in_force=TimeInForce.GTC
                )
                
                order = client.submit_order(order_data=order_data)
                print(f"   ✅ Order submitted: {order.id}")
                closed.append(symbol)
                
            except Exception as e:
                print(f"   ❌ Failed to close {symbol}: {e}")
    
    if closed:
        print(f"\n✅ Successfully closed {len(closed)} crypto positions:")
        for symbol in closed:
            print(f"   - {symbol}")
    else:
        print("\n✅ No crypto positions found (already clean)")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

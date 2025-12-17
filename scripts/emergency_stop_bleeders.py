#!/usr/bin/env python3
"""
EMERGENCY: Stop the bleeding positions.

Crypto and REITs are dragging us down while options are making money.
This script identifies and optionally closes bleeding positions.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BLEEDERS = {
    # Crypto - volatile, unpredictable, LOSING
    "ETHUSD": "Crypto - down 6.70%",
    "SOLUSD": "Crypto - down 3.44%", 
    "BTCUSD": "Crypto - down 2.64%",
    # REITs - all losing
    "DLR": "REIT - down 2.53%",
    "EQIX": "REIT - down 1.15%",
    "PSA": "REIT - down 1.05%",
    "CCI": "REIT - down 0.45%",
    "AMT": "REIT - down 0.13%",
}

def main():
    from alpaca.trading.client import TradingClient
    
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    
    if not api_key or not secret_key:
        print("❌ No Alpaca credentials")
        return 1
    
    client = TradingClient(api_key, secret_key, paper=True)
    positions = client.get_all_positions()
    
    print("=" * 60)
    print("🔴 BLEEDING POSITIONS ANALYSIS")
    print("=" * 60)
    
    total_bleed = 0
    for pos in positions:
        symbol = pos.symbol
        if symbol in BLEEDERS:
            unrealized_pl = float(pos.unrealized_pl)
            unrealized_pct = float(pos.unrealized_plpc) * 100
            market_value = float(pos.market_value)
            
            total_bleed += unrealized_pl
            
            print(f"\n🔴 {symbol}: {BLEEDERS[symbol]}")
            print(f"   Market Value: ${market_value:,.2f}")
            print(f"   Unrealized P/L: ${unrealized_pl:,.2f} ({unrealized_pct:.2f}%)")
    
    print(f"\n{'=' * 60}")
    print(f"💀 TOTAL BLEEDING: ${total_bleed:,.2f}")
    print(f"{'=' * 60}")
    
    # Check for --close flag
    if "--close" in sys.argv:
        print("\n⚠️ CLOSING BLEEDING POSITIONS...")
        for pos in positions:
            if pos.symbol in BLEEDERS:
                try:
                    client.close_position(pos.symbol)
                    print(f"   ✅ Closed {pos.symbol}")
                except Exception as e:
                    print(f"   ❌ Failed to close {pos.symbol}: {e}")
    else:
        print("\n💡 Run with --close to close these positions")
    
    return 0

if __name__ == "__main__":
    sys.exit(main())

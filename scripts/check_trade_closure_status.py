#!/usr/bin/env python3
"""
Check Trade Closure Status

Verifies that positions are being properly closed and recorded.
"""

import json
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.append(str(Path(__file__).parent.parent))

from src.core.alpaca_trader import AlpacaTrader

load_dotenv()


def main():
    print("=" * 80)
    print("🔍 TRADE CLOSURE STATUS CHECK")
    print("=" * 80)
    print()

    try:
        trader = AlpacaTrader(paper=True)

        # Get current positions
        positions = trader.get_positions()

        # Load system state
        state_file = Path("data/system_state.json")
        if state_file.exists():
            with open(state_file) as f:
                state = json.load(f)

            open_positions_state = state.get("performance", {}).get("open_positions", [])
            closed_trades = state.get("performance", {}).get("closed_trades", [])
            win_rate = state.get("performance", {}).get("win_rate", 0.0)

            print("📊 SYSTEM STATE:")
            print(f"   Open Positions (State): {len(open_positions_state)}")
            print(f"   Closed Trades: {len(closed_trades)}")
            print(f"   Win Rate: {win_rate:.1f}%")
            print()
        else:
            print("⚠️  System state file not found")
            open_positions_state = []
            closed_trades = []
            win_rate = 0.0

        # Get actual positions from Alpaca
        print("📈 ALPACA POSITIONS:")
        print(f"   Current Positions: {len(positions)}")
        print()

        if positions:
            print("   Position Details:")
            for pos in positions:
                symbol = pos.get("symbol", "UNKNOWN")
                qty = float(pos.get("qty", 0))
                current_price = float(pos.get("current_price", 0))
                market_value = qty * current_price
                unrealized_pl = float(pos.get("unrealized_pl", 0))
                unrealized_plpc = float(pos.get("unrealized_plpc", 0))

                print(f"   - {symbol}:")
                print(f"     Quantity: {qty:.4f} shares")
                print(f"     Current Price: ${current_price:.2f}")
                print(f"     Market Value: ${market_value:.2f}")
                print(f"     Unrealized P/L: ${unrealized_pl:.2f} ({unrealized_plpc * 100:.2f}%)")

                # Check if should be closed
                if unrealized_plpc >= 0.10:  # 10% take-profit
                    print("     ⚠️  SHOULD CLOSE: Take-profit target reached!")
                elif unrealized_plpc <= -0.03:  # 3% stop-loss
                    print("     ⚠️  SHOULD CLOSE: Stop-loss triggered!")
                print()
        else:
            print("   No open positions")
            print()

        # Check for discrepancies
        print("🔍 DISCREPANCY CHECK:")
        if len(positions) != len(open_positions_state):
            print(
                f"   ⚠️  MISMATCH: Alpaca has {len(positions)} positions, state has {len(open_positions_state)}"
            )
        else:
            print("   ✅ Position counts match")

        if len(closed_trades) == 0:
            print("   ⚠️  NO CLOSED TRADES: Win rate cannot be calculated")
            print("   💡 Action: Need to close positions to get win rate data")
        else:
            print(f"   ✅ Closed trades recorded: {len(closed_trades)}")

        print()
        print("=" * 80)

        # Recommendations
        print()
        print("💡 RECOMMENDATIONS:")
        if len(closed_trades) == 0:
            print("   1. Verify position management is executing")
            print("   2. Check if take-profit/stop-loss rules are triggering")
            print("   3. Ensure record_closed_trade() is being called")
        else:
            print(f"   ✅ System is tracking closed trades (Win rate: {win_rate:.1f}%)")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()

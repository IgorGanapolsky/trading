#!/usr/bin/env python3
"""
Emergency Stop-Loss Implementation

CTO/CFO Decision: Implement stop-loss on losing positions to limit downside.
"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from alpaca.tradeapi import REST

from scripts.state_manager import StateManager


def implement_stop_loss():
    """Implement stop-loss orders on losing positions."""
    print("=" * 80)
    print("🚨 EMERGENCY STOP-LOSS IMPLEMENTATION")
    print("=" * 80)

    # Load state
    state_manager = StateManager()
    state = state_manager.state

    # Get positions
    positions = state.get("performance", {}).get("open_positions", [])

    if not positions:
        print("No open positions found.")
        return

    # Initialize Alpaca
    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    base_url = os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")

    if not api_key or not secret_key:
        print("ERROR: Alpaca credentials not found")
        return

    api = REST(api_key, secret_key, base_url, api_version="v2")

    print(f"\n📊 Analyzing {len(positions)} positions...\n")

    actions_taken = []

    for pos in positions:
        symbol = pos.get("symbol", "")
        unrealized_pl_pct = pos.get("unrealized_pl_pct", 0)
        quantity = pos.get("quantity", 0)
        entry_price = pos.get("entry_price", 0)
        current_price = pos.get("current_price", 0)

        print(f"{symbol}:")
        print(f"  Entry: ${entry_price:.2f}, Current: ${current_price:.2f}")
        print(f"  Unrealized P/L: {unrealized_pl_pct:+.2f}%")

        # Decision logic
        if unrealized_pl_pct < -5:
            # Critical loss - immediate stop-loss at -5%
            stop_price = entry_price * 0.95
            print(f"  🚨 CRITICAL: Loss exceeds 5% - Setting stop-loss at ${stop_price:.2f}")

            try:
                # Place stop-loss order
                order = api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side="sell",
                    type="stop",
                    stop_price=stop_price,
                    time_in_force="gtc",
                )
                actions_taken.append(
                    {
                        "symbol": symbol,
                        "action": "stop_loss_placed",
                        "stop_price": stop_price,
                        "order_id": order.id,
                    }
                )
                print(f"  ✅ Stop-loss order placed: {order.id}")
            except Exception as e:
                print(f"  ❌ Failed to place stop-loss: {e}")
                actions_taken.append(
                    {
                        "symbol": symbol,
                        "action": "stop_loss_failed",
                        "error": str(e),
                    }
                )

        elif unrealized_pl_pct < -2:
            # Warning loss - set stop-loss at -2%
            stop_price = entry_price * 0.98
            print(f"  ⚠️  WARNING: Loss exceeds 2% - Setting stop-loss at ${stop_price:.2f}")

            try:
                order = api.submit_order(
                    symbol=symbol,
                    qty=quantity,
                    side="sell",
                    type="stop",
                    stop_price=stop_price,
                    time_in_force="gtc",
                )
                actions_taken.append(
                    {
                        "symbol": symbol,
                        "action": "stop_loss_placed",
                        "stop_price": stop_price,
                        "order_id": order.id,
                    }
                )
                print(f"  ✅ Stop-loss order placed: {order.id}")
            except Exception as e:
                print(f"  ❌ Failed to place stop-loss: {e}")

        else:
            print("  ✅ Position within acceptable range")

        print()

    print("=" * 80)
    print("📋 SUMMARY")
    print("=" * 80)
    print(f"Actions taken: {len([a for a in actions_taken if 'placed' in a.get('action', '')])}")

    for action in actions_taken:
        if "placed" in action.get("action", ""):
            print(f"  ✅ {action['symbol']}: Stop-loss at ${action['stop_price']:.2f}")

    return actions_taken


if __name__ == "__main__":
    implement_stop_loss()

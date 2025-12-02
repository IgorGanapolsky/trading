#!/usr/bin/env python3
"""
Update Win Rate Tracking - Migrate existing data to new structure

This script migrates the existing system_state.json to the new structure
that separates closed trades from open positions.
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from dotenv import load_dotenv

load_dotenv()

import alpaca_trade_api as tradeapi

# Connect to Alpaca
api = tradeapi.REST(
    os.getenv("ALPACA_API_KEY"),
    os.getenv("ALPACA_SECRET_KEY"),
    "https://paper-api.alpaca.markets",
    api_version="v2",
)


def main():
    """Migrate system_state.json to new win rate tracking structure"""
    state_file = Path("data/system_state.json")

    if not state_file.exists():
        print("❌ system_state.json not found")
        return

    # Load current state
    with open(state_file) as f:
        state = json.load(f)

    # Initialize new structure if needed
    if "closed_trades" not in state["performance"]:
        state["performance"]["closed_trades"] = []
    if "open_positions" not in state["performance"]:
        state["performance"]["open_positions"] = []

    # Get current positions from Alpaca
    positions = api.list_positions()

    print("📊 Updating Win Rate Tracking")
    print("=" * 70)

    # Update open positions
    open_positions_data = []
    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        entry_price = float(pos.avg_entry_price)
        current_price = float(pos.current_price)
        unrealized_pl = float(pos.unrealized_pl)
        unrealized_plpc = float(pos.unrealized_plpc) * 100

        # Find matching open position in state
        matching_pos = None
        for open_pos in state["performance"]["open_positions"]:
            if open_pos.get("symbol") == symbol:
                matching_pos = open_pos
                break

        if not matching_pos:
            # New position - add to open positions
            matching_pos = {
                "symbol": symbol,
                "tier": "unknown",  # Will be updated on next trade
                "amount": qty * entry_price,
                "order_id": None,
                "entry_date": datetime.now().isoformat(),
                "entry_price": entry_price,
            }
            state["performance"]["open_positions"].append(matching_pos)

        # Update with current data
        matching_pos["current_price"] = current_price
        matching_pos["quantity"] = qty
        matching_pos["unrealized_pl"] = unrealized_pl
        matching_pos["unrealized_pl_pct"] = unrealized_plpc
        matching_pos["last_updated"] = datetime.now().isoformat()

        open_positions_data.append(
            {
                "symbol": symbol,
                "qty": qty,
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pl": unrealized_pl,
                "unrealized_pl_pct": unrealized_plpc,
            }
        )

    print(f"✅ Updated {len(open_positions_data)} open positions")
    for pos in open_positions_data:
        status = "📈" if pos["unrealized_pl"] > 0 else "📉"
        print(
            f"   {status} {pos['symbol']}: {pos['unrealized_pl']:+.2f} ({pos['unrealized_pl_pct']:+.2f}%)"
        )

    # Recalculate win rate based on closed trades only
    closed_trades = state["performance"]["closed_trades"]
    winning_trades = sum(1 for t in closed_trades if t.get("pl", 0) > 0)
    losing_trades = sum(1 for t in closed_trades if t.get("pl", 0) < 0)

    state["performance"]["winning_trades"] = winning_trades
    state["performance"]["losing_trades"] = losing_trades

    if len(closed_trades) > 0:
        state["performance"]["win_rate"] = (winning_trades / len(closed_trades)) * 100
    else:
        state["performance"]["win_rate"] = 0.0

    print()
    print("📊 Win Rate Statistics:")
    print(f"   Closed Trades: {len(closed_trades)}")
    print(f"   Winning Trades: {winning_trades}")
    print(f"   Losing Trades: {losing_trades}")
    print(f"   Win Rate: {state['performance']['win_rate']:.1f}%")
    print(f"   Open Positions: {len(state['performance']['open_positions'])}")

    # Update metadata
    state["meta"]["last_updated"] = datetime.now().isoformat()
    state["meta"]["last_audit"] = datetime.now().isoformat()
    state["meta"]["audit_notes"] = (
        f"Day {state['challenge']['current_day']} - Win rate tracking updated (separated closed vs open)"
    )

    # Save updated state
    with open(state_file, "w") as f:
        json.dump(state, f, indent=2)

    print()
    print("✅ Win rate tracking updated successfully!")
    print("=" * 70)


if __name__ == "__main__":
    main()

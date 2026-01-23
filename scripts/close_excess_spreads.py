#!/usr/bin/env python3
"""
Close Excess Spreads - DYNAMIC position closure.

CRITICAL FIX Jan 23, 2026: Previous version had HARDCODED positions which caused:
1. Assuming wrong position direction (long vs short)
2. Creating orphan positions when some orders failed
3. Daily losses from malformed spread structures

This version reads ACTUAL positions from Alpaca and closes correctly.

Per CLAUDE.md:
- "Position limit: 1 iron condor at a time (4 legs max)"
- If more than 4 option positions exist, close excess
"""

import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from src.core.alpaca_trader import AlpacaTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Maximum positions allowed (1 iron condor = 4 legs)
MAX_POSITIONS = 4


def get_option_positions(trader) -> list:
    """Get all SPY option positions from Alpaca."""
    positions = trader.trading_client.get_all_positions()

    # Filter for SPY options only (symbol length > 5 for options)
    option_positions = [
        p for p in positions
        if p.symbol.startswith("SPY") and len(p.symbol) > 5
    ]

    return option_positions


def close_position(trader, position) -> bool:
    """
    Close a single position correctly based on its actual direction.

    CRITICAL: Check qty sign to determine if LONG or SHORT:
    - qty > 0 = LONG position = SELL to close
    - qty < 0 = SHORT position = BUY to close
    """
    symbol = position.symbol
    qty = int(float(position.qty))

    # Determine correct side to close
    if qty > 0:
        # LONG position: SELL to close
        side = OrderSide.SELL
        close_qty = qty
        direction = "LONG"
    else:
        # SHORT position: BUY to close
        side = OrderSide.BUY
        close_qty = abs(qty)
        direction = "SHORT"

    logger.info(f"Closing {direction} position: {side.name} {close_qty} {symbol}")

    try:
        order_req = MarketOrderRequest(
            symbol=symbol,
            qty=close_qty,
            side=side,
            time_in_force=TimeInForce.DAY,
        )
        order = trader.trading_client.submit_order(order_req)

        if order:
            logger.info(f"  ✅ Order submitted: {order.id}")
            return True
        else:
            logger.error(f"  ❌ Order failed - no order returned")
            return False

    except Exception as e:
        logger.error(f"  ❌ Error closing {symbol}: {e}")
        return False


def main():
    """Close excess spreads to comply with CLAUDE.md position limit."""
    logger.info("=" * 60)
    logger.info("CLOSE EXCESS SPREADS - DYNAMIC (Jan 23 Fix)")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Max positions allowed: {MAX_POSITIONS}")
    logger.info("")

    trader = AlpacaTrader(paper=True)
    clock = trader.trading_client.get_clock()

    if not clock.is_open:
        logger.warning("Market is CLOSED. Cannot close positions now.")
        logger.info(f"Next open: {clock.next_open}")
        return 0

    logger.info("Market is OPEN - checking positions")
    logger.info("")

    # Get actual positions from Alpaca
    option_positions = get_option_positions(trader)

    logger.info(f"Found {len(option_positions)} SPY option positions:")
    for p in option_positions:
        qty = int(float(p.qty))
        direction = "LONG" if qty > 0 else "SHORT"
        pnl = float(p.unrealized_pl)
        logger.info(f"  - {p.symbol}: {direction} {abs(qty)} (P/L: ${pnl:.2f})")
    logger.info("")

    # Check if we're over the limit
    if len(option_positions) <= MAX_POSITIONS:
        logger.info(f"✅ Position count ({len(option_positions)}) within limit ({MAX_POSITIONS})")
        logger.info("No action needed.")
        return 0

    # Need to close excess positions
    excess = len(option_positions) - MAX_POSITIONS
    logger.warning(f"⚠️ Over position limit by {excess} positions")
    logger.info("")

    # Sort by P/L to close the worst performing first
    # CRITICAL: Close positions with WORST P/L first to minimize damage
    sorted_positions = sorted(option_positions, key=lambda p: float(p.unrealized_pl))

    logger.info("Positions sorted by P/L (worst first):")
    for i, p in enumerate(sorted_positions):
        marker = "← CLOSE" if i < excess else "← KEEP"
        pnl = float(p.unrealized_pl)
        logger.info(f"  {i+1}. {p.symbol}: P/L ${pnl:.2f} {marker}")
    logger.info("")

    # Close excess positions (worst P/L first)
    positions_to_close = sorted_positions[:excess]

    logger.info(f"Closing {len(positions_to_close)} positions:")
    closed_count = 0
    errors = []

    for pos in positions_to_close:
        if close_position(trader, pos):
            closed_count += 1
        else:
            errors.append(pos.symbol)

    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed_count}/{len(positions_to_close)}")

    if errors:
        logger.error(f"Errors: {errors}")
        logger.error("⚠️ Some positions could not be closed!")
        return 1

    logger.info("✅ Now compliant with CLAUDE.md position limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())

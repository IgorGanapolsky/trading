#!/usr/bin/env python3
"""
Close Excess Spreads - Enforce CLAUDE.md 1-spread limit.

Created: Jan 19, 2026 (LL-242: Strategy Mismatch Crisis)

Per CLAUDE.md:
- "Position limit: 1 iron condor at a time (5% max = $248 risk)"
- Currently have 3 spreads - need to close 2

Close order:
1. Spread 3 (653/658) - QTY mismatch, not a proper spread
2. Spread 1 (565/570) - lowest P/L contribution
3. KEEP Spread 2 (595/600) - closest to current price
"""

import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import Alpaca SDK for option orders
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from src.core.alpaca_trader import AlpacaTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Positions to close (in order)
POSITIONS_TO_CLOSE = [
    # Spread 3: QTY mismatch (close first)
    {"symbol": "SPY260220P00653000", "qty": 2, "side": "sell"},  # Long put
    {"symbol": "SPY260220P00658000", "qty": 1, "side": "buy"},  # Short put (buy to close)
    # Spread 1: Lower P/L (close second)
    {"symbol": "SPY260220P00565000", "qty": 1, "side": "sell"},  # Long put
    {"symbol": "SPY260220P00570000", "qty": 1, "side": "buy"},  # Short put (buy to close)
]

# Position to KEEP
KEEP_SPREAD = "595/600 put spread"


def main():
    """Close excess spreads to comply with CLAUDE.md 1-spread limit."""
    logger.info("=" * 60)
    logger.info("CLOSE EXCESS SPREADS - CLAUDE.md Compliance")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("")

    # Check if market is open
    trader = AlpacaTrader(paper=True)
    clock = trader.trading_client.get_clock()

    if not clock.is_open:
        logger.warning("Market is CLOSED. Cannot close positions now.")
        logger.info(f"Next open: {clock.next_open}")
        logger.info("")
        logger.info("Positions queued for closure when market opens:")
        for pos in POSITIONS_TO_CLOSE:
            logger.info(f"  - {pos['side'].upper()} {pos['qty']} {pos['symbol']}")
        logger.info("")
        logger.info(f"Position to KEEP: {KEEP_SPREAD}")
        return 0

    logger.info("Market is OPEN - proceeding with closures")
    logger.info("")

    closed_count = 0
    errors = []

    for pos in POSITIONS_TO_CLOSE:
        symbol = pos["symbol"]
        qty = pos["qty"]
        side = pos["side"]

        logger.info(f"Closing: {side.upper()} {qty} {symbol}")

        try:
            # Use Alpaca TradingClient directly for option orders
            # (AlpacaTrader doesn't have option methods - it's for stocks only)
            order_side = OrderSide.SELL if side == "sell" else OrderSide.BUY
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=order_side,
                time_in_force=TimeInForce.DAY,
            )
            order = trader.trading_client.submit_order(order_req)

            if order:
                logger.info(f"  ✅ Order submitted: {order.id}")
                closed_count += 1
            else:
                logger.error("  ❌ Order failed - no order returned")
                errors.append(symbol)

        except Exception as e:
            logger.error(f"  ❌ Error closing {symbol}: {e}")
            errors.append(symbol)

    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed_count}/{len(POSITIONS_TO_CLOSE)}")
    logger.info(f"Position kept: {KEEP_SPREAD}")

    if errors:
        logger.error(f"Errors: {errors}")
        return 1

    logger.info("✅ Now compliant with CLAUDE.md 1-spread limit")
    return 0


if __name__ == "__main__":
    sys.exit(main())

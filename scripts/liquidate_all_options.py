#!/usr/bin/env python3
"""
EMERGENCY: Liquidate ALL Options Positions

Created: Jan 23, 2026 - To fix malformed spread positions causing daily losses.

This script closes ALL SPY option positions to start fresh.
Use when positions are malformed and causing consistent losses.

Usage:
    python3 scripts/liquidate_all_options.py --dry-run  # Test first
    python3 scripts/liquidate_all_options.py            # Execute
"""

import argparse
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


def main():
    parser = argparse.ArgumentParser(description="Liquidate all options positions")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be closed without executing")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("EMERGENCY LIQUIDATION - Close ALL Options")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    logger.info("")

    trader = AlpacaTrader(paper=True)

    # Check market status
    clock = trader.trading_client.get_clock()
    if not clock.is_open:
        logger.warning("⚠️ Market is CLOSED")
        logger.info(f"Next open: {clock.next_open}")
        if not args.dry_run:
            logger.error("Cannot execute liquidation while market is closed")
            return 1

    # Get all positions
    positions = trader.trading_client.get_all_positions()

    # Filter for SPY options
    option_positions = [
        p for p in positions
        if p.symbol.startswith("SPY") and len(p.symbol) > 5
    ]

    if not option_positions:
        logger.info("✅ No option positions to close")
        return 0

    logger.info(f"Found {len(option_positions)} option positions:")
    total_pnl = 0
    for p in option_positions:
        qty = int(float(p.qty))
        direction = "LONG" if qty > 0 else "SHORT"
        pnl = float(p.unrealized_pl)
        total_pnl += pnl
        logger.info(f"  - {p.symbol}: {direction} {abs(qty)} @ ${float(p.avg_entry_price):.2f} (P/L: ${pnl:.2f})")

    logger.info("")
    logger.info(f"Total unrealized P/L: ${total_pnl:.2f}")
    logger.info("")

    if args.dry_run:
        logger.info("DRY RUN - No orders will be submitted")
        logger.info("")
        logger.info("Would close:")
        for p in option_positions:
            qty = int(float(p.qty))
            if qty > 0:
                logger.info(f"  SELL {abs(qty)} {p.symbol}")
            else:
                logger.info(f"  BUY {abs(qty)} {p.symbol}")
        return 0

    # Execute liquidation
    logger.info("EXECUTING LIQUIDATION...")
    closed = 0
    errors = []

    for p in option_positions:
        symbol = p.symbol
        qty = int(float(p.qty))

        # Determine correct side to close
        if qty > 0:
            side = OrderSide.SELL
            close_qty = qty
        else:
            side = OrderSide.BUY
            close_qty = abs(qty)

        logger.info(f"Closing: {side.name} {close_qty} {symbol}")

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
                closed += 1
            else:
                logger.error(f"  ❌ Order failed")
                errors.append(symbol)

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            errors.append(symbol)

    logger.info("")
    logger.info("=" * 60)
    logger.info("LIQUIDATION SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Positions closed: {closed}/{len(option_positions)}")
    logger.info(f"Realized P/L: ~${total_pnl:.2f}")

    if errors:
        logger.error(f"Failed to close: {errors}")
        return 1

    logger.info("✅ All positions liquidated - ready for fresh start")
    return 0


if __name__ == "__main__":
    sys.exit(main())

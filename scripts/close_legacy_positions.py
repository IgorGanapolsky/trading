#!/usr/bin/env python3
"""
Close Legacy Positions - Jan 21, 2026

Problem: Trading blocked because of legacy positions from before Jan 19 strategy change:
1. SOFI260213P00032000 - Short put (violates SPY-only mandate)
2. SPY shares - Not part of iron condor strategy

Solution: Close both to free capital for proper SPY iron condors.

Usage:
    python scripts/close_legacy_positions.py --dry-run   # Preview only
    python scripts/close_legacy_positions.py             # Execute closures
"""

import argparse
import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Close legacy positions to unblock trading")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("CLOSE LEGACY POSITIONS - Unblock Trading")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE EXECUTION'}")
    logger.info("")

    # Import here to fail gracefully if alpaca not available
    try:
        from src.core.alpaca_trader import AlpacaTrader
    except ImportError as e:
        logger.error(f"Cannot import AlpacaTrader: {e}")
        logger.info("This script must run in GitHub Actions with alpaca-py installed")
        return 1

    # Initialize trader
    trader = AlpacaTrader(paper=True)

    # Check market status
    clock = trader.trading_client.get_clock()
    if not clock.is_open:
        logger.warning(f"Market is CLOSED. Next open: {clock.next_open}")
        if not args.dry_run:
            logger.info("Cannot execute - market closed. Run during market hours.")
            return 1

    # Get current positions
    positions = trader.trading_client.get_all_positions()
    logger.info(f"Found {len(positions)} positions:")

    legacy_positions = []
    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        market_value = float(pos.market_value)
        unrealized_pl = float(pos.unrealized_pl)

        logger.info(f"  {symbol}: qty={qty}, value=${market_value:.2f}, P/L=${unrealized_pl:.2f}")

        # Check if legacy (not SPY option spread)
        if "SOFI" in symbol or (symbol == "SPY" and not symbol.startswith("SPY2")):
            legacy_positions.append({
                "symbol": symbol,
                "qty": qty,
                "side": "buy" if qty < 0 else "sell",  # Buy to close short, sell to close long
                "unrealized_pl": unrealized_pl
            })

    logger.info("")

    if not legacy_positions:
        logger.info("✅ No legacy positions found - trading should be unblocked")
        return 0

    logger.info(f"Legacy positions to close: {len(legacy_positions)}")
    for lp in legacy_positions:
        logger.info(f"  {lp['side'].upper()} {abs(lp['qty'])} {lp['symbol']} (P/L: ${lp['unrealized_pl']:.2f})")

    if args.dry_run:
        logger.info("")
        logger.info("DRY RUN - No orders submitted")
        logger.info("Run without --dry-run to execute closures")
        return 0

    # Execute closures
    logger.info("")
    logger.info("Executing closures...")

    closed = 0
    errors = []

    for lp in legacy_positions:
        symbol = lp["symbol"]
        qty = abs(lp["qty"])
        side = lp["side"]

        logger.info(f"Closing {symbol}...")

        try:
            if symbol == "SPY" and not symbol.startswith("SPY2"):
                # Close stock position
                order = trader.trading_client.close_position(symbol)
            elif side == "buy":
                # Buy to close short option
                order = trader.buy_option(symbol, int(qty))
            else:
                # Sell to close long option
                order = trader.sell_option(symbol, int(qty))

            if order:
                logger.info(f"  ✅ Order submitted: {order.id if hasattr(order, 'id') else 'success'}")
                closed += 1
            else:
                logger.error("  ❌ No order returned")
                errors.append(symbol)

        except Exception as e:
            logger.error(f"  ❌ Error: {e}")
            errors.append(symbol)

    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Closed: {closed}/{len(legacy_positions)}")

    if errors:
        logger.error(f"Errors: {errors}")
        return 1

    logger.info("✅ Legacy positions closed - trading unblocked!")
    logger.info("New SPY iron condors can now be executed")
    return 0


if __name__ == "__main__":
    sys.exit(main())

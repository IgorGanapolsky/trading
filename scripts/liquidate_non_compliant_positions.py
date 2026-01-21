#!/usr/bin/env python3
"""
Liquidate Non-Compliant Positions - Enforce CLAUDE.md Strategy

Created: Jan 21, 2026 (LL-272: Strategy Violation Crisis)

Per CLAUDE.md:
- "Primary strategy: IRON CONDORS on SPY ONLY"
- "No individual stocks. The $100K success was SPY. The $5K failure was SOFI."

This script liquidates:
1. ALL stock positions (SPY shares included - iron condors use options only)
2. ALL non-SPY options (SOFI, etc.)

KEEP: SPY OPTIONS (put spreads, call spreads, iron condors)
"""

import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main(dry_run: bool = False):
    """Liquidate all non-compliant positions."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
    except ImportError:
        logger.error("alpaca-py not installed")
        sys.exit(1)

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=paper)

    logger.info("=" * 70)
    logger.info("LIQUIDATE NON-COMPLIANT POSITIONS - CLAUDE.md Enforcement")
    logger.info("=" * 70)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Dry run: {dry_run}")
    logger.info("")

    # Get all positions
    positions = client.get_all_positions()

    if not positions:
        logger.info("No positions found.")
        return 0

    to_liquidate = []
    to_keep = []

    for pos in positions:
        symbol = pos.symbol
        qty = float(pos.qty)
        market_value = float(pos.market_value)
        asset_class = str(pos.asset_class).lower() if pos.asset_class else "unknown"

        # Determine if position is compliant
        is_stock = asset_class == "us_equity" or (
            len(symbol) <= 5 and not any(c.isdigit() for c in symbol)
        )
        is_spy_option = symbol.startswith("SPY") and len(symbol) > 5

        if is_stock:
            # ALL stocks are non-compliant (iron condors only use options)
            to_liquidate.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "value": market_value,
                    "reason": "STOCK (iron condors use options only)",
                }
            )
        elif is_spy_option:
            # SPY options are compliant
            to_keep.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "value": market_value,
                    "reason": "SPY OPTION (compliant)",
                }
            )
        else:
            # Non-SPY options are non-compliant
            to_liquidate.append(
                {
                    "symbol": symbol,
                    "qty": qty,
                    "value": market_value,
                    "reason": "NON-SPY OPTION (SPY only mandate)",
                }
            )

    # Report
    logger.info("POSITIONS TO KEEP (COMPLIANT):")
    if to_keep:
        for pos in to_keep:
            logger.info(
                f"  ✅ {pos['symbol']}: {pos['qty']} (${pos['value']:.2f}) - {pos['reason']}"
            )
    else:
        logger.info("  (none)")

    logger.info("")
    logger.info("POSITIONS TO LIQUIDATE (NON-COMPLIANT):")
    if to_liquidate:
        for pos in to_liquidate:
            logger.info(
                f"  ❌ {pos['symbol']}: {pos['qty']} (${pos['value']:.2f}) - {pos['reason']}"
            )
    else:
        logger.info("  (none - all positions compliant)")
        return 0

    if dry_run:
        logger.info("")
        logger.info("DRY RUN - No orders submitted")
        logger.info("Run without --dry-run to execute liquidation")
        return 0

    # Check if market is open
    clock = client.get_clock()
    if not clock.is_open:
        logger.warning("")
        logger.warning("⚠️ MARKET IS CLOSED - Cannot liquidate now")
        logger.info(f"Next open: {clock.next_open}")
        logger.info("")
        logger.info("Run this script during market hours to liquidate.")
        return 0

    # Execute liquidation
    logger.info("")
    logger.info("EXECUTING LIQUIDATION...")
    logger.info("")

    success_count = 0
    error_count = 0

    for pos in to_liquidate:
        symbol = pos["symbol"]
        qty = abs(pos["qty"])  # Ensure positive for sell order

        logger.info(f"Selling {qty} {symbol}...")

        try:
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=OrderSide.SELL,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(order_req)
            logger.info(f"  ✅ Order submitted: {order.id}")
            success_count += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to sell {symbol}: {e}")
            error_count += 1

    logger.info("")
    logger.info("=" * 70)
    logger.info("LIQUIDATION SUMMARY")
    logger.info("=" * 70)
    logger.info(f"Positions liquidated: {success_count}")
    logger.info(f"Errors: {error_count}")
    logger.info(f"Positions kept: {len(to_keep)}")

    if error_count > 0:
        logger.error("Some liquidations failed - manual intervention may be required")
        return 1

    logger.info("")
    logger.info("✅ All non-compliant positions liquidated")
    logger.info("   System now compliant with CLAUDE.md iron condor strategy")
    return 0


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Liquidate non-compliant positions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    sys.exit(main(dry_run=args.dry_run))

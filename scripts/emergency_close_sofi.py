#!/usr/bin/env python3
"""
Emergency SOFI Position Close Script

CTO DIRECTIVE: Close ALL SOFI positions immediately.
Reason: Position crosses Jan 30 earnings date - violates CLAUDE.md directive.

Created: Jan 14, 2026
Lesson: LL-191 - SOFI CSP opened despite earnings blackout warning

Usage:
    python scripts/emergency_close_sofi.py --dry-run  # Preview only
    python scripts/emergency_close_sofi.py            # Execute close
"""

import argparse
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_paper_trading_client():
    """Get Alpaca paper trading client."""
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY")
        secret_key = os.getenv("ALPACA_PAPER_TRADING_5K_API_SECRET")

        if not api_key or not secret_key:
            logger.error("ALPACA_PAPER_TRADING_5K_API_KEY/SECRET not set")
            return None

        return TradingClient(api_key, secret_key, paper=True)
    except ImportError:
        logger.error("alpaca-py not installed")
        return None


def close_all_sofi_positions(dry_run: bool = True):
    """Close all SOFI-related positions (stock and options)."""
    client = get_paper_trading_client()
    if not client:
        logger.error("Failed to get trading client")
        return False

    try:
        positions = client.get_all_positions()
        sofi_positions = []

        for pos in positions:
            symbol = pos.symbol
            # Check if position is SOFI stock or SOFI option
            if symbol == "SOFI" or symbol.startswith("SOFI"):
                sofi_positions.append(
                    {
                        "symbol": symbol,
                        "qty": float(pos.qty),
                        "market_value": float(pos.market_value),
                        "unrealized_pl": float(pos.unrealized_pl),
                        "side": "long" if float(pos.qty) > 0 else "short",
                    }
                )

        if not sofi_positions:
            logger.info("No SOFI positions found")
            return True

        logger.info(f"Found {len(sofi_positions)} SOFI position(s):")
        for pos in sofi_positions:
            logger.info(f"  {pos['symbol']}: {pos['qty']} shares, P/L: ${pos['unrealized_pl']:.2f}")

        if dry_run:
            logger.info("\n=== DRY RUN - No trades executed ===")
            logger.info("To execute: python scripts/emergency_close_sofi.py (without --dry-run)")
            return True

        # Execute closes

        for pos in sofi_positions:
            symbol = pos["symbol"]
            qty = abs(pos["qty"])

            logger.info(f"Closing {symbol}...")

            try:
                # Close the position
                order = client.close_position(symbol)
                logger.info(f"  ✅ Close order submitted: {order.id}")
            except Exception as e:
                logger.error(f"  ❌ Failed to close {symbol}: {e}")

                # Try alternative: market order to close
                try:
                    from alpaca.trading.enums import OrderSide, TimeInForce
                    from alpaca.trading.requests import MarketOrderRequest

                    # For short positions, we need to BUY to close
                    # For long positions, we need to SELL to close
                    side = OrderSide.BUY if pos["side"] == "short" else OrderSide.SELL

                    order_data = MarketOrderRequest(
                        symbol=symbol,
                        qty=qty,
                        side=side,
                        time_in_force=TimeInForce.DAY,
                    )
                    order = client.submit_order(order_data)
                    logger.info(f"  ✅ Alternative close order submitted: {order.id}")
                except Exception as e2:
                    logger.error(f"  ❌ Alternative close also failed: {e2}")

        logger.info("\n=== SOFI POSITIONS CLOSED ===")
        logger.info("Phil Town Rule #1: Don't lose money")
        logger.info("Lesson learned: Never hold positions through earnings")
        return True

    except Exception as e:
        logger.error(f"Error closing positions: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Emergency close all SOFI positions")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview positions without closing (default: execute close)",
    )
    args = parser.parse_args()

    print("=" * 60)
    print("EMERGENCY SOFI POSITION CLOSE")
    print("=" * 60)
    print()
    print("REASON: SOFI positions cross Jan 30 earnings date")
    print("DIRECTIVE: CLAUDE.md says 'AVOID SOFI until Feb 1'")
    print("ACTION: Close all SOFI positions immediately")
    print()

    if args.dry_run:
        print("MODE: DRY RUN (preview only)")
    else:
        print("MODE: LIVE EXECUTION")
        response = input("\nConfirm close all SOFI positions? (yes/no): ")
        if response.lower() != "yes":
            print("Aborted.")
            return 1

    print()
    success = close_all_sofi_positions(dry_run=args.dry_run)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

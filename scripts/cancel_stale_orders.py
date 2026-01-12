#!/usr/bin/env python3
"""
Cancel Stale Orders - Free Up Buying Power

CEO Directive (Jan 12, 2026): "Why we didn't make money today?"
Root cause: Stale unfilled orders consume buying power, blocking new trades.

This script cancels orders older than MAX_ORDER_AGE_HOURS to free buying power.

Lesson ll_134: "Auto-cancel stale orders older than 1 day"
"""

import logging
import os
import sys
from datetime import datetime, timedelta, timezone

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# Orders older than this are considered stale
MAX_ORDER_AGE_HOURS = 24


def main() -> int:
    """Cancel stale orders to free buying power."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        logger.error("alpaca-py not installed")
        return 1

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        return 1

    client = TradingClient(api_key, secret_key, paper=paper)

    # Get all open orders
    orders = client.get_orders(status="open")

    if not orders:
        logger.info("No open orders found")
        return 0

    logger.info(f"Found {len(orders)} open orders")

    now = datetime.now(timezone.utc)
    stale_threshold = now - timedelta(hours=MAX_ORDER_AGE_HOURS)
    cancelled_count = 0
    freed_collateral = 0.0

    for order in orders:
        created_at = order.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        age_hours = (now - created_at).total_seconds() / 3600

        logger.info(f"\nOrder: {order.symbol}")
        logger.info(f"  ID: {order.id}")
        logger.info(f"  Side: {order.side}")
        logger.info(f"  Type: {order.order_type}")
        logger.info(f"  Qty: {order.qty}")
        logger.info(f"  Limit Price: {order.limit_price}")
        logger.info(f"  Created: {order.created_at}")
        logger.info(f"  Age: {age_hours:.1f} hours")

        if created_at < stale_threshold:
            logger.warning("  ⚠️ STALE ORDER - Cancelling...")
            try:
                client.cancel_order_by_id(order.id)
                cancelled_count += 1

                # Estimate freed collateral for options (strike * 100)
                if len(order.symbol) > 10:  # Options have long symbols
                    # Extract strike from OCC symbol (last 8 digits / 1000)
                    try:
                        strike = int(order.symbol[-8:]) / 1000
                        freed_collateral += strike * 100
                    except ValueError:
                        pass

                logger.info("  ✅ CANCELLED")
            except Exception as e:
                logger.error(f"  ❌ Failed to cancel: {e}")
        else:
            logger.info(f"  ✅ Order is fresh (< {MAX_ORDER_AGE_HOURS}h old)")

    logger.info("\n" + "=" * 60)
    logger.info("STALE ORDER CLEANUP SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Total open orders: {len(orders)}")
    logger.info(f"Stale orders cancelled: {cancelled_count}")
    logger.info(f"Estimated freed collateral: ${freed_collateral:,.2f}")

    if cancelled_count > 0:
        logger.info("\n💡 Buying power should now be available for new trades!")

    return 0


if __name__ == "__main__":
    sys.exit(main())

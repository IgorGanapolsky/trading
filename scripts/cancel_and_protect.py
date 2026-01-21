#!/usr/bin/env python3
"""
Emergency Order Management - Cancel dangerous orders and protect positions.

Usage: python scripts/cancel_and_protect.py [--dry-run]

This script:
1. Cancels any SELL orders on options we're already SHORT (prevents doubling down)
2. Places BUY TO CLOSE limit orders to protect short option positions

Phil Town Rule #1: Don't lose money.
"""

import argparse
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


def get_trading_client():
    """Get Alpaca trading client."""
    try:
        from alpaca.trading.client import TradingClient
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()
        return TradingClient(api_key, secret_key, paper=True)
    except Exception as e:
        logger.error(f"Failed to create trading client: {e}")
        return None


def cancel_dangerous_orders(client, dry_run: bool = False) -> list:
    """
    Cancel SELL orders on options we're already SHORT.

    These orders would increase risk exposure - violation of Rule #1.
    """
    cancelled = []

    try:
        # Get current positions
        positions = client.get_all_positions()
        short_options = {}

        for pos in positions:
            symbol = pos.symbol
            qty = float(pos.qty)
            # Options have symbols > 10 chars (e.g., SOFI260206P00024000)
            if len(symbol) > 10 and qty < 0:
                short_options[symbol] = qty
                logger.info(f"Found SHORT option: {symbol} (qty={qty})")

        if not short_options:
            logger.info("No short option positions found")
            return cancelled

        # Get open orders
        orders = client.get_orders()

        for order in orders:
            symbol = order.symbol
            side = str(order.side).lower()

            # Check if this is a SELL order on a short position
            if symbol in short_options and side == "sell":
                logger.warning(f"🚫 DANGEROUS ORDER FOUND: {order.id}")
                logger.warning(f"   Symbol: {symbol} (already SHORT {short_options[symbol]})")
                logger.warning(f"   Side: {side} - would INCREASE short exposure!")
                logger.warning(f"   Qty: {order.qty}")

                if not dry_run:
                    try:
                        client.cancel_order_by_id(order.id)
                        logger.info(f"✅ CANCELLED dangerous order: {order.id}")
                        cancelled.append(
                            {
                                "order_id": str(order.id),
                                "symbol": symbol,
                                "side": side,
                                "qty": str(order.qty),
                                "reason": "Would increase short exposure",
                            }
                        )
                    except Exception as e:
                        logger.error(f"Failed to cancel order {order.id}: {e}")
                else:
                    logger.info(f"[DRY RUN] Would cancel order: {order.id}")
                    cancelled.append(
                        {
                            "order_id": str(order.id),
                            "symbol": symbol,
                            "action": "WOULD_CANCEL",
                        }
                    )

        return cancelled

    except Exception as e:
        logger.error(f"Error checking orders: {e}")
        return cancelled


def place_protective_orders(client, dry_run: bool = False, max_loss_pct: float = 0.50) -> list:
    """
    Place BUY TO CLOSE limit orders to protect short option positions.

    For short puts, we BUY to close at a price that limits our loss.
    Default: 50% max loss (if we sold at $0.80, buy to close at $1.20 max)
    """
    protected = []

    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import LimitOrderRequest

        # Get current positions
        positions = client.get_all_positions()

        for pos in positions:
            symbol = pos.symbol
            qty = float(pos.qty)

            # Only process short option positions
            if len(symbol) <= 10 or qty >= 0:
                continue

            # Get current market value and cost basis
            market_value = abs(float(pos.market_value))
            cost_basis = abs(float(pos.cost_basis)) if hasattr(pos, "cost_basis") else market_value
            current_price = (
                float(pos.current_price)
                if hasattr(pos, "current_price")
                else market_value / abs(qty) / 100
            )

            # For short options: we sold at some price, now we need to buy back
            # Entry price per share (premium received)
            entry_price = cost_basis / (abs(qty) * 100) if qty != 0 else current_price

            # Max price we're willing to pay to close (limits loss to max_loss_pct)
            max_close_price = entry_price * (1 + max_loss_pct)
            max_close_price = round(max_close_price, 2)

            logger.info(f"📊 Short option: {symbol}")
            logger.info(f"   Qty: {qty} (short)")
            logger.info(f"   Entry (sold at): ~${entry_price:.2f}")
            logger.info(f"   Current price: ~${current_price:.2f}")
            logger.info(f"   Max close price ({max_loss_pct:.0%} loss): ${max_close_price:.2f}")

            # Check if protective order already exists
            existing_orders = client.get_orders()
            already_protected = False
            for order in existing_orders:
                if order.symbol == symbol and str(order.side).lower() == "buy":
                    logger.info(f"   ✅ Already has protective BUY order: {order.id}")
                    already_protected = True
                    break

            if already_protected:
                continue

            if not dry_run:
                try:
                    # Place BUY TO CLOSE limit order
                    order_request = LimitOrderRequest(
                        symbol=symbol,
                        qty=abs(qty),  # Buy back the same amount we're short
                        side=OrderSide.BUY,
                        time_in_force=TimeInForce.GTC,  # Good til cancelled
                        limit_price=max_close_price,
                    )
                    order = client.submit_order(order_request)
                    logger.info(
                        f"   ✅ PROTECTIVE ORDER PLACED: BUY {abs(qty)} @ ${max_close_price}"
                    )
                    logger.info(f"      Order ID: {order.id}")
                    protected.append(
                        {
                            "order_id": str(order.id),
                            "symbol": symbol,
                            "side": "buy",
                            "qty": abs(qty),
                            "limit_price": max_close_price,
                            "purpose": "BUY_TO_CLOSE protection",
                        }
                    )
                except Exception as e:
                    logger.error(f"   ❌ Failed to place protective order: {e}")
            else:
                logger.info(f"   [DRY RUN] Would place BUY order @ ${max_close_price}")
                protected.append(
                    {
                        "symbol": symbol,
                        "action": "WOULD_PLACE_BUY",
                        "limit_price": max_close_price,
                    }
                )

        return protected

    except Exception as e:
        logger.error(f"Error placing protective orders: {e}")
        return protected


def main():
    parser = argparse.ArgumentParser(description="Cancel dangerous orders and protect positions")
    parser.add_argument(
        "--dry-run", action="store_true", help="Show what would be done without executing"
    )
    parser.add_argument(
        "--max-loss",
        type=float,
        default=0.50,
        help="Max loss percentage for protection (default: 0.50 = 50%%)",
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("🛡️  EMERGENCY ORDER MANAGEMENT")
    logger.info(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    if args.dry_run:
        logger.info("🔍 DRY RUN MODE - no changes will be made")
    logger.info("=" * 60)

    client = get_trading_client()
    if not client:
        logger.error("Cannot proceed without trading client")
        sys.exit(1)

    # Step 1: Cancel dangerous SELL orders on short positions
    logger.info("\n📋 STEP 1: Cancelling dangerous orders...")
    cancelled = cancel_dangerous_orders(client, dry_run=args.dry_run)

    # Step 2: Place protective BUY TO CLOSE orders
    logger.info("\n📋 STEP 2: Placing protective orders...")
    protected = place_protective_orders(client, dry_run=args.dry_run, max_loss_pct=args.max_loss)

    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📊 SUMMARY")
    logger.info("=" * 60)
    logger.info(f"Orders cancelled: {len(cancelled)}")
    logger.info(f"Protective orders placed: {len(protected)}")

    if cancelled:
        logger.info("\nCancelled orders:")
        for c in cancelled:
            logger.info(f"  - {c}")

    if protected:
        logger.info("\nProtective orders:")
        for p in protected:
            logger.info(f"  - {p}")

    logger.info("\n✅ Phil Town Rule #1: Don't lose money - ENFORCED")


if __name__ == "__main__":
    main()

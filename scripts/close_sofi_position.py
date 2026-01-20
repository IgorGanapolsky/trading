#!/usr/bin/env python3
"""
Close SOFI Short Put Position - Cut the Loss

Position: SOFI260213P00032000 (short put)
Qty: -1.0 (short)
Current Price: $7.55
Unrealized P/L: -$150

Action: BUY to close the short put position.

Created: Jan 20, 2026
Reason: Exit SOFI position per CLAUDE.md directive - SPY ONLY strategy
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.utils.alpaca_client import get_alpaca_credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Target position to close
TARGET_SYMBOL = "SOFI260213P00032000"


def get_trading_client():
    """Get Alpaca paper trading client using centralized credentials."""
    try:
        from alpaca.trading.client import TradingClient

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error("Alpaca credentials not found. Check environment variables.")
            return None

        return TradingClient(api_key, secret_key, paper=True)
    except ImportError:
        logger.error("alpaca-py not installed. Run: pip install alpaca-py")
        return None
    except Exception as e:
        logger.error(f"Failed to create trading client: {e}")
        return None


def find_position(client, symbol: str):
    """Find a specific position by symbol."""
    try:
        positions = client.get_all_positions()
        for pos in positions:
            if pos.symbol == symbol:
                return pos
        return None
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return None


def close_short_put(dry_run: bool = False):
    """
    Close the SOFI short put position by buying to close.

    Args:
        dry_run: If True, only preview the trade without executing.

    Returns:
        True if successful, False otherwise.
    """
    print("=" * 60)
    print("CLOSE SOFI SHORT PUT POSITION")
    print("=" * 60)
    print()

    client = get_trading_client()
    if not client:
        logger.error("Failed to get Alpaca client")
        return False

    # Find the target position
    position = find_position(client, TARGET_SYMBOL)

    if not position:
        logger.warning(f"Position {TARGET_SYMBOL} not found in account")
        print("\nAvailable positions:")
        try:
            positions = client.get_all_positions()
            if not positions:
                print("  (no open positions)")
            for pos in positions:
                qty = float(pos.qty)
                price = float(pos.current_price)
                pl = float(pos.unrealized_pl)
                print(f"  - {pos.symbol}: {qty} @ ${price:.2f} (P/L: ${pl:.2f})")
        except Exception as e:
            print(f"  Error listing positions: {e}")
        return False

    # Position details
    qty = float(position.qty)
    current_price = float(position.current_price)
    unrealized_pl = float(position.unrealized_pl)
    avg_entry = float(position.avg_entry_price)
    market_value = float(position.market_value)

    print("Position found:")
    print(f"  Symbol: {TARGET_SYMBOL}")
    print(f"  Qty: {qty} (short)")
    print(f"  Avg Entry Price: ${avg_entry:.2f}")
    print(f"  Current Price: ${current_price:.2f}")
    print(f"  Market Value: ${market_value:.2f}")
    print(f"  Unrealized P/L: ${unrealized_pl:.2f}")
    print()

    # Verify it's a short position
    if qty >= 0:
        logger.error(f"Position is not short (qty={qty}). Cannot BUY to close.")
        return False

    # Calculate order quantity (absolute value)
    order_qty = abs(qty)

    print(f"Action: BUY {int(order_qty)} contract(s) to close short position")
    print(f"Order Type: MARKET")
    print(f"Expected Loss: ~${abs(unrealized_pl):.2f}")
    print()

    if dry_run:
        print("=== DRY RUN - No order submitted ===")
        print("To execute: python scripts/close_sofi_position.py")
        return True

    # Submit BUY to close order
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        order_request = MarketOrderRequest(
            symbol=TARGET_SYMBOL,
            qty=order_qty,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )

        logger.info(f"Submitting BUY order for {int(order_qty)} {TARGET_SYMBOL}...")
        order = client.submit_order(order_request)

        print("Order submitted successfully!")
        print(f"  Order ID: {order.id}")
        print(f"  Status: {order.status}")
        print(f"  Side: {order.side}")
        print(f"  Qty: {order.qty}")
        print(f"  Time in Force: {order.time_in_force}")
        print()
        print("Position will be closed when market opens.")
        print("Phil Town Rule #1: Don't lose money. Cut losses early.")

        logger.info(f"Order {order.id} submitted: BUY {order_qty} {TARGET_SYMBOL}")
        return True

    except Exception as e:
        logger.error(f"Order submission failed: {e}")
        print(f"\nOrder failed: {e}")

        # Try alternative method: close_position
        print("\nAttempting alternative close method...")
        try:
            order = client.close_position(TARGET_SYMBOL)
            print(f"Alternative close succeeded! Order ID: {order.id}")
            logger.info(f"Position closed via close_position(): {order.id}")
            return True
        except Exception as e2:
            logger.error(f"Alternative close also failed: {e2}")
            print(f"Alternative close failed: {e2}")
            return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Close SOFI short put position (BUY to close)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview the order without executing"
    )
    args = parser.parse_args()

    success = close_short_put(dry_run=args.dry_run)

    if success:
        print("\nScript completed successfully.")
    else:
        print("\nScript completed with errors.")

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Exit All SOFI Positions - Earnings Blackout Protection

Context:
- SOFI earnings blackout starts Jan 23 (9 days away)
- Per CLAUDE.md strategy: "AVOID SOFI until Feb 1"
- Current positions:
  - SOFI stock: 24.745561475 shares @ $26.85, P/L: +$10.96
  - SOFI260206P00024000 put: -2 contracts @ $0.67, P/L: +$23.00

Strategy:
1. Close put option first (buy to close 2 contracts)
2. Then sell all SOFI stock shares
3. Lock in total P/L: ~$33.96

Usage:
    python3 scripts/exit_sofi_positions.py
    python3 scripts/exit_sofi_positions.py --dry-run  # Preview without executing
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def load_env_file():
    """Load environment variables from .env file if not already set."""
    env_file = Path(__file__).parent.parent / ".env"
    if not env_file.exists():
        logger.warning(".env file not found, relying on environment variables")
        return

    try:
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    # Only set if not already in environment
                    if key not in os.environ:
                        os.environ[key] = value.strip('"').strip("'")
        logger.info("Loaded credentials from .env file")
    except Exception as e:
        logger.error(f"Failed to load .env file: {e}")


def get_sofi_positions(client):
    """Get all SOFI-related positions."""
    try:
        all_positions = client.get_all_positions()
        sofi_positions = []

        for pos in all_positions:
            if pos.symbol.startswith("SOFI"):
                sofi_positions.append({
                    "symbol": pos.symbol,
                    "qty": float(pos.qty),
                    "avg_entry_price": float(pos.avg_entry_price),
                    "current_price": float(pos.current_price),
                    "market_value": float(pos.market_value),
                    "unrealized_pl": float(pos.unrealized_pl),
                    "unrealized_plpc": float(pos.unrealized_plpc),
                    "is_option": len(pos.symbol) > 10,  # Options have longer symbols
                })

        return sofi_positions
    except Exception as e:
        logger.error(f"Failed to get positions: {e}")
        return []


def close_position(client, position, dry_run=False):
    """Close a single position (buy to close short, sell to close long)."""
    try:
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
    except ImportError:
        logger.error("alpaca-py not installed")
        return False

    symbol = position["symbol"]
    qty = abs(position["qty"])
    is_short = position["qty"] < 0

    # Determine order side
    if is_short:
        # Short position (sold option) - buy to close
        order_side = OrderSide.BUY
        action = "BUY TO CLOSE"
    else:
        # Long position (stock) - sell to close
        order_side = OrderSide.SELL
        action = "SELL TO CLOSE"

    logger.info(f"\n{symbol}:")
    logger.info(f"  Quantity: {position['qty']}")
    logger.info(f"  Entry Price: ${position['avg_entry_price']:.2f}")
    logger.info(f"  Current Price: ${position['current_price']:.2f}")
    logger.info(f"  Market Value: ${position['market_value']:.2f}")
    logger.info(f"  Unrealized P/L: ${position['unrealized_pl']:.2f} ({position['unrealized_plpc']*100:.2f}%)")
    logger.info(f"  Action: {action} {qty} {'contracts' if position['is_option'] else 'shares'}")

    if dry_run:
        logger.info(f"  Status: WOULD EXECUTE (dry run)")
        return True

    try:
        order = MarketOrderRequest(
            symbol=symbol,
            qty=qty,
            side=order_side,
            time_in_force=TimeInForce.DAY,
        )

        result = client.submit_order(order)
        logger.info(f"  Status: ✅ ORDER SUBMITTED - Order ID: {result.id}")
        return True

    except Exception as e:
        logger.error(f"  Status: ❌ FAILED - {e}")
        return False


def main(dry_run=False):
    """Exit all SOFI positions before earnings blackout."""
    # Load environment variables
    load_env_file()

    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        logger.error("alpaca-py not installed. Run: pip install alpaca-py")
        sys.exit(1)

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()

    if not api_key or not secret_key:
        logger.error("Alpaca credentials not found")
        logger.error("Required: ALPACA_PAPER_TRADING_5K_API_KEY and ALPACA_PAPER_TRADING_5K_API_SECRET")
        sys.exit(1)

    # Always use paper trading for this script
    client = TradingClient(api_key, secret_key, paper=True)

    logger.info("=" * 80)
    logger.info("EXIT SOFI POSITIONS - EARNINGS BLACKOUT PROTECTION")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info(f"Reason: SOFI earnings blackout starts Jan 23 (earnings Jan 30)")
    logger.info("=" * 80)

    # Get all SOFI positions
    sofi_positions = get_sofi_positions(client)

    if not sofi_positions:
        logger.info("\n✅ No SOFI positions found - already clean!")
        return

    logger.info(f"\nFound {len(sofi_positions)} SOFI positions to close:")

    # Separate options from stock
    options = [p for p in sofi_positions if p["is_option"]]
    stocks = [p for p in sofi_positions if not p["is_option"]]

    logger.info(f"  - Options: {len(options)}")
    logger.info(f"  - Stock: {len(stocks)}")

    # Calculate total P/L
    total_pl = sum(p["unrealized_pl"] for p in sofi_positions)
    logger.info(f"\nTotal Unrealized P/L: ${total_pl:.2f}")

    # Close options first (safer - defined risk)
    success_count = 0
    failed_count = 0
    closed_positions = []

    logger.info("\n" + "=" * 80)
    logger.info("STEP 1: CLOSE OPTIONS POSITIONS")
    logger.info("=" * 80)

    for position in options:
        if close_position(client, position, dry_run):
            success_count += 1
            closed_positions.append(position)
        else:
            failed_count += 1

    # Then close stock positions
    logger.info("\n" + "=" * 80)
    logger.info("STEP 2: CLOSE STOCK POSITIONS")
    logger.info("=" * 80)

    for position in stocks:
        if close_position(client, position, dry_run):
            success_count += 1
            closed_positions.append(position)
        else:
            failed_count += 1

    # Summary
    logger.info("\n" + "=" * 80)
    logger.info("EXECUTION SUMMARY")
    logger.info("=" * 80)
    logger.info(f"Total positions: {len(sofi_positions)}")
    logger.info(f"Successfully {'queued' if dry_run else 'submitted'}: {success_count}")
    logger.info(f"Failed: {failed_count}")

    if not dry_run:
        locked_pl = sum(p["unrealized_pl"] for p in closed_positions)
        logger.info(f"\n💰 P/L Locked In: ${locked_pl:.2f}")
        logger.info(f"📊 P/L Percentage: {(locked_pl / 5000 * 100):.2f}% of $5K account")

    logger.info("\n✅ SOFI positions cleared before earnings blackout (Jan 23-30)")
    logger.info("🔒 Capital protected - Ready to redeploy after Feb 1")
    logger.info("=" * 80)

    # Save execution log
    if not dry_run:
        log_file = Path(__file__).parent.parent / "data" / f"sofi_exit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        log_file.parent.mkdir(exist_ok=True)

        log_data = {
            "timestamp": datetime.now().isoformat(),
            "reason": "SOFI earnings blackout protection",
            "earnings_date": "2026-01-30",
            "blackout_period": "2026-01-23 to 2026-02-01",
            "positions_closed": closed_positions,
            "total_pl_locked": locked_pl,
            "success_count": success_count,
            "failed_count": failed_count,
        }

        with open(log_file, "w") as f:
            json.dump(log_data, f, indent=2)

        logger.info(f"\n📝 Execution log saved to: {log_file}")

    if failed_count > 0:
        logger.error("\n⚠️  Some positions failed to close - manual review required")
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Exit all SOFI positions before earnings blackout"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview actions without executing trades"
    )
    args = parser.parse_args()

    main(dry_run=args.dry_run)

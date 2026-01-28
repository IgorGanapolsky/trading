#!/usr/bin/env python3
"""
Unified Position Closing Script

Consolidates the functionality of multiple close scripts:
- close_all_positions.py (emergency-all mode)
- close_excess_spreads.py (excess-only mode)
- close_all_options.py (options-only mode)
- close_shorts_first.py (shorts-first mode)

Usage:
    python scripts/close_positions.py --mode emergency-all
    python scripts/close_positions.py --mode excess-only
    python scripts/close_positions.py --mode options-only
    python scripts/close_positions.py --mode shorts-first
    python scripts/close_positions.py --mode emergency-all --dry-run
    python scripts/close_positions.py --mode excess-only --ticker SPY

Phil Town Rule #1: Don't lose money.
"""

import argparse
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import ClosePositionRequest, MarketOrderRequest

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Maximum positions allowed (1 iron condor = 4 legs) per CLAUDE.md
MAX_POSITIONS = 4


def get_alpaca_client(paper: bool = True) -> Optional[TradingClient]:
    """
    Get Alpaca trading client using the canonical credential lookup.

    Follows the pattern from src/utils/alpaca_client.py for consistency.
    """
    # Try to use the shared utility first
    try:
        from src.utils.alpaca_client import get_alpaca_credentials

        api_key, secret_key = get_alpaca_credentials()
    except ImportError:
        # Fallback to direct env var lookup
        api_key = (
            os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY")
            or os.getenv("ALPACA_API_KEY")
            or os.getenv("ALPACA_PAPER_TRADING_30K_API_KEY")
        )
        secret_key = (
            os.getenv("ALPACA_PAPER_TRADING_5K_API_SECRET")
            or os.getenv("ALPACA_SECRET_KEY")
            or os.getenv("ALPACA_PAPER_TRADING_30K_API_SECRET")
        )

    if not api_key or not secret_key:
        logger.error("Missing Alpaca API credentials")
        return None

    return TradingClient(api_key, secret_key, paper=paper)


def is_option_symbol(symbol: str) -> bool:
    """Check if a symbol is an option (OCC format has 15+ chars)."""
    return len(symbol) > 10


def get_positions(client: TradingClient, ticker: Optional[str] = None) -> list:
    """Get positions, optionally filtered by ticker."""
    positions = client.get_all_positions()

    if ticker:
        positions = [p for p in positions if p.symbol.startswith(ticker.upper())]

    return positions


def get_option_positions(client: TradingClient, ticker: Optional[str] = None) -> list:
    """Get only option positions, optionally filtered by ticker."""
    positions = get_positions(client, ticker)
    return [p for p in positions if is_option_symbol(p.symbol)]


def close_position_safely(client: TradingClient, position, dry_run: bool = False) -> bool:
    """
    Close a single position correctly based on its actual direction.

    CRITICAL: Check qty sign to determine if LONG or SHORT:
    - qty > 0 = LONG position = SELL to close
    - qty < 0 = SHORT position = BUY to close
    """
    symbol = position.symbol
    qty = int(float(position.qty))
    pnl = float(position.unrealized_pl)

    # Determine correct side to close
    if qty > 0:
        direction = "LONG"
        close_qty = qty
        side = OrderSide.SELL
    else:
        direction = "SHORT"
        close_qty = abs(qty)
        side = OrderSide.BUY

    logger.info(f"Closing {direction} position: {symbol} (qty={qty}, P/L=${pnl:+.2f})")

    if dry_run:
        logger.info(f"  [DRY RUN] Would {side.name} {close_qty} {symbol}")
        return True

    try:
        # Use close_position API which handles direction automatically
        result = client.close_position(symbol)
        order_id = result.id if hasattr(result, "id") else "N/A"
        logger.info(f"  SUCCESS - Order ID: {order_id}")
        return True
    except Exception as e:
        logger.error(f"  FAILED: {e}")

        # Try manual order submission as fallback
        try:
            logger.info(f"  Trying manual {side.name} order...")
            order_req = MarketOrderRequest(
                symbol=symbol,
                qty=close_qty,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            order = client.submit_order(order_req)
            logger.info(f"  SUCCESS (manual) - Order ID: {order.id}")
            return True
        except Exception as e2:
            logger.error(f"  Manual order also failed: {e2}")
            return False


def mode_emergency_all(client: TradingClient, ticker: Optional[str], dry_run: bool) -> int:
    """
    EMERGENCY: Close ALL positions (stocks AND options) to stop losses.
    Phil Town Rule #1: Don't lose money.
    """
    logger.info("=" * 60)
    logger.info("EMERGENCY CLOSE ALL POSITIONS - Phil Town Rule #1")
    logger.info("=" * 60)

    # Get account status
    account = client.get_account()
    logger.info(f"Equity: ${float(account.equity):,.2f}")
    logger.info(f"Cash: ${float(account.cash):,.2f}")

    # Get positions
    positions = get_positions(client, ticker)

    logger.info(f"\nFound {len(positions)} total positions:")
    total_pl = 0
    for pos in positions:
        pl = float(pos.unrealized_pl)
        total_pl += pl
        qty = float(pos.qty)
        symbol = pos.symbol
        pos_type = "OPTION" if is_option_symbol(symbol) else "STOCK"
        logger.info(f"  [{pos_type}] {symbol}: qty={qty:+.4f}, P/L=${pl:+.2f}")

    logger.info(f"\nTotal Unrealized P/L: ${total_pl:+.2f}")

    if not positions:
        logger.info("\nNo positions to close!")
        return 0

    logger.info("\n" + "=" * 60)
    logger.info("CLOSING ALL POSITIONS")
    logger.info("=" * 60)

    closed = 0
    failed = 0

    for pos in positions:
        if close_position_safely(client, pos, dry_run):
            closed += 1
        else:
            failed += 1

    logger.info("\n" + "=" * 60)
    logger.info(f"RESULT: {closed} closed, {failed} failed")
    logger.info("=" * 60)

    # Final account status
    if not dry_run:
        account = client.get_account()
        logger.info(f"\nFinal Equity: ${float(account.equity):,.2f}")
        logger.info(f"Final Cash: ${float(account.cash):,.2f}")

    return 1 if failed > 0 else 0


def mode_excess_only(client: TradingClient, ticker: Optional[str], dry_run: bool) -> int:
    """
    Close excess spreads to comply with CLAUDE.md position limit.
    Per CLAUDE.md: "Position limit: 1 iron condor at a time (4 legs max)"
    """
    logger.info("=" * 60)
    logger.info("CLOSE EXCESS SPREADS - CLAUDE.md Compliance")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Max positions allowed: {MAX_POSITIONS}")
    logger.info(f"Ticker filter: {ticker or 'ALL'}")
    logger.info("")

    # Check market hours (only close during market hours)
    clock = client.get_clock()
    if not clock.is_open:
        logger.warning("Market is CLOSED. Cannot close positions now.")
        logger.info(f"Next open: {clock.next_open}")
        return 0

    logger.info("Market is OPEN - checking positions")
    logger.info("")

    # Get option positions
    option_positions = get_option_positions(client, ticker or "SPY")

    logger.info(f"Found {len(option_positions)} option positions:")
    for p in option_positions:
        qty = int(float(p.qty))
        direction = "LONG" if qty > 0 else "SHORT"
        pnl = float(p.unrealized_pl)
        logger.info(f"  - {p.symbol}: {direction} {abs(qty)} (P/L: ${pnl:.2f})")
    logger.info("")

    # Check if we're over the limit
    if len(option_positions) <= MAX_POSITIONS:
        logger.info(f"Position count ({len(option_positions)}) within limit ({MAX_POSITIONS})")
        logger.info("No action needed.")
        return 0

    # Need to close excess positions
    excess = len(option_positions) - MAX_POSITIONS
    logger.warning(f"Over position limit by {excess} positions")
    logger.info("")

    # Sort by P/L to close the worst performing first (minimize damage)
    sorted_positions = sorted(option_positions, key=lambda p: float(p.unrealized_pl))

    logger.info("Positions sorted by P/L (worst first):")
    for i, p in enumerate(sorted_positions):
        marker = "<- CLOSE" if i < excess else "<- KEEP"
        pnl = float(p.unrealized_pl)
        logger.info(f"  {i + 1}. {p.symbol}: P/L ${pnl:.2f} {marker}")
    logger.info("")

    # Close excess positions (worst P/L first)
    positions_to_close = sorted_positions[:excess]

    logger.info(f"Closing {len(positions_to_close)} positions:")
    closed_count = 0
    errors = []

    for pos in positions_to_close:
        if close_position_safely(client, pos, dry_run):
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
        logger.error("Some positions could not be closed!")
        return 1

    logger.info("Now compliant with CLAUDE.md position limit")
    return 0


def mode_options_only(client: TradingClient, ticker: Optional[str], dry_run: bool) -> int:
    """
    Close all option positions.
    Useful for cleaning up orphan positions from partial fills.
    """
    logger.info("=" * 60)
    logger.info(f"CLOSE ALL OPTION POSITIONS - {datetime.now()}")
    logger.info("=" * 60)
    logger.info(f"Ticker filter: {ticker or 'ALL'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("")

    # Get current positions
    positions = get_positions(client, ticker)
    option_positions = [p for p in positions if is_option_symbol(p.symbol)]

    logger.info(f"Total positions: {len(positions)}")
    logger.info(f"Option positions: {len(option_positions)}")
    logger.info("")

    if not option_positions:
        logger.info("No option positions to close")
        return 0

    logger.info("Option positions to close:")
    for pos in option_positions:
        qty = float(pos.qty)
        pl = float(pos.unrealized_pl)
        logger.info(f"  {pos.symbol}: {qty:+.0f} | P/L: ${pl:+.2f}")

    if dry_run:
        logger.info(f"\nDRY RUN - Would close {len(option_positions)} positions")
        return 0

    # Close each option position
    success_count = 0
    for pos in option_positions:
        if close_position_safely(client, pos, dry_run):
            success_count += 1

    logger.info(f"\n{'=' * 60}")
    logger.info(f"Closed {success_count}/{len(option_positions)} positions")
    logger.info("=" * 60)

    return 0 if success_count == len(option_positions) else 1


def mode_shorts_first(client: TradingClient, ticker: Optional[str], dry_run: bool) -> int:
    """
    Close SHORT positions first to free up margin, then close longs.

    Strategy:
    1. Close SHORT positions first (buy to close) - frees up margin
    2. Then close LONG positions (sell to close) - should have margin now
    """
    logger.info("=" * 60)
    logger.info(f"CLOSE SHORTS FIRST STRATEGY - {datetime.now()}")
    logger.info("=" * 60)
    logger.info(f"Ticker filter: {ticker or 'SPY'}")
    logger.info(f"Dry Run: {dry_run}")
    logger.info("")

    account = client.get_account()
    logger.info(f"Equity: ${float(account.equity):,.2f}")
    logger.info(f"Options Buying Power: ${float(account.options_buying_power):,.2f}")

    # Get option positions for ticker
    positions = get_positions(client, ticker or "SPY")

    shorts = []
    longs = []

    logger.info("\nCurrent Positions:")
    for pos in positions:
        qty = float(pos.qty)
        symbol = pos.symbol
        pnl = float(pos.unrealized_pl)

        # Only SPY options
        if not is_option_symbol(symbol):
            logger.info(f"  [SKIP - STOCK] {symbol}: qty={qty}")
            continue

        if qty < 0:
            shorts.append(pos)
            logger.info(f"  [SHORT] {symbol}: qty={qty}, P/L=${pnl:+.2f}")
        else:
            longs.append(pos)
            logger.info(f"  [LONG]  {symbol}: qty={qty}, P/L=${pnl:+.2f}")

    # Step 1: Close all SHORT positions first
    logger.info("\n" + "=" * 60)
    logger.info("STEP 1: CLOSE SHORT POSITIONS (buy to close)")
    logger.info("=" * 60)

    for pos in shorts:
        close_position_safely(client, pos, dry_run)

    # Refresh account after closing shorts
    if not dry_run and shorts:
        logger.info("\n--- Refreshing account data ---")
        account = client.get_account()
        logger.info(f"Options Buying Power now: ${float(account.options_buying_power):,.2f}")

    # Step 2: Close all LONG positions
    logger.info("\n" + "=" * 60)
    logger.info("STEP 2: CLOSE LONG POSITIONS (sell to close)")
    logger.info("=" * 60)

    for pos in longs:
        if not close_position_safely(client, pos, dry_run):
            # Try partial close as last resort
            if not dry_run:
                logger.info("  Trying partial close (1 contract)...")
                try:
                    close_req = ClosePositionRequest(qty="1")
                    result = client.close_position(pos.symbol, close_options=close_req)
                    order_id = result.id if hasattr(result, "id") else result
                    logger.info(f"  Closed 1 contract! Order ID: {order_id}")
                except Exception as e2:
                    logger.error(f"  Partial close also failed: {e2}")

    logger.info("\n" + "=" * 60)
    logger.info("CLOSE SHORTS FIRST STRATEGY COMPLETE")
    logger.info("=" * 60)

    return 0


def main():
    """Main entry point with argument parsing."""
    parser = argparse.ArgumentParser(
        description="Unified Position Closing Script - Phil Town Rule #1",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Modes:
  emergency-all   Close ALL positions (stocks AND options) immediately
  excess-only     Close only excess positions to comply with CLAUDE.md limits
  options-only    Close all option positions (leave stocks)
  shorts-first    Close SHORT positions first to free margin, then longs

Examples:
  python scripts/close_positions.py --mode emergency-all
  python scripts/close_positions.py --mode excess-only --ticker SPY
  python scripts/close_positions.py --mode options-only --dry-run
        """,
    )

    parser.add_argument(
        "--mode",
        required=True,
        choices=["emergency-all", "excess-only", "options-only", "shorts-first"],
        help="Closing mode to use",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulation mode - show what would be closed without executing",
    )

    parser.add_argument(
        "--ticker",
        default=None,
        help="Filter positions by ticker (default: SPY for excess-only/shorts-first, ALL for others)",
    )

    parser.add_argument(
        "--live",
        action="store_true",
        help="Use live trading (default: paper trading)",
    )

    args = parser.parse_args()

    # Override dry run from environment if set
    if os.getenv("DRY_RUN", "").lower() == "true":
        args.dry_run = True

    # Override paper trading from environment
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"
    if args.live:
        paper = False

    logger.info("=" * 60)
    logger.info(f"UNIFIED CLOSE POSITIONS SCRIPT - Mode: {args.mode.upper()}")
    logger.info("=" * 60)
    logger.info(f"Paper Trading: {paper}")
    logger.info(f"Dry Run: {args.dry_run}")
    logger.info(f"Ticker Filter: {args.ticker or 'DEFAULT'}")
    logger.info("")

    # Get client
    client = get_alpaca_client(paper=paper)
    if not client:
        logger.error("Failed to create Alpaca client")
        return 1

    # Dispatch to appropriate mode
    if args.mode == "emergency-all":
        return mode_emergency_all(client, args.ticker, args.dry_run)
    elif args.mode == "excess-only":
        return mode_excess_only(client, args.ticker, args.dry_run)
    elif args.mode == "options-only":
        return mode_options_only(client, args.ticker, args.dry_run)
    elif args.mode == "shorts-first":
        return mode_shorts_first(client, args.ticker, args.dry_run)
    else:
        logger.error(f"Unknown mode: {args.mode}")
        return 1


if __name__ == "__main__":
    sys.exit(main())

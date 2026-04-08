#!/usr/bin/env python3
"""Close all orphan option legs that are not part of a complete iron condor.

An iron condor has 4 legs per expiry (2 puts, 2 calls, with both long and short).
Any expiry with fewer than 4 legs or missing short positions is an orphan.

Usage:
    python3 scripts/close_orphan_legs.py --dry-run   # preview
    python3 scripts/close_orphan_legs.py              # close for real
"""

import argparse
import logging
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.safety.mandatory_trade_gate import safe_submit_order

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_client():
    from alpaca.trading.client import TradingClient

    key = os.environ.get("ALPACA_PAPER_TRADING_API_KEY") or os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_PAPER_TRADING_API_SECRET") or os.environ.get(
        "ALPACA_SECRET_KEY"
    )
    if not key or not secret:
        logger.error("Alpaca credentials not found")
        sys.exit(1)
    return TradingClient(key, secret, paper=True)


def find_orphans(client):
    """Find option positions that aren't part of complete iron condors."""
    positions = client.get_all_positions()

    by_expiry = {}
    for p in positions:
        sym = p.symbol
        if len(sym) <= 10:
            continue  # Skip stock positions

        exp = sym[3:9]
        opt_type = "P" if "P0" in sym else "C"
        qty = float(p.qty)
        side = "SHORT" if qty < 0 else "LONG"

        if exp not in by_expiry:
            by_expiry[exp] = []
        by_expiry[exp].append(
            {"symbol": sym, "type": opt_type, "qty": qty, "side": side, "position": p}
        )

    orphans = []
    for exp, legs in by_expiry.items():
        puts = [leg for leg in legs if leg["type"] == "P"]
        calls = [leg for leg in legs if leg["type"] == "C"]
        shorts = [leg for leg in legs if leg["side"] == "SHORT"]

        is_complete_ic = len(legs) == 4 and len(puts) == 2 and len(calls) == 2 and len(shorts) == 2
        if not is_complete_ic:
            orphans.extend(legs)

    return orphans


def close_orphans(client, orphans, dry_run=False):
    """Close each orphan leg individually."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    closed = 0
    for leg in orphans:
        sym = leg["symbol"]
        qty = abs(int(leg["qty"]))
        close_side = OrderSide.SELL if leg["qty"] > 0 else OrderSide.BUY

        logger.info(
            f"  {close_side.name} {qty}x {sym} (closing orphan {leg['side']} {leg['type']})"
        )

        if dry_run:
            logger.info("    [DRY RUN] Skipped")
            closed += 1
            continue

        try:
            order = MarketOrderRequest(
                symbol=sym,
                qty=qty,
                side=close_side,
                time_in_force=TimeInForce.DAY,
            )
            result = safe_submit_order(client, order, strategy="orphan_cleanup")
            logger.info(f"    Submitted: {result.id} status={result.status}")
            closed += 1
        except Exception as e:
            logger.error(f"    FAILED: {e}")

    return closed


def main():
    parser = argparse.ArgumentParser(description="Close orphan option legs")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    client = get_client()

    logger.info("=" * 60)
    logger.info("ORPHAN LEG CLEANUP")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info("=" * 60)

    orphans = find_orphans(client)

    if not orphans:
        logger.info("No orphan legs found. All positions are complete iron condors.")
        return

    logger.info(f"Found {len(orphans)} orphan leg(s)")
    closed = close_orphans(client, orphans, dry_run=args.dry_run)
    logger.info(f"\nClosed: {closed}/{len(orphans)}")


if __name__ == "__main__":
    main()

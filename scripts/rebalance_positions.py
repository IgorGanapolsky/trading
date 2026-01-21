#!/usr/bin/env python3
"""
Rebalance Positions - Enforce CLAUDE.md position limits.

Created: Jan 21, 2026 (LL-280: Position Limit Contract Counting)

This script:
1. Reads current SPY option positions from Alpaca
2. Identifies imbalances (qty > 1 per leg, missing legs)
3. Closes excess contracts to get to proper 1 iron condor

Per CLAUDE.md:
- "Position limit: 1 iron condor at a time (5% max risk)"
- Iron condor = 4 legs: long put, short put, short call, long call
- Each leg should have qty = 1
"""

import logging
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from alpaca.trading.enums import OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest
from src.utils.alpaca_client import get_alpaca_credentials

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def get_trading_client():
    """Get Alpaca trading client."""
    from alpaca.trading.client import TradingClient

    api_key, secret = get_alpaca_credentials()
    if not api_key or not secret:
        raise ValueError("Alpaca credentials not found")
    return TradingClient(api_key, secret, paper=True)


def analyze_positions(client) -> dict:
    """Analyze current positions and identify issues."""
    positions = client.get_all_positions()

    # Filter SPY options only
    spy_options = [
        p for p in positions if p.symbol.startswith("SPY") and len(p.symbol) > 5
    ]

    analysis = {
        "total_contracts": 0,
        "unique_symbols": len(spy_options),
        "puts": [],
        "calls": [],
        "imbalances": [],
        "positions": [],
    }

    for pos in spy_options:
        qty = int(float(pos.qty))
        abs_qty = abs(qty)
        analysis["total_contracts"] += abs_qty

        position_info = {
            "symbol": pos.symbol,
            "qty": qty,
            "abs_qty": abs_qty,
            "side": "long" if qty > 0 else "short",
            "type": "P" if "P" in pos.symbol else "C",
            "unrealized_pl": float(pos.unrealized_pl) if pos.unrealized_pl else 0,
        }
        analysis["positions"].append(position_info)

        if "P" in pos.symbol:
            analysis["puts"].append(position_info)
        else:
            analysis["calls"].append(position_info)

        # Check for imbalances
        if abs_qty > 1:
            analysis["imbalances"].append(
                {
                    "symbol": pos.symbol,
                    "current_qty": qty,
                    "target_qty": 1 if qty > 0 else -1,
                    "excess": abs_qty - 1,
                }
            )

    return analysis


def generate_cleanup_orders(analysis: dict) -> list:
    """Generate orders to close excess positions."""
    orders = []

    for imbalance in analysis["imbalances"]:
        symbol = imbalance["symbol"]
        current_qty = imbalance["current_qty"]
        excess = imbalance["excess"]

        # To reduce long position, we SELL
        # To reduce short position, we BUY
        if current_qty > 0:
            side = OrderSide.SELL
            action = "Sell to reduce long"
        else:
            side = OrderSide.BUY
            action = "Buy to reduce short"

        orders.append(
            {"symbol": symbol, "qty": excess, "side": side, "action": action}
        )

    return orders


def execute_cleanup(client, orders: list, dry_run: bool = True) -> dict:
    """Execute cleanup orders."""
    results = {"success": 0, "failed": 0, "orders": []}

    for order_info in orders:
        symbol = order_info["symbol"]
        qty = order_info["qty"]
        side = order_info["side"]
        action = order_info["action"]

        logger.info(f"  {action}: {qty}x {symbol}")

        if dry_run:
            logger.info("    [DRY RUN] Would submit order")
            results["orders"].append({"symbol": symbol, "status": "dry_run"})
            continue

        try:
            order_req = MarketOrderRequest(
                symbol=symbol, qty=qty, side=side, time_in_force=TimeInForce.DAY
            )
            order = client.submit_order(order_req)
            logger.info(f"    ✅ Order submitted: {order.id}")
            results["success"] += 1
            results["orders"].append(
                {"symbol": symbol, "status": "submitted", "order_id": str(order.id)}
            )
        except Exception as e:
            logger.error(f"    ❌ Failed: {e}")
            results["failed"] += 1
            results["orders"].append({"symbol": symbol, "status": "failed", "error": str(e)})

    return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Rebalance SPY option positions")
    parser.add_argument(
        "--execute", action="store_true", help="Actually execute orders (default is dry run)"
    )
    parser.add_argument(
        "--close-all", action="store_true", help="Close ALL positions instead of rebalancing"
    )
    args = parser.parse_args()

    dry_run = not args.execute

    logger.info("=" * 60)
    logger.info("POSITION REBALANCER - CLAUDE.md Compliance")
    logger.info("=" * 60)
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Mode: {'EXECUTE' if args.execute else 'DRY RUN'}")
    logger.info("")

    try:
        client = get_trading_client()
    except Exception as e:
        logger.error(f"Failed to connect to Alpaca: {e}")
        return 1

    # Check market status
    clock = client.get_clock()
    if not clock.is_open:
        logger.warning("Market is CLOSED")
        logger.info(f"Next open: {clock.next_open}")
        if args.execute:
            logger.error("Cannot execute orders while market is closed")
            return 1
        logger.info("Continuing with analysis (dry run only)...")

    # Analyze positions
    logger.info("Analyzing current positions...")
    analysis = analyze_positions(client)

    logger.info("")
    logger.info("Current State:")
    logger.info(f"  Unique symbols: {analysis['unique_symbols']}")
    logger.info(f"  Total contracts: {analysis['total_contracts']}")
    logger.info(f"  Put positions: {len(analysis['puts'])}")
    logger.info(f"  Call positions: {len(analysis['calls'])}")
    logger.info("")

    # Show positions
    logger.info("Positions:")
    total_pl = 0
    for pos in analysis["positions"]:
        pl = pos["unrealized_pl"]
        total_pl += pl
        logger.info(
            f"  {pos['symbol']}: {pos['qty']} ({pos['side']} {pos['type']}) P/L: ${pl:.2f}"
        )
    logger.info(f"  Total Unrealized P/L: ${total_pl:.2f}")
    logger.info("")

    # Check for issues
    issues = []
    if analysis["total_contracts"] > 4:
        issues.append(f"Over position limit: {analysis['total_contracts']} contracts (max 4)")
    if len(analysis["calls"]) == 0 and len(analysis["puts"]) > 0:
        issues.append("Missing CALL legs - incomplete iron condor")
    if analysis["imbalances"]:
        issues.append(f"{len(analysis['imbalances'])} positions with qty > 1")

    if issues:
        logger.warning("Issues Found:")
        for issue in issues:
            logger.warning(f"  - {issue}")
        logger.info("")

    # Generate cleanup orders
    if args.close_all:
        logger.info("Close ALL mode - generating orders to close everything")
        orders = []
        for pos in analysis["positions"]:
            qty = abs(pos["qty"])
            side = OrderSide.SELL if pos["qty"] > 0 else OrderSide.BUY
            action = "Sell to close long" if pos["qty"] > 0 else "Buy to close short"
            orders.append(
                {"symbol": pos["symbol"], "qty": qty, "side": side, "action": action}
            )
    else:
        orders = generate_cleanup_orders(analysis)

    if not orders:
        logger.info("✅ No rebalancing needed - positions are compliant")
        return 0

    logger.info("Cleanup Orders:")
    results = execute_cleanup(client, orders, dry_run=dry_run)

    logger.info("")
    logger.info("=" * 60)
    logger.info("SUMMARY")
    logger.info("=" * 60)

    if dry_run:
        logger.info("DRY RUN - No orders were executed")
        logger.info(f"Would have submitted {len(orders)} orders")
        logger.info("")
        logger.info("To execute, run with --execute flag")
    else:
        logger.info(f"Orders submitted: {results['success']}")
        logger.info(f"Orders failed: {results['failed']}")

    return 0 if results["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())

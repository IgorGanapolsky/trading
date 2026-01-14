#!/usr/bin/env python3
"""
Execute Pending Trades - Process queued trade orders

This script reads pending trades from data/pending_trades_*.json files
and executes them at market open. Used for scheduled risk management actions.

Author: AI Trading System
Date: January 13, 2026
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.alpaca_trader import AlpacaTrader

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def execute_pending_trades() -> dict:
    """Execute all pending trades from JSON files."""
    results = {"executed": [], "failed": [], "skipped": []}

    data_dir = Path("data")
    today = datetime.now().strftime("%Y-%m-%d")

    # Find pending trade files for today
    pending_files = list(data_dir.glob("pending_trades_*.json"))

    if not pending_files:
        logger.info("No pending trade files found")
        return results

    trader = AlpacaTrader(paper=True)

    for file_path in pending_files:
        logger.info(f"Processing: {file_path}")

        try:
            with open(file_path) as f:
                pending = json.load(f)

            # Check if already processed
            if pending.get("status") == "EXECUTED":
                logger.info(f"  Already executed, skipping")
                results["skipped"].append(str(file_path))
                continue

            # Execute each trade
            for trade in pending.get("trades", []):
                symbol = trade.get("symbol")
                action = trade.get("action", "BUY")
                quantity = trade.get("quantity", 1)
                order_type = trade.get("order_type", "market")
                limit_price = trade.get("limit_price")

                logger.info(f"  Executing: {action} {quantity} {symbol}")

                try:
                    # Build order params
                    if order_type == "limit" and limit_price:
                        order = trader.submit_option_order(
                            symbol=symbol,
                            qty=quantity,
                            side=action.lower(),
                            order_type="limit",
                            limit_price=limit_price
                        )
                    else:
                        order = trader.submit_option_order(
                            symbol=symbol,
                            qty=quantity,
                            side=action.lower(),
                            order_type="market"
                        )

                    results["executed"].append({
                        "symbol": symbol,
                        "action": action,
                        "quantity": quantity,
                        "order_id": str(order.id) if order else None,
                        "status": "submitted"
                    })
                    logger.info(f"    Order submitted: {order.id if order else 'N/A'}")

                except Exception as e:
                    logger.error(f"    Failed: {e}")
                    results["failed"].append({
                        "symbol": symbol,
                        "error": str(e)
                    })

            # Mark file as processed
            pending["status"] = "EXECUTED"
            pending["executed_at"] = datetime.now().isoformat()

            with open(file_path, "w") as f:
                json.dump(pending, f, indent=2)

        except Exception as e:
            logger.error(f"Error processing {file_path}: {e}")
            results["failed"].append({"file": str(file_path), "error": str(e)})

    return results


def main():
    """Main entry point."""
    logger.info("=" * 60)
    logger.info("EXECUTING PENDING TRADES")
    logger.info("=" * 60)

    results = execute_pending_trades()

    logger.info("")
    logger.info("RESULTS:")
    logger.info(f"  Executed: {len(results['executed'])}")
    logger.info(f"  Failed: {len(results['failed'])}")
    logger.info(f"  Skipped: {len(results['skipped'])}")

    if results["failed"]:
        logger.error("FAILURES:")
        for fail in results["failed"]:
            logger.error(f"  - {fail}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())

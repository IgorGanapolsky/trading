#!/usr/bin/env python3
"""
Manage Open Positions - Apply Stop-Losses and Exit Conditions

CEO Directive (Jan 7, 2026):
"Losing money is NOT allowed" - Phil Town Rule 1

This script FINALLY uses the PositionManager class that was written but NEVER CALLED.
It evaluates all open positions against exit conditions and executes exits.

Exit Conditions (from position_manager.py):
- Take-profit: 15% gain
- Stop-loss: 8% loss
- Time-decay: 30 days max hold
- ATR-based dynamic stop

Usage:
    python3 scripts/manage_positions.py
    python3 scripts/manage_positions.py --dry-run  # Preview without executing
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


def main(dry_run: bool = False):
    """Evaluate all positions and execute exits."""
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest
    except ImportError:
        logger.error("alpaca-py not installed")
        sys.exit(1)

    try:
        from src.risk.position_manager import (
            ExitConditions,
            PositionManager,
        )
    except ImportError as e:
        logger.error(f"Cannot import PositionManager: {e}")
        sys.exit(1)

    api_key = os.getenv("ALPACA_API_KEY")
    secret_key = os.getenv("ALPACA_SECRET_KEY")
    paper = os.getenv("PAPER_TRADING", "true").lower() == "true"

    if not api_key or not secret_key:
        logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY required")
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=paper)

    # Initialize Position Manager with Phil Town-aligned conditions
    conditions = ExitConditions(
        take_profit_pct=0.15,  # 15% profit target
        stop_loss_pct=0.08,  # 8% stop-loss (Phil Town Rule 1)
        max_holding_days=30,
        enable_momentum_exit=False,
        enable_atr_stop=True,
        atr_multiplier=2.5,
    )
    position_manager = PositionManager(conditions=conditions)

    # Get current positions
    positions = client.get_all_positions()

    if not positions:
        logger.info("No open positions to manage")
        return

    logger.info("=" * 70)
    logger.info("POSITION MANAGEMENT - Phil Town Rule 1: Don't Lose Money")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 70)
    logger.info(f"Evaluating {len(positions)} positions")

    # Convert Alpaca positions to dict format for PositionManager
    position_dicts = []
    for pos in positions:
        position_dicts.append({
            "symbol": pos.symbol,
            "qty": pos.qty,
            "avg_entry_price": pos.avg_entry_price,
            "current_price": pos.current_price,
            "unrealized_pl": pos.unrealized_pl,
            "unrealized_plpc": pos.unrealized_plpc,
            "market_value": pos.market_value,
        })

    # Evaluate all positions
    exits = position_manager.manage_all_positions(position_dicts)

    if not exits:
        logger.info("No positions meet exit conditions - all positions HOLD")
        return

    logger.info(f"\n{len(exits)} positions flagged for exit:")

    executed_count = 0
    for exit_info in exits:
        symbol = exit_info["symbol"]
        reason = exit_info["reason"]
        details = exit_info["details"]
        position = exit_info["position"]

        logger.info(f"\n  {symbol}:")
        logger.info(f"    Reason: {reason}")
        logger.info(f"    Details: {details}")
        logger.info(f"    Qty: {position.quantity}")
        logger.info(f"    Entry: ${position.entry_price:.2f}")
        logger.info(f"    Current: ${position.current_price:.2f}")
        logger.info(f"    P/L: ${position.unrealized_pl:.2f} ({position.unrealized_plpc*100:.2f}%)")

        if dry_run:
            logger.info("    Action: WOULD SELL (dry run)")
            continue

        # Execute the exit
        try:
            # Determine order side based on position direction
            qty = abs(float(position.quantity))

            # Check if it's a short position (options sold)
            if float(position.quantity) < 0:
                # Short position - buy to close
                order = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.BUY,
                    time_in_force=TimeInForce.DAY,
                )
            else:
                # Long position - sell to close
                order = MarketOrderRequest(
                    symbol=symbol,
                    qty=qty,
                    side=OrderSide.SELL,
                    time_in_force=TimeInForce.DAY,
                )

            result = client.submit_order(order)
            logger.info(f"    Action: EXIT ORDER SUBMITTED - Order ID: {result.id}")
            executed_count += 1

            # Clear entry tracking after exit
            position_manager.clear_entry(symbol)

        except Exception as e:
            logger.error(f"    Action: EXIT FAILED - {e}")

    logger.info("\n" + "=" * 70)
    logger.info(f"SUMMARY: {executed_count}/{len(exits)} exits executed")
    logger.info("=" * 70)

    # Update system state with management timestamp
    state_file = Path(__file__).parent.parent / "data" / "system_state.json"
    try:
        with open(state_file) as f:
            state = json.load(f)

        if "position_management" not in state:
            state["position_management"] = {}

        state["position_management"]["last_run"] = datetime.now().isoformat()
        state["position_management"]["positions_evaluated"] = len(positions)
        state["position_management"]["exits_triggered"] = len(exits)
        state["position_management"]["exits_executed"] = executed_count

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not update system state: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage open positions with stop-losses")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    main(dry_run=args.dry_run)

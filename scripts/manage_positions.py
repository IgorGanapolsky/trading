#!/usr/bin/env python3
"""
Manage Open Positions - Apply Stop-Losses and Exit Conditions

CEO Directive (Jan 7, 2026):
"Losing money is NOT allowed" - Phil Town Rule 1

This script FINALLY uses the PositionManager class that was written but NEVER CALLED.
It evaluates all open positions against exit conditions and executes exits.

FIX Jan 27, 2026 (LL-TBD): Made IRON-CONDOR-AWARE
- Previous bug: Script evaluated each option leg individually, causing partial closes
- Symptoms: 3-leg positions instead of 4-leg iron condors
- Fix: Detect multi-leg iron condor structures, skip individual leg management
- Iron condors must be managed as a UNIT, not as separate legs

Exit Conditions (from position_manager.py):
- Take-profit: 15% gain (for STOCK positions only)
- Stop-loss: 8% loss (for STOCK positions only)
- Time-decay: 30 days max hold
- ATR-based dynamic stop
- IRON CONDORS: 50% max profit OR 200% stop-loss per CLAUDE.md

Usage:
    python3 scripts/manage_positions.py
    python3 scripts/manage_positions.py --dry-run  # Preview without executing
"""

import json
import logging
import os
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def is_option_symbol(symbol: str) -> bool:
    """Check if symbol is an option (vs stock).

    Option format: SPY260227P00655000 (ticker + date + P/C + strike)
    Stock format: SPY, AAPL, etc.
    """
    if not symbol:
        return False
    # Options have format: TICKER + YYMMDD + P/C + 8-digit strike
    # Example: SPY260227P00655000
    return len(symbol) > 10 and bool(re.match(r"[A-Z]+\d{6}[PC]\d{8}", symbol))


def parse_option_symbol(symbol: str) -> dict | None:
    """Parse option symbol into components.

    Example: SPY260227P00655000 -> {
        'underlying': 'SPY',
        'expiry': '260227',
        'type': 'P',
        'strike': 655.00
    }
    """
    match = re.match(r"([A-Z]+)(\d{6})([PC])(\d{8})", symbol)
    if not match:
        return None
    return {
        "underlying": match.group(1),
        "expiry": match.group(2),
        "type": match.group(3),  # P=put, C=call
        "strike": int(match.group(4)) / 1000,  # Convert to dollars
    }


def identify_iron_condor_legs(positions: list) -> dict:
    """Group option positions by underlying/expiry to identify iron condors.

    An iron condor has 4 legs on the same underlying and expiry:
    - Long put (lower strike, qty > 0)
    - Short put (higher put strike, qty < 0)
    - Short call (lower call strike, qty < 0)
    - Long call (higher call strike, qty > 0)

    Returns: dict mapping (underlying, expiry) -> list of leg symbols
    """
    # Group options by underlying + expiry
    grouped = defaultdict(list)

    for pos in positions:
        symbol = pos.symbol if hasattr(pos, "symbol") else pos.get("symbol")
        if not is_option_symbol(symbol):
            continue

        parsed = parse_option_symbol(symbol)
        if not parsed:
            continue

        qty = float(pos.qty if hasattr(pos, "qty") else pos.get("qty", 0))
        key = (parsed["underlying"], parsed["expiry"])
        grouped[key].append(
            {
                "symbol": symbol,
                "type": parsed["type"],
                "strike": parsed["strike"],
                "qty": qty,
            }
        )

    # Identify valid iron condors (must have 4 legs with correct structure)
    iron_condors = {}
    for key, legs in grouped.items():
        # Need exactly 4 legs
        if len(legs) < 4:
            # Could be partial iron condor - still protect from individual management
            if len(legs) >= 2:
                logger.warning(
                    f"⚠️ Partial multi-leg structure detected: {key[0]} exp {key[1]} "
                    f"has {len(legs)} legs (expected 4 for iron condor)"
                )
                iron_condors[key] = [leg["symbol"] for leg in legs]
            continue

        puts = [leg for leg in legs if leg["type"] == "P"]
        calls = [leg for leg in legs if leg["type"] == "C"]

        # Iron condor: 2 puts, 2 calls
        if len(puts) == 2 and len(calls) == 2:
            iron_condors[key] = [leg["symbol"] for leg in legs]
            logger.info(f"✅ Iron condor detected: {key[0]} exp {key[1]} with {len(legs)} legs")

    return iron_condors


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

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
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
    logger.info(f"Total positions: {len(positions)}")

    # FIX Jan 27, 2026: Identify iron condor legs to exclude from individual management
    # Iron condors must be managed as a UNIT, not as separate legs
    iron_condors = identify_iron_condor_legs(positions)
    iron_condor_symbols = set()
    for legs in iron_condors.values():
        iron_condor_symbols.update(legs)

    if iron_condor_symbols:
        logger.info(
            f"🔒 Iron condor legs PROTECTED from individual exit: {len(iron_condor_symbols)}"
        )
        for key, legs in iron_condors.items():
            logger.info(f"   {key[0]} exp {key[1]}: {', '.join(legs)}")
        logger.info("   These must be managed as a unit via manage_iron_condor_positions.py")

    # Convert Alpaca positions to dict format for PositionManager
    # EXCLUDE iron condor legs - they are managed separately
    position_dicts = []
    skipped_count = 0
    for pos in positions:
        if pos.symbol in iron_condor_symbols:
            logger.info(f"   ⏭️ Skipping {pos.symbol} (part of iron condor)")
            skipped_count += 1
            continue
        position_dicts.append(
            {
                "symbol": pos.symbol,
                "qty": pos.qty,
                "avg_entry_price": pos.avg_entry_price,
                "current_price": pos.current_price,
                "unrealized_pl": pos.unrealized_pl,
                "unrealized_plpc": pos.unrealized_plpc,
                "market_value": pos.market_value,
            }
        )

    logger.info(
        f"Evaluating {len(position_dicts)} non-iron-condor positions (skipped {skipped_count})"
    )

    if not position_dicts:
        logger.info("No non-iron-condor positions to evaluate")
        logger.info("Iron condors should be managed via scripts/manage_iron_condor_positions.py")
        return

    # Evaluate non-iron-condor positions only
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
        logger.info(
            f"    P/L: ${position.unrealized_pl:.2f} ({position.unrealized_plpc * 100:.2f}%)"
        )

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

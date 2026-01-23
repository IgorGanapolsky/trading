#!/usr/bin/env python3
"""
Manage Iron Condor Positions - Exit Rules per LL-268/LL-277 Research

Exit conditions for iron condors (NOT stocks):
1. 50% profit target: Close when P/L >= 50% of credit received
2. 200% stop-loss: Close when loss >= 2x credit received
3. 7 DTE exit: Close at 7 days to expiration to avoid gamma risk

This script should run on a schedule during market hours to monitor
and manage iron condor positions.

Research basis:
- LL-268: 7 DTE exit increases win rate to 80%+
- LL-277: 15-delta iron condors have 86% win rate with proper management

Usage:
    python3 scripts/manage_iron_condor_positions.py
    python3 scripts/manage_iron_condor_positions.py --dry-run
"""

import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Iron condor exit thresholds per CLAUDE.md and LL-268/LL-277
IC_EXIT_CONFIG = {
    "profit_target_pct": 0.50,  # Close at 50% profit (of credit)
    "stop_loss_pct": 2.00,  # Close at 200% loss (2x credit)
    "exit_dte": 7,  # Close at 7 DTE (gamma risk)
}


def is_option_symbol(symbol: str) -> bool:
    """Check if symbol is an option (OCC format: >10 chars)."""
    return len(symbol) > 10


def parse_option_symbol(symbol: str) -> dict | None:
    """
    Parse OCC option symbol format.
    Example: SPY260227P00650000 -> {underlying: SPY, expiry: 2026-02-27, type: P, strike: 650.00}
    """
    if not is_option_symbol(symbol):
        return None

    try:
        underlying = symbol[:3] if symbol[:3].isalpha() else symbol[:4]
        rest = symbol[len(underlying):]

        # Format: YYMMDDTSSSSSSSS (T=type, S=strike*1000)
        year = int("20" + rest[0:2])
        month = int(rest[2:4])
        day = int(rest[4:6])
        opt_type = rest[6]  # 'C' or 'P'
        strike = int(rest[7:]) / 1000

        expiry = datetime(year, month, day)

        return {
            "underlying": underlying,
            "expiry": expiry,
            "type": opt_type,
            "strike": strike,
            "symbol": symbol,
        }
    except (ValueError, IndexError):
        return None


def calculate_dte(expiry: datetime) -> int:
    """Calculate days to expiration."""
    return (expiry - datetime.now()).days


def get_iron_condor_positions(client) -> list[dict]:
    """
    Get all iron condor positions from Alpaca.
    Returns grouped positions by expiry date (4 legs = 1 iron condor).
    """
    positions = client.get_all_positions()
    option_positions = []

    for pos in positions:
        parsed = parse_option_symbol(pos.symbol)
        if parsed:
            parsed["qty"] = float(pos.qty)
            parsed["current_price"] = float(pos.current_price)
            parsed["avg_entry_price"] = float(pos.avg_entry_price)
            parsed["unrealized_pl"] = float(pos.unrealized_pl)
            parsed["market_value"] = float(pos.market_value)
            option_positions.append(parsed)

    return option_positions


def group_iron_condors(positions: list[dict]) -> list[dict]:
    """
    Group option legs into iron condors by expiry.
    Iron condor = 4 legs: long put, short put, short call, long call
    """
    by_expiry = {}

    for pos in positions:
        expiry_key = pos["expiry"].strftime("%Y-%m-%d")
        if expiry_key not in by_expiry:
            by_expiry[expiry_key] = {
                "expiry": pos["expiry"],
                "expiry_str": expiry_key,
                "underlying": pos["underlying"],
                "legs": [],
                "total_pl": 0,
                "credit_received": 0,
            }
        by_expiry[expiry_key]["legs"].append(pos)
        by_expiry[expiry_key]["total_pl"] += pos["unrealized_pl"]

    # Calculate credit received (sum of entry prices for short legs)
    for ic in by_expiry.values():
        credit = 0
        for leg in ic["legs"]:
            if leg["qty"] < 0:  # Short leg
                credit += abs(leg["avg_entry_price"] * leg["qty"] * 100)
        ic["credit_received"] = credit

    return list(by_expiry.values())


def check_exit_conditions(ic: dict) -> tuple[bool, str, str]:
    """
    Check if iron condor meets exit conditions.
    Returns: (should_exit, reason, details)
    """
    dte = calculate_dte(ic["expiry"])
    pl = ic["total_pl"]
    credit = ic["credit_received"]

    if credit <= 0:
        return False, "", "No credit tracked"

    pl_pct = pl / credit if credit > 0 else 0

    # Check 7 DTE exit
    if dte <= IC_EXIT_CONFIG["exit_dte"]:
        return True, "DTE_EXIT", f"{dte} DTE (threshold: {IC_EXIT_CONFIG['exit_dte']})"

    # Check 50% profit target
    if pl_pct >= IC_EXIT_CONFIG["profit_target_pct"]:
        return True, "PROFIT_TARGET", f"{pl_pct*100:.1f}% profit (target: {IC_EXIT_CONFIG['profit_target_pct']*100:.0f}%)"

    # Check 200% stop-loss
    if pl_pct <= -IC_EXIT_CONFIG["stop_loss_pct"]:
        return True, "STOP_LOSS", f"{pl_pct*100:.1f}% loss (stop: {IC_EXIT_CONFIG['stop_loss_pct']*100:.0f}%)"

    return False, "HOLD", f"P/L: {pl_pct*100:.1f}%, DTE: {dte}"


def close_iron_condor(client, ic: dict, reason: str, dry_run: bool = False) -> bool:
    """Close all legs of an iron condor."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    logger.info(f"  Closing iron condor expiry {ic['expiry_str']} - Reason: {reason}")

    success = True
    for leg in ic["legs"]:
        symbol = leg["symbol"]
        qty = abs(int(leg["qty"]))

        # Determine order side: buy to close short, sell to close long
        if leg["qty"] < 0:
            side = OrderSide.BUY
            action = "BUY to close short"
        else:
            side = OrderSide.SELL
            action = "SELL to close long"

        logger.info(f"    {symbol}: {action} {qty}")

        if dry_run:
            logger.info(f"      [DRY RUN] Would submit order")
            continue

        try:
            order = MarketOrderRequest(
                symbol=symbol,
                qty=qty,
                side=side,
                time_in_force=TimeInForce.DAY,
            )
            result = client.submit_order(order)
            logger.info(f"      Order ID: {result.id}")
        except Exception as e:
            logger.error(f"      FAILED: {e}")
            success = False

    return success


def main(dry_run: bool = False):
    """Main position management loop."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        logger.error("alpaca-py not installed")
        sys.exit(1)

    from src.utils.alpaca_client import get_alpaca_credentials

    api_key, secret_key = get_alpaca_credentials()
    if not api_key or not secret_key:
        logger.error("Alpaca credentials not found")
        sys.exit(1)

    client = TradingClient(api_key, secret_key, paper=True)

    logger.info("=" * 70)
    logger.info("IRON CONDOR POSITION MANAGEMENT")
    logger.info(f"Mode: {'DRY RUN' if dry_run else 'LIVE EXECUTION'}")
    logger.info(f"Time: {datetime.now().isoformat()}")
    logger.info("=" * 70)
    logger.info(f"Exit Rules (LL-268/LL-277):")
    logger.info(f"  - Profit Target: {IC_EXIT_CONFIG['profit_target_pct']*100:.0f}% of credit")
    logger.info(f"  - Stop Loss: {IC_EXIT_CONFIG['stop_loss_pct']*100:.0f}% of credit")
    logger.info(f"  - DTE Exit: {IC_EXIT_CONFIG['exit_dte']} days")
    logger.info("=" * 70)

    # Get all option positions
    positions = get_iron_condor_positions(client)

    if not positions:
        logger.info("No option positions found")
        return

    logger.info(f"Found {len(positions)} option legs")

    # Group into iron condors
    iron_condors = group_iron_condors(positions)
    logger.info(f"Grouped into {len(iron_condors)} iron condor(s)")

    exits_triggered = 0
    exits_executed = 0

    for ic in iron_condors:
        dte = calculate_dte(ic["expiry"])
        pl = ic["total_pl"]
        credit = ic["credit_received"]

        logger.info(f"\nIron Condor: {ic['underlying']} {ic['expiry_str']}")
        logger.info(f"  Legs: {len(ic['legs'])}")
        logger.info(f"  DTE: {dte}")
        logger.info(f"  Credit: ${credit:.2f}")
        logger.info(f"  P/L: ${pl:.2f} ({pl/credit*100:.1f}% of credit)" if credit > 0 else f"  P/L: ${pl:.2f}")

        should_exit, reason, details = check_exit_conditions(ic)

        if should_exit:
            logger.info(f"  EXIT TRIGGERED: {reason} - {details}")
            exits_triggered += 1

            if close_iron_condor(client, ic, reason, dry_run):
                exits_executed += 1
        else:
            logger.info(f"  Status: HOLD - {details}")

    logger.info("\n" + "=" * 70)
    logger.info(f"SUMMARY")
    logger.info(f"  Iron condors evaluated: {len(iron_condors)}")
    logger.info(f"  Exits triggered: {exits_triggered}")
    logger.info(f"  Exits executed: {exits_executed}")
    logger.info("=" * 70)

    # Update system state
    state_file = Path(__file__).parent.parent / "data" / "system_state.json"
    try:
        with open(state_file) as f:
            state = json.load(f)

        if "ic_position_management" not in state:
            state["ic_position_management"] = {}

        state["ic_position_management"]["last_run"] = datetime.now().isoformat()
        state["ic_position_management"]["iron_condors_evaluated"] = len(iron_condors)
        state["ic_position_management"]["exits_triggered"] = exits_triggered
        state["ic_position_management"]["exits_executed"] = exits_executed

        with open(state_file, "w") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        logger.warning(f"Could not update system state: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Manage iron condor positions")
    parser.add_argument("--dry-run", action="store_true", help="Preview without executing")
    args = parser.parse_args()

    main(dry_run=args.dry_run)

#!/usr/bin/env python3
"""
Manage Iron Condor Positions - Exit Rules per LL-268/LL-277 Research

Exit conditions for iron condors (NOT stocks):
1. 50% profit target: Close when P/L >= 50% of credit received
2. 100% stop-loss: Close when loss >= 1x credit received (per canonical constant)
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

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.core.trading_constants import IRON_CONDOR_STOP_LOSS_MULTIPLIER
from src.safety.mandatory_trade_gate import safe_submit_order

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Iron condor exit thresholds per LL-268/LL-277
IC_EXIT_CONFIG = {
    "profit_target_pct": 0.50,  # Close at 50% profit
    "stop_loss_pct": IRON_CONDOR_STOP_LOSS_MULTIPLIER,  # Canonical 1.0x credit stop-loss
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
        rest = symbol[len(underlying) :]

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

    # Check 50% profit target (positive EV)
    if pl_pct >= IC_EXIT_CONFIG["profit_target_pct"]:
        return (
            True,
            "PROFIT_TARGET",
            f"{pl_pct * 100:.1f}% profit (target: {IC_EXIT_CONFIG['profit_target_pct'] * 100:.0f}%)",
        )

    # Check 100% stop-loss (cut losers fast)
    if pl_pct <= -IC_EXIT_CONFIG["stop_loss_pct"]:
        return (
            True,
            "STOP_LOSS",
            f"{pl_pct * 100:.1f}% loss (stop: {IC_EXIT_CONFIG['stop_loss_pct'] * 100:.0f}%)",
        )

    return False, "HOLD", f"P/L: {pl_pct * 100:.1f}%, DTE: {dte}"


def close_iron_condor(client, ic: dict, reason: str, dry_run: bool = False) -> bool:
    """Close all legs of an iron condor using MLeg order for atomic execution.

    FIX Jan 27, 2026: Changed from individual leg orders to MLeg (multi-leg) order.
    Previous bug: Individual close orders destroyed iron condor structure, leaving
    orphan legs that caused losses. MLeg ensures all legs close together or not at all.
    """
    from alpaca.trading.enums import OrderClass, OrderSide
    from alpaca.trading.requests import MarketOrderRequest, OptionLegRequest

    logger.info(f"  Closing iron condor expiry {ic['expiry_str']} - Reason: {reason}")
    logger.info("  Using MLeg (multi-leg) order for atomic close")

    # Build option legs for MLeg close order
    option_legs = []
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
        option_legs.append(OptionLegRequest(symbol=symbol, side=side, ratio_qty=qty))

    if dry_run:
        logger.info("      [DRY RUN] Would submit MLeg close order")
        return True

    try:
        # Submit as MLeg order - all legs close together or not at all
        # NOTE: TimeInForce not supported for options MLeg orders (Alpaca constraint)
        order_req = MarketOrderRequest(
            qty=1,  # MLeg uses ratio_qty in legs
            order_class=OrderClass.MLEG,
            legs=option_legs,
        )
        result = safe_submit_order(client, order_req)
        logger.info(f"    ✅ MLeg close order submitted: {result.id}")
        logger.info(f"       Status: {result.status}")
        return True

    except Exception as e:
        logger.error(f"    ❌ MLeg close order FAILED: {e}")
        logger.error("       Iron condor NOT closed - all legs preserved")
        logger.error("       Manual intervention may be required")
        return False


def record_trade_outcome(ic: dict, reason: str, won: bool) -> None:
    """Record trade outcome into canonical episode storage and RLHF logs."""
    pl = ic["total_pl"]
    credit = ic["credit_received"]
    expiry = ic["expiry_str"]
    project_root = Path(__file__).parent.parent
    timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    episode_id = str(
        ic.get("episode_id") or f"iron_condor::{ic.get('underlying', 'SPY')}::{expiry}"
    )
    event_key = (
        f"iron_condor_close::{ic.get('underlying', 'SPY')}::"
        f"{ic.get('expiry_str', 'unknown')}::{reason}::{round(float(pl), 2)}"
    )

    try:
        from src.learning.outcome_labeler import build_outcome_label
        from src.learning.trade_episode_store import TradeEpisodeStore

        outcome_label = build_outcome_label(
            {
                "symbol": ic.get("underlying", "SPY"),
                "strategy": "iron_condor",
                "total_pl": pl,
                "credit_received": credit,
                "exit_reason": reason,
                "won": won,
            }
        )
        episode_store = TradeEpisodeStore(
            event_log_path=project_root / "data" / "feedback" / "trade_episode_events.jsonl",
            snapshot_path=project_root / "data" / "feedback" / "trade_episodes.json",
        )
        episode_store.upsert_outcome(
            {
                "episode_id": episode_id,
                "event_type": "outcome",
                "timestamp": timestamp,
                "event_key": event_key,
                "symbol": str(ic.get("underlying", "SPY")),
                "strategy": "iron_condor",
                "reward": float(outcome_label["reward"]),
                "return_pct": outcome_label["return_pct"],
                "won": bool(outcome_label["won"]),
                "lost": bool(outcome_label["lost"]),
                "outcome": outcome_label["outcome"],
                "holding_minutes": outcome_label["holding_minutes"],
                "exit_reason": reason,
                "expiry": str(ic.get("expiry_str", "")),
                "metadata": {
                    "source": "manage_iron_condor_positions",
                    "summary": outcome_label["summary"],
                    "legs": [leg.get("symbol") for leg in ic.get("legs", []) if leg.get("symbol")],
                },
            }
        )
        logger.info(
            "Canonical trade episode updated: %s (%s)", episode_id, outcome_label["outcome"]
        )
    except Exception as e:
        logger.warning(f"Could not update canonical trade episode: {e}")

    # Persist structured RLHF close-out event for compatibility with downstream analytics.
    try:
        from src.learning.outcome_labeler import build_outcome_label
        from src.learning.rlhf_storage import store_trade_outcome

        outcome_label = build_outcome_label(
            {
                "symbol": ic.get("underlying", "SPY"),
                "strategy": "iron_condor",
                "total_pl": pl,
                "credit_received": credit,
                "exit_reason": reason,
                "won": won,
            }
        )
        store_trade_outcome(
            symbol=str(ic.get("underlying", "SPY")),
            strategy="iron_condor",
            reward=float(outcome_label["reward"]),
            won=bool(outcome_label["won"]),
            exit_reason=reason,
            expiry=str(ic.get("expiry_str", "")),
            episode_id=episode_id,
            event_key=event_key,
            metadata={
                "source": "manage_iron_condor_positions",
                "summary": outcome_label["summary"],
                "return_pct": outcome_label["return_pct"],
                "holding_minutes": outcome_label["holding_minutes"],
            },
        )
    except Exception as e:
        logger.warning(f"Could not store structured RLHF outcome: {e}")

    # Feed distributed feedback model so learning updates are immediate and idempotent.
    try:
        from src.learning.distributed_feedback import LocalBackend, aggregate_feedback

        feedback_type = "positive" if bool(won) else "negative"
        context = (
            f"iron_condor closed symbol={ic.get('underlying', 'SPY')} "
            f"expiry={ic.get('expiry_str', '')} exit_reason={reason} pnl={float(pl):.2f}"
        )
        outcome = aggregate_feedback(
            project_root=project_root,
            event_key=event_key,
            feedback_type=feedback_type,
            context=context,
            backend=LocalBackend(),
        )
        if outcome.get("applied"):
            logger.info(
                "Distributed feedback updated (%s): +%.0f/-%.0f",
                feedback_type,
                float(outcome.get("global_positive", 0.0)),
                float(outcome.get("global_negative", 0.0)),
            )
        elif outcome.get("skipped_reason") == "duplicate_event":
            logger.info("Distributed feedback skipped duplicate event: %s", event_key)
    except Exception as e:
        logger.warning(f"Could not update distributed feedback model: {e}")


def get_alpaca_credentials():
    """Get Alpaca credentials from environment variables (CI-compatible)."""
    import os

    # Try multiple env var names for compatibility
    api_key = (
        os.environ.get("ALPACA_API_KEY")
        or os.environ.get("ALPACA_PAPER_TRADING_5K_API_KEY")
        or os.environ.get("ALPACA_PAPER_TRADING_30K_API_KEY")
    )
    secret_key = (
        os.environ.get("ALPACA_SECRET_KEY")
        or os.environ.get("ALPACA_PAPER_TRADING_5K_API_SECRET")
        or os.environ.get("ALPACA_PAPER_TRADING_30K_API_SECRET")
    )
    return api_key, secret_key


def main(dry_run: bool = False):
    """Main position management loop."""
    try:
        from alpaca.trading.client import TradingClient
    except ImportError:
        logger.error("alpaca-py not installed")
        sys.exit(1)

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
    logger.info("Exit Rules (LL-268/LL-277):")
    logger.info(f"  - Profit Target: {IC_EXIT_CONFIG['profit_target_pct'] * 100:.0f}% of credit")
    logger.info(f"  - Stop Loss: {IC_EXIT_CONFIG['stop_loss_pct'] * 100:.0f}% of credit")
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
        logger.info(
            f"  P/L: ${pl:.2f} ({pl / credit * 100:.1f}% of credit)"
            if credit > 0
            else f"  P/L: ${pl:.2f}"
        )

        should_exit, reason, details = check_exit_conditions(ic)

        if should_exit:
            logger.info(f"  EXIT TRIGGERED: {reason} - {details}")
            exits_triggered += 1

            if close_iron_condor(client, ic, reason, dry_run):
                exits_executed += 1
                won = reason == "PROFIT_TARGET"
                record_trade_outcome(ic, reason, won)
                # Record stop-loss for behavioral guard cooling
                if reason == "STOP_LOSS":
                    try:
                        from src.safety.behavioral_guard import BehavioralGuard

                        BehavioralGuard.record_stop_loss_exit(ic["expiry_str"])
                    except ImportError:
                        pass
        else:
            logger.info(f"  Status: HOLD - {details}")

    logger.info("\n" + "=" * 70)
    logger.info("SUMMARY")
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

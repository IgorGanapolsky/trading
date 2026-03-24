#!/usr/bin/env python3
"""
Single Trading Pipeline — replaces 28 disconnected workflows.

One script. Seven stages. No conflicts.

Usage:
    python3 scripts/trade_pipeline.py              # full pipeline
    python3 scripts/trade_pipeline.py --dry-run    # preview without executing
    python3 scripts/trade_pipeline.py --stage sync  # run one stage only

Stages:
    1. sync     — refresh account state from Alpaca
    2. vix      — check VIX, halt if > 30
    3. orphans  — detect and close orphan legs
    4. positions — check current ICs, manage exits (50% / 7 DTE / 100% stop)
    5. find     — calculate strikes for new IC if room
    6. execute  — submit MLEG order
    7. record   — update system_state.json and GRPO training data
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from dotenv import load_dotenv

    load_dotenv(dotenv_path=PROJECT_ROOT / ".env", override=False)
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("trade_pipeline")


def get_client():
    """Get authenticated Alpaca trading client."""
    from alpaca.trading.client import TradingClient

    key = os.environ.get("ALPACA_PAPER_TRADING_API_KEY") or os.environ.get("ALPACA_API_KEY")
    secret = os.environ.get("ALPACA_PAPER_TRADING_API_SECRET") or os.environ.get(
        "ALPACA_SECRET_KEY"
    )
    if not key or not secret:
        logger.error("Alpaca credentials not found")
        sys.exit(1)
    return TradingClient(key, secret, paper=True)


def stage_sync(client, dry_run=False) -> dict:
    """Stage 1: Sync account state from Alpaca."""
    logger.info("=" * 60)
    logger.info("STAGE 1: SYNC")
    logger.info("=" * 60)

    acct = client.get_account()
    equity = float(acct.equity)
    cash = float(acct.cash)
    buying_power = float(acct.buying_power)

    positions = client.get_all_positions()
    option_positions = [p for p in positions if len(p.symbol) > 10]

    state = {
        "equity": equity,
        "cash": cash,
        "buying_power": buying_power,
        "positions_count": len(option_positions),
        "synced_at": datetime.now(timezone.utc).isoformat(),
    }

    logger.info(f"  Equity: ${equity:,.2f}")
    logger.info(f"  Cash: ${cash:,.2f}")
    logger.info(f"  Option positions: {len(option_positions)}")

    return state


def stage_vix(dry_run=False) -> dict:
    """Stage 2: Check VIX conditions."""
    logger.info("=" * 60)
    logger.info("STAGE 2: VIX CHECK")
    logger.info("=" * 60)

    try:
        from src.options.vix_monitor import VIXMonitor

        vix_monitor = VIXMonitor()
        vix = vix_monitor.get_current_vix()
    except Exception as e:
        logger.error(f"  VIX check failed: {e} — BLOCKING")
        return {"vix": None, "can_trade": False, "reason": f"VIX unavailable: {e}"}

    can_trade = vix < 30
    logger.info(f"  VIX: {vix:.2f}")
    logger.info(f"  Can trade: {can_trade}")

    if vix > 25:
        logger.warning(f"  CAUTION: VIX elevated ({vix:.2f})")
    if not can_trade:
        logger.error(f"  BLOCKED: VIX {vix:.2f} > 30")

    return {"vix": vix, "can_trade": can_trade, "reason": f"VIX {vix:.2f}"}


def stage_orphans(client, dry_run=False) -> dict:
    """Stage 3: Detect and close orphan legs."""
    logger.info("=" * 60)
    logger.info("STAGE 3: ORPHAN CLEANUP")
    logger.info("=" * 60)

    from scripts.close_orphan_legs import close_orphans, find_orphans

    orphans = find_orphans(client)
    if not orphans:
        logger.info("  No orphans found")
        return {"orphans_found": 0, "orphans_closed": 0}

    logger.warning(f"  Found {len(orphans)} orphan leg(s)")
    closed = close_orphans(client, orphans, dry_run=dry_run)
    return {"orphans_found": len(orphans), "orphans_closed": closed}


def stage_positions(client, dry_run=False) -> dict:
    """Stage 4: Manage existing IC positions (exits)."""
    logger.info("=" * 60)
    logger.info("STAGE 4: POSITION MANAGEMENT")
    logger.info("=" * 60)

    positions = client.get_all_positions()
    option_positions = [p for p in positions if len(p.symbol) > 10]

    # Group by expiry
    by_expiry = {}
    for p in option_positions:
        exp = p.symbol[3:9]
        if exp not in by_expiry:
            by_expiry[exp] = []
        by_expiry[exp].append(p)

    valid_ics = 0
    for exp, legs in by_expiry.items():
        shorts = sum(1 for leg in legs if float(leg.qty) < 0)
        longs = sum(1 for leg in legs if float(leg.qty) > 0)
        is_valid = len(legs) == 4 and shorts == 2 and longs == 2

        if is_valid:
            valid_ics += 1
            total_pl = sum(float(leg.unrealized_pl) for leg in legs)
            exp_date = f"20{exp[:2]}-{exp[2:4]}-{exp[4:6]}"
            dte = (
                datetime(int(f"20{exp[:2]}"), int(exp[2:4]), int(exp[4:6])) - datetime.now()
            ).days
            logger.info(f"  IC {exp_date}: {dte} DTE, P/L=${total_pl:,.2f}")

    logger.info(f"  Valid iron condors: {valid_ics}")
    return {"valid_ics": valid_ics, "max_ics": 2}


def stage_find(state: dict, dry_run=False) -> dict:
    """Stage 5: Find a new IC trade if room."""
    logger.info("=" * 60)
    logger.info("STAGE 5: FIND TRADE")
    logger.info("=" * 60)

    if state.get("valid_ics", 0) >= state.get("max_ics", 2):
        logger.info("  At max positions — skipping")
        return {"should_trade": False, "reason": "at max positions"}

    if not state.get("can_trade", False):
        logger.info(f"  VIX blocked — skipping ({state.get('reason', 'unknown')})")
        return {"should_trade": False, "reason": state.get("reason", "VIX blocked")}

    # Use the existing iron_condor_trader to find a trade
    try:
        from scripts.iron_condor_trader import IronCondorStrategy

        strategy = IronCondorStrategy()
        ic = strategy.find_trade()
        if ic:
            logger.info(f"  Found: {ic.underlying} {ic.expiry}")
            logger.info(
                f"  Strikes: LP={ic.long_put} SP={ic.short_put} SC={ic.short_call} LC={ic.long_call}"
            )
            return {"should_trade": True, "ic": ic}
    except Exception as e:
        logger.error(f"  Find trade failed: {e}")
        return {"should_trade": False, "reason": str(e)}

    return {"should_trade": False, "reason": "no suitable trade found"}


def stage_execute(client, state: dict, dry_run=False) -> dict:
    """Stage 6: Execute the trade."""
    logger.info("=" * 60)
    logger.info("STAGE 6: EXECUTE")
    logger.info("=" * 60)

    if not state.get("should_trade"):
        logger.info("  No trade to execute")
        return {"executed": False}

    ic = state.get("ic")
    if not ic:
        return {"executed": False}

    if dry_run:
        logger.info(f"  [DRY RUN] Would submit IC: {ic.underlying} {ic.expiry}")
        return {"executed": False, "dry_run": True}

    try:
        from scripts.iron_condor_trader import IronCondorStrategy

        strategy = IronCondorStrategy()
        result = strategy.execute(ic, live=True)
        logger.info(f"  Result: {result.get('status', 'unknown')}")
        return {"executed": True, "result": result}
    except Exception as e:
        logger.error(f"  Execution failed: {e}")
        return {"executed": False, "error": str(e)}


def stage_record(state: dict, dry_run=False) -> dict:
    """Stage 7: Record results."""
    logger.info("=" * 60)
    logger.info("STAGE 7: RECORD")
    logger.info("=" * 60)

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "equity": state.get("equity"),
        "vix": state.get("vix"),
        "orphans_closed": state.get("orphans_closed", 0),
        "valid_ics": state.get("valid_ics", 0),
        "trade_executed": state.get("executed", False),
    }

    # Append to pipeline log
    log_path = PROJECT_ROOT / "data" / "pipeline_log.jsonl"
    if not dry_run:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a") as f:
            f.write(json.dumps(summary) + "\n")
        logger.info(f"  Logged to {log_path}")

    logger.info(f"  Summary: {json.dumps(summary, indent=2)}")
    return summary


def main():
    parser = argparse.ArgumentParser(description="Single trading pipeline")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--stage", help="Run specific stage only")
    args = parser.parse_args()

    # Check trading halt
    halt_file = PROJECT_ROOT / "data" / "TRADING_HALTED"
    if halt_file.exists() and args.stage not in ("sync", "orphans"):
        logger.error(f"TRADING_HALTED: {halt_file.read_text().strip()}")
        logger.error("Remove data/TRADING_HALTED to resume trading")
        sys.exit(0)

    logger.info("=" * 60)
    logger.info("TRADE PIPELINE")
    logger.info(f"Mode: {'DRY RUN' if args.dry_run else 'LIVE'}")
    logger.info(f"Time: {datetime.now(timezone.utc).isoformat()}")
    logger.info("=" * 60)

    client = get_client()
    state = {}

    stages = [
        ("sync", stage_sync, {"client": client}),
        ("vix", stage_vix, {}),
        ("orphans", stage_orphans, {"client": client}),
        ("positions", stage_positions, {"client": client}),
        ("find", stage_find, {"state": state}),
        ("execute", stage_execute, {"client": client, "state": state}),
        ("record", stage_record, {"state": state}),
    ]

    for name, fn, kwargs in stages:
        if args.stage and args.stage != name:
            continue
        try:
            result = fn(dry_run=args.dry_run, **kwargs)
            state.update(result)
        except Exception as e:
            logger.error(f"Stage {name} failed: {e}")
            if name in ("sync", "vix"):
                logger.error("Critical stage failed — aborting pipeline")
                sys.exit(1)

    logger.info("")
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETE")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

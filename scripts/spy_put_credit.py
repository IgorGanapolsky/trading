#!/usr/bin/env python3
"""SPY bull put credit — active validation strategy after IC Simple kill.

Paper-only, 1-lot, $5-wide, 30-45 DTE, 15-delta short put.
Does NOT place live orders unless --live is passed AND kill switch allows
(live is blocked by default in strategy_kill_switch.json).

Usage:
  .venv/bin/python scripts/spy_put_credit.py --dry-run
  .venv/bin/python scripts/spy_put_credit.py --status
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("spy_put_credit")

ENTRIES_FILE = ROOT / "data" / "put_credit_entries.json"
AUDIT_DIR = ROOT / "data" / "audit"


def _load_profile():
    from src.core.trading_profiles import get_put_credit_profile

    return get_put_credit_profile()


def _assert_active() -> None:
    from src.core.active_strategy import assert_entry_allowed, load_kill_state

    assert_entry_allowed("spy_put_credit")
    state = load_kill_state()
    if state.live_blocked:
        logger.info("Live capital blocked by kill switch (paper validation only).")


def _inventory_ok() -> bool:
    try:
        from src.core.trading_constants import (
            MAX_CONCURRENT_IRON_CONDORS,
            MAX_CONTRACTS_PER_TRADE,
        )
        from src.risk.open_inventory_audit import audit_from_files, write_audit_report
    except ImportError:
        # open_inventory_audit may not be merged yet — fail open with warn
        logger.warning("open_inventory_audit not available; skipping inventory gate")
        return True

    result = audit_from_files(
        ROOT,
        max_contracts_per_trade=float(MAX_CONTRACTS_PER_TRADE),
        max_concurrent_iron_condors=int(MAX_CONCURRENT_IRON_CONDORS),
    )
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    write_audit_report(result, AUDIT_DIR / "open_inventory_latest.json")
    if not result.clean:
        logger.error("UNCLEAN_INVENTORY — resolve open IC/orphan legs before put-credit entry")
        for reason in result.block_reasons()[:5]:
            logger.error("  - %s", reason)
        return False
    return True


def plan_structure(dry_run: bool = True) -> dict:
    """Build a planned put-credit structure (scan or placeholder when chain unavailable)."""
    profile = _load_profile()
    cfg = profile.as_strategy_config()
    plan = {
        "strategy_family": "spy_put_credit",
        "structure": "bull_put_credit",
        "underlying": cfg["underlying"],
        "quantity": cfg["max_contracts_per_trade"],
        "wing_width": cfg["wing_width"],
        "target_dte": cfg["target_dte"],
        "min_dte": cfg["min_dte"],
        "max_dte": cfg["max_dte"],
        "short_delta": cfg["short_delta"],
        "delta_band": [cfg["delta_band_min"], cfg["delta_band_max"]],
        "take_profit_pct": cfg["take_profit_pct"],
        "stop_loss_pct": cfg["stop_loss_pct"],
        "exit_dte": cfg["exit_dte"],
        "min_hold_hours": cfg["min_hold_hours"],
        "min_credit": cfg["min_credit"],
        "dry_run": dry_run,
        "planned_at": datetime.now(timezone.utc).isoformat(),
        "status": "planned",
    }

    # Best-effort live chain scan; never required for --status / unit tests.
    try:
        from src.utils.alpaca_client import get_alpaca_credentials
        from src.utils.options_analysis import get_underlying_price

        price = get_underlying_price("SPY")
        plan["spy_price"] = price
        key, secret = get_alpaca_credentials()
        if key and secret:
            plan["credentials_present"] = True
        else:
            plan["credentials_present"] = False
            plan["note"] = "No Alpaca credentials in this shell — plan only"
    except Exception as exc:  # noqa: BLE001
        plan["scan_error"] = str(exc)
        plan["note"] = "Chain scan skipped; policy plan only"

    return plan


def write_plan(plan: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "spy_put_credit_latest_plan.json"
    path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="SPY put credit validation entry")
    parser.add_argument("--dry-run", action="store_true", default=True)
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="Allow paper fill path (still blocked if inventory unclean / live flags)",
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--live", action="store_true", help="Rejected while live_blocked")
    args = parser.parse_args()

    from src.core.active_strategy import load_kill_state

    state = load_kill_state()
    logger.info("=" * 60)
    logger.info(
        "SPY PUT CREDIT | active=%s killed=%s",
        state.active_family,
        list(state.killed_families),
    )
    logger.info("=" * 60)

    if args.status:
        plan = plan_structure(dry_run=True)
        path = write_plan(plan)
        print(json.dumps({"kill_state": state.__dict__, "plan": plan, "plan_path": str(path)}, indent=2, default=str))
        return 0

    if args.live or not state.paper_only:
        if state.live_blocked or args.live:
            logger.error("LIVE BLOCKED: put-credit validation is paper-only until kill criteria clear")
            return 2

    try:
        _assert_active()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    if not _inventory_ok():
        return 2

    dry = not args.execute_paper
    plan = plan_structure(dry_run=dry)
    path = write_plan(plan)
    logger.info("Plan written: %s", path)
    logger.info(
        "Policy: SPY 1-lot bull put $%.0f-wide | Δ=%.2f | DTE %s-%s | TP %.0f%% | SL %.0fx credit",
        plan["wing_width"],
        plan["short_delta"],
        plan["min_dte"],
        plan["max_dte"],
        plan["take_profit_pct"] * 100,
        plan["stop_loss_pct"],
    )

    if dry or args.dry_run:
        logger.info("DRY RUN complete — no order submitted (use --execute-paper when ready)")
        print(json.dumps({"success": True, "dry_run": True, "plan_path": str(path)}, indent=2))
        return 0

    # Explicit paper execute path is intentionally conservative: require a
    # separate broker-submit implementation with mleg put vertical + gate.
    # Do not call legacy execute_credit_spread (SOFI/individual underlyings).
    logger.error(
        "Paper execute path not enabled in this scaffold. "
        "Dry-run planning is live; wire mleg put vertical via TradeGateway next."
    )
    return 3


if __name__ == "__main__":
    raise SystemExit(main())

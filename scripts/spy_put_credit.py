#!/usr/bin/env python3
"""SPY bull put credit — active validation system after IC Simple was KILLED.

Replaces 4-leg iron condors with a 2-leg defined-risk put credit:
  sell 1 SPY put + buy 1 lower put, 1-lot, paper only.

Usage:
  .venv/bin/python scripts/spy_put_credit.py --status
  .venv/bin/python scripts/spy_put_credit.py --dry-run
  .venv/bin/python scripts/spy_put_credit.py --execute-paper   # paper MLEG only
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("spy_put_credit")

ENTRIES_FILE = ROOT / "data" / "put_credit_entries.json"
AUDIT_DIR = ROOT / "data" / "audit"
SYSTEM_STATE = ROOT / "data" / "system_state.json"


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
        logger.warning("open_inventory_audit not available; treating inventory as clean")
        return True

    result = audit_from_files(
        ROOT,
        max_contracts_per_trade=float(MAX_CONTRACTS_PER_TRADE),
        max_concurrent_iron_condors=int(MAX_CONCURRENT_IRON_CONDORS),
    )
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    write_audit_report(result, AUDIT_DIR / "open_inventory_latest.json")
    if not result.clean:
        logger.error("UNCLEAN_INVENTORY — clean residual IC/orphan legs before put-credit entry")
        for reason in result.block_reasons()[:5]:
            logger.error("  - %s", reason)
        return False
    return True


def _get_paper_client():
    from src.utils.alpaca_client import get_alpaca_credentials

    key, secret = get_alpaca_credentials()
    if not key or not secret:
        raise RuntimeError("Alpaca paper credentials missing")
    from alpaca.trading.client import TradingClient

    return TradingClient(key, secret, paper=True)


def find_put_credit_opportunity(spy_price: float) -> dict | None:
    """Select put vertical via live delta; ignore call side of IC selector."""
    from src.markets.option_chain import select_strikes_by_delta

    profile = _load_profile()
    selection = select_strikes_by_delta(
        underlying_price=spy_price,
        wing_width=profile.wing_width,
        target_delta=profile.short_delta,
        target_dte=profile.target_dte,
        min_dte=profile.min_dte,
        max_dte=profile.max_dte,
    )
    if selection.method != "live_delta":
        logger.warning("Strike method %r is not live_delta — skip", selection.method)
        return None

    put_delta = abs(float(selection.put_delta or 0.0))
    if not (profile.delta_band_min <= put_delta <= profile.delta_band_max):
        logger.warning(
            "Put delta %.3f outside band %.2f-%.2f — skip",
            put_delta,
            profile.delta_band_min,
            profile.delta_band_max,
        )
        return None

    put_wing = round(float(selection.short_put) - float(selection.long_put), 2)
    if put_wing != profile.wing_width:
        logger.warning(
            "Put wing $%s != required $%s — skip", put_wing, profile.wing_width
        )
        return None

    # Put-side credit only (not full IC net credit)
    est_credit = round(float(selection.put_bid) - float(selection.long_put_ask), 2)
    if est_credit < profile.min_credit:
        logger.warning(
            "Put credit $%.2f < min $%.2f — skip", est_credit, profile.min_credit
        )
        return None

    opp = {
        "expiry": selection.expiry,
        "short_put": float(selection.short_put),
        "long_put": float(selection.long_put),
        "put_wing": put_wing,
        "est_credit": est_credit,
        "put_delta": put_delta,
        "method": selection.method,
        "quantity": profile.max_contracts_per_trade,
        "spy_price": spy_price,
    }
    logger.info(
        "Opportunity: SPY put credit short=%.0f long=%.0f credit=$%.2f delta=%.3f exp=%s",
        opp["short_put"],
        opp["long_put"],
        opp["est_credit"],
        opp["put_delta"],
        opp["expiry"],
    )
    return opp


def place_put_credit(client, opp: dict) -> str | None:
    """Submit 2-leg MLEG limit order for the bull put (paper client)."""
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest

    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    profile = _load_profile()
    expiry_yymmdd = str(opp["expiry"]).replace("-", "")[2:]

    def sym(strike: float) -> str:
        return f"SPY{expiry_yymmdd}P{int(strike * 1000):08d}"

    legs = [
        OptionLegRequest(symbol=sym(opp["long_put"]), side=OrderSide.BUY, ratio_qty=1),
        OptionLegRequest(symbol=sym(opp["short_put"]), side=OrderSide.SELL, ratio_qty=1),
    ]

    limit_credit = max(profile.min_credit, round(float(opp["est_credit"]) - 0.05, 2))
    walk = 0.0
    order_id = None
    while walk <= 0.20:
        current = round(limit_credit - walk, 2)
        if current < profile.min_credit:
            break
        logger.info("MLEG put credit limit >= $%.2f (walk $%.2f)", current, walk)
        try:
            order = safe_submit_order(
                client,
                LimitOrderRequest(
                    qty=int(opp.get("quantity") or 1),
                    order_class=OrderClass.MLEG,
                    legs=legs,
                    time_in_force=TimeInForce.DAY,
                    limit_price=round(-current, 2),
                    client_order_id=build_client_order_id("OPEN", "PCS"),
                ),
                strategy="spy_put_credit",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Put credit submit failed: %s", exc)
            return None
        order_id = str(order.id)
        logger.info("Order %s status=%s", order_id, order.status)
        # Brief wait for accept; full fill sync is handled by existing sync jobs.
        time.sleep(3)
        try:
            refreshed = client.get_order_by_id(order_id)
            status = str(getattr(refreshed, "status", "") or "")
            if "FILL" in status.upper() or "FILLED" in status.upper():
                break
            if "CANCEL" in status.upper() or "REJECT" in status.upper():
                walk += 0.05
                continue
            # accepted / new — stop walking
            break
        except Exception:
            break
        walk += 0.05

    if order_id:
        _record_entry(opp, order_id)
    return order_id


def _record_entry(opp: dict, order_id: str) -> None:
    entries: dict = {}
    if ENTRIES_FILE.exists():
        try:
            entries = json.loads(ENTRIES_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            entries = {}
    expiry_key = str(opp["expiry"]).replace("-", "")[2:]
    key = f"PCS_{expiry_key}"
    entries[key] = {
        "strategy_family": "spy_put_credit",
        "order_id": order_id,
        "entry_time": datetime.now(timezone.utc).isoformat(),
        "quantity": opp.get("quantity", 1),
        "credit": opp.get("est_credit"),
        "put_delta": opp.get("put_delta"),
        "selection_method": opp.get("method"),
        "strikes": {
            "short_put": opp["short_put"],
            "long_put": opp["long_put"],
        },
        "signature": (
            f"SPY_{opp['expiry']}_P{int(opp['long_put'])}-{int(opp['short_put'])}"
        ),
        "validation_phase": True,
        "profile_name": "spy-put-credit",
    }
    ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENTRIES_FILE.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    logger.info("Recorded %s in %s", key, ENTRIES_FILE)


def plan_structure(dry_run: bool = True, opp: dict | None = None) -> dict:
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
        "opportunity": opp,
    }
    return plan


def write_plan(plan: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "spy_put_credit_latest_plan.json"
    path.write_text(json.dumps(plan, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="SPY put credit validation (IC successor)")
    parser.add_argument("--dry-run", action="store_true", help="Plan only (default if no execute)")
    parser.add_argument(
        "--execute-paper",
        action="store_true",
        help="Submit paper MLEG put credit via TradeGateway",
    )
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--live", action="store_true", help="Always rejected while live_blocked")
    args = parser.parse_args()

    from src.core.active_strategy import load_kill_state
    from src.utils.options_analysis import get_underlying_price

    state = load_kill_state()
    logger.info("=" * 60)
    logger.info(
        "SPY PUT CREDIT | active=%s killed=%s",
        state.active_family,
        list(state.killed_families),
    )
    logger.info("=" * 60)

    if args.live:
        logger.error("LIVE BLOCKED until put-credit cohort clears kill criteria")
        return 2

    try:
        _assert_active()
    except RuntimeError as exc:
        logger.error("%s", exc)
        return 2

    if args.status:
        try:
            price = get_underlying_price("SPY")
        except Exception:
            price = None
        plan = plan_structure(dry_run=True)
        plan["spy_price"] = price
        path = write_plan(plan)
        print(
            json.dumps(
                {"kill_state": state.__dict__, "plan": plan, "plan_path": str(path)},
                indent=2,
                default=str,
            )
        )
        return 0

    if not _inventory_ok():
        return 2

    try:
        spy_price = float(get_underlying_price("SPY"))
    except Exception as exc:
        logger.error("Cannot get SPY price: %s", exc)
        return 1

    opp = find_put_credit_opportunity(spy_price)
    dry = not args.execute_paper
    plan = plan_structure(dry_run=dry, opp=opp)
    plan["spy_price"] = spy_price
    path = write_plan(plan)

    if opp is None:
        logger.warning("No valid put-credit opportunity right now")
        print(json.dumps({"success": False, "reason": "no_opportunity", "plan_path": str(path)}))
        return 1

    logger.info(
        "Policy: 1-lot $%.0f-wide put credit | Δ=%.2f | credit=$%.2f | TP %.0f%% | SL %.0fx",
        plan["wing_width"],
        opp["put_delta"],
        opp["est_credit"],
        plan["take_profit_pct"] * 100,
        plan["stop_loss_pct"],
    )

    if dry:
        logger.info("DRY RUN — no order (pass --execute-paper for paper MLEG)")
        print(
            json.dumps(
                {"success": True, "dry_run": True, "opportunity": opp, "plan_path": str(path)},
                indent=2,
                default=str,
            )
        )
        return 0

    if state.live_blocked:
        # paper is allowed; live is not — we always use paper client
        logger.info("Using paper TradingClient (live_blocked=%s)", state.live_blocked)

    try:
        client = _get_paper_client()
    except Exception as exc:
        logger.error("Paper client failed: %s", exc)
        return 1

    order_id = place_put_credit(client, opp)
    ok = order_id is not None
    print(
        json.dumps(
            {
                "success": ok,
                "dry_run": False,
                "order_id": order_id,
                "opportunity": opp,
                "plan_path": str(path),
            },
            indent=2,
            default=str,
        )
    )
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())

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
import re
import sys
import time
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("spy_put_credit")

ENTRIES_FILE = ROOT / "data" / "put_credit_entries.json"
AUDIT_DIR = ROOT / "data" / "audit"
SYSTEM_STATE = ROOT / "data" / "system_state.json"
CLOSED_ENTRY_STATES = {
    "closed",
    "cancelled",
    "canceled",
    "canceled_unfilled",
    "cancelled_unfilled",
    "rejected",
    "expired",
}
EASTERN = ZoneInfo("America/New_York")


def _load_profile():
    from src.core.trading_profiles import get_put_credit_profile

    return get_put_credit_profile()


def _assert_active() -> None:
    from src.core.active_strategy import assert_entry_allowed, load_kill_state

    assert_entry_allowed("spy_put_credit")
    state = load_kill_state()
    if state.live_blocked:
        logger.info("Live capital blocked by kill switch (paper validation only).")


def _inventory_ok(client: Any | None = None) -> bool:
    """Require broker-order reconstruction to explain every live option leg."""

    try:
        from scripts.residual_ic_manager import manage_residual_ics

        broker = client or _get_paper_client()
        result = manage_residual_ics(broker, dry_run=True)
    except Exception as exc:  # noqa: BLE001
        logger.error("BROKER_INVENTORY_UNVERIFIED — put-credit entry blocked: %s", exc)
        return False
    if result["broken"]:
        logger.error("UNCLEAN_INVENTORY — broker reconstruction has unexplained option legs")
        if result.get("unresolved"):
            logger.error("  - unresolved=%s", result["unresolved"])
        return False
    logger.info(
        "Broker inventory verified: residual_ics=%s pcs_legs=%s unresolved=0",
        result["reconciled"],
        len(result.get("pcs_inventory_excluded") or {}),
    )
    return True


def _get_paper_client():
    from src.utils.alpaca_client import get_alpaca_credentials

    key, secret = get_alpaca_credentials()
    if not key or not secret:
        raise RuntimeError("Alpaca paper credentials missing")
    from alpaca.trading.client import TradingClient

    return TradingClient(key, secret, paper=True)


def _load_entries() -> dict[str, dict[str, Any]]:
    if not ENTRIES_FILE.exists():
        return {}
    payload = json.loads(ENTRIES_FILE.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected object in {ENTRIES_FILE}")
    return {str(key): value for key, value in payload.items() if isinstance(value, dict)}


def _save_entries(entries: dict[str, dict[str, Any]]) -> None:
    ENTRIES_FILE.parent.mkdir(parents=True, exist_ok=True)
    temporary = ENTRIES_FILE.with_suffix(f"{ENTRIES_FILE.suffix}.tmp")
    temporary.write_text(json.dumps(entries, indent=2) + "\n", encoding="utf-8")
    temporary.replace(ENTRIES_FILE)


def _is_active_entry(entry: dict[str, Any]) -> bool:
    return str(entry.get("status") or "open").strip().lower() not in CLOSED_ENTRY_STATES


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def evaluate_entry_limits(
    entries: dict[str, dict[str, Any]],
    *,
    candidate_signature: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enforce one new structure/day, concurrency, and signature uniqueness."""

    profile = _load_profile()
    current = (now or datetime.now(UTC)).astimezone(EASTERN)
    active = {key: entry for key, entry in entries.items() if _is_active_entry(entry)}
    today_count = 0
    for entry in entries.values():
        entry_dt = _parse_timestamp(entry.get("entry_time"))
        if entry_dt and entry_dt.astimezone(EASTERN).date() == current.date():
            today_count += 1

    blockers: list[str] = []
    if len(active) >= profile.max_concurrent_positions:
        blockers.append(f"Concurrent put credits {len(active)}/{profile.max_concurrent_positions}.")
    if today_count >= profile.max_daily_structures:
        blockers.append(f"Daily put-credit limit {today_count}/{profile.max_daily_structures}.")
    if candidate_signature and any(
        str(entry.get("signature")) == candidate_signature for entry in active.values()
    ):
        blockers.append(f"Open put credit already uses signature {candidate_signature}.")

    return {
        "allowed": not blockers,
        "blockers": blockers,
        "active_count": len(active),
        "today_count": today_count,
        "max_concurrent": profile.max_concurrent_positions,
        "max_daily": profile.max_daily_structures,
    }


def _expiry_yymmdd(entry: dict[str, Any]) -> str:
    text = str(entry.get("expiry") or "").replace("-", "")
    if len(text) == 8 and text.startswith("20"):
        return text[2:]
    if len(text) == 6 and text.isdigit():
        return text
    signature = str(entry.get("signature") or "")
    match = re.search(r"SPY_(\d{4})-(\d{2})-(\d{2})_", signature)
    return "".join(match.groups())[2:] if match else ""


def _option_symbol(expiry_yymmdd: str, strike: float) -> str:
    return f"SPY{expiry_yymmdd}P{int(float(strike) * 1000):08d}"


def evaluate_put_credit_exit(
    entry: dict[str, Any],
    *,
    short_price: float,
    long_price: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Evaluate the fixed TP/SL/DTE lifecycle from current option marks."""

    profile = _load_profile()
    current = now or datetime.now(UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)
    expiry_yymmdd = _expiry_yymmdd(entry)
    if not expiry_yymmdd:
        raise ValueError("Put-credit journal entry has no parseable expiry")
    expiry = date(2000 + int(expiry_yymmdd[:2]), int(expiry_yymmdd[2:4]), int(expiry_yymmdd[4:6]))
    dte = (expiry - current.astimezone(EASTERN).date()).days
    credit = float(entry.get("credit") or entry.get("limit_credit") or 0.0)
    quantity = abs(int(float(entry.get("quantity") or 1)))
    current_debit = max(0.0, float(short_price) - float(long_price))
    pnl = (credit - current_debit) * 100 * quantity
    max_profit = credit * 100 * quantity
    entered = _parse_timestamp(entry.get("entry_time"))
    hold_hours = (current.astimezone(UTC) - entered).total_seconds() / 3600 if entered else None

    reason = None
    if dte <= 1:
        reason = "assignment_failsafe"
    elif dte <= profile.exit_dte:
        reason = "dte_exit"
    elif hold_hours is None:
        reason = None
    elif hold_hours >= profile.min_hold_hours:
        if pnl >= max_profit * profile.take_profit_pct:
            reason = "profit_target"
        elif pnl <= -(max_profit * profile.stop_loss_pct):
            reason = "stop_loss"

    result = {
        "should_exit": reason is not None,
        "exit_reason": reason,
        "dte": dte,
        "hold_hours": hold_hours,
        "credit": credit,
        "current_debit": current_debit,
        "estimated_pnl": pnl,
        "profit_target": max_profit * profile.take_profit_pct,
        "stop_loss": -(max_profit * profile.stop_loss_pct),
    }
    try:
        from src.risk.put_credit_regime import attach_counterfactuals

        result = attach_counterfactuals(result, credit=credit, quantity=quantity, dte=dte)
    except Exception as exc:  # noqa: BLE001
        logger.debug("counterfactual attach skipped: %s", exc)
    return result


def _position_map(client) -> dict[str, Any]:
    return {str(position.symbol): position for position in client.get_all_positions()}


def _position_price(position: Any) -> float:
    value = getattr(position, "current_price", None)
    if value is None:
        value = getattr(position, "avg_entry_price", 0.0)
    return float(value or 0.0)


def _position_qty(position: Any) -> float:
    return float(getattr(position, "qty", 0.0) or 0.0)


def _order_status_name(value: Any) -> str:
    return str(value or "").rsplit(".", 1)[-1].upper()


def _put_symbol_parts(symbol: Any) -> tuple[str, float] | None:
    match = re.fullmatch(r"SPY(\d{6})P(\d{8})", str(symbol or ""))
    if not match:
        return None
    return match.group(1), int(match.group(2)) / 1000


def _matching_plan_snapshot(
    *,
    expiry: str,
    long_put: float,
    short_put: float,
    order_time: datetime,
) -> dict[str, Any]:
    """Return exact pre-submit selection evidence when it matches the broker fill."""

    snapshot_dir = AUDIT_DIR / "put_credit_plans"
    paths = sorted(snapshot_dir.glob("*.json"), reverse=True) if snapshot_dir.exists() else []
    paths.append(AUDIT_DIR / "spy_put_credit_latest_plan.json")
    for path in paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        opportunity = payload.get("opportunity")
        if not isinstance(opportunity, dict):
            continue
        try:
            exact_structure = (
                str(opportunity.get("expiry")) == expiry
                and float(opportunity.get("long_put")) == long_put
                and float(opportunity.get("short_put")) == short_put
            )
        except (TypeError, ValueError):
            continue
        planned_at = _parse_timestamp(payload.get("planned_at"))
        if (
            not exact_structure
            or planned_at is None
            or not 0 <= (order_time - planned_at).total_seconds() <= 30 * 60
        ):
            continue
        return {
            "put_delta": opportunity.get("put_delta"),
            "put_delta_source": "execution_plan_snapshot",
            "selection_method": opportunity.get("method"),
            "selection_snapshot_planned_at": planned_at.isoformat(),
            "planned_credit": opportunity.get("est_credit"),
            "underlying_price_at_scan": opportunity.get("spy_price"),
        }
    return {}


def _filled_bps_legs(order_id: str, order: Any) -> tuple[Any, Any, str, float, float]:
    legs = list(getattr(order, "legs", None) or [])
    buys = [leg for leg in legs if _order_status_name(getattr(leg, "side", None)) == "BUY"]
    sells = [leg for leg in legs if _order_status_name(getattr(leg, "side", None)) == "SELL"]
    if len(legs) != 2 or len(buys) != 1 or len(sells) != 1:
        raise ValueError(f"{order_id}: filled BPS parent is not one buy plus one sell")

    long_parts = _put_symbol_parts(getattr(buys[0], "symbol", None))
    short_parts = _put_symbol_parts(getattr(sells[0], "symbol", None))
    if long_parts is None or short_parts is None or long_parts[0] != short_parts[0]:
        raise ValueError(f"{order_id}: filled BPS legs are not same-expiry SPY puts")
    expiry_yymmdd, long_put = long_parts
    _, short_put = short_parts
    if long_put >= short_put:
        raise ValueError(f"{order_id}: filled BPS strike direction is invalid")
    return buys[0], sells[0], expiry_yymmdd, long_put, short_put


def _filled_bps_quantity(order_id: str, order: Any) -> int:
    try:
        quantity = abs(int(float(getattr(order, "filled_qty", None) or order.qty)))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValueError(f"{order_id}: filled BPS quantity is invalid") from exc
    if quantity <= 0:
        raise ValueError(f"{order_id}: filled BPS quantity must be positive")
    return quantity


def _filled_bps_credit(order_id: str, order: Any, long_leg: Any, short_leg: Any) -> float:
    raw_fill = getattr(order, "filled_avg_price", None)
    try:
        parent_fill = float(raw_fill)
    except (TypeError, ValueError):
        parent_fill = 0.0
    if raw_fill not in (None, "") and parent_fill >= 0:
        raise ValueError(f"{order_id}: filled BPS parent is not a net credit")
    if parent_fill < 0:
        return abs(parent_fill)
    try:
        credit = float(short_leg.filled_avg_price) - float(long_leg.filled_avg_price)
    except (AttributeError, TypeError, ValueError):
        credit = 0.0
    if credit <= 0:
        raise ValueError(f"{order_id}: filled BPS credit is unavailable")
    return credit


def _recovered_put_credit_entry(order: Any) -> tuple[str, dict[str, Any]]:
    """Build a durable PCS entry from one authoritative filled parent order."""

    order_id = str(getattr(order, "id", "") or "")
    filled_at = _parse_timestamp(getattr(order, "filled_at", None))
    if not order_id or filled_at is None:
        raise ValueError("filled BPS order is missing order_id or filled_at")

    long_leg, short_leg, expiry_yymmdd, long_put, short_put = _filled_bps_legs(order_id, order)
    quantity = _filled_bps_quantity(order_id, order)
    credit = _filled_bps_credit(order_id, order, long_leg, short_leg)

    expiry = datetime.strptime(expiry_yymmdd, "%y%m%d").date().isoformat()
    signature = f"SPY_{expiry}_P{int(long_put)}-{int(short_put)}"
    safe_order_id = re.sub(r"[^A-Za-z0-9]", "", order_id) or "unknown"
    key = f"PCS_{expiry_yymmdd}_{safe_order_id}"
    submitted_at = _parse_timestamp(getattr(order, "submitted_at", None))
    plan = _matching_plan_snapshot(
        expiry=expiry,
        long_put=long_put,
        short_put=short_put,
        order_time=submitted_at or filled_at,
    )
    if not plan:
        plan = {
            "put_delta": None,
            "put_delta_source": "unavailable_after_broker_reconstruction",
            "selection_method": "broker_reconstructed_unverified",
        }

    limit_price = getattr(order, "limit_price", None)
    try:
        limit_credit = abs(float(limit_price)) if limit_price not in (None, "") else None
    except (TypeError, ValueError):
        limit_credit = None
    return key, {
        "strategy_family": "spy_put_credit",
        "structure": "bull_put_credit",
        "account_mode": "paper",
        "order_id": order_id,
        "client_order_id": str(getattr(order, "client_order_id", "") or ""),
        "entry_time": filled_at.isoformat(),
        "submitted_at": submitted_at.isoformat() if submitted_at else None,
        "filled_at": filled_at.isoformat(),
        "expiry": expiry,
        "quantity": quantity,
        "credit": round(credit, 4),
        "limit_credit": round(limit_credit, 4) if limit_credit is not None else None,
        "credit_source": "broker_fill",
        "fill_confirmed_at": filled_at.isoformat(),
        **plan,
        "strikes": {"short_put": short_put, "long_put": long_put},
        "signature": signature,
        "validation_phase": True,
        "profile_name": "spy-put-credit",
        "status": "open",
        "reconciled_at": datetime.now(UTC).isoformat(),
        "reconstruction_reason": "filled_broker_order_missing_durable_strategy_journal",
    }


def _entry_has_open_broker_legs(entry: dict[str, Any], positions: dict[str, Any]) -> bool:
    expiry = _expiry_yymmdd(entry)
    strikes = entry.get("strikes") or {}
    try:
        short = positions.get(_option_symbol(expiry, float(strikes["short_put"])))
        long = positions.get(_option_symbol(expiry, float(strikes["long_put"])))
        quantity = abs(float(entry.get("quantity") or 1))
    except (KeyError, TypeError, ValueError):
        return False
    return (
        short is not None
        and long is not None
        and _position_qty(short) <= -quantity
        and _position_qty(long) >= quantity
    )


def reconcile_put_credit_entries(client: Any, *, dry_run: bool = False) -> dict[str, Any]:
    """Recover missing PCS journals from our filled paper BPS parent orders."""

    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest
    from src.utils.order_intent import parse_client_order_id

    entries = _load_entries()
    existing_order_ids = {
        str(entry.get("order_id") or "")
        for entry in entries.values()
        if isinstance(entry, dict) and entry.get("order_id")
    }
    positions = _position_map(client)
    orders = list(
        client.get_orders(
            filter=GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                nested=True,
                after=datetime.now(UTC) - timedelta(days=120),
                limit=500,
            )
        )
    )
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "matched_filled_orders": 0,
        "existing": 0,
        "inactive_filled_orders": 0,
        "invalid_filled_orders": 0,
        "recovered": 0,
        "would_recover": 0,
        "broken": 0,
        "details": [],
    }
    changed = False
    for order in orders:
        parsed = parse_client_order_id(str(getattr(order, "client_order_id", "") or ""))
        if (
            not parsed
            or parsed["role"] != "OPEN"
            or parsed["intent"] != "BPS"
            or _order_status_name(getattr(order, "status", None)) != "FILLED"
        ):
            continue
        report["matched_filled_orders"] += 1
        order_id = str(getattr(order, "id", "") or "")
        if order_id in existing_order_ids:
            report["existing"] += 1
            continue
        try:
            key, entry = _recovered_put_credit_entry(order)
        except ValueError as exc:
            report["invalid_filled_orders"] += 1
            report["details"].append({"order_id": order_id, "status": "invalid", "error": str(exc)})
            continue
        if not _entry_has_open_broker_legs(entry, positions):
            report["inactive_filled_orders"] += 1
            report["details"].append(
                {"order_id": order_id, "key": key, "status": "no_open_broker_structure"}
            )
            continue
        if dry_run:
            report["would_recover"] += 1
            report["details"].append({"order_id": order_id, "key": key, "status": "would_recover"})
            continue
        entries[key] = entry
        existing_order_ids.add(order_id)
        changed = True
        report["recovered"] += 1
        report["details"].append({"order_id": order_id, "key": key, "status": "recovered"})

    if changed:
        _save_entries(entries)
    return report


def _confirm_entry_credit(client, entry: dict[str, Any], short_pos: Any, long_pos: Any) -> bool:
    if entry.get("credit_source") == "broker_fill":
        return False
    order_id = str(entry.get("order_id") or "")
    if order_id:
        try:
            order = client.get_order_by_id(order_id)
            fill = getattr(order, "filled_avg_price", None)
            if fill not in (None, ""):
                entry["credit"] = abs(float(fill))
                entry["credit_source"] = "broker_fill"
                entry["fill_confirmed_at"] = datetime.now(UTC).isoformat()
                entry["status"] = "open"
                return True
        except Exception as exc:
            logger.warning("Could not confirm put-credit fill from order %s: %s", order_id, exc)
    short_entry = float(getattr(short_pos, "avg_entry_price", 0.0) or 0.0)
    long_entry = float(getattr(long_pos, "avg_entry_price", 0.0) or 0.0)
    derived = short_entry - long_entry
    if derived > 0:
        entry["credit"] = derived
        entry["credit_source"] = "broker_position_derived"
        entry["fill_confirmed_at"] = datetime.now(UTC).isoformat()
        entry["status"] = "open"
        return True
    return False


def _pending_exit_is_active(client, entry: dict[str, Any]) -> bool:
    exit_order_id = str(entry.get("exit_order_id") or "")
    if not exit_order_id:
        return False
    try:
        order = client.get_order_by_id(exit_order_id)
        status = _order_status_name(getattr(order, "status", ""))
    except Exception:
        return True
    if status == "FILLED":
        entry["status"] = "closed"
        entry["exit_filled_at"] = datetime.now(UTC).isoformat()
        return True
    if status in {"CANCELED", "CANCELLED", "REJECTED", "EXPIRED"}:
        entry["status"] = "open"
        entry.pop("exit_order_id", None)
        return False
    return True


def _entry_order_status(client, entry: dict[str, Any]) -> str:
    order_id = str(entry.get("order_id") or "")
    if not order_id:
        return "UNKNOWN"
    try:
        order = client.get_order_by_id(order_id)
    except Exception:
        return "UNKNOWN"
    return _order_status_name(getattr(order, "status", ""))


def _submit_orphan_close(client, position: Any):
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest
    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    qty = _position_qty(position)
    is_short = qty < 0
    intent = "BPS" if is_short else "BPL"
    leg_tag = "SP" if is_short else "LP"
    return safe_submit_order(
        client,
        MarketOrderRequest(
            symbol=str(position.symbol),
            qty=abs(qty),
            side=OrderSide.BUY if qty < 0 else OrderSide.SELL,
            time_in_force=TimeInForce.DAY,
            client_order_id=build_client_order_id("CLOSE", intent, leg_tag),
        ),
        strategy="spy_put_credit",
    )


def _submit_spread_close(client, entry: dict[str, Any], decision: dict[str, Any]):
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    expiry = _expiry_yymmdd(entry)
    strikes = entry["strikes"]
    legs = [
        OptionLegRequest(
            symbol=_option_symbol(expiry, float(strikes["short_put"])),
            side=OrderSide.BUY,
            ratio_qty=1,
        ),
        OptionLegRequest(
            symbol=_option_symbol(expiry, float(strikes["long_put"])),
            side=OrderSide.SELL,
            ratio_qty=1,
        ),
    ]
    profile = _load_profile()
    limit_debit = min(
        profile.wing_width,
        max(0.01, round(float(decision["current_debit"]) + 0.05, 2)),
    )
    return safe_submit_order(
        client,
        LimitOrderRequest(
            qty=abs(int(float(entry.get("quantity") or 1))),
            order_class=OrderClass.MLEG,
            legs=legs,
            time_in_force=TimeInForce.DAY,
            limit_price=limit_debit,
            client_order_id=build_client_order_id("CLOSE", "BPS"),
        ),
        strategy="spy_put_credit",
    )


def manage_put_credit_exits(client, *, dry_run: bool = False) -> dict[str, Any]:
    """Manage every journaled PCS without duplicating pending close orders."""

    entries = _load_entries()
    positions = _position_map(client)
    report: dict[str, Any] = {
        "checked": 0,
        "holds": 0,
        "would_exit": 0,
        "submitted": 0,
        "pending": 0,
        "broken": 0,
        "details": [],
    }
    changed = False

    for key, entry in entries.items():
        if not _is_active_entry(entry):
            continue
        report["checked"] += 1
        expiry = _expiry_yymmdd(entry)
        strikes = entry.get("strikes") or {}
        try:
            short_symbol = _option_symbol(expiry, float(strikes["short_put"]))
            long_symbol = _option_symbol(expiry, float(strikes["long_put"]))
        except (KeyError, TypeError, ValueError):
            report["broken"] += 1
            report["details"].append({"key": key, "status": "invalid_journal"})
            continue
        short_pos = positions.get(short_symbol)
        long_pos = positions.get(long_symbol)
        if str(entry.get("status")) == "exit_pending" and _pending_exit_is_active(client, entry):
            changed = True
            report["pending"] += 1
            report["details"].append({"key": key, "status": "exit_pending"})
            continue
        if short_pos is None or long_pos is None:
            entry_status = _entry_order_status(client, entry)
            if (
                short_pos is None
                and long_pos is None
                and any(state in entry_status for state in ("NEW", "ACCEPT", "PENDING", "HELD"))
            ):
                entry["status"] = "entry_pending"
                changed = True
                report["pending"] += 1
                report["details"].append({"key": key, "status": "entry_pending"})
                continue
            if (
                short_pos is None
                and long_pos is None
                and any(state in entry_status for state in ("CANCEL", "REJECT", "EXPIRE"))
            ):
                entry["status"] = "rejected"
                entry["entry_terminal_status"] = entry_status
                changed = True
                report["details"].append({"key": key, "status": "entry_rejected"})
                continue
            entry["status"] = "broken_structure"
            entry["last_error"] = (
                f"Expected legs absent: short_present={short_pos is not None}, "
                f"long_present={long_pos is not None}"
            )
            changed = True
            report["broken"] += 1
            logger.error("%s: %s", key, entry["last_error"])
            orphan = short_pos if short_pos is not None else long_pos
            if orphan is not None:
                if dry_run:
                    report["would_exit"] += 1
                    report["details"].append(
                        {"key": key, "status": "would_close_orphan", "symbol": orphan.symbol}
                    )
                    continue
                order = _submit_orphan_close(client, orphan)
                entry["status"] = "exit_pending"
                entry["exit_reason"] = "orphan_cleanup"
                entry["exit_order_id"] = str(order.id)
                entry["exit_submitted_at"] = datetime.now(UTC).isoformat()
                _save_entries(entries)
                report["submitted"] += 1
                report["details"].append(
                    {
                        "key": key,
                        "status": "orphan_close_submitted",
                        "symbol": orphan.symbol,
                        "order_id": str(order.id),
                    }
                )
                continue
            report["details"].append({"key": key, "status": "broken_structure"})
            continue
        if _position_qty(short_pos) >= 0 or _position_qty(long_pos) <= 0:
            report["broken"] += 1
            report["details"].append({"key": key, "status": "wrong_leg_direction"})
            continue
        if _confirm_entry_credit(client, entry, short_pos, long_pos):
            changed = True
        decision = evaluate_put_credit_exit(
            entry,
            short_price=_position_price(short_pos),
            long_price=_position_price(long_pos),
        )
        # Greptile #4280 P1: persist counterfactuals on the journal so cohort
        # analysis can compare 25% TP / 7-DTE vs public 50% / 21-DTE later.
        if isinstance(decision.get("counterfactuals"), dict):
            entry["last_counterfactuals"] = decision["counterfactuals"]
            entry["last_counterfactuals_at"] = datetime.now(UTC).isoformat()
            entry["last_mark"] = {
                "current_debit": decision.get("current_debit"),
                "estimated_pnl": decision.get("estimated_pnl"),
                "dte": decision.get("dte"),
                "hold_hours": decision.get("hold_hours"),
            }
            changed = True
        detail = {"key": key, **decision}
        if not decision["should_exit"]:
            report["holds"] += 1
            detail["status"] = "hold"
            report["details"].append(detail)
            continue
        if dry_run:
            report["would_exit"] += 1
            detail["status"] = "would_exit"
            report["details"].append(detail)
            continue

        order = _submit_spread_close(client, entry, decision)
        entry["status"] = "exit_pending"
        entry["exit_reason"] = decision["exit_reason"]
        entry["exit_order_id"] = str(order.id)
        entry["exit_submitted_at"] = datetime.now(UTC).isoformat()
        entry["estimated_exit_debit"] = decision["current_debit"]
        entry["estimated_exit_pnl"] = decision["estimated_pnl"]
        if isinstance(decision.get("counterfactuals"), dict):
            entry["exit_counterfactuals"] = decision["counterfactuals"]
        _save_entries(entries)
        changed = True
        report["submitted"] += 1
        detail["status"] = "exit_submitted"
        detail["order_id"] = str(order.id)
        report["details"].append(detail)

    if changed:
        _save_entries(entries)
    return report


def _friday_expiries(min_dte: int, max_dte: int, target_dte: int) -> list[str]:
    """Candidate Friday expiries in [min_dte, max_dte], target first."""
    today = datetime.now(UTC).date()
    fridays: list[tuple[int, str]] = []
    # walk ~10 weeks forward
    d = today
    for _ in range(80):
        d = d + timedelta(days=1)
        if d.weekday() != 4:  # Friday
            continue
        dte = (d - today).days
        if dte < min_dte:
            continue
        if dte > max_dte:
            break
        fridays.append((abs(dte - target_dte), d.isoformat()))
    fridays.sort(key=lambda x: x[0])
    return [exp for _, exp in fridays]


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _scan_put_credit_candidates(
    expiry: str,
    options: list[dict[str, Any]],
    profile: Any,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Return policy-qualified candidates and the best sub-minimum candidate."""
    puts: dict[float, dict[str, Any]] = {}
    for option in options:
        if option.get("type") != "put" or option.get("expiration") != expiry:
            continue
        strike = _as_float(option.get("strike"))
        if strike is not None:
            puts[strike] = option

    candidates: list[dict[str, Any]] = []
    best_sub_min: dict[str, Any] | None = None
    for short_strike, short in puts.items():
        delta = _as_float(short.get("delta"))
        short_bid = _as_float(short.get("bid"))
        if delta is None or short_bid is None or short_bid < 0.05:
            continue

        put_delta = abs(delta)
        if not (profile.delta_band_min <= put_delta <= profile.delta_band_max):
            continue

        long_strike = round(short_strike - float(profile.wing_width), 2)
        long_option = puts.get(long_strike)
        long_ask = _as_float(long_option.get("ask")) if long_option else None
        if long_ask is None or long_ask <= 0:
            continue

        est_credit = round(short_bid - long_ask, 2)
        if est_credit <= 0:
            continue
        row = {
            "expiry": expiry,
            "short_put": short_strike,
            "long_put": long_strike,
            "put_wing": float(profile.wing_width),
            "est_credit": est_credit,
            "put_delta": put_delta,
            "method": "live_delta_band_scan",
            "quantity": profile.max_contracts_per_trade,
            "spy_price": None,
            "delta_distance": abs(put_delta - float(profile.short_delta)),
        }
        if est_credit >= profile.min_credit:
            candidates.append(row)
        elif best_sub_min is None or est_credit > best_sub_min["est_credit"]:
            best_sub_min = row
    return candidates, best_sub_min


def find_put_credit_opportunity(spy_price: float) -> dict | None:
    """Scan live put chain for $5-wide bull put credits in the policy delta band.

    Unlike the IC dual-side selector (which often yields thin put-only credits at
    exactly 15Δ), this searches the full put delta band and prefers candidates
    that clear min_credit, then closest to target_delta, then higher credit.
    """
    from src.data.iv_data_provider import IVDataProvider

    profile = _load_profile()
    provider = IVDataProvider()
    band_lo = float(profile.delta_band_min)
    band_hi = float(profile.delta_band_max)
    min_credit = float(profile.min_credit)

    candidates: list[dict] = []
    best_sub_min: dict | None = None
    try:
        # IVDataProvider currently fetches the complete Alpaca chain before
        # filtering. Fetch once, then partition locally instead of repeating the
        # same network request for every expiry and delta slice.
        options = provider.get_options_chain_with_greeks(
            symbol=profile.underlying,
            min_open_interest=0,
        )
    except Exception as exc:
        logger.warning("Chain fetch failed: %s", exc)
        return None

    for expiry in _friday_expiries(profile.min_dte, profile.max_dte, profile.target_dte):
        expiry_candidates, expiry_sub_min = _scan_put_credit_candidates(
            expiry,
            options,
            profile,
        )
        for row in expiry_candidates:
            row["spy_price"] = spy_price
        candidates.extend(expiry_candidates)
        if expiry_sub_min and (
            best_sub_min is None or expiry_sub_min["est_credit"] > best_sub_min["est_credit"]
        ):
            expiry_sub_min["spy_price"] = spy_price
            best_sub_min = expiry_sub_min

    if not candidates:
        if best_sub_min:
            logger.warning(
                "Best put credit in band $%.2f < min $%.2f (short=%.0f Δ=%.3f exp=%s) — skip",
                best_sub_min["est_credit"],
                min_credit,
                best_sub_min["short_put"],
                best_sub_min["put_delta"],
                best_sub_min["expiry"],
            )
        else:
            logger.warning("No put verticals found in delta band %.2f-%.2f", band_lo, band_hi)
        return None

    # Prefer higher natural credit (fillability), then closer to target delta.
    # Prior delta-first ranking often picked thin OTMs with est_credit inflated vs book.
    qualified = [r for r in candidates if float(r.get("est_credit") or 0) >= min_credit]
    pool = qualified or candidates
    pool.sort(key=lambda r: (-float(r["est_credit"]), r["delta_distance"]))
    opp = pool[0]
    opp.pop("delta_distance", None)
    logger.info(
        "Opportunity: SPY put credit short=%.0f long=%.0f credit=$%.2f delta=%.3f exp=%s "
        "(scanned %d band-qualified, %d min-credit-qualified)",
        opp["short_put"],
        opp["long_put"],
        opp["est_credit"],
        opp["put_delta"],
        opp["expiry"],
        len(candidates),
        len(qualified),
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

    # Start near natural credit (est_credit is short_bid - long_ask), not above book.
    limit_credit = max(profile.min_credit, round(float(opp["est_credit"]), 2))
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
                    client_order_id=build_client_order_id("OPEN", "BPS"),
                ),
                strategy="spy_put_credit",
            )
        except Exception as exc:  # noqa: BLE001
            logger.error("Put credit submit failed: %s", exc)
            return None
        order_id = str(order.id)
        logger.info("Order %s status=%s", order_id, order.status)
        # Wait briefly for fill; unfilled NEW/ACCEPTED blocks concurrent slots forever.
        time.sleep(4)
        try:
            refreshed = client.get_order_by_id(order_id)
            status = _order_status_name(getattr(refreshed, "status", ""))
            filled_qty = float(getattr(refreshed, "filled_qty", 0) or 0)
            if status == "FILLED" or filled_qty > 0:
                break
            if status in {"CANCELED", "CANCELLED", "REJECTED", "EXPIRED"}:
                order_id = None
                walk += 0.05
                continue
            # Resting unfilled: cancel and walk credit down (still >= min_credit)
            try:
                client.cancel_order_by_id(order_id)
                logger.warning(
                    "Canceled unfilled put-credit order %s at limit $%.2f; walking credit down",
                    order_id,
                    current,
                )
            except Exception as cancel_exc:  # noqa: BLE001
                logger.warning("Cancel unfilled %s failed: %s", order_id, cancel_exc)
            order_id = None
            walk += 0.05
            continue
        except Exception:
            break
        walk += 0.05

    if order_id:
        _record_entry(opp, order_id)
    return order_id


def _record_entry(opp: dict, order_id: str) -> None:
    entries = _load_entries()
    expiry_key = str(opp["expiry"]).replace("-", "")[2:]
    safe_order_id = re.sub(r"[^A-Za-z0-9]", "", str(order_id)) or "unknown"
    key = f"PCS_{expiry_key}_{safe_order_id}"
    if key in entries and entries[key].get("order_id") != order_id:
        raise RuntimeError(f"Put-credit journal identity collision for {key}")
    signature = f"SPY_{opp['expiry']}_P{int(opp['long_put'])}-{int(opp['short_put'])}"
    regime = opp.get("regime") if isinstance(opp.get("regime"), dict) else None
    if regime is None:
        try:
            from src.risk.put_credit_regime import capture_regime_snapshot

            regime = capture_regime_snapshot(
                float(opp["spy_price"]) if opp.get("spy_price") is not None else None
            ).as_dict()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Regime snapshot at journal failed: %s", exc)
            regime = {"error": str(exc)}
    entries[key] = {
        "strategy_family": "spy_put_credit",
        "order_id": order_id,
        "entry_time": datetime.now(UTC).isoformat(),
        "expiry": opp["expiry"],
        "quantity": opp.get("quantity", 1),
        "credit": opp.get("est_credit"),
        "limit_credit": opp.get("est_credit"),
        "credit_source": "limit_estimate_unconfirmed",
        "put_delta": opp.get("put_delta"),
        "selection_method": opp.get("method"),
        "strikes": {
            "short_put": opp["short_put"],
            "long_put": opp["long_put"],
        },
        "signature": signature,
        "validation_phase": True,
        "profile_name": "spy-put-credit",
        "status": "submitted_unconfirmed",
        "regime": regime,
    }
    _save_entries(entries)
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
        "planned_at": datetime.now(UTC).isoformat(),
        "status": "planned",
        "opportunity": opp,
    }
    return plan


def write_plan(plan: dict) -> Path:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    path = AUDIT_DIR / "spy_put_credit_latest_plan.json"
    serialized = json.dumps(plan, indent=2, default=str) + "\n"
    path.write_text(serialized, encoding="utf-8")
    opportunity = plan.get("opportunity")
    if plan.get("dry_run") is False and isinstance(opportunity, dict):
        planned_at = str(plan.get("planned_at") or datetime.now(UTC).isoformat())
        timestamp = re.sub(r"[^0-9]", "", planned_at)[:20] or str(time.time_ns())
        expiry = re.sub(r"[^0-9]", "", str(opportunity.get("expiry") or "unknown"))
        long_put = re.sub(r"[^0-9]", "", str(opportunity.get("long_put") or "unknown"))
        short_put = re.sub(r"[^0-9]", "", str(opportunity.get("short_put") or "unknown"))
        snapshot_dir = AUDIT_DIR / "put_credit_plans"
        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot = snapshot_dir / f"{timestamp}_SPY_{expiry}_P{long_put}-{short_put}.json"
        if not snapshot.exists():
            snapshot.write_text(serialized, encoding="utf-8")
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
    parser.add_argument(
        "--cohort",
        action="store_true",
        help="Print put-credit validation cohort scorecard (edge truth)",
    )
    parser.add_argument(
        "--manage-exits",
        action="store_true",
        help="Evaluate and submit paper exits for open put credits.",
    )
    parser.add_argument(
        "--reconcile-entries",
        action="store_true",
        help="Recover missing PCS journals from filled paper BPS orders.",
    )
    parser.add_argument(
        "--ignore-regime-gate",
        action="store_true",
        help="Bypass IVR/VIX regime entry gate (paper debug only; still paper-only).",
    )
    parser.add_argument(
        "--regime-status",
        action="store_true",
        help="Print current regime snapshot and gate decision only.",
    )
    parser.add_argument("--live", action="store_true", help="Always rejected while live_blocked")
    parser.add_argument(
        "--skip-production-gate",
        action="store_true",
        help="Bypass ops production gate (debug only; still paper-only / kill switch)",
    )
    parser.add_argument(
        "--production-gate",
        action="store_true",
        help="Print production gate JSON and exit (0=ops ok for new paper risk)",
    )
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

    # Production gate: halt, family, inventory, broker freshness (ops A+ control plane)
    if args.production_gate or not args.skip_production_gate:
        try:
            from src.risk.production_gate import evaluate_production_gate

            pg = evaluate_production_gate(for_live=False)
            if args.production_gate:
                print(json.dumps(pg.to_dict(), indent=2, default=str))
                return 0 if pg.allow_new_risk else 2
            if not args.skip_production_gate and not pg.allow_new_risk:
                # Allow status/cohort/reconcile/manage without blocking
                status_only = (
                    args.status
                    or args.cohort
                    or args.reconcile_entries
                    or args.manage_exits
                    or args.regime_status
                    or args.dry_run
                )
                if not status_only:
                    logger.error(
                        "PRODUCTION GATE blocked new risk: grade=%s blockers=%s",
                        pg.grade,
                        pg.blockers,
                    )
                    print(json.dumps(pg.to_dict(), indent=2, default=str))
                    return 2
                logger.warning(
                    "PRODUCTION GATE: allow_new_risk=false grade=%s blockers=%s "
                    "(continuing because status/dry-run path)",
                    pg.grade,
                    pg.blockers,
                )
            else:
                logger.info(
                    "PRODUCTION GATE ok grade=%s score=%s allow_new_risk=%s",
                    pg.grade,
                    pg.score_0_10,
                    pg.allow_new_risk,
                )
        except Exception as exc:  # noqa: BLE001
            logger.warning("PRODUCTION GATE evaluation failed (non-fatal for status): %s", exc)
            if not (
                args.status
                or args.cohort
                or args.reconcile_entries
                or args.manage_exits
                or args.regime_status
                or args.dry_run
                or args.skip_production_gate
            ):
                return 2

    if args.reconcile_entries:
        try:
            client = _get_paper_client()
        except Exception as exc:
            logger.error("Paper client failed: %s", exc)
            return 1
        report = reconcile_put_credit_entries(client, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, default=str))
        return 2 if report["broken"] else 0

    if args.cohort:
        from scripts.put_credit_cohort_scorecard import build_scorecard

        card = build_scorecard()
        print(json.dumps(card, indent=2, default=str))
        return 0

    if args.status:
        try:
            price = get_underlying_price("SPY")
        except Exception:
            price = None
        plan = plan_structure(dry_run=True)
        plan["spy_price"] = price
        path = write_plan(plan)
        try:
            from scripts.put_credit_cohort_scorecard import build_scorecard

            cohort = build_scorecard()
        except Exception as exc:  # noqa: BLE001
            cohort = {"error": str(exc)}
        print(
            json.dumps(
                {
                    "kill_state": state.__dict__,
                    "plan": plan,
                    "plan_path": str(path),
                    "cohort": cohort,
                },
                indent=2,
                default=str,
            )
        )
        return 0

    if args.manage_exits:
        try:
            client = _get_paper_client()
        except Exception as exc:
            logger.error("Paper client failed: %s", exc)
            return 1
        report = manage_put_credit_exits(client, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, default=str))
        return 2 if report["broken"] else 0

    if args.regime_status:
        try:
            price = float(get_underlying_price("SPY"))
        except Exception:
            price = None
        from src.risk.put_credit_regime import capture_regime_snapshot, evaluate_regime_gate

        snap = capture_regime_snapshot(price)
        gate = evaluate_regime_gate(snap)
        print(json.dumps(gate, indent=2, default=str))
        return 0 if gate["allowed"] else 2

    if not _inventory_ok():
        return 2

    limit_report = evaluate_entry_limits(_load_entries())
    if not limit_report["allowed"]:
        logger.error("PUT-CREDIT ENTRY LIMIT: %s", " | ".join(limit_report["blockers"]))
        print(json.dumps(limit_report, indent=2))
        return 2

    try:
        spy_price = float(get_underlying_price("SPY"))
    except Exception as exc:
        logger.error("Cannot get SPY price: %s", exc)
        return 1

    # Research-backed regime gate (IVR / VIX) before scanning or submitting.
    from src.risk.put_credit_regime import capture_regime_snapshot, evaluate_regime_gate

    regime_snap = capture_regime_snapshot(spy_price)
    regime_gate = evaluate_regime_gate(regime_snap)
    if not regime_gate["allowed"] and not args.ignore_regime_gate:
        logger.error(
            "PUT-CREDIT REGIME GATE BLOCKED: %s",
            " | ".join(regime_gate["blockers"]),
        )
        print(
            json.dumps(
                {
                    "success": False,
                    "reason": "regime_gate_blocked",
                    "regime": regime_gate,
                },
                indent=2,
                default=str,
            )
        )
        return 2
    if regime_gate.get("soft_flags"):
        logger.warning("Regime soft flags: %s", " | ".join(regime_gate["soft_flags"]))
    if args.ignore_regime_gate and not regime_gate["allowed"]:
        logger.warning(
            "Ignoring regime gate blockers (debug): %s",
            " | ".join(regime_gate["blockers"]),
        )

    opp = find_put_credit_opportunity(spy_price)
    if isinstance(opp, dict):
        opp["spy_price"] = spy_price
        opp["regime"] = regime_snap.as_dict()
        opp["regime_gate"] = {
            "allowed": regime_gate["allowed"],
            "blockers": regime_gate["blockers"],
            "soft_flags": regime_gate["soft_flags"],
            "thresholds": regime_gate["thresholds"],
        }
    dry = not args.execute_paper
    plan = plan_structure(dry_run=dry, opp=opp)
    plan["spy_price"] = spy_price
    plan["regime"] = regime_snap.as_dict()
    plan["regime_gate"] = regime_gate
    path = write_plan(plan)

    if opp is None:
        logger.warning("No valid put-credit opportunity right now")
        print(json.dumps({"success": False, "reason": "no_opportunity", "plan_path": str(path)}))
        return 1

    signature = f"SPY_{opp['expiry']}_P{int(opp['long_put'])}-{int(opp['short_put'])}"
    limit_report = evaluate_entry_limits(_load_entries(), candidate_signature=signature)
    if not limit_report["allowed"]:
        logger.error("PUT-CREDIT ENTRY LIMIT: %s", " | ".join(limit_report["blockers"]))
        print(json.dumps(limit_report, indent=2))
        return 2

    logger.info(
        "Policy: 1-lot $%.0f-wide put credit | Δ=%.2f | credit=$%.2f | TP %.0f%% | SL %.0fx | "
        "IVR=%s VIX=%s",
        plan["wing_width"],
        opp["put_delta"],
        opp["est_credit"],
        plan["take_profit_pct"] * 100,
        plan["stop_loss_pct"],
        regime_snap.iv_rank_proxy,
        regime_snap.vix,
    )

    if dry:
        logger.info("DRY RUN — no order (pass --execute-paper for paper MLEG)")
        print(
            json.dumps(
                {
                    "success": True,
                    "dry_run": True,
                    "opportunity": opp,
                    "regime": regime_gate,
                    "plan_path": str(path),
                },
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

    from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock

    try:
        with acquire_trade_lock(timeout=10):
            if not _inventory_ok(client):
                return 2
            # Re-check regime under lock (stale window)
            regime_snap2 = capture_regime_snapshot(spy_price)
            regime_gate2 = evaluate_regime_gate(regime_snap2)
            if not regime_gate2["allowed"] and not args.ignore_regime_gate:
                logger.error(
                    "PUT-CREDIT REGIME GATE BLOCKED after lock: %s",
                    " | ".join(regime_gate2["blockers"]),
                )
                return 2
            opp["regime"] = regime_snap2.as_dict()
            limit_report = evaluate_entry_limits(_load_entries(), candidate_signature=signature)
            if not limit_report["allowed"]:
                logger.error(
                    "PUT-CREDIT ENTRY LIMIT after lock: %s",
                    " | ".join(limit_report["blockers"]),
                )
                return 2
            order_id = place_put_credit(client, opp)
    except TradeLockTimeout as exc:
        logger.warning("Put-credit entry lock unavailable: %s", exc)
        return 2
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

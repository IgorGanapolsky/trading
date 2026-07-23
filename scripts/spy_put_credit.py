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
from datetime import date, datetime, timedelta, timezone
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
CLOSED_ENTRY_STATES = {"closed", "cancelled", "rejected"}
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
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def evaluate_entry_limits(
    entries: dict[str, dict[str, Any]],
    *,
    candidate_signature: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Enforce one new structure/day, concurrency, and signature uniqueness."""

    profile = _load_profile()
    current = (now or datetime.now(timezone.utc)).astimezone(EASTERN)
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
    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
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
    hold_hours = (
        (current.astimezone(timezone.utc) - entered).total_seconds() / 3600 if entered else None
    )

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

    return {
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
    filled_at: datetime,
) -> dict[str, Any]:
    """Return exact pre-submit selection evidence when it matches the broker fill."""

    path = AUDIT_DIR / "spy_put_credit_latest_plan.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    opportunity = payload.get("opportunity")
    if not isinstance(opportunity, dict):
        return {}
    try:
        exact_structure = (
            str(opportunity.get("expiry")) == expiry
            and float(opportunity.get("long_put")) == long_put
            and float(opportunity.get("short_put")) == short_put
        )
    except (TypeError, ValueError):
        return {}
    planned_at = _parse_timestamp(payload.get("planned_at"))
    if not exact_structure or planned_at is None:
        return {}
    if abs((filled_at - planned_at).total_seconds()) > 30 * 60:
        return {}
    return {
        "put_delta": opportunity.get("put_delta"),
        "put_delta_source": "execution_plan_snapshot",
        "selection_method": opportunity.get("method"),
        "selection_snapshot_planned_at": planned_at.isoformat(),
        "planned_credit": opportunity.get("est_credit"),
        "underlying_price_at_scan": opportunity.get("spy_price"),
    }


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

    long_leg, short_leg, expiry_yymmdd, long_put, short_put = _filled_bps_legs(
        order_id, order
    )
    quantity = _filled_bps_quantity(order_id, order)
    credit = _filled_bps_credit(order_id, order, long_leg, short_leg)

    expiry = datetime.strptime(expiry_yymmdd, "%y%m%d").date().isoformat()
    signature = f"SPY_{expiry}_P{int(long_put)}-{int(short_put)}"
    safe_order_id = re.sub(r"[^A-Za-z0-9]", "", order_id) or "unknown"
    key = f"PCS_{expiry_yymmdd}_{safe_order_id}"
    plan = _matching_plan_snapshot(
        expiry=expiry,
        long_put=long_put,
        short_put=short_put,
        filled_at=filled_at,
    )
    if not plan:
        plan = {
            "put_delta": None,
            "put_delta_source": "unavailable_after_broker_reconstruction",
            "selection_method": "broker_reconstructed_unverified",
        }

    submitted_at = _parse_timestamp(getattr(order, "submitted_at", None))
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
        "reconciled_at": datetime.now(timezone.utc).isoformat(),
        "reconstruction_reason": "filled_broker_order_missing_durable_strategy_journal",
    }


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
    orders = list(
        client.get_orders(
            filter=GetOrdersRequest(
                status=QueryOrderStatus.ALL,
                nested=True,
                after=datetime.now(timezone.utc) - timedelta(days=120),
                limit=500,
            )
        )
    )
    report: dict[str, Any] = {
        "dry_run": dry_run,
        "matched_filled_orders": 0,
        "existing": 0,
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
            report["broken"] += 1
            report["details"].append({"order_id": order_id, "status": "invalid", "error": str(exc)})
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
                entry["fill_confirmed_at"] = datetime.now(timezone.utc).isoformat()
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
        entry["fill_confirmed_at"] = datetime.now(timezone.utc).isoformat()
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
        entry["exit_filled_at"] = datetime.now(timezone.utc).isoformat()
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
                entry["exit_submitted_at"] = datetime.now(timezone.utc).isoformat()
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
        entry["exit_submitted_at"] = datetime.now(timezone.utc).isoformat()
        entry["estimated_exit_debit"] = decision["current_debit"]
        entry["estimated_exit_pnl"] = decision["estimated_pnl"]
        _save_entries(entries)
        changed = True
        report["submitted"] += 1
        detail["status"] = "exit_submitted"
        detail["order_id"] = str(order.id)
        report["details"].append(detail)

    if changed:
        _save_entries(entries)
    return report


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
        logger.warning("Put wing $%s != required $%s — skip", put_wing, profile.wing_width)
        return None

    # Put-side credit only (not full IC net credit)
    est_credit = round(float(selection.put_bid) - float(selection.long_put_ask), 2)
    if est_credit < profile.min_credit:
        logger.warning("Put credit $%.2f < min $%.2f — skip", est_credit, profile.min_credit)
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
                    client_order_id=build_client_order_id("OPEN", "BPS"),
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
            status = _order_status_name(getattr(refreshed, "status", ""))
            if status == "FILLED":
                break
            if status in {"CANCELED", "CANCELLED", "REJECTED", "EXPIRED"}:
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
    entries = _load_entries()
    expiry_key = str(opp["expiry"]).replace("-", "")[2:]
    safe_order_id = re.sub(r"[^A-Za-z0-9]", "", str(order_id)) or "unknown"
    key = f"PCS_{expiry_key}_{safe_order_id}"
    if key in entries and entries[key].get("order_id") != order_id:
        raise RuntimeError(f"Put-credit journal identity collision for {key}")
    signature = f"SPY_{opp['expiry']}_P{int(opp['long_put'])}-{int(opp['short_put'])}"
    entries[key] = {
        "strategy_family": "spy_put_credit",
        "order_id": order_id,
        "entry_time": datetime.now(timezone.utc).isoformat(),
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

    if args.reconcile_entries:
        try:
            client = _get_paper_client()
        except Exception as exc:
            logger.error("Paper client failed: %s", exc)
            return 1
        report = reconcile_put_credit_entries(client, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, default=str))
        return 2 if report["broken"] else 0

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

    if args.manage_exits:
        try:
            client = _get_paper_client()
        except Exception as exc:
            logger.error("Paper client failed: %s", exc)
            return 1
        report = manage_put_credit_exits(client, dry_run=args.dry_run)
        print(json.dumps(report, indent=2, default=str))
        return 2 if report["broken"] else 0

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

    opp = find_put_credit_opportunity(spy_price)
    dry = not args.execute_paper
    plan = plan_structure(dry_run=dry, opp=opp)
    plan["spy_price"] = spy_price
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

    from src.safety.trade_lock import TradeLockTimeout, acquire_trade_lock

    try:
        with acquire_trade_lock(timeout=10):
            if not _inventory_ok(client):
                return 2
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

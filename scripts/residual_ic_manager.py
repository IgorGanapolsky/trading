#!/usr/bin/env python3
"""Recover and manage residual ICs from broker-confirmed opening orders.

The legacy manager grouped positions only by expiry and therefore skipped two
valid one-lot iron condors when they shared a call vertical (six distinct OCC
symbols, with the common call legs aggregated to quantity two).  This manager
uses filled MLEG opening orders as the structure source of truth, allocates the
current broker inventory back to each opening order, and evaluates each trade
independently.

It never opens a position.  A close is atomic MLEG-only; failure leaves the
defined-risk structure intact for the next scheduled retry.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

AUDIT_PATH = ROOT / "data" / "audit" / "residual_ic_latest.json"
EASTERN = ZoneInfo("America/New_York")
logger = logging.getLogger("residual_ic_manager")


def _text(value: Any) -> str:
    return str(value or "").rsplit(".", 1)[-1].upper()


def _number(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _timestamp(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    else:
        raw = str(value or "").strip()
        if not raw:
            return None
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _is_option(symbol: str) -> bool:
    return len(symbol) > 10 and symbol.startswith("SPY") and symbol[-9:-8] in {"P", "C"}


def _signed_order_leg_qty(parent: Any, leg: Any) -> float:
    parent_qty = abs(_number(getattr(parent, "filled_qty", None) or getattr(parent, "qty", 1), 1))
    leg_qty = abs(_number(getattr(leg, "filled_qty", None) or getattr(leg, "qty", 1), 1))
    magnitude = parent_qty * leg_qty
    return magnitude if _text(getattr(leg, "side", None)) == "BUY" else -magnitude


def _is_filled_ic_open(order: Any) -> bool:
    from src.utils.order_intent import parse_client_order_id

    parsed = parse_client_order_id(str(getattr(order, "client_order_id", "") or ""))
    legs = list(getattr(order, "legs", None) or [])
    if not parsed or parsed["role"] != "OPEN" or parsed["intent"] != "IC":
        return False
    if "FILL" not in _text(getattr(order, "status", None)) or len(legs) != 4:
        return False
    symbols = [str(getattr(leg, "symbol", "") or "") for leg in legs]
    return (
        all(_is_option(symbol) for symbol in symbols)
        and sum(symbol[-9:-8] == "P" for symbol in symbols) == 2
        and sum(symbol[-9:-8] == "C" for symbol in symbols) == 2
        and sum(_text(getattr(leg, "side", None)) == "BUY" for leg in legs) == 2
        and sum(_text(getattr(leg, "side", None)) == "SELL" for leg in legs) == 2
    )


def recover_active_structures(
    positions: list[Any], orders: list[Any]
) -> tuple[list[dict[str, Any]], dict[str, float]]:
    """Allocate current signed position quantities to recent filled IC opens."""

    position_map = {
        str(pos.symbol): pos
        for pos in positions
        if _is_option(str(getattr(pos, "symbol", "") or ""))
        and abs(_number(getattr(pos, "qty", 0))) > 1e-9
    }
    available = {symbol: _number(pos.qty) for symbol, pos in position_map.items()}
    candidates = [order for order in orders if _is_filled_ic_open(order)]
    candidates.sort(
        key=lambda order: (
            _timestamp(getattr(order, "filled_at", None) or getattr(order, "created_at", None))
            or datetime.min.replace(tzinfo=timezone.utc)
        ),
        reverse=True,
    )

    recovered: list[dict[str, Any]] = []
    for order in candidates:
        order_legs = list(getattr(order, "legs", None) or [])
        needed: dict[str, float] = {}
        for leg in order_legs:
            symbol = str(leg.symbol)
            needed[symbol] = needed.get(symbol, 0.0) + _signed_order_leg_qty(order, leg)

        def enough(symbol: str, qty: float) -> bool:
            have = available.get(symbol, 0.0)
            return have * qty > 0 and abs(have) + 1e-9 >= abs(qty)

        if not all(enough(symbol, qty) for symbol, qty in needed.items()):
            continue

        credit = 0.0
        legs: list[dict[str, Any]] = []
        for leg in order_legs:
            symbol = str(leg.symbol)
            signed_qty = _signed_order_leg_qty(order, leg)
            available[symbol] -= signed_qty
            entry_price = _number(getattr(leg, "filled_avg_price", None))
            if signed_qty < 0:
                credit += entry_price * abs(signed_qty)
            else:
                credit -= entry_price * abs(signed_qty)
            pos = position_map[symbol]
            legs.append(
                {
                    "symbol": symbol,
                    "qty": signed_qty,
                    "entry_price": entry_price,
                    "current_price": _number(
                        getattr(pos, "current_price", None),
                        _number(getattr(pos, "avg_entry_price", None)),
                    ),
                }
            )

        if credit <= 0:
            for symbol, qty in needed.items():
                available[symbol] += qty
            continue
        sample_symbol = legs[0]["symbol"]
        recovered.append(
            {
                "entry_order_id": str(order.id),
                "client_order_id": str(getattr(order, "client_order_id", "") or ""),
                "entry_time": (
                    _timestamp(getattr(order, "filled_at", None))
                    or _timestamp(getattr(order, "created_at", None))
                ).isoformat(),
                "expiry_yymmdd": sample_symbol[3:9],
                "credit": round(credit, 4),
                "quantity": abs(_number(getattr(order, "filled_qty", None) or 1, 1)),
                "legs": legs,
            }
        )

    unresolved = {symbol: qty for symbol, qty in available.items() if abs(qty) > 1e-9}
    return recovered, unresolved


def evaluate_residual_exit(
    structure: dict[str, Any], *, now: datetime | None = None
) -> dict[str, Any]:
    """Apply canonical 50% profit, 100%-of-credit stop, and 7-DTE exit."""

    from src.core.trading_constants import (
        IC_PROFIT_TARGET_PCT,
        IRON_CONDOR_EXIT_DTE,
        IRON_CONDOR_MIN_HOLD_HOURS,
        IRON_CONDOR_STOP_LOSS_MULTIPLIER,
    )

    current = now or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    expiry_raw = str(structure["expiry_yymmdd"])
    expiry = date(2000 + int(expiry_raw[:2]), int(expiry_raw[2:4]), int(expiry_raw[4:6]))
    dte = (expiry - current.astimezone(EASTERN).date()).days
    entered = _timestamp(structure.get("entry_time"))
    hold_hours = (
        (current.astimezone(timezone.utc) - entered).total_seconds() / 3600 if entered else None
    )
    credit = _number(structure.get("credit"))
    current_debit = sum(
        _number(leg.get("current_price")) * (1 if _number(leg.get("qty")) < 0 else -1)
        for leg in structure.get("legs", [])
    )
    current_debit = max(0.0, current_debit)
    quantity = max(1.0, abs(_number(structure.get("quantity"), 1)))
    max_profit = credit * quantity * 100
    pnl = (credit - current_debit) * quantity * 100

    reason = None
    if dte <= 1:
        reason = "assignment_failsafe"
    elif dte <= IRON_CONDOR_EXIT_DTE:
        reason = "dte_exit"
    elif hold_hours is not None and hold_hours >= IRON_CONDOR_MIN_HOLD_HOURS:
        if pnl >= max_profit * IC_PROFIT_TARGET_PCT:
            reason = "profit_target"
        elif pnl <= -(max_profit * IRON_CONDOR_STOP_LOSS_MULTIPLIER):
            reason = "stop_loss"

    return {
        "should_exit": reason is not None,
        "exit_reason": reason,
        "dte": dte,
        "hold_hours": hold_hours,
        "credit": round(credit, 4),
        "current_debit": round(current_debit, 4),
        "pnl": round(pnl, 2),
        "max_profit": round(max_profit, 2),
    }


def _close_signature(structure: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (
                str(leg["symbol"]),
                "BUY" if _number(leg.get("qty")) < 0 else "SELL",
            )
            for leg in structure.get("legs", [])
        )
    )


def _order_signature(order: Any) -> tuple[tuple[str, str], ...]:
    return tuple(
        sorted(
            (str(getattr(leg, "symbol", "")), _text(getattr(leg, "side", None)))
            for leg in list(getattr(order, "legs", None) or [])
        )
    )


def _submit_close(client: Any, structure: dict[str, Any], decision: dict[str, Any]):
    from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest, OptionLegRequest
    from src.safety.mandatory_trade_gate import safe_submit_order
    from src.utils.order_intent import build_client_order_id

    legs = [
        OptionLegRequest(
            symbol=str(leg["symbol"]),
            side=OrderSide.BUY if _number(leg.get("qty")) < 0 else OrderSide.SELL,
            ratio_qty=abs(int(_number(leg.get("qty"), 1))),
        )
        for leg in structure["legs"]
    ]
    put_strikes = [
        int(str(leg["symbol"])[-8:]) / 1000
        for leg in structure["legs"]
        if str(leg["symbol"])[-9:-8] == "P"
    ]
    call_strikes = [
        int(str(leg["symbol"])[-8:]) / 1000
        for leg in structure["legs"]
        if str(leg["symbol"])[-9:-8] == "C"
    ]
    max_width = max(max(put_strikes) - min(put_strikes), max(call_strikes) - min(call_strikes))
    limit_debit = min(max_width, max(0.01, round(_number(decision["current_debit"]) + 0.10, 2)))
    request = LimitOrderRequest(
        qty=abs(int(_number(structure.get("quantity"), 1))),
        order_class=OrderClass.MLEG,
        legs=legs,
        time_in_force=TimeInForce.DAY,
        limit_price=limit_debit,
        client_order_id=build_client_order_id("CLOSE", "IC"),
    )
    return safe_submit_order(client, request, strategy="iron_condor")


def _get_orders(client: Any, *, open_only: bool = False) -> list[Any]:
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    kwargs: dict[str, Any] = {
        "status": QueryOrderStatus.OPEN if open_only else QueryOrderStatus.ALL,
        "nested": True,
        "limit": 500,
    }
    if not open_only:
        kwargs["after"] = datetime.now(timezone.utc) - timedelta(days=120)
    return list(client.get_orders(filter=GetOrdersRequest(**kwargs)))


def manage_residual_ics(client: Any, *, dry_run: bool = False) -> dict[str, Any]:
    positions = list(client.get_all_positions())
    option_positions = [pos for pos in positions if _is_option(str(getattr(pos, "symbol", "")))]
    all_orders = _get_orders(client)
    structures, unresolved = recover_active_structures(option_positions, all_orders)
    pending_signatures = {_order_signature(order) for order in _get_orders(client, open_only=True)}
    report: dict[str, Any] = {
        "audited_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "reconciled": len(structures),
        "unresolved": unresolved,
        "checked": 0,
        "holds": 0,
        "would_exit": 0,
        "submitted": 0,
        "pending": 0,
        "broken": 1 if unresolved else 0,
        "details": [],
    }

    for structure in structures:
        report["checked"] += 1
        decision = evaluate_residual_exit(structure)
        detail = {
            "entry_order_id": structure["entry_order_id"],
            "expiry_yymmdd": structure["expiry_yymmdd"],
            "credit": structure["credit"],
            "symbols": [leg["symbol"] for leg in structure["legs"]],
            **decision,
        }
        if not decision["should_exit"]:
            report["holds"] += 1
            detail["status"] = "hold"
        elif _close_signature(structure) in pending_signatures:
            report["pending"] += 1
            detail["status"] = "exit_pending"
        elif dry_run:
            report["would_exit"] += 1
            detail["status"] = "would_exit"
        else:
            try:
                order = _submit_close(client, structure, decision)
                report["submitted"] += 1
                detail["status"] = "exit_submitted"
                detail["exit_order_id"] = str(order.id)
            except Exception as exc:  # noqa: BLE001
                report["broken"] += 1
                detail["status"] = "exit_submit_failed"
                detail["error"] = str(exc)
        report["details"].append(detail)

    AUDIT_PATH.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def _client():
    from alpaca.trading.client import TradingClient
    from src.utils.alpaca_client import get_alpaca_credentials

    key, secret = get_alpaca_credentials()
    if not key or not secret:
        raise RuntimeError("Alpaca paper credentials missing")
    return TradingClient(key, secret, paper=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Recover and manage residual broker ICs")
    parser.add_argument("--dry-run", action="store_true", help="Evaluate without submitting closes")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    report = manage_residual_ics(_client(), dry_run=args.dry_run)
    print(json.dumps(report, indent=2))
    return 2 if report["broken"] else 0


if __name__ == "__main__":
    raise SystemExit(main())

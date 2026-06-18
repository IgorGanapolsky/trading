#!/usr/bin/env python3
"""
Sync closed iron condor trades into data/trades.json.

This script consumes Alpaca fills from data/system_state.json::trade_history and
builds closed SPY iron condor round-trips for win-rate tracking.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SYSTEM_STATE_FILE = DATA_DIR / "system_state.json"
TRADES_FILE = DATA_DIR / "trades.json"
IC_ENTRIES_FILE = DATA_DIR / "ic_entries.json"
DEFAULT_BROKER_ORDER_LIMIT = 1000
OPTION_SYMBOL_RE = re.compile(
    r"^(?P<underlying>[A-Z]{1,8})(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<kind>[CP])(?P<strike>\d{8})$"
)
ENTRY_PROVENANCE_FIELDS = (
    "selection_method",
    "strike_selection_method",
    "target_delta",
    "put_delta",
    "call_delta",
    "profile_name",
    "validation_phase",
    "entry_reason",
)


def _parse_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _parse_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _parse_dt(value: Any) -> datetime | None:
    if value is None:
        return None
    raw = str(value).strip()
    if not raw:
        return None
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    try:
        return datetime.fromisoformat(raw)
    except ValueError:
        return None


def _parse_side(value: Any) -> str | None:
    raw = str(value or "").upper()
    if "SELL" in raw:
        return "SELL"
    if "BUY" in raw:
        return "BUY"
    return None


def _parse_position_intent(value: Any) -> str | None:
    raw = str(value or "").strip().upper()
    if not raw or raw == "NONE":
        return None
    if raw.startswith("POSITIONINTENT."):
        raw = raw.split(".", 1)[1]
    return raw or None


def _strike_from_raw(raw: str) -> float:
    return int(raw) / 1000.0


def _strike_text(strike: float) -> str:
    if abs(strike - int(strike)) < 1e-9:
        return str(int(strike))
    return f"{strike:.3f}".rstrip("0").rstrip(".")


def _parse_option_symbol(symbol: Any) -> dict[str, Any] | None:
    raw = str(symbol or "").strip()
    m = OPTION_SYMBOL_RE.match(raw)
    if not m:
        return None
    yy = int(m.group("yy"))
    year = 2000 + yy
    month = int(m.group("mm"))
    day = int(m.group("dd"))
    try:
        expiry = datetime(year, month, day, tzinfo=timezone.utc).date()
    except ValueError:
        return None
    return {
        "symbol": raw,
        "underlying": m.group("underlying"),
        "expiry": expiry.isoformat(),
        "kind": m.group("kind"),
        "strike": _strike_from_raw(m.group("strike")),
    }


def _build_signature(parsed_legs: list[dict[str, Any]]) -> str | None:
    if not parsed_legs:
        return None
    underlyings = {row["underlying"] for row in parsed_legs}
    expiries = {row["expiry"] for row in parsed_legs}
    if len(underlyings) != 1 or len(expiries) != 1:
        return None

    put_strikes = sorted({row["strike"] for row in parsed_legs if row["kind"] == "P"})
    call_strikes = sorted({row["strike"] for row in parsed_legs if row["kind"] == "C"})
    if len(put_strikes) < 2 or len(call_strikes) < 2:
        return None

    put_part = "-".join(_strike_text(s) for s in put_strikes[:2])
    call_part = "-".join(_strike_text(s) for s in call_strikes[:2])
    return f"{next(iter(underlyings))}_{next(iter(expiries))}_P{put_part}_C{call_part}"


def _signature_to_legs(signature: str) -> dict[str, Any]:
    parts = signature.split("_")
    if len(parts) < 4:
        return {"underlying": "SPY", "expiry": None, "put_strikes": [], "call_strikes": []}
    underlying = parts[0]
    expiry = parts[1]
    put_raw = parts[2][1:] if parts[2].startswith("P") else ""
    call_raw = parts[3][1:] if parts[3].startswith("C") else ""
    put_strikes = [_parse_float(v, 0.0) for v in put_raw.split("-") if v]
    call_strikes = [_parse_float(v, 0.0) for v in call_raw.split("-") if v]
    return {
        "underlying": underlying,
        "expiry": expiry,
        "put_strikes": put_strikes,
        "call_strikes": call_strikes,
    }


def _field(source: Any, key: str) -> Any:
    if isinstance(source, dict):
        return source.get(key)
    return getattr(source, key, None)


# LL-354: leg_tag -> close action. Short legs are bought back to close;
# long legs are sold to close.
_LEG_TAG_TO_CLOSE_ACTION = {
    "SP": "BUY_TO_CLOSE",   # short put
    "SC": "BUY_TO_CLOSE",   # short call
    "LP": "SELL_TO_CLOSE",  # long put
    "LC": "SELL_TO_CLOSE",  # long call
}


def _intent_from_stamped_cid(client_order_id: Any) -> str | None:
    """If WE stamped the order at submission, derive the close action
    directly from `client_order_id`. Returns None for legacy / non-IC
    orders (which fall through to the reverse-lookup heuristic)."""
    try:
        from src.utils.order_intent import parse_client_order_id
    except Exception:  # pragma: no cover - import safety
        return None
    parsed = parse_client_order_id(
        client_order_id if isinstance(client_order_id, str) else None
    )
    if parsed is None or parsed["role"] != "CLOSE":
        return None
    leg_tag = parsed.get("leg_tag")
    if not leg_tag:
        # CLOSE-IC parent: leg-level rows are handled separately in the
        # MLEG branch of _close_inventory; nothing to do here.
        return None
    return _LEG_TAG_TO_CLOSE_ACTION.get(leg_tag)


def _serialize_leg(leg: Any) -> dict[str, Any]:
    return {
        "id": str(_field(leg, "id") or ""),
        "symbol": _field(leg, "symbol"),
        "side": str(_field(leg, "side") or ""),
        "qty": str(_field(leg, "qty") or ""),
        "filled_qty": str(_field(leg, "filled_qty") or ""),
        "filled_avg_price": str(_field(leg, "filled_avg_price") or ""),
        "position_intent": str(_field(leg, "position_intent") or ""),
        "status": str(_field(leg, "status") or ""),
        "client_order_id": str(_field(leg, "client_order_id") or ""),
    }


def _serialize_order(order: Any) -> dict[str, Any]:
    raw_legs = _field(order, "legs")
    legs = [_serialize_leg(leg) for leg in raw_legs or []]
    return {
        "id": str(_field(order, "id") or ""),
        "symbol": _field(order, "symbol"),
        "side": str(_field(order, "side") or ""),
        "qty": str(_field(order, "filled_qty") or _field(order, "qty") or ""),
        "price": str(_field(order, "filled_avg_price") or _field(order, "price") or ""),
        "filled_at": str(_field(order, "filled_at") or ""),
        "status": str(_field(order, "status") or ""),
        "order_class": str(_field(order, "order_class") or ""),
        "position_intent": str(_field(order, "position_intent") or ""),
        "client_order_id": str(_field(order, "client_order_id") or ""),
        "legs": legs,
    }


def _row_dedupe_key(row: dict[str, Any]) -> str:
    row_id = str(row.get("id") or "").strip()
    if row_id:
        return f"id::{row_id}"
    filled_at = str(row.get("filled_at") or "")
    symbol = str(row.get("symbol") or "")
    legs = row.get("legs") if isinstance(row.get("legs"), list) else []
    leg_symbols = [
        str(leg.get("symbol") if isinstance(leg, dict) else leg or "")
        for leg in legs
        if leg is not None
    ]
    return (
        f"composite::{filled_at}::{symbol}::{row.get('side')}::{row.get('qty')}::"
        f"{row.get('price')}::{'|'.join(sorted(leg_symbols))}"
    )


def _row_detail_score(row: dict[str, Any]) -> tuple[int, int]:
    raw_legs = row.get("legs") if isinstance(row.get("legs"), list) else []
    detailed_legs = sum(1 for leg in raw_legs if isinstance(leg, dict))
    return detailed_legs, len(raw_legs)


def _merge_trade_rows(*collections: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged: dict[str, dict[str, Any]] = {}
    for rows in collections:
        for row in rows:
            if not isinstance(row, dict):
                continue
            key = _row_dedupe_key(row)
            existing = merged.get(key)
            if existing is None or _row_detail_score(row) > _row_detail_score(existing):
                merged[key] = row
    return sorted(merged.values(), key=lambda row: _parse_dt(row.get("filled_at")) or datetime.min)


def _fetch_broker_trade_history(limit: int = DEFAULT_BROKER_ORDER_LIMIT) -> list[dict[str, Any]]:
    try:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest
        from src.utils.alpaca_client import get_alpaca_credentials
    except Exception as exc:
        logger.info("Broker trade-history sync unavailable: %s", exc)
        return []

    api_key, secret_key = get_alpaca_credentials()
    if not api_key or not secret_key:
        return []

    try:
        client = TradingClient(api_key, secret_key, paper=True)
        try:
            orders = client.get_orders(
                filter=GetOrdersRequest(
                    status=QueryOrderStatus.CLOSED,
                    limit=limit,
                    nested=True,
                    direction="desc",
                )
            )
        except TypeError:
            orders = client.get_orders(
                filter=GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=limit, nested=True)
            )
    except Exception as exc:
        logger.warning("Failed to fetch broker trade history: %s", exc)
        return []

    rows = []
    for order in orders:
        filled_dt = _parse_dt(_field(order, "filled_at"))
        if filled_dt is None:
            continue
        rows.append(_serialize_order(order))
    logger.info("Fetched %s closed orders from broker for ledger sync", len(rows))
    return rows


def _load_trade_history() -> tuple[list[dict[str, Any]], str]:
    state = _load_system_state()
    state_history = state.get("trade_history", []) if isinstance(state, dict) else []
    if not isinstance(state_history, list):
        state_history = []

    broker_history = _fetch_broker_trade_history()
    if broker_history:
        merged = _merge_trade_rows(state_history, broker_history)
        return merged, "broker+system_state"
    return state_history, "system_state"


def _normalize_leg_row(raw_leg: Any) -> dict[str, Any] | None:
    if isinstance(raw_leg, str):
        parsed = _parse_option_symbol(raw_leg)
        if parsed is None:
            return None
        return {
            "symbol": parsed["symbol"],
            "parsed": parsed,
            "side": None,
            "qty": 0.0,
            "price": 0.0,
            "position_intent": None,
        }

    symbol = _field(raw_leg, "symbol")
    parsed = _parse_option_symbol(symbol)
    if parsed is None:
        return None
    return {
        "symbol": parsed["symbol"],
        "parsed": parsed,
        "side": _parse_side(_field(raw_leg, "side")),
        "qty": _parse_float(
            _field(raw_leg, "filled_qty"), _parse_float(_field(raw_leg, "qty"), 0.0)
        ),
        "price": _parse_float(
            _field(raw_leg, "filled_avg_price"),
            _parse_float(_field(raw_leg, "price"), 0.0),
        ),
        "position_intent": _parse_position_intent(_field(raw_leg, "position_intent")),
    }


def _normalized_row_legs(row: dict[str, Any]) -> list[dict[str, Any]]:
    raw_legs = row.get("legs") if isinstance(row.get("legs"), list) else []
    normalized = []
    for raw_leg in raw_legs:
        leg = _normalize_leg_row(raw_leg)
        if leg is not None:
            normalized.append(leg)
    return normalized


def _phase_from_legs(legs: list[dict[str, Any]]) -> str | None:
    phases = {
        "OPEN" if leg.get("position_intent") and "OPEN" in str(leg["position_intent"]) else "CLOSE"
        for leg in legs
        if leg.get("position_intent")
    }
    if len(phases) == 1:
        return next(iter(phases))
    return None


def _signed_cash(side: str | None, qty: float, price: float) -> float:
    if side == "SELL":
        return qty * price * 100.0
    if side == "BUY":
        return -qty * price * 100.0
    return 0.0


def _close_action_for_open_leg(leg: dict[str, Any]) -> str | None:
    intent = str(leg.get("position_intent") or "")
    if "SELL_TO_OPEN" in intent:
        return "BUY_TO_CLOSE"
    if "BUY_TO_OPEN" in intent:
        return "SELL_TO_CLOSE"
    side = leg.get("side")
    if side == "SELL":
        return "BUY_TO_CLOSE"
    if side == "BUY":
        return "SELL_TO_CLOSE"
    return None


def _event_from_parent_order(row: dict[str, Any]) -> dict[str, Any] | None:
    filled_dt = _parse_dt(row.get("filled_at"))
    if filled_dt is None:
        return None

    legs = _normalized_row_legs(row)
    parsed_legs = [leg["parsed"] for leg in legs]
    if not parsed_legs:
        legs_symbols = row.get("legs") if isinstance(row.get("legs"), list) else []
        parsed_legs = [
            parsed for symbol in legs_symbols if (parsed := _parse_option_symbol(symbol))
        ]
    signature = _build_signature(parsed_legs)
    if signature is None:
        return None

    detailed_legs = [
        leg
        for leg in legs
        if leg.get("side") and leg.get("qty", 0.0) > 0 and leg.get("price", 0.0) > 0
    ]
    if detailed_legs:
        net_cash = sum(
            _signed_cash(
                str(leg.get("side")),
                _parse_float(leg.get("qty"), 0.0),
                _parse_float(leg.get("price"), 0.0),
            )
            for leg in detailed_legs
        )
    else:
        side = _parse_side(row.get("side"))
        if side is None:
            return None
        qty = _parse_float(row.get("qty"), 1.0)
        price = _parse_float(row.get("price"), 0.0)
        cash = qty * price * 100.0
        if cash <= 0:
            return None
        net_cash = cash if side == "SELL" else -cash
    if abs(net_cash) < 0.01:
        return None

    return {
        "source": "alpaca_parent",
        "signature": signature,
        "timestamp": filled_dt,
        "net_cash": round(net_cash, 4),
        "symbols": sorted(
            {leg["symbol"] for leg in legs} or {str(s) for s in row.get("legs", []) if s}
        ),
        "order_ids": [str(row.get("id"))] if row.get("id") else [],
    }


def _candidate_leg_fills(trade_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in trade_history:
        if not isinstance(row, dict):
            continue
        parsed = _parse_option_symbol(row.get("symbol"))
        if parsed is None:
            continue
        if parsed["underlying"] != "SPY":
            continue
        filled_dt = _parse_dt(row.get("filled_at"))
        side = _parse_side(row.get("side"))
        if filled_dt is None or side is None:
            continue
        qty = _parse_float(row.get("qty"), 0.0)
        price = _parse_float(row.get("price"), 0.0)
        if qty <= 0 or price <= 0:
            continue
        rows.append(
            {
                "id": str(row.get("id")) if row.get("id") else None,
                "timestamp": filled_dt,
                "side": side,
                "qty": qty,
                "price": price,
                "symbol": parsed["symbol"],
                "parsed": parsed,
            }
        )
    rows.sort(key=lambda item: item["timestamp"])
    return rows


def _events_from_leg_clusters(trade_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    fills = _candidate_leg_fills(trade_history)
    if not fills:
        return []

    by_series: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in fills:
        key = (row["parsed"]["underlying"], row["parsed"]["expiry"])
        by_series[key].append(row)

    events: list[dict[str, Any]] = []
    cluster_window = timedelta(seconds=25)

    for _series_key, series_rows in by_series.items():
        cluster: list[dict[str, Any]] = []
        cluster_start: datetime | None = None

        def flush_cluster(rows: list[dict[str, Any]]) -> None:
            if not rows:
                return
            symbols = [row["symbol"] for row in rows]
            parsed_legs = [row["parsed"] for row in rows]
            signature = _build_signature(parsed_legs)
            if signature is None:
                return

            unique_symbols = {row["symbol"] for row in rows}
            kinds = {row["parsed"]["kind"] for row in rows}
            sides = {row["side"] for row in rows}
            if len(unique_symbols) < 4 or kinds != {"C", "P"} or not {"BUY", "SELL"} <= sides:
                return

            sell_cash = sum(
                row["qty"] * row["price"] * 100.0 for row in rows if row["side"] == "SELL"
            )
            buy_cash = sum(
                row["qty"] * row["price"] * 100.0 for row in rows if row["side"] == "BUY"
            )
            net_cash = sell_cash - buy_cash
            if abs(net_cash) < 0.01:
                return

            events.append(
                {
                    "source": "alpaca_leg_cluster",
                    "signature": signature,
                    "timestamp": min(row["timestamp"] for row in rows),
                    "net_cash": round(net_cash, 4),
                    "symbols": sorted(set(symbols)),
                    "order_ids": [row["id"] for row in rows if row.get("id")],
                }
            )

        for row in series_rows:
            if cluster_start is None:
                cluster = [row]
                cluster_start = row["timestamp"]
                continue

            if row["timestamp"] - cluster_start <= cluster_window:
                cluster.append(row)
                continue

            flush_cluster(cluster)
            cluster = [row]
            cluster_start = row["timestamp"]

        flush_cluster(cluster)

    return events


def _collect_events(trade_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    parent_events = [
        event
        for row in trade_history
        if isinstance(row, dict)
        for event in [_event_from_parent_order(row)]
        if event is not None
    ]
    cluster_events = _events_from_leg_clusters(trade_history)

    deduped: dict[tuple[str, str, float], dict[str, Any]] = {}
    for event in parent_events + cluster_events:
        dedupe_key = (
            event["signature"],
            event["timestamp"].isoformat(),
            round(event["net_cash"], 2),
        )
        existing = deduped.get(dedupe_key)
        if existing is None or event["source"] == "alpaca_parent":
            deduped[dedupe_key] = event

    return sorted(deduped.values(), key=lambda item: item["timestamp"])


def _open_parent_lots(trade_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lots: list[dict[str, Any]] = []
    for row in sorted(
        trade_history, key=lambda item: _parse_dt(item.get("filled_at")) or datetime.min
    ):
        if not isinstance(row, dict):
            continue
        filled_dt = _parse_dt(row.get("filled_at"))
        if filled_dt is None:
            continue
        legs = _normalized_row_legs(row)
        if not legs:
            continue
        if _phase_from_legs(legs) != "OPEN":
            continue
        signature = _build_signature([leg["parsed"] for leg in legs])
        if signature is None:
            continue
        quantity = _parse_float(row.get("qty"), 0.0) or min(
            (_parse_float(leg.get("qty"), 0.0) for leg in legs),
            default=0.0,
        )
        if quantity <= 0:
            continue
        expected_close_legs = []
        for leg in legs:
            close_action = _close_action_for_open_leg(leg)
            if close_action is None:
                expected_close_legs = []
                break
            expected_close_legs.append(
                {
                    "symbol": leg["symbol"],
                    "close_action": close_action,
                    "quantity": quantity,
                }
            )
        if not expected_close_legs:
            continue
        entry_net_cash = round(
            sum(
                _signed_cash(
                    str(leg.get("side")),
                    _parse_float(leg.get("qty"), 0.0),
                    _parse_float(leg.get("price"), 0.0),
                )
                for leg in legs
            ),
            2,
        )
        lots.append(
            {
                "signature": signature,
                "timestamp": filled_dt,
                "net_cash": entry_net_cash,
                "quantity": quantity,
                "symbols": sorted({leg["symbol"] for leg in legs}),
                "expected_close_legs": expected_close_legs,
                "source": "alpaca_parent_lot",
                "order_ids": [str(row.get("id"))] if row.get("id") else [],
            }
        )
    return lots


def _expected_close_index(
    open_lots: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Index of `symbol -> [expected close-leg specs]` from open parent lots.

    Used to back-fill `position_intent` on SIMPLE close rows when the broker
    fill never carried the intent tag. Without this, singleton SIMPLE closes
    against an open IC lot are silently dropped and the realized P/L
    under-reports the true loss.
    """
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for lot in open_lots:
        lot_ts = lot.get("timestamp")
        for leg in lot.get("expected_close_legs") or []:
            index[str(leg.get("symbol"))].append(
                {
                    "close_action": leg.get("close_action"),
                    "quantity": _parse_float(leg.get("quantity"), 0.0),
                    "lot_timestamp": lot_ts,
                }
            )
    return index


def _close_inventory(
    trade_history: list[dict[str, Any]],
    *,
    expected_close_index: dict[str, list[dict[str, Any]]] | None = None,
) -> dict[tuple[str, str], list[dict[str, Any]]]:
    inventory: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    sorted_rows = sorted(
        (row for row in trade_history if isinstance(row, dict)),
        key=lambda item: _parse_dt(item.get("filled_at")) or datetime.min,
    )
    for row in sorted_rows:
        filled_dt = _parse_dt(row.get("filled_at"))
        if filled_dt is None:
            continue
        legs = _normalized_row_legs(row)
        if legs and _phase_from_legs(legs) == "CLOSE":
            for leg in legs:
                action = str(leg.get("position_intent") or "")
                if not action or "CLOSE" not in action:
                    continue
                quantity = _parse_float(leg.get("qty"), 0.0)
                price = _parse_float(leg.get("price"), 0.0)
                if quantity <= 0 or price <= 0:
                    continue
                inventory[(leg["symbol"], action)].append(
                    {
                        "timestamp": filled_dt,
                        "remaining_qty": quantity,
                        "price": price,
                        "side": leg.get("side"),
                        "order_id": str(row.get("id") or ""),
                        "source": "alpaca_parent_close",
                    }
                )
            continue

        parsed = _parse_option_symbol(row.get("symbol"))
        if parsed is None:
            continue
        action = _parse_position_intent(row.get("position_intent"))
        side = _parse_side(row.get("side"))
        quantity = _parse_float(row.get("qty"), 0.0)
        price = _parse_float(row.get("price"), 0.0)
        if quantity <= 0 or price <= 0:
            continue

        source_tag = "alpaca_simple_close"
        # LL-354: authoritative path — if WE stamped client_order_id at
        # submission, the intent is self-describing and beats both
        # broker position_intent and the reverse-lookup heuristic.
        if action is None or "CLOSE" not in action:
            stamped = _intent_from_stamped_cid(row.get("client_order_id"))
            if stamped is not None:
                action = stamped
                source_tag = "alpaca_simple_close_client_order_id"

        # Reverse-lookup fallback: position_intent missing on the broker row,
        # but the symbol+side matches an open parent-lot's expected-close leg.
        # Without this, singleton SIMPLE closes never enter the paired ledger
        # and the kill-criteria expectancy math under-reports realized loss.
        if (action is None or "CLOSE" not in action) and expected_close_index is not None:
            candidates = expected_close_index.get(parsed["symbol"], [])
            inferred_action: str | None = None
            for candidate in candidates:
                cand_action = str(candidate.get("close_action") or "")
                if not cand_action:
                    continue
                if cand_action == "BUY_TO_CLOSE" and side != "BUY":
                    continue
                if cand_action == "SELL_TO_CLOSE" and side != "SELL":
                    continue
                cand_ts = candidate.get("lot_timestamp")
                if isinstance(cand_ts, datetime) and filled_dt < cand_ts:
                    continue
                inferred_action = cand_action
                break
            if inferred_action is not None:
                action = inferred_action
                source_tag = "alpaca_simple_close_reverse_lookup"

        if action is None or "CLOSE" not in action:
            if parsed["underlying"] == "SPY":
                logger.debug(
                    "Singleton close bucketed (no intent, no open-lot match): "
                    "order_id=%s symbol=%s side=%s qty=%s price=%s",
                    row.get("id"),
                    parsed["symbol"],
                    side,
                    quantity,
                    price,
                )
            continue
        inventory[(parsed["symbol"], action)].append(
            {
                "timestamp": filled_dt,
                "remaining_qty": quantity,
                "price": price,
                "side": side,
                "order_id": str(row.get("id") or ""),
                "source": source_tag,
            }
        )
    return inventory


def _plan_close_allocations(
    fills: list[dict[str, Any]],
    *,
    needed_qty: float,
    not_before: datetime,
) -> list[tuple[dict[str, Any], float]] | None:
    remaining = needed_qty
    allocations: list[tuple[dict[str, Any], float]] = []
    for fill in fills:
        available_qty = _parse_float(fill.get("remaining_qty"), 0.0)
        fill_ts = fill.get("timestamp")
        if available_qty <= 0:
            continue
        if not isinstance(fill_ts, datetime) or fill_ts < not_before:
            continue
        take_qty = min(remaining, available_qty)
        if take_qty <= 0:
            continue
        allocations.append((fill, take_qty))
        remaining = round(remaining - take_qty, 8)
        if remaining <= 1e-8:
            return allocations
    return None


def _allocation_net_cash(fill: dict[str, Any], quantity: float, action: str) -> float:
    side = _parse_side(fill.get("side"))
    if side is None:
        side = "BUY" if "BUY_TO_CLOSE" in action else "SELL"
    return round(_signed_cash(side, quantity, _parse_float(fill.get("price"), 0.0)), 4)


def _to_closed_trade_from_inventory(
    lot: dict[str, Any],
    matched_legs: list[dict[str, Any]],
) -> dict[str, Any]:
    signature = str(lot["signature"])
    entry_ts = lot["timestamp"]
    exit_ts = max(
        allocation.get("timestamp") for leg in matched_legs for allocation, _ in leg["allocations"]
    )
    exit_net_cash = round(
        sum(
            _allocation_net_cash(allocation, take_qty, leg["close_action"])
            for leg in matched_legs
            for allocation, take_qty in leg["allocations"]
        ),
        2,
    )
    pnl = round(_parse_float(lot.get("net_cash"), 0.0) + exit_net_cash, 2)
    outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
    legs = _signature_to_legs(signature)
    entry_net_cash = round(_parse_float(lot.get("net_cash"), 0.0), 2)
    order_ids = sorted(
        {
            str(order_id)
            for order_id in (
                list(lot.get("order_ids") or [])
                + [
                    allocation.get("order_id")
                    for leg in matched_legs
                    for allocation, _ in leg["allocations"]
                ]
            )
            if order_id
        }
    )
    return {
        "id": _trade_id(signature, entry_ts, exit_ts),
        "symbol": legs.get("underlying") or "SPY",
        "type": "option",
        "strategy": "iron_condor",
        "status": "closed",
        "entry_date": entry_ts.date().isoformat(),
        "exit_date": exit_ts.date().isoformat(),
        "entry_time": entry_ts.isoformat(),
        "exit_time": exit_ts.isoformat(),
        "entry_net_cash": entry_net_cash,
        "entry_credit": round(max(entry_net_cash, 0.0), 2),
        "entry_debit": round(max(-entry_net_cash, 0.0), 2),
        "entry_style": "credit" if entry_net_cash > 0 else "debit",
        "exit_net_cash": exit_net_cash,
        "exit_credit": round(max(exit_net_cash, 0.0), 2),
        "exit_debit": round(max(-exit_net_cash, 0.0), 2),
        "exit_style": "credit" if exit_net_cash > 0 else "debit",
        "realized_pnl": pnl,
        "outcome": outcome,
        "signature": signature,
        "legs": legs,
        "quantity": lot.get("quantity"),
        "source": "alpaca_parent_lot->alpaca_close_inventory",
        "order_ids": {
            "entry": list(lot.get("order_ids") or []),
            "exit": [
                order_id
                for order_id in order_ids
                if order_id not in set(lot.get("order_ids") or [])
            ],
        },
    }


def _pair_closed_trades_from_inventory(trade_history: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lots = _open_parent_lots(trade_history)
    if not lots:
        return []

    inventory = _close_inventory(
        trade_history,
        expected_close_index=_expected_close_index(lots),
    )
    closed: list[dict[str, Any]] = []
    for lot in lots:
        matched_legs = []
        for leg in lot["expected_close_legs"]:
            fills = inventory.get((leg["symbol"], leg["close_action"]), [])
            plan = _plan_close_allocations(
                fills,
                needed_qty=_parse_float(lot.get("quantity"), 0.0),
                not_before=lot["timestamp"],
            )
            if plan is None:
                matched_legs = []
                break
            matched_legs.append(
                {
                    "symbol": leg["symbol"],
                    "close_action": leg["close_action"],
                    "allocations": plan,
                }
            )
        if not matched_legs:
            continue
        for leg in matched_legs:
            for allocation, take_qty in leg["allocations"]:
                allocation["remaining_qty"] = round(
                    _parse_float(allocation.get("remaining_qty"), 0.0) - take_qty,
                    8,
                )
        closed.append(_to_closed_trade_from_inventory(lot, matched_legs))
    closed.sort(key=lambda row: row.get("exit_time") or "")
    return closed


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def _trade_id(signature: str, entry_ts: datetime, exit_ts: datetime) -> str:
    return (
        f"IC_{_safe_id(signature)}_"
        f"{entry_ts.strftime('%Y%m%d%H%M%S')}_{exit_ts.strftime('%Y%m%d%H%M%S')}"
    )


def _derive_exit_reason(
    entry_net_cash: float,
    exit_net_cash: float,
    pnl: float,
    exit_ts: datetime,
    legs: dict[str, Any],
) -> str:
    """Derive a structured exit reason from broker-fill signals.

    Replaces the historical "unknown" / "SYNC_CLOSED_POSITION" placeholder so the
    learning loop can distinguish profit-target closes from stop-loss closes
    from DTE-driven closes. Heuristic — fills carry no semantic tag, so we
    reconstruct from the same signals the guardian scripts use.
    """
    expiry_iso = (legs or {}).get("expiry")
    if expiry_iso:
        try:
            expiry_date = datetime.fromisoformat(str(expiry_iso)).date()
        except ValueError:
            expiry_date = None
    else:
        expiry_date = None

    if expiry_date and exit_ts.date() >= expiry_date:
        return "expired"

    if expiry_date:
        dte_at_exit = (expiry_date - exit_ts.date()).days
        if 0 < dte_at_exit <= 7:
            return "7dte"

    if entry_net_cash > 0:
        # Credit-entry IC: profit-target if we captured ≥50% of the credit;
        # stop-loss if we paid ≥100% of the credit on the way out.
        if pnl >= 0.5 * entry_net_cash:
            return "profit_target"
        if pnl <= -1.0 * entry_net_cash:
            return "stop_loss"

    return "manual_close"


def _to_closed_trade(entry: dict[str, Any], exit_event: dict[str, Any]) -> dict[str, Any]:
    signature = str(entry["signature"])
    entry_ts = entry["timestamp"]
    exit_ts = exit_event["timestamp"]
    pnl = round(entry["net_cash"] + exit_event["net_cash"], 2)
    outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
    legs = _signature_to_legs(signature)
    entry_net_cash = round(_parse_float(entry.get("net_cash"), 0.0), 2)
    exit_net_cash = round(_parse_float(exit_event.get("net_cash"), 0.0), 2)
    exit_reason = _derive_exit_reason(entry_net_cash, exit_net_cash, pnl, exit_ts, legs)

    return {
        "id": _trade_id(signature, entry_ts, exit_ts),
        "symbol": legs.get("underlying") or "SPY",
        "type": "option",
        "strategy": "iron_condor",
        "status": "closed",
        "entry_date": entry_ts.date().isoformat(),
        "exit_date": exit_ts.date().isoformat(),
        "entry_time": entry_ts.isoformat(),
        "exit_time": exit_ts.isoformat(),
        "entry_net_cash": entry_net_cash,
        "entry_credit": round(max(entry_net_cash, 0.0), 2),
        "entry_debit": round(max(-entry_net_cash, 0.0), 2),
        "entry_style": "credit" if entry_net_cash > 0 else "debit",
        "exit_net_cash": exit_net_cash,
        "exit_credit": round(max(exit_net_cash, 0.0), 2),
        "exit_debit": round(max(-exit_net_cash, 0.0), 2),
        "exit_style": "credit" if exit_net_cash > 0 else "debit",
        "realized_pnl": pnl,
        "outcome": outcome,
        "exit_reason": exit_reason,
        "signature": signature,
        "legs": legs,
        "source": f"{entry['source']}->{exit_event['source']}",
        "order_ids": {
            "entry": entry.get("order_ids", []),
            "exit": exit_event.get("order_ids", []),
        },
    }


def _pair_closed_trades(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_signature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        by_signature[str(event["signature"])].append(event)

    closed: list[dict[str, Any]] = []
    for signature, signature_events in by_signature.items():
        open_entries: deque[dict[str, Any]] = deque()
        for event in sorted(signature_events, key=lambda item: item["timestamp"]):
            if not open_entries:
                open_entries.append(event)
                continue

            entry = open_entries[0]
            event_is_credit = _parse_float(event.get("net_cash"), 0.0) > 0
            entry_is_credit = _parse_float(entry.get("net_cash"), 0.0) > 0

            if event_is_credit == entry_is_credit:
                open_entries.append(event)
                continue

            entry = open_entries.popleft()
            closed.append(_to_closed_trade(entry, event))

    closed.sort(key=lambda row: row.get("exit_time") or "")
    return closed


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return default


def _load_system_state() -> dict[str, Any]:
    return _load_json(SYSTEM_STATE_FILE, {})


def _load_ic_entries() -> dict[str, Any]:
    return _load_json(IC_ENTRIES_FILE, {})


def _expiry_from_entry_key(key: str) -> str | None:
    raw = str(key or "").strip()
    if not raw.startswith("IC_"):
        return None
    token = raw[3:9]
    if not re.fullmatch(r"\d{6}", token):
        return None
    year = 2000 + int(token[:2])
    month = int(token[2:4])
    day = int(token[4:6])
    try:
        return datetime(year, month, day, tzinfo=timezone.utc).date().isoformat()
    except ValueError:
        return None


def _normalize_entry_provenance_records(raw_entries: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_entries, dict):
        return []

    records: list[dict[str, Any]] = []
    for key, value in raw_entries.items():
        if not isinstance(value, dict):
            continue
        record = dict(value)
        record["_key"] = str(key)
        record["signature"] = str(record.get("signature") or "").strip()
        record["expiry"] = str(
            record.get("expiry") or _expiry_from_entry_key(str(key)) or ""
        ).strip()
        entry_ts = _parse_dt(record.get("entry_time") or record.get("date"))
        record["_entry_ts"] = entry_ts
        records.append(record)
    return records


def _normalized_dt(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _entry_provenance_for_trade(
    signature: str,
    entry_ts: datetime,
    raw_entries: Any,
) -> dict[str, Any]:
    records = _normalize_entry_provenance_records(raw_entries)
    if not records:
        return {}

    expiry = str(_signature_to_legs(signature).get("expiry") or "")
    target_ts = _normalized_dt(entry_ts)
    candidates = [
        record
        for record in records
        if record.get("signature") == signature or (expiry and record.get("expiry") == expiry)
    ]
    if not candidates:
        return {}

    def sort_key(record: dict[str, Any]) -> tuple[int, int, float]:
        signature_penalty = 0 if record.get("signature") == signature else 1
        expiry_penalty = 0 if record.get("expiry") == expiry else 1
        record_ts = _normalized_dt(record.get("_entry_ts"))
        if target_ts is None or record_ts is None:
            time_penalty = float("inf")
        else:
            time_penalty = abs((record_ts - target_ts).total_seconds())
        return (signature_penalty, expiry_penalty, time_penalty)

    chosen = min(candidates, key=sort_key)
    merged = {
        field: chosen.get(field)
        for field in ENTRY_PROVENANCE_FIELDS
        if chosen.get(field) not in (None, "", [])
    }
    if chosen.get("quantity") not in (None, "", []):
        merged["quantity"] = chosen.get("quantity")
    if chosen.get("entry_time") not in (None, "", []):
        merged["entry_time"] = chosen.get("entry_time")
    return merged


def _merge_entry_provenance(trade: dict[str, Any], raw_entries: Any) -> dict[str, Any]:
    signature = str(trade.get("signature") or "").strip()
    entry_ts = _parse_dt(trade.get("entry_time"))
    if not signature or entry_ts is None:
        return trade

    provenance = _entry_provenance_for_trade(signature, entry_ts, raw_entries)
    if not provenance:
        return trade

    merged = dict(trade)
    for key, value in provenance.items():
        if merged.get(key) in (None, "", []):
            merged[key] = value
    return merged


def _empty_ledger() -> dict[str, Any]:
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "meta": {
            "version": "1.1",
            "created": now_iso,
            "purpose": "Master ledger for closed iron condor tracking",
            "paper_phase_start": "2026-01-22",
            "last_sync": now_iso,
            "sync_source": "sync_closed_positions.py",
        },
        "stats": {},
        "trades": [],
    }


def _normalize_existing_trade_ids(trades: list[dict[str, Any]]) -> int:
    normalized = 0
    seen_ids: set[str] = set()
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if str(trade.get("status", "")).lower() != "closed":
            continue
        if str(trade.get("strategy", "")).lower() != "iron_condor":
            continue
        signature = str(trade.get("signature") or "")
        entry_dt = _parse_dt(trade.get("entry_time"))
        exit_dt = _parse_dt(trade.get("exit_time"))
        if not signature or entry_dt is None or exit_dt is None:
            continue

        expected = _trade_id(signature, entry_dt, exit_dt)
        current = str(trade.get("id") or "")
        if current != expected:
            trade["id"] = expected
            normalized += 1
        seen_ids.add(expected)
    return normalized


def _compute_stats(
    trades: list[dict[str, Any]],
    paper_phase_start: str,
    unpaired_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    closed = [
        row
        for row in trades
        if isinstance(row, dict)
        and str(row.get("status", "")).lower() == "closed"
        and str(row.get("strategy", "")).lower() == "iron_condor"
    ]
    open_trades = [
        row
        for row in trades
        if isinstance(row, dict)
        and str(row.get("status", "")).lower() == "open"
        and str(row.get("strategy", "")).lower() == "iron_condor"
    ]

    wins = [row for row in closed if _parse_float(row.get("realized_pnl"), 0.0) > 0]
    losses = [row for row in closed if _parse_float(row.get("realized_pnl"), 0.0) < 0]
    breakeven = [row for row in closed if _parse_float(row.get("realized_pnl"), 0.0) == 0.0]

    win_amounts = [_parse_float(row.get("realized_pnl"), 0.0) for row in wins]
    loss_amounts = [abs(_parse_float(row.get("realized_pnl"), 0.0)) for row in losses]
    total_wins = sum(win_amounts)
    total_losses = sum(loss_amounts)
    total_pnl = round(sum(_parse_float(row.get("realized_pnl"), 0.0) for row in closed), 2)

    # Fold unpaired singletons directly into all-time metrics if present
    u_wins = unpaired_stats.get("unpaired_wins", 0) if unpaired_stats else 0
    u_losses = unpaired_stats.get("unpaired_losses", 0) if unpaired_stats else 0
    u_breakeven = unpaired_stats.get("unpaired_breakeven", 0) if unpaired_stats else 0
    u_gross_profit = unpaired_stats.get("unpaired_gross_profit", 0.0) if unpaired_stats else 0.0
    u_gross_loss = unpaired_stats.get("unpaired_gross_loss", 0.0) if unpaired_stats else 0.0
    u_pnl = unpaired_stats.get("unpaired_realized_pnl", 0.0) if unpaired_stats else 0.0

    wins_folded = len(wins) + u_wins
    losses_folded = len(losses) + u_losses
    breakeven_folded = len(breakeven) + u_breakeven
    closed_folded = len(closed) + u_wins + u_losses + u_breakeven

    total_wins_folded = total_wins + u_gross_profit
    total_losses_folded = total_losses + u_gross_loss
    total_pnl_folded = round(total_pnl + u_pnl, 2)

    win_rate_pct = round((wins_folded / closed_folded) * 100.0, 2) if closed_folded else None
    avg_win = round(total_wins_folded / wins_folded, 2) if wins_folded else None
    avg_loss = round(total_losses_folded / losses_folded, 2) if losses_folded else None
    profit_factor = round(total_wins_folded / total_losses_folded, 2) if total_losses_folded > 0 else None
    expectancy = round(total_pnl_folded / closed_folded, 2) if closed_folded else None

    paper_days = 0
    try:
        start = datetime.fromisoformat(paper_phase_start).date()
        paper_days = (datetime.now(timezone.utc).date() - start).days
    except Exception:
        pass

    return {
        "total_trades": closed_folded + len(open_trades),
        "closed_trades": closed_folded,
        "open_trades": len(open_trades),
        "wins": wins_folded,
        "losses": losses_folded,
        "breakeven": breakeven_folded,
        "win_rate_pct": win_rate_pct,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "profit_factor": profit_factor,
        "expectancy": expectancy,
        "total_pnl": total_pnl_folded,
        "total_realized_pnl": total_pnl_folded,
        "paper_phase_start": paper_phase_start,
        "paper_phase_days": paper_days,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


COHORT_START_DATE = "2026-04-09"


def _compute_unpaired_singleton_pnl(
    trade_history: list[dict[str, Any]],
    paired_trades: list[dict[str, Any]],
    *,
    cohort_start: str = COHORT_START_DATE,
    open_symbols: set[str] | None = None,
) -> dict[str, Any]:
    """Surface SPY-option SIMPLE fills whose order_id never appears in any
    paired trade's exit order_ids.

    Returns:
      - unpaired_realized_pnl: signed_cash sum of all unpaired SPY-option
        SIMPLE fills (all-time).
      - unpaired_in_cohort_pnl: same, but filtered to filled_at >= cohort_start.
        THIS is the figure that feeds `.claude/rules/kill-criteria.md` math.
      - unpaired_order_count: count of dropped orders.
    """
    paired_exit_ids: set[str] = set()
    for trade in paired_trades:
        order_ids = trade.get("order_ids")
        if isinstance(order_ids, dict):
            # Include both entry and exit IDs to prevent double-counting
            for oid in (order_ids.get("entry") or []) + (order_ids.get("exit") or []):
                if oid:
                    paired_exit_ids.add(str(oid))

    try:
        cohort_dt = datetime.fromisoformat(cohort_start).replace(tzinfo=timezone.utc)
    except ValueError:
        cohort_dt = None

    unpaired_all = 0.0
    unpaired_cohort = 0.0
    unpaired_count = 0

    unpaired_wins_count = 0
    unpaired_losses_count = 0
    unpaired_breakeven_count = 0
    unpaired_gross_profit = 0.0
    unpaired_gross_loss = 0.0

    unpaired_cohort_wins_count = 0
    unpaired_cohort_losses_count = 0
    unpaired_cohort_breakeven_count = 0
    unpaired_cohort_gross_profit = 0.0
    unpaired_cohort_gross_loss = 0.0

    for row in trade_history:
        if not isinstance(row, dict):
            continue
        order_id = str(row.get("id") or "")
        if not order_id or order_id in paired_exit_ids:
            continue
        # Check if SPY option (handling MLEG with legs and SIMPLE symbols)
        symbol = str(row.get("symbol") or "")
        order_class = str(row.get("order_class") or "")
        raw_legs = row.get("legs") or []
        leg_symbols = []
        for leg in raw_legs:
            if isinstance(leg, dict) and leg.get("symbol"):
                leg_symbols.append(leg["symbol"])
            elif isinstance(leg, str):
                leg_symbols.append(leg)

        # Exclude open positions
        if open_symbols:
            if symbol in open_symbols:
                continue
            if any(ls in open_symbols for ls in leg_symbols):
                continue

        is_spy_opt = False
        if "MLEG" in order_class:
            if leg_symbols and all(ls.startswith("SPY") and len(ls) > 5 for ls in leg_symbols):
                is_spy_opt = True
        else:
            if symbol and symbol.startswith("SPY") and len(symbol) > 5:
                is_spy_opt = True

        if not is_spy_opt:
            continue

        filled_dt = _parse_dt(row.get("filled_at"))
        qty = _parse_float(row.get("qty"), 0.0)
        price = _parse_float(row.get("price"), 0.0)
        if filled_dt is None or qty <= 0:
            continue

        # Cash flow calculation
        if "MLEG" in order_class:
            cash = -qty * price * 100.0
        else:
            side = _parse_side(row.get("side"))
            if side is None or price <= 0:
                continue
            cash = _signed_cash(side, qty, price)
        unpaired_all += cash
        unpaired_count += 1

        if cash > 0:
            unpaired_wins_count += 1
            unpaired_gross_profit += cash
        elif cash < 0:
            unpaired_losses_count += 1
            unpaired_gross_loss += abs(cash)
        else:
            unpaired_breakeven_count += 1

        if cohort_dt is not None and filled_dt >= cohort_dt:
            unpaired_cohort += cash
            if cash > 0:
                unpaired_cohort_wins_count += 1
                unpaired_cohort_gross_profit += cash
            elif cash < 0:
                unpaired_cohort_losses_count += 1
                unpaired_cohort_gross_loss += abs(cash)
            else:
                unpaired_cohort_breakeven_count += 1

    return {
        "unpaired_realized_pnl": round(unpaired_all, 2),
        "unpaired_in_cohort_pnl": round(unpaired_cohort, 2),
        "unpaired_order_count": unpaired_count,
        "unpaired_cohort_start": cohort_start,
        "unpaired_wins": unpaired_wins_count,
        "unpaired_losses": unpaired_losses_count,
        "unpaired_breakeven": unpaired_breakeven_count,
        "unpaired_gross_profit": round(unpaired_gross_profit, 2),
        "unpaired_gross_loss": round(unpaired_gross_loss, 2),
        "unpaired_cohort_wins": unpaired_cohort_wins_count,
        "unpaired_cohort_losses": unpaired_cohort_losses_count,
        "unpaired_cohort_breakeven": unpaired_cohort_breakeven_count,
        "unpaired_cohort_gross_profit": round(unpaired_cohort_gross_profit, 2),
        "unpaired_cohort_gross_loss": round(unpaired_cohort_gross_loss, 2),
    }


def _learning_event_key(trade: dict[str, Any]) -> str:
    trade_id = str(trade.get("id") or "unknown")
    return f"closed_trade_sync::{trade_id}"


def _learning_feedback_type(trade: dict[str, Any]) -> str:
    outcome = str(trade.get("outcome") or "").strip().lower()
    pnl = _parse_float(trade.get("realized_pnl"), 0.0)
    if outcome == "win" or pnl > 0:
        return "positive"
    return "negative"


def _learning_context(trade: dict[str, Any]) -> str:
    symbol = str(trade.get("symbol") or "UNKNOWN")
    strategy = str(trade.get("strategy") or "unknown")
    outcome = str(trade.get("outcome") or "unknown")
    pnl = _parse_float(trade.get("realized_pnl"), 0.0)
    exit_time = str(trade.get("exit_time") or "unknown")
    return (
        "closed trade sync outcome "
        f"symbol={symbol} strategy={strategy} outcome={outcome} pnl={pnl:.2f} "
        f"exit_time={exit_time}"
    )


def _apply_learning_update_for_trade(
    trade: dict[str, Any], *, project_root: Path
) -> dict[str, Any]:
    event_key = _learning_event_key(trade)
    feedback_type = _learning_feedback_type(trade)
    context = _learning_context(trade)
    symbol = str(trade.get("symbol") or "SPY")
    strategy = str(trade.get("strategy") or "iron_condor")
    pnl = _parse_float(trade.get("realized_pnl"), 0.0)
    expiry = str((trade.get("legs") or {}).get("expiry") or "")
    trade_id = str(trade.get("id") or "")
    exit_time = str(trade.get("exit_time") or datetime.now(timezone.utc).isoformat())

    from src.learning.distributed_feedback import LocalBackend, aggregate_feedback
    from src.learning.outcome_labeler import build_outcome_label
    from src.learning.rlhf_storage import store_trade_outcome
    from src.learning.trade_episode_store import TradeEpisodeStore

    derived_exit_reason = str(trade.get("exit_reason") or "manual_close")

    outcome_label = build_outcome_label(
        {
            "symbol": symbol,
            "strategy": strategy,
            "realized_pl": pnl,
            "exit_reason": derived_exit_reason,
            "won": str(trade.get("outcome") or "").strip().lower() == "win",
            "exit_time": exit_time,
        }
    )
    distributed_outcome = aggregate_feedback(
        project_root=project_root,
        event_key=event_key,
        feedback_type=feedback_type,
        context=context,
        backend=LocalBackend(),
    )

    result: dict[str, Any] = {
        "event_key": event_key,
        "feedback_type": feedback_type,
        "distributed_applied": bool(distributed_outcome.get("applied")),
        "distributed_skipped_reason": distributed_outcome.get("skipped_reason"),
    }
    if not distributed_outcome.get("applied"):
        return result

    episode_store = TradeEpisodeStore(
        event_log_path=project_root / "data" / "feedback" / "trade_episode_events.jsonl",
        snapshot_path=project_root / "data" / "feedback" / "trade_episodes.json",
    )
    episode_store.upsert_outcome(
        {
            "episode_id": trade_id or event_key,
            "order_id": trade_id or None,
            "event_type": "outcome",
            "timestamp": exit_time,
            "event_key": event_key,
            "symbol": symbol,
            "strategy": strategy,
            "reward": float(outcome_label["reward"]),
            "return_pct": outcome_label["return_pct"],
            "won": bool(outcome_label["won"]),
            "lost": bool(outcome_label["lost"]),
            "outcome": outcome_label["outcome"],
            "holding_minutes": outcome_label["holding_minutes"],
            "exit_reason": derived_exit_reason,
            "expiry": expiry,
            "metadata": {
                "source": "sync_closed_positions",
                "trade_id": trade_id,
                "summary": outcome_label["summary"],
            },
        }
    )

    store_trade_outcome(
        symbol=symbol,
        strategy=strategy,
        reward=float(outcome_label["reward"]),
        won=bool(outcome_label["won"]),
        exit_reason=derived_exit_reason,
        expiry=expiry,
        episode_id=trade_id or event_key,
        event_key=event_key,
        metadata={
            "source": "sync_closed_positions",
            "trade_id": trade_id,
            "distributed_feedback_applied": True,
            "summary": outcome_label["summary"],
            "return_pct": outcome_label["return_pct"],
            "holding_minutes": outcome_label["holding_minutes"],
        },
    )
    result["applied"] = True
    return result


def sync_closed_positions(dry_run: bool = False) -> dict[str, Any]:
    logger.info("=" * 60)
    logger.info("SYNC CLOSED POSITIONS")
    logger.info("=" * 60)

    trade_history, trade_history_source = _load_trade_history()
    if not isinstance(trade_history, list) or not trade_history:
        logger.warning("No trade_history available from broker or system_state.json")
        return {"success": False, "error": "no_trade_history"}

    events = _collect_events(trade_history)
    inventory_candidates = _pair_closed_trades_from_inventory(trade_history)
    legacy_candidates = _pair_closed_trades(events)
    raw_ic_entries = _load_ic_entries()
    deduped_candidates: dict[str, dict[str, Any]] = {}
    for row in inventory_candidates + legacy_candidates:
        row = _merge_entry_provenance(row, raw_ic_entries)
        row_id = str(row.get("id") or "")
        if row_id and row_id not in deduped_candidates:
            deduped_candidates[row_id] = row
    closed_candidates = sorted(
        deduped_candidates.values(),
        key=lambda row: row.get("exit_time") or "",
    )
    logger.info(
        "Trade history source: %s | Events detected: %s | Inventory candidates: %s | Closed candidates: %s",
        trade_history_source,
        len(events),
        len(inventory_candidates),
        len(closed_candidates),
    )

    ledger = _load_json(TRADES_FILE, _empty_ledger())
    if not isinstance(ledger, dict):
        ledger = _empty_ledger()
    ledger.setdefault("meta", {})
    ledger.setdefault("stats", {})
    ledger.setdefault("trades", [])
    if not isinstance(ledger["trades"], list):
        ledger["trades"] = []

    existing_ids = {str(row.get("id")) for row in ledger["trades"] if isinstance(row, dict)}
    new_rows = [row for row in closed_candidates if str(row.get("id")) not in existing_ids]
    normalized_ids = _normalize_existing_trade_ids(ledger["trades"])
    if new_rows:
        ledger["trades"].extend(new_rows)

    paper_phase_start = (
        str(ledger.get("meta", {}).get("paper_phase_start"))
        or str(ledger.get("stats", {}).get("paper_phase_start"))
        or "2026-01-22"
    )
    system_state = _load_system_state()
    positions = system_state.get("positions") or []
    open_symbols = {p["symbol"] for p in positions if isinstance(p, dict) and p.get("symbol")}
    unpaired_stats = _compute_unpaired_singleton_pnl(
        trade_history,
        ledger["trades"],
        open_symbols=open_symbols,
    )
    ledger["stats"] = _compute_stats(ledger["trades"], paper_phase_start, unpaired_stats)
    ledger["stats"].update(unpaired_stats)
    ledger["meta"]["paper_phase_start"] = paper_phase_start
    ledger["meta"]["last_sync"] = datetime.now(timezone.utc).isoformat()
    ledger["meta"]["sync_source"] = "sync_closed_positions.py"

    new_payload = json.dumps(ledger, indent=2) + "\n"
    old_payload = TRADES_FILE.read_text(encoding="utf-8") if TRADES_FILE.exists() else ""
    changed = new_payload != old_payload

    if dry_run:
        logger.info(
            "Dry run: changed=%s new_closed=%s normalized_ids=%s",
            changed,
            len(new_rows),
            normalized_ids,
        )
        return {
            "success": True,
            "dry_run": True,
            "changed": changed,
            "new_closed": len(new_rows),
            "normalized_ids": normalized_ids,
            "closed_total": _parse_int(ledger.get("stats", {}).get("closed_trades"), 0),
            "trade_history_source": trade_history_source,
        }

    learning_applied = 0
    learning_duplicates = 0
    learning_errors = 0
    for row in new_rows:
        try:
            learning_outcome = _apply_learning_update_for_trade(row, project_root=PROJECT_ROOT)
            if learning_outcome.get("distributed_applied"):
                learning_applied += 1
            elif learning_outcome.get("distributed_skipped_reason") == "duplicate_event":
                learning_duplicates += 1
        except Exception as exc:
            learning_errors += 1
            logger.warning(
                "Learning update failed for trade_id=%s: %s",
                str(row.get("id") or ""),
                exc,
            )

    if changed:
        TRADES_FILE.parent.mkdir(parents=True, exist_ok=True)
        TRADES_FILE.write_text(new_payload, encoding="utf-8")
        logger.info(
            "Updated trades.json: new_closed=%s normalized_ids=%s closed_total=%s learning_applied=%s learning_duplicates=%s learning_errors=%s",
            len(new_rows),
            normalized_ids,
            ledger["stats"].get("closed_trades"),
            learning_applied,
            learning_duplicates,
            learning_errors,
        )
    else:
        logger.info("No ledger changes required")

    return {
        "success": True,
        "changed": changed,
        "new_closed": len(new_rows),
        "normalized_ids": normalized_ids,
        "closed_total": _parse_int(ledger.get("stats", {}).get("closed_trades"), 0),
        "learning_applied": learning_applied,
        "learning_duplicates": learning_duplicates,
        "learning_errors": learning_errors,
        "trade_history_source": trade_history_source,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Sync closed iron condor trades into trades.json")
    parser.add_argument("--dry-run", action="store_true", help="Show changes without writing")
    args = parser.parse_args()

    try:
        result = sync_closed_positions(dry_run=args.dry_run)
        if result.get("success"):
            return 0
        return 1
    except Exception as exc:
        logger.error("sync_closed_positions failed: %s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())

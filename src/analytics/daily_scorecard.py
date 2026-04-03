"""Direct daily trading scorecard from live Alpaca account state plus repo blockers."""

from __future__ import annotations

import importlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from src.utils.alpaca_client import get_alpaca_credentials, get_brokerage_credentials

ET_TZ = ZoneInfo("America/New_York")
_OCC_RE = re.compile(r"^(?P<underlying>[A-Z]{1,6})(?P<date>\d{6})[CP](?P<strike>\d{8})$")


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fmt_money(value: float | None) -> str:
    if value is None:
        return "n/a"
    if value < 0:
        return f"-${abs(value):,.2f}"
    return f"${value:,.2f}"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.2f}%"


@dataclass(frozen=True)
class PositionSnapshot:
    symbol: str
    qty: float
    intraday_pl: float
    unrealized_pl: float
    avg_entry_price: float
    current_price: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "intraday_pl": round(self.intraday_pl, 2),
            "unrealized_pl": round(self.unrealized_pl, 2),
            "avg_entry_price": round(self.avg_entry_price, 4),
            "current_price": round(self.current_price, 4),
        }


@dataclass(frozen=True)
class StructureSnapshot:
    structure_id: str
    underlying: str
    expiry: str | None
    positions: list[PositionSnapshot]
    intraday_pl: float
    unrealized_pl: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "structure_id": self.structure_id,
            "underlying": self.underlying,
            "expiry": self.expiry,
            "intraday_pl": round(self.intraday_pl, 2),
            "unrealized_pl": round(self.unrealized_pl, 2),
            "legs": [position.to_dict() for position in self.positions],
        }


@dataclass(frozen=True)
class FillSnapshot:
    symbol: str | None
    qty: float
    filled_avg_price: float
    filled_at_et: str
    side: str | None = None
    order_class: str | None = None
    structure_id: str | None = None
    premium_cash_flow: float | None = None
    source_order_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "qty": self.qty,
            "filled_avg_price": round(self.filled_avg_price, 4),
            "filled_at_et": self.filled_at_et,
            "side": self.side,
            "order_class": self.order_class,
            "structure_id": self.structure_id,
            "premium_cash_flow": round(self.premium_cash_flow, 2)
            if self.premium_cash_flow is not None
            else None,
            "source_order_id": self.source_order_id,
        }


def _driver_entry_from_position(position: PositionSnapshot) -> dict[str, Any]:
    return {
        "symbol": position.symbol,
        "qty": position.qty,
        "intraday_pl": round(position.intraday_pl, 2),
        "unrealized_pl": round(position.unrealized_pl, 2),
        "avg_entry_price": round(position.avg_entry_price, 4),
        "current_price": round(position.current_price, 4),
    }


def _driver_entry_from_structure(structure: StructureSnapshot) -> dict[str, Any]:
    return {
        "structure_id": structure.structure_id,
        "underlying": structure.underlying,
        "expiry": structure.expiry,
        "intraday_pl": round(structure.intraday_pl, 2),
        "unrealized_pl": round(structure.unrealized_pl, 2),
        "legs_count": len(structure.positions),
    }


def _normalize_side(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().upper()
    if text.startswith("ORDERSIDE."):
        text = text.split(".", 1)[1]
    return text or None


def _contract_multiplier(symbol: str | None) -> float:
    return 100.0 if symbol and _OCC_RE.match(symbol.strip().upper()) else 1.0


def _signed_premium_cash_flow(
    symbol: str | None, qty: float, price: float, side: str | None
) -> float:
    if side is None:
        return 0.0
    if "SELL" in side:
        sign = 1.0
    elif "BUY" in side:
        sign = -1.0
    else:
        sign = 0.0
    return round(sign * abs(qty) * price * _contract_multiplier(symbol), 2)


def _position_from_alpaca(position: Any) -> PositionSnapshot:
    return PositionSnapshot(
        symbol=str(getattr(position, "symbol", "")),
        qty=_as_float(getattr(position, "qty", 0)),
        intraday_pl=_as_float(getattr(position, "unrealized_intraday_pl", 0)),
        unrealized_pl=_as_float(getattr(position, "unrealized_pl", 0)),
        avg_entry_price=_as_float(getattr(position, "avg_entry_price", 0)),
        current_price=_as_float(getattr(position, "current_price", 0)),
    )


def _group_structure_key(symbol: str) -> tuple[str, str | None, str]:
    match = _OCC_RE.match(symbol.strip().upper())
    if not match:
        return symbol.upper(), None, symbol.upper()
    underlying = match.group("underlying")
    expiry_raw = match.group("date")
    expiry = f"20{expiry_raw[:2]}-{expiry_raw[2:4]}-{expiry_raw[4:6]}"
    return underlying, expiry, f"{underlying} {expiry}"


def summarize_open_structures(positions: list[PositionSnapshot]) -> list[StructureSnapshot]:
    grouped: dict[str, dict[str, Any]] = {}
    for position in positions:
        underlying, expiry, structure_id = _group_structure_key(position.symbol)
        bucket = grouped.setdefault(
            structure_id,
            {
                "underlying": underlying,
                "expiry": expiry,
                "positions": [],
                "intraday_pl": 0.0,
                "unrealized_pl": 0.0,
            },
        )
        bucket["positions"].append(position)
        bucket["intraday_pl"] += position.intraday_pl
        bucket["unrealized_pl"] += position.unrealized_pl

    structures = [
        StructureSnapshot(
            structure_id=structure_id,
            underlying=str(bucket["underlying"]),
            expiry=bucket["expiry"],
            positions=sorted(bucket["positions"], key=lambda position: position.symbol),
            intraday_pl=round(bucket["intraday_pl"], 2),
            unrealized_pl=round(bucket["unrealized_pl"], 2),
        )
        for structure_id, bucket in grouped.items()
    ]
    return sorted(structures, key=lambda structure: structure.structure_id)


def _fill_structure_id(symbol: str | None) -> str | None:
    if not symbol:
        return None
    _, _, structure_id = _group_structure_key(symbol)
    return structure_id


def _rank_position_drivers(
    positions: list[PositionSnapshot], *, positive: bool, limit: int = 3
) -> list[dict[str, Any]]:
    filtered = (
        [position for position in positions if position.intraday_pl > 0]
        if positive
        else [position for position in positions if position.intraday_pl < 0]
    )
    ranked = sorted(filtered, key=lambda position: position.intraday_pl, reverse=positive)
    return [_driver_entry_from_position(position) for position in ranked[:limit]]


def _rank_structure_drivers(
    structures: list[StructureSnapshot], *, positive: bool, limit: int = 3
) -> list[dict[str, Any]]:
    filtered = (
        [structure for structure in structures if structure.intraday_pl > 0]
        if positive
        else [structure for structure in structures if structure.intraday_pl < 0]
    )
    ranked = sorted(filtered, key=lambda structure: structure.intraday_pl, reverse=positive)
    return [_driver_entry_from_structure(structure) for structure in ranked[:limit]]


def _summarize_why_today(
    positions: list[PositionSnapshot],
    structures: list[StructureSnapshot],
    fills_today: list[FillSnapshot],
    *,
    total_change: float,
    realized_today: float,
    unrealized_today: float,
) -> dict[str, Any]:
    top_dragging_structure = _rank_structure_drivers(structures, positive=False, limit=1)
    top_offsetting_structure = _rank_structure_drivers(structures, positive=True, limit=1)
    top_dragging_leg = _rank_position_drivers(positions, positive=False, limit=1)
    top_offsetting_leg = _rank_position_drivers(positions, positive=True, limit=1)

    if not positions:
        summary = (
            "No open positions are contributing to today's move."
            if not fills_today
            else "No open positions remain; today's move is driven by fills and closed activity."
        )
    else:
        driver_bits: list[str] = []
        contribution_bits = []
        if fills_today or realized_today:
            contribution_bits.append(
                f"realized activity {_fmt_money(realized_today)} across {len(fills_today)} fills"
            )
        contribution_bits.append(f"open-position repricing {_fmt_money(unrealized_today)}")

        if total_change < 0:
            summary = "Today's loss comes from "
        elif total_change > 0:
            summary = "Today's gain comes from "
        else:
            summary = "Today's flat result comes from "
        summary += ", ".join(
            sorted(
                contribution_bits,
                key=lambda item: (
                    abs(realized_today)
                    if item.startswith("realized activity")
                    else abs(unrealized_today)
                ),
                reverse=True,
            )
        )

        if top_dragging_structure:
            driver_bits.append(
                f"biggest structure drag {top_dragging_structure[0]['structure_id']} "
                f"{_fmt_money(top_dragging_structure[0]['intraday_pl'])}"
            )
        if top_offsetting_structure:
            driver_bits.append(
                f"biggest structure offset {top_offsetting_structure[0]['structure_id']} "
                f"{_fmt_money(top_offsetting_structure[0]['intraday_pl'])}"
            )
        if top_dragging_leg:
            driver_bits.append(
                f"biggest leg drag {top_dragging_leg[0]['symbol']} "
                f"{_fmt_money(top_dragging_leg[0]['intraday_pl'])}"
            )
        if top_offsetting_leg:
            driver_bits.append(
                f"biggest leg offset {top_offsetting_leg[0]['symbol']} "
                f"{_fmt_money(top_offsetting_leg[0]['intraday_pl'])}"
            )
        if driver_bits:
            summary += f". Drivers: {'; '.join(driver_bits)}."
        else:
            summary += "."

    return {
        "summary": summary,
        "top_dragging_structures": _rank_structure_drivers(structures, positive=False),
        "top_offsetting_structures": _rank_structure_drivers(structures, positive=True),
        "top_dragging_legs": _rank_position_drivers(positions, positive=False),
        "top_offsetting_legs": _rank_position_drivers(positions, positive=True),
        "filled_orders_today_count": len(fills_today),
    }


def _filled_today(order: Any, now: datetime) -> tuple[datetime, str] | None:
    filled_at = getattr(order, "filled_at", None)
    if filled_at is None:
        return None
    filled_et = filled_at.astimezone(ET_TZ)
    if filled_et.date() != now.date():
        return None
    return filled_at, filled_et.isoformat()


def _fill_from_leg(leg: Any, *, filled_at_et: str, source_order_id: str | None) -> FillSnapshot:
    symbol = getattr(leg, "symbol", None)
    qty = _as_float(getattr(leg, "filled_qty", None), _as_float(getattr(leg, "qty", 0)))
    side = _normalize_side(getattr(leg, "side", None))
    price = _as_float(getattr(leg, "filled_avg_price", 0))
    return FillSnapshot(
        symbol=symbol,
        qty=qty,
        filled_avg_price=price,
        filled_at_et=filled_at_et,
        side=side,
        order_class="MLEG_LEG",
        structure_id=_fill_structure_id(symbol),
        premium_cash_flow=_signed_premium_cash_flow(symbol, qty, price, side),
        source_order_id=source_order_id,
    )


def _fill_from_order(order: Any, now: datetime) -> FillSnapshot | None:
    filled = _filled_today(order, now)
    if filled is None:
        return None
    _, filled_at_et = filled
    symbol = getattr(order, "symbol", None)
    qty = _as_float(getattr(order, "filled_qty", None), _as_float(getattr(order, "qty", 0)))
    side = _normalize_side(getattr(order, "side", None))
    order_class = str(getattr(order, "order_class", "") or "") or None
    return FillSnapshot(
        symbol=symbol,
        qty=qty,
        filled_avg_price=_as_float(getattr(order, "filled_avg_price", 0)),
        filled_at_et=filled_at_et,
        side=side,
        order_class=order_class,
        structure_id=_fill_structure_id(symbol),
        premium_cash_flow=_signed_premium_cash_flow(
            symbol, qty, _as_float(getattr(order, "filled_avg_price", 0)), side
        ),
        source_order_id=str(getattr(order, "id", "") or "") or None,
    )


def _flatten_fill_legs_from_order(order: Any, now: datetime) -> list[FillSnapshot]:
    filled = _filled_today(order, now)
    if filled is None:
        return []
    _, filled_at_et = filled
    legs = getattr(order, "legs", None)
    order_id = str(getattr(order, "id", "") or "") or None
    if legs:
        return [
            _fill_from_leg(leg, filled_at_et=filled_at_et, source_order_id=order_id) for leg in legs
        ]
    fill = _fill_from_order(order, now)
    return [fill] if fill is not None else []


def summarize_fill_activity_by_structure(fill_legs: list[FillSnapshot]) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for fill in fill_legs:
        structure_id = fill.structure_id or fill.symbol or "UNKNOWN"
        bucket = grouped.setdefault(
            structure_id,
            {
                "structure_id": structure_id,
                "premium_cash_flow": 0.0,
                "buy_premium_cash_flow": 0.0,
                "sell_premium_cash_flow": 0.0,
                "fills_count": 0,
                "symbols": set(),
            },
        )
        bucket["premium_cash_flow"] += fill.premium_cash_flow or 0.0
        bucket["fills_count"] += 1
        if fill.symbol:
            bucket["symbols"].add(fill.symbol)
        side = fill.side or ""
        if "BUY" in side:
            bucket["buy_premium_cash_flow"] += abs(fill.premium_cash_flow or 0.0)
        elif "SELL" in side:
            bucket["sell_premium_cash_flow"] += abs(fill.premium_cash_flow or 0.0)

    summaries = []
    for bucket in grouped.values():
        summaries.append(
            {
                "structure_id": bucket["structure_id"],
                "premium_cash_flow": round(bucket["premium_cash_flow"], 2),
                "buy_premium_cash_flow": round(bucket["buy_premium_cash_flow"], 2),
                "sell_premium_cash_flow": round(bucket["sell_premium_cash_flow"], 2),
                "fills_count": bucket["fills_count"],
                "symbols": sorted(bucket["symbols"]),
            }
        )
    return sorted(summaries, key=lambda item: abs(item["premium_cash_flow"]), reverse=True)


def _build_account_scorecard(
    label: str, account: Any, positions: list[Any], orders: list[Any], now: datetime
) -> dict[str, Any]:
    position_views = [_position_from_alpaca(position) for position in positions]
    structure_views = summarize_open_structures(position_views)
    filled_orders_today = [
        fill for order in orders if (fill := _fill_from_order(order, now)) is not None
    ]
    fill_legs_today = [
        fill for order in orders for fill in _flatten_fill_legs_from_order(order, now)
    ]
    fill_activity_by_structure = summarize_fill_activity_by_structure(fill_legs_today)

    equity = _as_float(getattr(account, "equity", 0))
    last_equity = _as_float(getattr(account, "last_equity", 0))
    total_change = round(equity - last_equity, 2)
    unrealized_today = round(sum(position.intraday_pl for position in position_views), 2)
    realized_today = round(total_change - unrealized_today, 2)
    realized_method = (
        "exact_from_account_delta_no_fills"
        if not filled_orders_today
        else "derived_from_account_delta_minus_open_position_intraday_marks"
    )
    why_today = _summarize_why_today(
        position_views,
        structure_views,
        filled_orders_today,
        total_change=total_change,
        realized_today=realized_today,
        unrealized_today=unrealized_today,
    )

    return {
        "account_label": label,
        "equity": round(equity, 2),
        "last_equity": round(last_equity, 2),
        "cash": round(_as_float(getattr(account, "cash", 0)), 2),
        "buying_power": round(_as_float(getattr(account, "buying_power", 0)), 2),
        "total_pnl_today": total_change,
        "realized_pnl_today": realized_today,
        "realized_pnl_method": realized_method,
        "unrealized_pnl_today": unrealized_today,
        "fills_today_count": len(filled_orders_today),
        "fills_today": [fill.to_dict() for fill in filled_orders_today],
        "fill_legs_today_count": len(fill_legs_today),
        "fill_legs_today": [fill.to_dict() for fill in fill_legs_today],
        "fill_activity_method": "exact_filled_order_leg_cash_flows_grouped_by_structure",
        "fill_activity_by_structure": fill_activity_by_structure,
        "positions_count": len(position_views),
        "open_positions": [position.to_dict() for position in position_views],
        "open_structures": [structure.to_dict() for structure in structure_views],
        "why_today": why_today,
    }


def _load_north_star_status(repo_root: Path, now: datetime) -> dict[str, Any]:
    state = _load_json(repo_root / "data" / "system_state.json", {})
    if not isinstance(state, dict):
        return {"available": False, "reason": "system_state.json missing or invalid"}

    north_star = state.get("north_star") if isinstance(state.get("north_star"), dict) else {}
    weekly_gate = (
        state.get("north_star_weekly_gate")
        if isinstance(state.get("north_star_weekly_gate"), dict)
        else {}
    )
    cadence_kpi = (
        weekly_gate.get("cadence_kpi") if isinstance(weekly_gate.get("cadence_kpi"), dict) else {}
    )
    scaling_sample_gate = (
        weekly_gate.get("scaling_sample_gate")
        if isinstance(weekly_gate.get("scaling_sample_gate"), dict)
        else {}
    )
    updated_at_raw = (
        north_star.get("updated_at")
        or weekly_gate.get("updated_at")
        or state.get("last_updated")
        or state.get("meta", {}).get("last_updated")
    )
    updated_at = _parse_iso(updated_at_raw)
    stale = True
    if updated_at is not None:
        stale = (now.astimezone(timezone.utc) - updated_at).total_seconds() > 24 * 60 * 60

    return {
        "available": True,
        "updated_at": updated_at.isoformat().replace("+00:00", "Z") if updated_at else None,
        "stale": stale,
        "probability_score": north_star.get("probability_score"),
        "probability_label": north_star.get("probability_label"),
        "estimated_monthly_after_tax": north_star.get(
            "estimated_monthly_after_tax_from_expectancy"
        ),
        "monthly_target_progress_pct": north_star.get("monthly_target_progress_pct"),
        "qualified_setups_this_week": cadence_kpi.get("qualified_setups_observed"),
        "closed_trades_this_week": cadence_kpi.get("closed_trades_observed"),
        "verified_edge_available": weekly_gate.get("verified_edge_available"),
        "recommended_max_position_pct": weekly_gate.get("recommended_max_position_pct"),
        "scale_allowed": bool(
            weekly_gate.get("verified_edge_available")
            and not weekly_gate.get("scale_blocked_by_cadence")
            and scaling_sample_gate.get("passed")
        ),
        "scaling_gate_closed_trades_observed": scaling_sample_gate.get("closed_trades_observed"),
        "scaling_gate_min_closed_trades": scaling_sample_gate.get("min_closed_trades_for_scaling"),
        "blocker_reason": weekly_gate.get("reason") or cadence_kpi.get("summary"),
    }


def _paired_trade_structure_id(trade: dict[str, Any]) -> str:
    legs = trade.get("legs")
    if isinstance(legs, dict):
        underlying = str(legs.get("underlying") or trade.get("symbol") or "UNKNOWN")
        expiry = str(legs.get("expiry") or "").strip()
        if expiry:
            return f"{underlying} {expiry}"
    signature = str(trade.get("signature") or "").strip()
    if signature:
        parts = signature.split("_")
        if len(parts) >= 2:
            return f"{parts[0]} {parts[1]}"
        return signature
    return str(trade.get("symbol") or "UNKNOWN")


def _paired_trade_exit_dt(trade: dict[str, Any]) -> datetime | None:
    return (
        _parse_iso(trade.get("exit_time"))
        or _parse_iso(trade.get("closed_at"))
        or _parse_iso(trade.get("timestamp"))
    )


def _load_paired_closed_trade_status(repo_root: Path, now: datetime) -> dict[str, Any]:
    ledger_path = repo_root / "data" / "trades.json"
    payload = _load_json(ledger_path, {})
    if not isinstance(payload, dict):
        return {"available": False, "reason": "trades.json missing or invalid"}

    trades = payload.get("trades")
    if not isinstance(trades, list):
        trades = []
    meta = payload.get("meta") if isinstance(payload.get("meta"), dict) else {}
    stats = payload.get("stats") if isinstance(payload.get("stats"), dict) else {}

    today_iso = now.date().isoformat()
    closed_today: list[dict[str, Any]] = []
    for trade in trades:
        if not isinstance(trade, dict):
            continue
        if str(trade.get("status", "")).lower() != "closed":
            continue
        exit_dt = _paired_trade_exit_dt(trade)
        exit_date = str(trade.get("exit_date") or "")
        if exit_date != today_iso and (
            exit_dt is None or exit_dt.astimezone(ET_TZ).date() != now.date()
        ):
            continue
        closed_today.append(
            {
                "trade_id": str(trade.get("id") or ""),
                "structure_id": _paired_trade_structure_id(trade),
                "signature": trade.get("signature"),
                "realized_pnl": round(_as_float(trade.get("realized_pnl", 0.0)), 2),
                "outcome": str(trade.get("outcome") or ""),
                "entry_style": trade.get("entry_style"),
                "exit_style": trade.get("exit_style"),
                "exit_time": exit_dt.astimezone(ET_TZ).isoformat()
                if exit_dt
                else trade.get("exit_time"),
            }
        )

    closed_today.sort(
        key=lambda row: abs(_as_float(row.get("realized_pnl"), 0.0)),
        reverse=True,
    )
    return {
        "available": True,
        "ledger_path": str(ledger_path),
        "ledger_last_updated": meta.get("last_sync") or stats.get("last_updated"),
        "closed_trades_total": stats.get("closed_trades"),
        "closed_trades_today_count": len(closed_today),
        "exact_realized_pnl_today": round(
            sum(_as_float(row.get("realized_pnl"), 0.0) for row in closed_today), 2
        ),
        "closed_trades_today": closed_today,
    }


def _sync_paired_closed_trade_ledger(repo_root: Path) -> dict[str, Any]:
    try:
        sync_module = importlib.import_module("scripts.sync_closed_positions")
    except Exception as exc:
        return {"attempted": True, "success": False, "error": f"import_failed: {exc}"}

    original_values = {
        "PROJECT_ROOT": getattr(sync_module, "PROJECT_ROOT", None),
        "DATA_DIR": getattr(sync_module, "DATA_DIR", None),
        "SYSTEM_STATE_FILE": getattr(sync_module, "SYSTEM_STATE_FILE", None),
        "TRADES_FILE": getattr(sync_module, "TRADES_FILE", None),
    }
    try:
        data_dir = repo_root / "data"
        sync_module.PROJECT_ROOT = repo_root
        sync_module.DATA_DIR = data_dir
        sync_module.SYSTEM_STATE_FILE = data_dir / "system_state.json"
        sync_module.TRADES_FILE = data_dir / "trades.json"
        result = sync_module.sync_closed_positions(dry_run=False)
        if not isinstance(result, dict):
            result = {"success": False, "error": "sync_returned_non_dict"}
        return {"attempted": True, **result}
    except Exception as exc:
        return {"attempted": True, "success": False, "error": str(exc)}
    finally:
        for name, value in original_values.items():
            setattr(sync_module, name, value)


def _create_client(credentials: tuple[str | None, str | None], *, paper: bool) -> Any | None:
    api_key, secret_key = credentials
    if not api_key or not secret_key:
        return None
    from alpaca.trading.client import TradingClient

    return TradingClient(api_key, secret_key, paper=paper)


def build_daily_scorecard(
    repo_root: Path,
    *,
    now: datetime | None = None,
    paper_client: Any | None = None,
    live_client: Any | None = None,
    sync_paired_ledger: bool = False,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    now = now or datetime.now(ET_TZ)

    paper_client = paper_client or _create_client(get_alpaca_credentials(), paper=True)
    live_client = live_client or _create_client(get_brokerage_credentials(), paper=False)
    paired_closed_trade_sync = (
        _sync_paired_closed_trade_ledger(repo_root)
        if sync_paired_ledger
        else {"attempted": False, "success": None}
    )

    scorecard: dict[str, Any] = {
        "generated_at_et": now.isoformat(),
        "repo_root": str(repo_root),
        "paper": None,
        "live": None,
        "north_star": _load_north_star_status(repo_root, now),
        "paired_closed_trade_sync": paired_closed_trade_sync,
        "paired_closed_trades": _load_paired_closed_trade_status(repo_root, now),
    }

    if paper_client is not None:
        from alpaca.trading.enums import QueryOrderStatus
        from alpaca.trading.requests import GetOrdersRequest

        paper_orders = paper_client.get_orders(
            filter=GetOrdersRequest(
                status=QueryOrderStatus.ALL, limit=200, nested=True, direction="desc"
            )
        )
        scorecard["paper"] = _build_account_scorecard(
            "paper",
            paper_client.get_account(),
            paper_client.get_all_positions(),
            paper_orders,
            now,
        )
    else:
        scorecard["paper"] = {
            "available": False,
            "reason": "Paper Alpaca credentials not available.",
        }

    if live_client is not None:
        scorecard["live"] = _build_account_scorecard(
            "live",
            live_client.get_account(),
            live_client.get_all_positions(),
            [],
            now,
        )
    else:
        scorecard["live"] = {"available": False, "reason": "Live Alpaca credentials not available."}

    return scorecard


def render_daily_scorecard_markdown(scorecard: dict[str, Any]) -> str:
    paper = scorecard.get("paper") or {}
    live = scorecard.get("live") or {}
    north_star = scorecard.get("north_star") or {}
    why_today = paper.get("why_today") or {}
    paired_sync = scorecard.get("paired_closed_trade_sync") or {}
    paired_closed = scorecard.get("paired_closed_trades") or {}

    def _structure_line(structure: dict[str, Any]) -> str:
        return (
            f"- `{structure.get('structure_id')}`: intraday `{_fmt_money(structure.get('intraday_pl'))}`, "
            f"unrealized `{_fmt_money(structure.get('unrealized_pl'))}`, legs `{len(structure.get('legs') or [])}`"
        )

    def _driver_structure_line(structure: dict[str, Any]) -> str:
        return (
            f"- `{structure.get('structure_id')}`: intraday `{_fmt_money(structure.get('intraday_pl'))}`, "
            f"unrealized `{_fmt_money(structure.get('unrealized_pl'))}`, legs `{structure.get('legs_count')}`"
        )

    def _driver_leg_line(position: dict[str, Any]) -> str:
        return (
            f"- `{position.get('symbol')}` qty `{position.get('qty')}`: intraday "
            f"`{_fmt_money(position.get('intraday_pl'))}`, unrealized "
            f"`{_fmt_money(position.get('unrealized_pl'))}`"
        )

    def _fill_activity_line(structure: dict[str, Any]) -> str:
        return (
            f"- `{structure.get('structure_id')}`: net premium cash flow "
            f"`{_fmt_money(structure.get('premium_cash_flow'))}`, buy premium "
            f"`{_fmt_money(structure.get('buy_premium_cash_flow'))}`, sell premium "
            f"`{_fmt_money(structure.get('sell_premium_cash_flow'))}`, fills "
            f"`{structure.get('fills_count')}`"
        )

    def _closed_trade_line(trade: dict[str, Any]) -> str:
        return (
            f"- `{trade.get('structure_id')}`: exact realized P/L "
            f"`{_fmt_money(trade.get('realized_pnl'))}`, outcome "
            f"`{trade.get('outcome')}`, exit `{trade.get('exit_time')}`"
        )

    lines = [
        "# Daily Trading Scorecard",
        "",
        f"- Generated at ET: `{scorecard.get('generated_at_et')}`",
        "",
        "## Today",
        f"- Paper realized P/L: `{_fmt_money(paper.get('realized_pnl_today'))}`",
        f"- Paper realized method: `{paper.get('realized_pnl_method', 'n/a')}`",
        f"- Paper unrealized P/L: `{_fmt_money(paper.get('unrealized_pnl_today'))}`",
        f"- Paper total P/L: `{_fmt_money(paper.get('total_pnl_today'))}`",
        f"- Paper fills today: `{paper.get('fills_today_count', 'n/a')}`",
        f"- Paper equity: `{_fmt_money(paper.get('equity'))}`",
        f"- Live total P/L: `{_fmt_money(live.get('total_pnl_today'))}`",
        f"- Live equity: `{_fmt_money(live.get('equity'))}`",
        "",
        "## Why Today",
        f"- Summary: `{why_today.get('summary', 'n/a')}`",
        "- Top dragging structures:",
    ]
    lines.extend(
        [
            _driver_structure_line(structure)
            for structure in why_today.get("top_dragging_structures", [])
        ]
        or ["- None"]
    )
    lines.extend(
        [
            "- Top offsetting structures:",
            *(
                [
                    _driver_structure_line(structure)
                    for structure in why_today.get("top_offsetting_structures", [])
                ]
                or ["- None"]
            ),
            "- Top dragging legs:",
            *(
                [_driver_leg_line(position) for position in why_today.get("top_dragging_legs", [])]
                or ["- None"]
            ),
            "- Top offsetting legs:",
            *(
                [
                    _driver_leg_line(position)
                    for position in why_today.get("top_offsetting_legs", [])
                ]
                or ["- None"]
            ),
            "",
            "## Fill Attribution",
            f"- Filled orders today: `{paper.get('fills_today_count', 'n/a')}`",
            f"- Attributed fill legs today: `{paper.get('fill_legs_today_count', 'n/a')}`",
            f"- Fill attribution method: `{paper.get('fill_activity_method', 'n/a')}`",
            *(
                [
                    _fill_activity_line(structure)
                    for structure in paper.get("fill_activity_by_structure", [])
                ]
                or ["- None"]
            ),
            "",
            "## Paired Ledger Sync",
            f"- Sync attempted: `{paired_sync.get('attempted')}`",
            f"- Sync success: `{paired_sync.get('success')}`",
            f"- Ledger changed: `{paired_sync.get('changed', 'n/a')}`",
            f"- New closed trades added: `{paired_sync.get('new_closed', 'n/a')}`",
            f"- Closed trades total after sync: `{paired_sync.get('closed_total', 'n/a')}`",
            f"- Sync error: `{paired_sync.get('error', 'n/a')}`",
            "",
            "## Exact Closed Structures Today",
            f"- Paired closed trades today: `{paired_closed.get('closed_trades_today_count', 'n/a')}`",
            f"- Exact realized P/L from paired ledger: `{_fmt_money(paired_closed.get('exact_realized_pnl_today'))}`",
            f"- Paired ledger closed trades total: `{paired_closed.get('closed_trades_total', 'n/a')}`",
            f"- Paired ledger last updated: `{paired_closed.get('ledger_last_updated', 'n/a')}`",
            *(
                [
                    _closed_trade_line(trade)
                    for trade in paired_closed.get("closed_trades_today", [])
                ]
                or ["- None"]
            ),
            "",
            "## Open Structures",
        ]
    )
    lines.extend(
        [_structure_line(structure) for structure in paper.get("open_structures", [])] or ["- None"]
    )
    lines.extend(
        [
            "",
            "## North Star",
            f"- Estimated monthly after-tax: `{_fmt_money(north_star.get('estimated_monthly_after_tax'))}`",
            f"- Monthly progress: `{_fmt_pct(north_star.get('monthly_target_progress_pct'))}`",
            f"- Qualified setups this week: `{north_star.get('qualified_setups_this_week')}`",
            f"- Closed trades this week: `{north_star.get('closed_trades_this_week')}`",
            f"- Verified edge available: `{north_star.get('verified_edge_available')}`",
            f"- Scale allowed: `{north_star.get('scale_allowed')}`",
            f"- Recommended max position pct: `{north_star.get('recommended_max_position_pct')}`",
            f"- Scaling sample gate: `{north_star.get('scaling_gate_closed_trades_observed')}` / `{north_star.get('scaling_gate_min_closed_trades')}`",
            f"- Exact blocker: `{north_star.get('blocker_reason')}`",
            f"- North Star snapshot stale: `{north_star.get('stale')}`",
        ]
    )
    return "\n".join(lines) + "\n"


def write_daily_scorecard_artifacts(
    repo_root: Path,
    *,
    json_out: Path,
    markdown_out: Path,
    now: datetime | None = None,
    paper_client: Any | None = None,
    live_client: Any | None = None,
    sync_paired_ledger: bool = True,
) -> dict[str, Any]:
    scorecard = build_daily_scorecard(
        repo_root,
        now=now,
        paper_client=paper_client,
        live_client=live_client,
        sync_paired_ledger=sync_paired_ledger,
    )
    json_out.parent.mkdir(parents=True, exist_ok=True)
    markdown_out.parent.mkdir(parents=True, exist_ok=True)
    json_out.write_text(json.dumps(scorecard, indent=2), encoding="utf-8")
    markdown_out.write_text(render_daily_scorecard_markdown(scorecard), encoding="utf-8")
    return scorecard

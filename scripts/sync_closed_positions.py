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
OPTION_SYMBOL_RE = re.compile(
    r"^(?P<underlying>[A-Z]{1,8})(?P<yy>\d{2})(?P<mm>\d{2})(?P<dd>\d{2})(?P<kind>[CP])(?P<strike>\d{8})$"
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


def _event_from_parent_order(row: dict[str, Any]) -> dict[str, Any] | None:
    filled_dt = _parse_dt(row.get("filled_at"))
    if filled_dt is None:
        return None
    side = _parse_side(row.get("side"))
    if side is None:
        return None

    legs_symbols = row.get("legs") if isinstance(row.get("legs"), list) else []
    parsed_legs = [parsed for symbol in legs_symbols if (parsed := _parse_option_symbol(symbol))]
    signature = _build_signature(parsed_legs)
    if signature is None:
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
        "symbols": sorted({str(s) for s in legs_symbols if s}),
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


def _safe_id(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]+", "_", value).strip("_")


def _trade_id(signature: str, entry_ts: datetime, exit_ts: datetime) -> str:
    return (
        f"IC_{_safe_id(signature)}_"
        f"{entry_ts.strftime('%Y%m%d%H%M%S')}_{exit_ts.strftime('%Y%m%d%H%M%S')}"
    )


def _to_closed_trade(entry: dict[str, Any], exit_event: dict[str, Any]) -> dict[str, Any]:
    signature = str(entry["signature"])
    entry_ts = entry["timestamp"]
    exit_ts = exit_event["timestamp"]
    pnl = round(entry["net_cash"] + exit_event["net_cash"], 2)
    outcome = "win" if pnl > 0 else "loss" if pnl < 0 else "breakeven"
    legs = _signature_to_legs(signature)

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
        "entry_credit": round(max(entry["net_cash"], 0.0), 2),
        "exit_debit": round(max(-exit_event["net_cash"], 0.0), 2),
        "realized_pnl": pnl,
        "outcome": outcome,
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
            if event["net_cash"] > 0:
                open_entries.append(event)
                continue
            if event["net_cash"] < 0 and open_entries:
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


def _compute_stats(trades: list[dict[str, Any]], paper_phase_start: str) -> dict[str, Any]:
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

    paper_days = 0
    try:
        start = datetime.fromisoformat(paper_phase_start).date()
        paper_days = (datetime.now(timezone.utc).date() - start).days
    except Exception:
        pass

    return {
        "total_trades": len(closed) + len(open_trades),
        "closed_trades": len(closed),
        "open_trades": len(open_trades),
        "wins": len(wins),
        "losses": len(losses),
        "breakeven": len(breakeven),
        "win_rate_pct": round((len(wins) / len(closed)) * 100.0, 2) if closed else None,
        "avg_win": round(total_wins / len(wins), 2) if wins else None,
        "avg_loss": round(total_losses / len(losses), 2) if losses else None,
        "profit_factor": round(total_wins / total_losses, 2) if total_losses > 0 else None,
        "total_pnl": total_pnl,
        "total_realized_pnl": total_pnl,
        "paper_phase_start": paper_phase_start,
        "paper_phase_days": paper_days,
        "last_updated": datetime.now(timezone.utc).isoformat(),
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

    from src.learning.distributed_feedback import LocalBackend, aggregate_feedback

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

    from src.learning.rlhf_storage import store_trade_outcome
    from src.ml.trade_confidence import get_trade_confidence_model

    symbol = str(trade.get("symbol") or "SPY")
    strategy = str(trade.get("strategy") or "iron_condor")
    pnl = _parse_float(trade.get("realized_pnl"), 0.0)
    won = str(trade.get("outcome") or "").strip().lower() == "win"
    expiry = str((trade.get("legs") or {}).get("expiry") or "")

    model = get_trade_confidence_model()
    model.record_trade_outcome(success=won, strategy=strategy, ticker=symbol)

    store_trade_outcome(
        symbol=symbol,
        strategy=strategy,
        reward=pnl,
        won=won,
        exit_reason="SYNC_CLOSED_POSITION",
        expiry=expiry,
        event_key=event_key,
        metadata={
            "source": "sync_closed_positions",
            "trade_id": str(trade.get("id") or ""),
            "distributed_feedback_applied": True,
        },
    )
    result["applied"] = True
    return result


def sync_closed_positions(dry_run: bool = False) -> dict[str, Any]:
    logger.info("=" * 60)
    logger.info("SYNC CLOSED POSITIONS")
    logger.info("=" * 60)

    state = _load_system_state()
    trade_history = state.get("trade_history", []) if isinstance(state, dict) else []
    if not isinstance(trade_history, list) or not trade_history:
        logger.warning("No trade_history available in system_state.json")
        return {"success": False, "error": "no_trade_history"}

    events = _collect_events(trade_history)
    closed_candidates = _pair_closed_trades(events)
    logger.info("Events detected: %s | Closed candidates: %s", len(events), len(closed_candidates))

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
    ledger["stats"] = _compute_stats(ledger["trades"], paper_phase_start)
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

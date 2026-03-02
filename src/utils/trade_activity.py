from __future__ import annotations

import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping

_NON_FILL_STATUSES = {
    "SIMULATED",
    "LIVE_SUBMITTED",
    "SUBMITTED",
    "PENDING",
    "NEW",
    "CANCELED",
    "CANCELLED",
    "REJECTED",
    "FAILED",
    "LIVE_FAILED",
    "LIVE_ERROR",
    "ORDER_SUBMITTED",
}


def parse_trade_timestamp(value: Any) -> datetime | None:
    """Parse known trade timestamp formats into a datetime object."""
    if isinstance(value, datetime):
        return value
    if not value:
        return None

    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(float(value), tz=timezone.utc)
        except (OverflowError, OSError, ValueError):
            return None

    if not isinstance(value, str):
        return None

    text = value.strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00") if text.endswith("Z") else text

    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    formats = (
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%f",
        "%Y-%m-%dT%H:%M:%S",
        "%Y-%m-%d %H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S.%f",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _extract_status(trade: Mapping[str, Any]) -> str:
    status = trade.get("status")
    if not status and isinstance(trade.get("result"), Mapping):
        status = trade["result"].get("status")
    if not status and isinstance(trade.get("order"), Mapping):
        status = trade["order"].get("status")
    return str(status or "").strip().upper()


def _extract_activity_type(trade: Mapping[str, Any]) -> str:
    return str(trade.get("activity_type") or "").strip().upper()


def _extract_timestamp(trade: Mapping[str, Any]) -> datetime | None:
    for key in ("filled_at", "timestamp", "date"):
        parsed = parse_trade_timestamp(trade.get(key))
        if parsed is not None:
            return parsed
    return None


def _is_fill_trade(trade: Mapping[str, Any], *, source: str) -> bool:
    status = _extract_status(trade)
    activity_type = _extract_activity_type(trade)

    if status in _NON_FILL_STATUSES:
        return False
    if status and "FILL" in status:
        return True
    if activity_type == "FILL":
        return True

    # trade_history is intended to be canonical fill history.
    if source == "trade_history":
        return _extract_timestamp(trade) is not None

    # fallback file: only count status-less entries if they include a filled timestamp.
    return parse_trade_timestamp(trade.get("filled_at")) is not None


def _normalize_for_fingerprint(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return f"{value:.8f}".rstrip("0").rstrip(".")
    return str(value).strip().upper()


def _trade_fingerprint(trade: Mapping[str, Any], timestamp: datetime | None) -> str:
    if timestamp is None:
        ts_value = ""
    elif timestamp.tzinfo is None:
        ts_value = timestamp.replace(microsecond=0).isoformat()
    else:
        ts_value = timestamp.astimezone(timezone.utc).replace(microsecond=0).isoformat()

    return "|".join(
        (
            _normalize_for_fingerprint(trade.get("symbol")),
            _normalize_for_fingerprint(trade.get("side") or trade.get("action")),
            _normalize_for_fingerprint(trade.get("qty") or trade.get("quantity")),
            _normalize_for_fingerprint(trade.get("price")),
            ts_value,
        )
    )


def _load_fallback_trade_entries(data_dir: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    for path in sorted(data_dir.glob("trades_*.json")):
        try:
            with open(path, encoding="utf-8") as handle:
                payload = json.load(handle)
            if isinstance(payload, list):
                for item in payload:
                    if isinstance(item, dict):
                        entries.append(item)
        except (OSError, json.JSONDecodeError):
            continue
    return entries


def reconcile_filled_trade_activity(
    system_state: Mapping[str, Any] | None,
    *,
    data_dir: str | Path = "data",
    today: date | datetime | None = None,
) -> dict[str, Any]:
    """
    Build canonical fill activity from system_state trade_history plus fallback trade files.

    Returns a dictionary with:
    - last_trade_date: YYYY-MM-DD or None
    - trades_today: int
    - total_fills: int
    """
    if isinstance(today, datetime):
        today_date = today.date()
    elif isinstance(today, date):
        today_date = today
    else:
        today_date = datetime.now(timezone.utc).date()

    state = system_state if isinstance(system_state, Mapping) else {}
    trade_history = state.get("trade_history")
    state_entries = trade_history if isinstance(trade_history, list) else []
    fallback_entries = _load_fallback_trade_entries(Path(data_dir))

    all_entries = [("trade_history", entry) for entry in state_entries] + [
        ("fallback", entry) for entry in fallback_entries
    ]

    seen_order_ids: set[str] = set()
    seen_fingerprints: set[str] = set()
    fill_dates: list[date] = []

    for source, raw_entry in all_entries:
        if not isinstance(raw_entry, Mapping):
            continue
        if not _is_fill_trade(raw_entry, source=source):
            continue

        timestamp = _extract_timestamp(raw_entry)
        if timestamp is None:
            continue

        order_id = raw_entry.get("order_id") or raw_entry.get("id")
        normalized_order_id = str(order_id).strip() if order_id else ""
        if normalized_order_id:
            if normalized_order_id in seen_order_ids:
                continue
            seen_order_ids.add(normalized_order_id)

        fingerprint = _trade_fingerprint(raw_entry, timestamp)
        if fingerprint in seen_fingerprints:
            continue
        seen_fingerprints.add(fingerprint)

        fill_dates.append(timestamp.date())

    if not fill_dates:
        return {"last_trade_date": None, "trades_today": 0, "total_fills": 0}

    last_trade = max(fill_dates)
    trades_today = sum(1 for d in fill_dates if d == today_date)
    return {
        "last_trade_date": last_trade.isoformat(),
        "trades_today": trades_today,
        "total_fills": len(fill_dates),
    }

"""RLHF trade trajectory storage for learning and audits."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

TRAJECTORY_PATH = Path("data/feedback/trade_trajectories.jsonl")


def _utc_now_iso() -> str:
    """Return UTC timestamp with explicit Z suffix."""
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _append_jsonl(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=True) + "\n")


def _stable_event_key(material: dict[str, Any]) -> str:
    raw = json.dumps(material, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return f"trajectory::{digest}"


def _coerce_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def store_trade_trajectory(
    order: dict[str, Any] | None = None,
    strategy: str | None = None,
    price: float | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Persist trade trajectory entries.

    Supports both call shapes used across the repo:
    1) Legacy:
       store_trade_trajectory(order=<dict>, strategy=<str>, price=<float>)
    2) Structured:
       store_trade_trajectory(
           episode_id=..., entry_state=..., action=..., exit_state=...,
           reward=..., symbol=..., policy_version=..., metadata=...
       )
    """
    timestamp = _utc_now_iso()

    if kwargs:
        entry_state = kwargs.get("entry_state", {}) or {}
        metadata = kwargs.get("metadata", {}) or {}
        symbol = kwargs.get("symbol") or entry_state.get("symbol")
        payload = {
            "timestamp": timestamp,
            "event_type": "entry",
            "episode_id": str(kwargs.get("episode_id") or ""),
            "strategy": str(
                kwargs.get("strategy") or metadata.get("strategy") or strategy or "unknown"
            ),
            "symbol": symbol,
            "action": int(kwargs.get("action", 0)),
            "reward": _coerce_float(kwargs.get("reward"), 0.0),
            "entry_state": entry_state,
            "exit_state": kwargs.get("exit_state", {}) or {},
            "policy_version": kwargs.get("policy_version"),
            "metadata": metadata,
            "source": str(metadata.get("source") or "alpaca_executor"),
        }
        payload["event_key"] = _stable_event_key(
            {
                "event_type": payload["event_type"],
                "episode_id": payload["episode_id"],
                "strategy": payload["strategy"],
                "symbol": payload["symbol"],
                "action": payload["action"],
            }
        )
        _append_jsonl(TRAJECTORY_PATH, payload)
        return payload

    order_payload = order or {}
    payload = {
        "timestamp": timestamp,
        "event_type": "entry",
        "strategy": strategy or "unknown",
        "symbol": order_payload.get("symbol"),
        "side": order_payload.get("side"),
        "qty": order_payload.get("filled_qty", order_payload.get("qty")),
        "price": _coerce_float(price, _coerce_float(order_payload.get("filled_avg_price"))),
        "order_id": order_payload.get("id"),
        "source": "alpaca_executor",
        "metadata": {
            "status": order_payload.get("status"),
            "mode": order_payload.get("mode"),
        },
    }
    payload["event_key"] = _stable_event_key(
        {
            "event_type": payload["event_type"],
            "strategy": payload["strategy"],
            "symbol": payload["symbol"],
            "side": payload["side"],
            "order_id": payload["order_id"],
        }
    )
    _append_jsonl(TRAJECTORY_PATH, payload)
    return payload


def store_trade_outcome(
    *,
    symbol: str,
    strategy: str,
    reward: float,
    won: bool,
    exit_reason: str,
    expiry: str | None = None,
    episode_id: str | None = None,
    event_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Persist close-time outcome event for learning and audit."""
    meta = metadata or {}
    key = event_key or _stable_event_key(
        {
            "event_type": "outcome",
            "symbol": symbol,
            "strategy": strategy,
            "reward": round(float(reward), 2),
            "won": bool(won),
            "exit_reason": exit_reason,
            "expiry": expiry,
            "episode_id": episode_id,
        }
    )
    payload = {
        "timestamp": _utc_now_iso(),
        "event_type": "outcome",
        "event_key": key,
        "episode_id": episode_id,
        "strategy": strategy,
        "symbol": symbol,
        "reward": float(reward),
        "won": bool(won),
        "exit_reason": exit_reason,
        "expiry": expiry,
        "metadata": meta,
        "source": str(meta.get("source") or "position_manager"),
    }
    _append_jsonl(TRAJECTORY_PATH, payload)
    return payload

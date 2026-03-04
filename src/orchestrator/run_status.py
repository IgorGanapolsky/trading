"""Canonical control-plane run status tracking for autonomous execution."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_LATEST_STATUS_PATH = Path("data/runtime/autonomous_run_status_latest.json")
DEFAULT_HISTORY_PATH = Path("data/runtime/autonomous_run_status_history.jsonl")


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _safe_read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    if isinstance(payload, dict):
        return payload
    return {}


def read_latest_run_status(path: Path = DEFAULT_LATEST_STATUS_PATH) -> dict[str, Any]:
    """Read latest run status payload. Returns empty dict on missing/corrupt file."""
    return _safe_read_json(path)


def update_run_status(
    *,
    run_id: str,
    session_id: str | None = None,
    status: str | None = None,
    phase: str | None = None,
    retry_count: int | None = None,
    blocker_reason: str | None = None,
    last_heartbeat_utc: str | None = None,
    metadata: dict[str, Any] | None = None,
    latest_path: Path = DEFAULT_LATEST_STATUS_PATH,
    history_path: Path = DEFAULT_HISTORY_PATH,
) -> dict[str, Any]:
    """Update canonical run status and append a history event."""
    now_iso = _utc_now_iso()

    previous = _safe_read_json(latest_path)
    if previous.get("run_id") != run_id:
        previous = {}

    merged_metadata: dict[str, Any] = {}
    existing_metadata = previous.get("metadata")
    if isinstance(existing_metadata, dict):
        merged_metadata.update(existing_metadata)
    if metadata:
        merged_metadata.update(metadata)

    heartbeat_iso = last_heartbeat_utc or now_iso

    payload = {
        "run_id": run_id,
        "session_id": session_id or previous.get("session_id"),
        "status": status or previous.get("status") or "running",
        "phase": phase or previous.get("phase") or "unknown",
        "last_heartbeat_utc": heartbeat_iso,
        "retry_count": int(
            retry_count if retry_count is not None else previous.get("retry_count", 0)
        ),
        "blocker_reason": blocker_reason,
        "updated_at_utc": now_iso,
        "metadata": merged_metadata,
    }

    latest_path.parent.mkdir(parents=True, exist_ok=True)
    latest_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")

    history_event = dict(payload)
    history_event["event_at_utc"] = now_iso

    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(history_event, sort_keys=True) + "\n")

    return payload

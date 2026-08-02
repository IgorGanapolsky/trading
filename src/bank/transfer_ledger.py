"""Durable transfer ledger: Mercury ↔ brokerage ACH/API plans and outcomes.

Every transfer (planned or executed) is logged with amount, direction, and time.
Secrets never appear in records.
"""

from __future__ import annotations

import json
import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER_PATH = REPO_ROOT / "data" / "audit" / "mercury_broker_transfers.jsonl"


class TransferDirection(StrEnum):
    """Money movement direction relative to the trading brokerage."""

    MERCURY_TO_BROKER = "mercury_to_broker"  # fund trading account
    BROKER_TO_MERCURY = "broker_to_mercury"  # remit proceeds to bank


class TransferStatus(StrEnum):
    PLANNED = "planned"
    DRY_RUN = "dry_run"
    BLOCKED = "blocked"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    FAILED = "failed"


@dataclass(frozen=True)
class TransferRecord:
    """One transfer plan or execution row (no secrets)."""

    transfer_id: str
    direction: str
    amount_usd: float
    timestamp: str
    status: str
    dry_run: bool
    source: str
    destination: str
    reason: str = ""
    block_reason: str = ""
    external_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        # Never allow secret-like keys into durable log
        meta = dict(payload.get("metadata") or {})
        for banned in list(meta.keys()):
            low = str(banned).lower()
            if any(tok in low for tok in ("secret", "password", "token", "api_key", "apikey")):
                meta.pop(banned, None)
        payload["metadata"] = meta
        return payload


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def new_transfer_id() -> str:
    return f"xfer_{uuid.uuid4().hex[:16]}"


def build_transfer_record(
    *,
    direction: TransferDirection | str,
    amount_usd: float,
    status: TransferStatus | str,
    dry_run: bool,
    reason: str = "",
    block_reason: str = "",
    external_ref: str = "",
    metadata: dict[str, Any] | None = None,
    transfer_id: str | None = None,
    timestamp: str | None = None,
) -> TransferRecord:
    """Construct a validated transfer record (pure)."""
    amt = float(amount_usd)
    if amt < 0:
        raise ValueError("amount_usd must be non-negative")
    direction_s = direction.value if isinstance(direction, TransferDirection) else str(direction)
    if direction_s not in {d.value for d in TransferDirection}:
        raise ValueError(f"invalid direction: {direction_s}")
    status_s = status.value if isinstance(status, TransferStatus) else str(status)

    if direction_s == TransferDirection.MERCURY_TO_BROKER.value:
        source, destination = "mercury_ai_bank", "brokerage_live"
    else:
        source, destination = "brokerage_live", "mercury_ai_bank"

    return TransferRecord(
        transfer_id=transfer_id or new_transfer_id(),
        direction=direction_s,
        amount_usd=round(amt, 2),
        timestamp=timestamp or _now_iso(),
        status=status_s,
        dry_run=bool(dry_run),
        source=source,
        destination=destination,
        reason=str(reason or ""),
        block_reason=str(block_reason or ""),
        external_ref=str(external_ref or ""),
        metadata=dict(metadata or {}),
    )


def append_transfer_record(
    record: TransferRecord,
    *,
    ledger_path: Path | None = None,
) -> Path:
    """Append one JSONL row. Creates parent dirs. Returns path written."""
    path = ledger_path or Path(os.environ.get("MERCURY_TRANSFER_LEDGER", str(DEFAULT_LEDGER_PATH)))
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record.as_dict(), sort_keys=True) + "\n"
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line)
    return path


def load_transfer_ledger(*, ledger_path: Path | None = None) -> list[TransferRecord]:
    """Load all transfer records from JSONL (skips bad lines)."""
    path = ledger_path or Path(os.environ.get("MERCURY_TRANSFER_LEDGER", str(DEFAULT_LEDGER_PATH)))
    if not path.is_file():
        return []
    out: list[TransferRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(raw, dict):
            continue
        try:
            out.append(
                TransferRecord(
                    transfer_id=str(raw.get("transfer_id") or ""),
                    direction=str(raw.get("direction") or ""),
                    amount_usd=float(raw.get("amount_usd") or 0),
                    timestamp=str(raw.get("timestamp") or ""),
                    status=str(raw.get("status") or ""),
                    dry_run=bool(raw.get("dry_run", True)),
                    source=str(raw.get("source") or ""),
                    destination=str(raw.get("destination") or ""),
                    reason=str(raw.get("reason") or ""),
                    block_reason=str(raw.get("block_reason") or ""),
                    external_ref=str(raw.get("external_ref") or ""),
                    metadata=dict(raw.get("metadata") or {})
                    if isinstance(raw.get("metadata"), dict)
                    else {},
                )
            )
        except (TypeError, ValueError):
            continue
    return out

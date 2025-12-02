"""Telemetry helpers for the hybrid funnel orchestrator."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OrchestratorTelemetry:
    """Append structured events to a JSONL audit trail."""

    def __init__(self, log_path: str | Path | None = None) -> None:
        default_path = Path("data/audit_trail/hybrid_funnel_runs.jsonl")
        self.log_path = Path(log_path) if log_path else default_path
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_id = datetime.utcnow().strftime("%Y%m%dT%H%M%S")
        self.run_id = os.getenv("GITHUB_RUN_ID") or os.getenv("RUN_ID")

    def record(self, event_type: str, ticker: str, status: str, payload: dict[str, Any]) -> None:
        entry = {
            "ts": datetime.utcnow().isoformat(),
            "session": self.session_id,
            "run_id": self.run_id,
            "event": event_type,
            "ticker": ticker,
            "status": status,
            "payload": payload,
        }
        try:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(entry, default=str) + "\n")
        except Exception as exc:  # pragma: no cover - best effort logging
            logger.warning("Telemetry write failed: %s", exc)

    def gate_pass(self, gate: str, ticker: str, payload: dict[str, Any]) -> None:
        self.record(event_type=f"gate.{gate}", ticker=ticker, status="pass", payload=payload)

    def gate_reject(self, gate: str, ticker: str, payload: dict[str, Any]) -> None:
        self.record(event_type=f"gate.{gate}", ticker=ticker, status="reject", payload=payload)

    def order_event(self, ticker: str, payload: dict[str, Any]) -> None:
        self.record(
            event_type="execution.order",
            ticker=ticker,
            status="submitted",
            payload=payload,
        )

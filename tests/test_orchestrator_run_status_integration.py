"""Integration tests for telemetry -> run status control-plane updates."""

from __future__ import annotations

import json
from pathlib import Path

from src.orchestrator.telemetry import OrchestratorTelemetry


def test_telemetry_error_event_updates_retry_and_blocker(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    telemetry = OrchestratorTelemetry(log_path=Path("data/audit_trail/test.jsonl"))
    telemetry.record(
        event_type="gate.risk",
        ticker="SPY",
        status="error",
        payload={"attempts": [{"error": "first"}, {"error": "second"}]},
    )

    status_file = Path("data/runtime/autonomous_run_status_latest.json")
    assert status_file.exists()
    payload = json.loads(status_file.read_text(encoding="utf-8"))

    assert payload["status"] == "retrying"
    assert payload["phase"] == "gate.risk"
    assert payload["retry_count"] == 1
    assert "second" in str(payload["blocker_reason"])


def test_telemetry_blocked_event_sets_blocked_status(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    telemetry = OrchestratorTelemetry(log_path=Path("data/audit_trail/test.jsonl"))
    telemetry.record(
        event_type="context_freshness.blocked",
        ticker="SYSTEM",
        status="blocked",
        payload={"reason": "Stale context indexes detected"},
    )

    status_file = Path("data/runtime/autonomous_run_status_latest.json")
    payload = json.loads(status_file.read_text(encoding="utf-8"))

    assert payload["status"] == "blocked"
    assert payload["phase"] == "context_freshness.blocked"
    assert "Stale context" in str(payload["blocker_reason"])

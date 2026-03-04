"""Tests for canonical autonomous run status control-plane state."""

from __future__ import annotations

import json
from pathlib import Path

from src.orchestrator.run_status import read_latest_run_status, update_run_status


def test_update_run_status_writes_latest_and_history(tmp_path: Path) -> None:
    latest = tmp_path / "latest.json"
    history = tmp_path / "history.jsonl"

    payload = update_run_status(
        run_id="run-1",
        session_id="session-1",
        status="running",
        phase="bootstrap",
        retry_count=0,
        latest_path=latest,
        history_path=history,
    )

    assert payload["run_id"] == "run-1"
    assert payload["phase"] == "bootstrap"
    assert latest.exists()
    assert history.exists()

    latest_payload = read_latest_run_status(latest)
    assert latest_payload["run_id"] == "run-1"
    assert latest_payload["status"] == "running"

    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 1
    assert rows[0]["phase"] == "bootstrap"


def test_update_run_status_merges_metadata_and_retry_count(tmp_path: Path) -> None:
    latest = tmp_path / "latest.json"
    history = tmp_path / "history.jsonl"

    update_run_status(
        run_id="run-2",
        session_id="session-2",
        status="running",
        phase="attempt.start",
        retry_count=0,
        metadata={"source_control_plane": "scripts.autonomous_trader"},
        latest_path=latest,
        history_path=history,
    )

    payload = update_run_status(
        run_id="run-2",
        status="retrying",
        phase="attempt.failed",
        retry_count=1,
        blocker_reason="Timeout",
        metadata={"last_telemetry_ticker": "SPY"},
        latest_path=latest,
        history_path=history,
    )

    assert payload["retry_count"] == 1
    assert payload["blocker_reason"] == "Timeout"
    assert payload["metadata"]["source_control_plane"] == "scripts.autonomous_trader"
    assert payload["metadata"]["last_telemetry_ticker"] == "SPY"

    rows = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines() if line]
    assert len(rows) == 2
    assert rows[-1]["status"] == "retrying"


def test_new_run_id_resets_previous_status(tmp_path: Path) -> None:
    latest = tmp_path / "latest.json"
    history = tmp_path / "history.jsonl"

    update_run_status(
        run_id="run-old",
        session_id="session-old",
        status="failed",
        phase="attempt.failed",
        retry_count=3,
        blocker_reason="old failure",
        latest_path=latest,
        history_path=history,
    )

    payload = update_run_status(
        run_id="run-new",
        session_id="session-new",
        status="running",
        phase="bootstrap",
        latest_path=latest,
        history_path=history,
    )

    assert payload["run_id"] == "run-new"
    assert payload["session_id"] == "session-new"
    assert payload["retry_count"] == 0

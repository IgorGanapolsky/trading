"""Tests for Decisions UO FORMAT steal on spy_put_credit (AGENT-606)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import put_credit_govern as govern


def test_process_record_has_where_stuck_next(monkeypatch, tmp_path: Path):
    entries = {
        "pcs_a": {
            "status": "open",
            "entry_time": "2026-09-11T12:00:00+00:00",
            "signature": "SPY_2026-09-18_580_575",
        }
    }
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "put_credit_entries.json").write_text(
        json.dumps(entries), encoding="utf-8"
    )

    monkeypatch.setattr(govern, "_regime_snapshot", lambda: {"allowed": True, "blockers": [], "soft_flags": []})
    monkeypatch.setattr(govern, "_kill_switch", lambda: {"live_blocked": True, "entry_allowed": True})
    monkeypatch.setattr(govern, "_mandatory_gate_present", lambda: True)

    # Force occupancy helpers via real evaluate_entry_limits on provided entries
    monkeypatch.setattr(
        govern,
        "_occupancy_from_entries",
        lambda _e: {
            "allowed": True,
            "blockers": [],
            "active_count": 1,
            "today_count": 1,
            "max_concurrent": 2,
            "max_daily": 4,
        },
    )

    record = govern.build_process_record(root=tmp_path, entries=entries)
    assert record["schemaVersion"] == 1
    assert record["instructionsAreNotControl"] is True
    assert record["rulesBeforeAction"] is True
    assert record["liveExecuteAllowed"] is False
    assert "where" in record and "stuck" in record and "next" in record
    assert record["where"]["occupancy"] == 1
    assert record["where"]["max_concurrent"] == 2
    assert any("execute-paper" in step or "check-ready" in step for step in record["next"])
    assert "Decisions universal orchestrator product" in record["weAreNot"]


def test_paper_factory_when_occupancy_below_max(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(govern, "_regime_snapshot", lambda: {"allowed": True, "blockers": [], "soft_flags": []})
    monkeypatch.setattr(govern, "_kill_switch", lambda: {"live_blocked": True})
    monkeypatch.setattr(govern, "_mandatory_gate_present", lambda: True)
    monkeypatch.setattr(
        govern,
        "_occupancy_from_entries",
        lambda _e: {
            "allowed": True,
            "blockers": [],
            "active_count": 0,
            "today_count": 0,
            "max_concurrent": 2,
            "max_daily": 4,
        },
    )
    (tmp_path / "data").mkdir()
    record = govern.build_process_record(root=tmp_path, entries={})
    assert record["paperFactoryEligible"] is True
    assert any("--execute-paper" in step for step in record["next"])
    assert record["stuck"] == []


def test_stuck_when_book_full(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(govern, "_regime_snapshot", lambda: {"allowed": True, "blockers": [], "soft_flags": []})
    monkeypatch.setattr(govern, "_kill_switch", lambda: {"live_blocked": True})
    monkeypatch.setattr(govern, "_mandatory_gate_present", lambda: True)
    monkeypatch.setattr(
        govern,
        "_occupancy_from_entries",
        lambda _e: {
            "allowed": False,
            "blockers": ["Concurrent put credits 2/2."],
            "active_count": 2,
            "today_count": 2,
            "max_concurrent": 2,
            "max_daily": 4,
        },
    )
    (tmp_path / "data").mkdir()
    record = govern.build_process_record(root=tmp_path, entries={})
    assert record["paperFactoryEligible"] is False
    assert any("2/2" in s for s in record["stuck"])
    assert any("manage-exits" in step for step in record["next"])


def test_live_execute_refused():
    code = govern.main(["--execute"])
    assert code == 2
    code2 = govern.main(["--execute-live"])
    assert code2 == 2


def test_check_ready_ok(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(govern, "_regime_snapshot", lambda: {"allowed": True, "blockers": [], "soft_flags": []})
    monkeypatch.setattr(govern, "_kill_switch", lambda: {"live_blocked": True})
    monkeypatch.setattr(govern, "_mandatory_gate_present", lambda: True)
    monkeypatch.setattr(
        govern,
        "_occupancy_from_entries",
        lambda _e: {
            "allowed": True,
            "blockers": [],
            "active_count": 0,
            "today_count": 0,
            "max_concurrent": 2,
            "max_daily": 4,
        },
    )
    monkeypatch.setattr(govern, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    code = govern.main(["--check-ready"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["checkReady"]["ok"] is True


def test_check_ready_fails_without_gate(monkeypatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    monkeypatch.setattr(govern, "_regime_snapshot", lambda: {"allowed": True, "blockers": [], "soft_flags": []})
    monkeypatch.setattr(govern, "_kill_switch", lambda: {"live_blocked": True})
    monkeypatch.setattr(govern, "_mandatory_gate_present", lambda: False)
    monkeypatch.setattr(
        govern,
        "_occupancy_from_entries",
        lambda _e: {
            "allowed": True,
            "blockers": [],
            "active_count": 0,
            "today_count": 0,
            "max_concurrent": 2,
            "max_daily": 4,
        },
    )
    monkeypatch.setattr(govern, "ROOT", tmp_path)
    (tmp_path / "data").mkdir()
    code = govern.main(["--check-ready"])
    assert code == 2
    payload = json.loads(capsys.readouterr().out)
    assert payload["checkReady"]["ok"] is False
    assert "mandatory_trade_gate_missing" in payload["checkReady"]["issues"]

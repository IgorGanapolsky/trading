"""Tests for the exit-reason coverage guard (LL-361).

The guard's whole value is that it FAILS when a close is unattributable. These tests
assert the failure path first -- a gate that only ever passes is decoration.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PROJECT_ROOT / "scripts" / "check_exit_reason_coverage.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("check_exit_reason_coverage", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def guard(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    module = _load_module()

    def write(trades: list[dict[str, Any]], journal: dict[str, Any] | None = None) -> None:
        trades_file = tmp_path / "trades.json"
        trades_file.write_text(json.dumps({"trades": trades}))
        journal_file = tmp_path / "journal.json"
        journal_file.write_text(json.dumps(journal or {}))
        monkeypatch.setattr(module, "TRADES_PATH", trades_file)
        monkeypatch.setattr(module, "JOURNAL_PATH", journal_file)

    module.write_fixtures = write
    return module


def test_active_family_close_without_exit_reason_fails(guard) -> None:
    guard.write_fixtures(
        [{"id": "PCS_1", "strategy": "spy_put_credit", "status": "closed", "realized_pnl": -50.0}]
    )
    report = guard.collect()

    assert report["passed"] is False
    assert len(report["violations"]) == 1
    assert report["violations"][0]["id"] == "PCS_1"
    assert guard.main.__call__ is not None  # sanity: CLI entrypoint exists


def test_legacy_iron_condor_row_is_excluded_from_the_gate(guard) -> None:
    """Historical rows cannot be repaired; they are reported, never a failure."""
    guard.write_fixtures(
        [{"id": "IC_1", "strategy": "iron_condor", "status": "closed", "realized_pnl": -300.0}]
    )
    report = guard.collect()

    assert report["passed"] is True
    assert report["legacy_missing"] == 1
    assert report["violations"] == []


def test_recorded_exit_reason_passes(guard) -> None:
    guard.write_fixtures(
        [
            {
                "id": "PCS_2",
                "strategy": "spy_put_credit",
                "status": "closed",
                "exit_reason": "profit_target",
            }
        ]
    )
    report = guard.collect()

    assert report["passed"] is True
    assert report["exit_reason_recorded"] == 1
    assert report["coverage"] == 1.0


def test_open_journal_row_is_not_graded(guard) -> None:
    """A structure still open has no exit path yet -- grading it would be a false alarm."""
    guard.write_fixtures(
        [],
        {"PCS_OPEN": {"strategy_family": "spy_put_credit", "status": "open"}},
    )
    report = guard.collect()

    assert report["total_closed"] == 0
    assert report["passed"] is True


def test_closed_journal_row_without_exit_reason_fails(guard) -> None:
    guard.write_fixtures(
        [],
        {"PCS_CLOSED": {"strategy_family": "spy_put_credit", "status": "closed"}},
    )
    report = guard.collect()

    assert report["passed"] is False
    assert report["violations"][0]["source"] == "journal"


def test_cli_exit_code_is_nonzero_on_violation(guard, monkeypatch, capsys) -> None:
    guard.write_fixtures([{"id": "PCS_3", "strategy": "spy_put_credit", "status": "closed"}])
    monkeypatch.setattr("sys.argv", ["check_exit_reason_coverage.py"])

    assert guard.main() == 1
    assert "FAIL" in capsys.readouterr().out


def test_real_repo_state_passes_the_gate() -> None:
    """The committed ledger must satisfy the gate, or CI is red for a real reason."""
    module = _load_module()
    report = module.collect()
    assert report["passed"] is True, f"unattributable closes: {report['violations']}"

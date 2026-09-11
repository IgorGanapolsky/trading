"""Tests for Parallel Basis FORMAT steal (local ledgers only)."""

from __future__ import annotations

import json
from pathlib import Path

from src.ops.put_credit_basis import build_basis, readiness_ok


def _write(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_ledgers_are_low_confidence_not_crash(tmp_path: Path) -> None:
    receipt = build_basis(tmp_path)
    assert receipt["ticker"] == "SPY"
    assert receipt["trade"]["submitted"] == 0
    assert receipt["trade"]["parallel_api_called"] is False
    assert receipt["trade"]["findall_other_tickers"] is False
    assert all(c["confidence"] in {"high", "medium", "low"} for c in receipt["basis"])
    assert readiness_ok(receipt) is False


def test_kill_switch_and_paired_stats_are_cited(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {
            "active_family": "spy_put_credit",
            "paper_only": True,
            "live_blocked": True,
        },
    )
    _write(
        tmp_path,
        "data/put_credit_entries.json",
        {"a": {"status": "open"}, "b": {"status": "closed"}},
    )
    _write(
        tmp_path,
        "data/trades.json",
        {"stats": {"by_strategy": {"spy_put_credit": {"closed": 3}}}},
    )
    _write(
        tmp_path,
        "data/system_state.json",
        {"paper_account": {"equity": 94136.95}},
    )
    receipt = build_basis(tmp_path)
    assert receipt["search"]["active_family"] == "spy_put_credit"
    assert receipt["evaluate"]["open_journal"] == 1
    assert receipt["evaluate"]["paired_closed"] == 3
    assert receipt["evaluate"]["n30_remaining"] == 27
    assert receipt["trade"]["submitted"] == 0
    by_claim = {c["claim"]: c for c in receipt["basis"]}
    assert by_claim["live_blocked"]["confidence"] == "high"
    assert by_claim["paired_put_credit_closed"]["source"].startswith("data/trades.json")
    assert readiness_ok(receipt) is True
    assert "FindAll" in " ".join(receipt["forbid"])


def test_cli_check_ready_via_module(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    import runpy
    import sys

    argv = sys.argv
    sys.argv = [
        "put_credit_basis.py",
        "--check-ready",
        "--project-root",
        str(tmp_path),
    ]
    try:
        ns = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts" / "put_credit_basis.py"),
            run_name="not_main",
        )
        assert ns["main"](["--check-ready", "--project-root", str(tmp_path)]) == 0
    finally:
        sys.argv = argv

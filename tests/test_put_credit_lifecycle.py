"""Tests for Senpi 5-phase FORMAT steal (local ledgers, no Hyperliquid)."""

from __future__ import annotations

import json
from pathlib import Path

from src.ops.put_credit_lifecycle import PHASES, build_lifecycle, readiness_ok


def _write(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_ledgers_do_not_submit(tmp_path: Path) -> None:
    receipt = build_lifecycle(tmp_path)
    assert receipt["ticker"] == "SPY"
    assert receipt["phases"] == list(PHASES)
    assert receipt["hyperliquid"] is False
    assert receipt["wallet_funded"] is False
    assert receipt["execute"]["submitted"] == 0
    assert receipt["execute"]["live_execute"] is False
    assert readiness_ok(receipt) is False


def test_five_phases_cite_kill_switch_and_journal(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    _write(
        tmp_path,
        "data/put_credit_entries.json",
        {
            "a": {"status": "open"},
            "b": {"status": "exit_pending"},
            "c": {"status": "closed"},
        },
    )
    _write(
        tmp_path,
        "data/trades.json",
        {"stats": {"by_strategy": {"spy_put_credit": {"closed_trades": 3}}}},
    )
    _write(
        tmp_path,
        "data/system_state.json",
        {"live_account": {"equity": 0.0}},
    )
    receipt = build_lifecycle(tmp_path)
    assert receipt["decide"]["confluence_cleared"] is True
    assert receipt["manage"]["open"] == 1
    assert receipt["manage"]["exit_pending"] == 1
    assert receipt["exit"]["paired_closed"] == 3
    assert receipt["exit"]["n30_remaining"] == 27
    assert receipt["exit"]["edge_claim_allowed"] is False
    assert receipt["execute"]["live_equity"] == 0.0
    assert readiness_ok(receipt) is True
    assert "Hyperliquid" in " ".join(receipt["forbid"])


def test_cli_check_ready(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    import runpy
    import sys

    argv = sys.argv
    sys.argv = [
        "put_credit_lifecycle.py",
        "--check-ready",
        "--project-root",
        str(tmp_path),
    ]
    try:
        runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts" / "put_credit_lifecycle.py"),
            run_name="__main__",
        )
    except SystemExit as exc:
        assert exc.code == 0
    finally:
        sys.argv = argv

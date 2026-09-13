"""Tests for Decisions UO process-record FORMAT steal."""

from __future__ import annotations

import json
from pathlib import Path

from src.ops.put_credit_govern import build_process_record, readiness_ok


def _write(root: Path, rel: str, payload: dict) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_missing_ledgers_do_not_submit(tmp_path: Path) -> None:
    rec = build_process_record(tmp_path)
    assert rec["trade"]["submitted"] == 0
    assert rec["control"]["instructions_are_not_control"] is True
    assert rec["ticker"] == "SPY"
    assert rec["observability"]["stuck"] in {"wrong_family", "paired_stats_missing"}
    assert readiness_ok(rec) is False


def test_occupancy_full_waits(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    _write(
        tmp_path,
        "data/put_credit_entries.json",
        {"a": {"status": "open"}, "b": {"status": "open"}},
    )
    _write(
        tmp_path,
        "data/trades.json",
        {"stats": {"by_strategy": {"spy_put_credit": {"closed_trades": 3}}}},
    )
    rec = build_process_record(tmp_path)
    assert rec["state"]["open_journal"] == 2
    assert rec["observability"]["stuck"] == "occupancy_full"
    assert rec["observability"]["next"] == "wait_exit_then_factory_paper"
    assert rec["control"]["factory_may_submit_paper"] is False
    assert readiness_ok(rec) is True
    assert rec["trade"]["submitted"] == 0


def test_insufficient_sample_points_at_factory(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    _write(tmp_path, "data/put_credit_entries.json", {"a": {"status": "open"}})
    _write(
        tmp_path,
        "data/trades.json",
        {"stats": {"by_strategy": {"spy_put_credit": {"closed_trades": 3}}}},
    )
    rec = build_process_record(tmp_path)
    assert rec["state"]["n30_remaining"] == 27
    assert rec["observability"]["stuck"] == "insufficient_sample"
    assert rec["observability"]["next"] == "factory_paper_if_gates_pass"
    assert rec["control"]["factory_may_submit_paper"] is True
    assert readiness_ok(rec) is True


def test_paired_stats_missing_is_not_ready(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "data/runtime/strategy_kill_switch.json",
        {"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True},
    )
    rec = build_process_record(tmp_path)
    assert rec["observability"]["stuck"] == "paired_stats_missing"
    assert rec["control"]["factory_may_submit_paper"] is False
    assert readiness_ok(rec) is False

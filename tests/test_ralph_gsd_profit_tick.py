"""Unit tests for Ralph+GSD profit tick reporting."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import ralph_gsd_profit_tick as tick


def test_tick_includes_regime_and_gsd_fields(tmp_path, monkeypatch):
    """Tick v2 must record regime + GSD metadata and never claim profitable."""

    root = tmp_path
    (root / "scripts").mkdir()
    (root / "data" / "audit" / "ralph_ticks").mkdir(parents=True)
    (root / ".claude" / "ralph").mkdir(parents=True)
    (root / ".venv" / "bin").mkdir(parents=True)

    # Point module ROOT at temp
    monkeypatch.setattr(tick, "ROOT", root)

    cohort = {
        "closed": {
            "closed_n": 0,
            "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"},
            "rolling_20": {"window": 20, "sample_sufficient": False},
        },
        "open": {"open_n": 2},
        "progress": {"pct_to_gate": 0.0},
        "honesty": {"claim_profitable": False, "live_deposit_ready": False},
    }
    regime = {
        "allowed": True,
        "blockers": [],
        "soft_flags": ["SPY 200-DMA unavailable"],
        "snapshot": {"vix": 18.0, "iv_rank_proxy": 55.0},
    }

    def fake_run(args: list[str]) -> dict:
        cmd = " ".join(args)
        if "audit_open_inventory" in cmd:
            return {"cmd": args, "rc": 0, "stdout_tail": "clean=True", "stderr_tail": ""}
        if "--regime-status" in cmd:
            return {
                "cmd": args,
                "rc": 0,
                "stdout_tail": json.dumps(regime),
                "stderr_tail": "",
            }
        if "manage-exits" in cmd:
            return {"cmd": args, "rc": 0, "stdout_tail": "{}", "stderr_tail": ""}
        if "residual_ic" in cmd:
            return {"cmd": args, "rc": 0, "stdout_tail": "{}", "stderr_tail": ""}
        if "put_credit_cohort" in cmd:
            return {
                "cmd": args,
                "rc": 0,
                "stdout_tail": json.dumps(cohort),
                "stderr_tail": "",
            }
        return {"cmd": args, "rc": 1, "stdout_tail": "", "stderr_tail": "unknown"}

    monkeypatch.setattr(tick, "_run", fake_run)
    # Avoid needing real python binary path existence for py check
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    rc = tick.main()
    assert rc == 0

    reports = list((root / "data" / "audit" / "ralph_ticks").glob("tick_*.json"))
    assert reports, "expected tick report"
    # exclude detail dumps
    main_reports = [p for p in reports if "_cohort" not in p.name and "_regime" not in p.name and "_inventory" not in p.name]
    report = json.loads(main_reports[0].read_text())
    assert report["schema_version"] == "ralph-gsd-profit-tick/2"
    assert report["framework"] == "ralph+gsd"
    assert report["inventory_clean"] is True
    assert report["regime"]["allowed"] is True
    assert report["regime"]["vix"] == 18.0
    assert report["cohort"]["closed_n"] == 0
    assert report["cohort"]["claim_profitable"] is False
    assert report["cohort"]["live_deposit_ready"] is False
    assert report["gsd"]["milestone"] == "v2.0-put-credit-edge"
    assert report["gsd"]["phase"] == 2
    assert "profitability claim" in report["honesty"]

    ralph = json.loads((root / ".claude" / "ralph" / "state.json").read_text())
    assert ralph["active"] is True
    assert ralph["claim_profitable"] is False
    assert ralph["completion_promise"] == "EDGE_GATE_READY_OR_KILLED"
    assert ralph["framework"] == "ralph+gsd"

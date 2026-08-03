"""Unit tests for Ralph+GSD profit tick reporting."""

from __future__ import annotations

import json
from pathlib import Path

from scripts import ralph_gsd_profit_tick as tick


def test_tick_includes_regime_gsd_and_production_fields(tmp_path, monkeypatch):
    """Tick v3 must record regime + GSD + production plane; never claim profitable."""

    root = tmp_path
    (root / "scripts").mkdir()
    (root / "data" / "audit" / "ralph_ticks").mkdir(parents=True)
    (root / ".claude" / "ralph").mkdir(parents=True)
    (root / ".venv" / "bin").mkdir(parents=True)

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
    world_class = {
        "schema_version": "world-class-production-scorecard/1",
        "truth": {
            "put_credit_closed_n": 0,
            "kill_verdict": "INSUFFICIENT_SAMPLE",
            "claim_profitable": False,
        },
        "overall": {
            "score_0_10": 4.2,
            "grade": "C-",
            "label": "NOT production cash engine",
            "process_ops_score_0_10": 9.5,
            "process_ops_grade": "A+",
        },
        "production_gate": {
            "grade": "A+",
            "score_0_10": 10.0,
            "allow_new_risk": True,
            "allow_live_capital": False,
            "ok": True,
            "blockers": [],
        },
    }

    def fake_run(args: list[str], **_kwargs) -> dict:
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
        if "world_class_production_scorecard" in cmd:
            # Also materialize audit file path used by loader
            audit = root / "data" / "audit" / "world_class_production_latest.json"
            audit.parent.mkdir(parents=True, exist_ok=True)
            audit.write_text(json.dumps(world_class) + "\n", encoding="utf-8")
            return {
                "cmd": args,
                "rc": 0,
                "stdout_tail": json.dumps(world_class),
                "stderr_tail": "",
            }
        return {"cmd": args, "rc": 1, "stdout_tail": "", "stderr_tail": "unknown"}

    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "_evaluate_production_gate_safe",
        lambda: {
            "ok": True,
            "score_0_10": 10.0,
            "grade": "A+",
            "allow_new_risk": True,
            "allow_live_capital": False,
            "blockers": [],
            "source": "evaluate_production_gate",
        },
    )
    # Keep Path.is_file real for audit JSON; only pretend venv python missing
    real_is_file = Path.is_file

    def _is_file(self: Path) -> bool:
        if str(self).endswith(".venv/bin/python") or self.name == "python":
            return False
        return real_is_file(self)

    monkeypatch.setattr(Path, "is_file", _is_file)

    rc = tick.main()
    assert rc == 0

    reports = list((root / "data" / "audit" / "ralph_ticks").glob("tick_*.json"))
    assert reports, "expected tick report"
    main_reports = [
        p
        for p in reports
        if "_cohort" not in p.name
        and "_regime" not in p.name
        and "_inventory" not in p.name
        and "_world_class" not in p.name
        and "_production_gate" not in p.name
    ]
    report = json.loads(main_reports[0].read_text())
    assert report["schema_version"] == "ralph-gsd-profit-tick/3"
    assert report["framework"] == "ralph+gsd"
    assert report["inventory_clean"] is True
    assert report["regime"]["allowed"] is True
    assert report["regime"]["vix"] == 18.0
    assert report["cohort"]["closed_n"] == 0
    assert report["cohort"]["claim_profitable"] is False
    assert report["cohort"]["live_deposit_ready"] is False
    assert report["production_gate"]["grade"] == "A+"
    assert report["production_gate"]["score_0_10"] == 10.0
    assert report["production_gate"]["allow_new_risk"] is True
    assert report["world_class"]["overall_grade"] == "C-"
    assert report["world_class"]["process_ops_grade"] == "A+"
    assert report["gsd"]["milestone"] == "v2.0-put-credit-edge"
    assert report["gsd"]["phase"] == 2
    assert report["gsd"]["production_control_plane"] is True
    assert "production control plane" in report["gsd"]["phase_note"]
    assert "profitability claim" in report["honesty"] or "no profitability claim" in report["honesty"]
    assert "paper" in report["honesty"]

    ralph = json.loads((root / ".claude" / "ralph" / "state.json").read_text())
    assert ralph["active"] is True
    assert ralph["claim_profitable"] is False
    assert ralph["completion_promise"] == "EDGE_GATE_READY_OR_KILLED"
    assert ralph["framework"] == "ralph+gsd"
    assert ralph["production_gate_grade"] == "A+"


def test_tick_degrades_when_production_gate_import_fails(tmp_path, monkeypatch):
    """Missing production_gate module must not crash the tick."""

    root = tmp_path
    (root / "scripts").mkdir()
    (root / "data" / "audit" / "ralph_ticks").mkdir(parents=True)
    (root / ".claude" / "ralph").mkdir(parents=True)

    monkeypatch.setattr(tick, "ROOT", root)

    def fake_run(args: list[str], **_kwargs) -> dict:
        cmd = " ".join(args)
        if "world_class" in cmd:
            return {
                "cmd": args,
                "rc": 1,
                "stdout_tail": "module missing",
                "stderr_tail": "ImportError",
            }
        if "put_credit_cohort" in cmd:
            return {
                "cmd": args,
                "rc": 0,
                "stdout_tail": json.dumps(
                    {
                        "closed": {"closed_n": 0, "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"}},
                        "open": {"open_n": 0},
                        "progress": {"pct_to_gate": 0.0},
                        "honesty": {"claim_profitable": False, "live_deposit_ready": False},
                    }
                ),
                "stderr_tail": "",
            }
        if "--regime-status" in cmd:
            return {
                "cmd": args,
                "rc": 0,
                "stdout_tail": json.dumps({"allowed": False, "blockers": ["test"], "snapshot": {}}),
                "stderr_tail": "",
            }
        return {"cmd": args, "rc": 0, "stdout_tail": "{}", "stderr_tail": ""}

    monkeypatch.setattr(tick, "_run", fake_run)
    monkeypatch.setattr(
        tick,
        "_evaluate_production_gate_safe",
        lambda: {
            "error": "No module named 'src.risk.production_gate'",
            "ok": False,
            "score_0_10": None,
            "grade": None,
            "allow_new_risk": False,
            "allow_live_capital": False,
            "blockers": ["import_or_eval_failed:No module named 'src.risk.production_gate'"],
            "source": "degraded",
        },
    )
    monkeypatch.setattr(
        tick,
        "_load_world_class_card",
        lambda _step: {"parse_error": True, "error": "scorecard unavailable"},
    )
    monkeypatch.setattr(Path, "is_file", lambda self: False)

    rc = tick.main()
    assert rc == 0
    reports = [
        p
        for p in (root / "data" / "audit" / "ralph_ticks").glob("tick_*.json")
        if "_cohort" not in p.name
        and "_regime" not in p.name
        and "_inventory" not in p.name
        and "_world_class" not in p.name
        and "_production_gate" not in p.name
    ]
    report = json.loads(reports[0].read_text())
    assert report["production_gate"]["allow_new_risk"] is False
    assert report["production_gate"]["grade"] is None
    assert report["gsd"]["production_control_plane"] is False
    assert report["cohort"]["claim_profitable"] is False
    assert "paper" in report["honesty"]


def test_evaluate_production_gate_safe_uses_to_dict(monkeypatch):
    class FakeGate:
        def to_dict(self):
            return {
                "ok": True,
                "score_0_10": 9.0,
                "grade": "A",
                "allow_new_risk": True,
                "allow_live_capital": False,
                "blockers": [],
            }

    import sys
    import types

    mod = types.ModuleType("src.risk.production_gate")
    mod.evaluate_production_gate = lambda for_live=False: FakeGate()
    risk_pkg = types.ModuleType("src.risk")
    src_pkg = types.ModuleType("src")
    monkeypatch.setitem(sys.modules, "src", src_pkg)
    monkeypatch.setitem(sys.modules, "src.risk", risk_pkg)
    monkeypatch.setitem(sys.modules, "src.risk.production_gate", mod)

    out = tick._evaluate_production_gate_safe()
    assert out["grade"] == "A"
    assert out["score_0_10"] == 9.0
    assert out["allow_new_risk"] is True


def test_evaluate_production_gate_safe_on_import_error(monkeypatch):
    import sys

    # Force import path to fail
    monkeypatch.setitem(sys.modules, "src.risk.production_gate", None)

    def boom(*_a, **_k):
        raise ImportError("missing")

    # Patch the import by making evaluate unavailable via a broken module
    import types

    broken = types.ModuleType("src.risk.production_gate")

    def _raise(*_a, **_k):
        raise RuntimeError("gate down")

    broken.evaluate_production_gate = _raise
    monkeypatch.setitem(sys.modules, "src.risk.production_gate", broken)

    out = tick._evaluate_production_gate_safe()
    assert out["ok"] is False
    assert out["allow_new_risk"] is False
    assert "error" in out

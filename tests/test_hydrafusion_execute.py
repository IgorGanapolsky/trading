"""Tests for HydraFusion runtime execute (Cascade early-exit + Critique isolation)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "hydrafusion_execute.py"
    spec = importlib.util.spec_from_file_location("hydrafusion_execute", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_cascade_early_exit_saves_cost():
    mod = _load()
    out = mod.execute(task="debug flaky ci", dry_rails=True)
    assert out["pattern"] == "cascade"
    assert out["status"] == "accepted_cascade_early_exit"
    assert out["ok"] is True
    assert out["accounting"]["cascade_early_exit"] is True
    roles = [e["role"] for e in out["accounting"]["legs_run"]]
    assert "escalation" not in roles
    assert out["accounting"]["saved_vs_full_plan"] > 0


def test_critique_critic_is_tool_less():
    mod = _load()
    out = mod.execute(task="kill switch", high_risk=True, dry_rails=True)
    assert out["pattern"] == "critique"
    assert out["critic"] is not None
    assert out["critic"]["isolated"] is True
    assert out["critic"]["tools_used"] == []
    assert out["ok"] is True
    assert out["status"] == "accepted_critique"


def test_single_throwaway():
    mod = _load()
    out = mod.execute(task="typo", throwaway=True, dry_rails=True)
    assert out["pattern"] == "single"
    assert out["status"] in {"accepted_single", "rejected_single"}


def test_accounting_has_all_principles():
    mod = _load()
    out = mod.execute(task="refactor", dry_rails=True)
    assert set(out["principles_enforced"]) == {
        "complete_accounting",
        "bounded_execution",
        "isolated_review",
        "fail_safe_apply",
        "validated_routing",
    }
    assert out["accounting"]["cost_units_spent"] >= 1


def test_cli_dry_and_ralph_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hydrafusion_execute.py"),
            "--task",
            "debug flaky ci",
            "--dry-rails",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "hydrafusion_execute"
    assert data["accounting"]["cascade_early_exit"] is True

    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--hydrafusion-execute",
            "--task",
            "kill switch",
            "--high-risk",
            "--dry-rails",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r2.returncode == 0, r2.stderr
    d2 = json.loads(r2.stdout)
    assert d2["tick"] == "hydrafusion_execute"
    assert d2["pattern"] == "critique"

"""Tests for HydraFusion routing FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "hydrafusion_route.py"
    spec = importlib.util.spec_from_file_location("hydrafusion_route", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "HYDRAFUSION.md").read_text()
    assert "Cascade" in text
    assert "Critique" in text
    assert "complete_accounting" in text or "Complete accounting" in text


def test_classify_patterns():
    mod = _load()
    assert mod.classify(task="fix typo", throwaway=True) == "single"
    assert mod.classify(task="debug flaky ci") == "cascade"
    assert mod.classify(task="risk kill switch", high_risk=True) == "critique"
    assert mod.classify(task="merge credentials", regulated=True) == "critique"


def test_critique_isolates_critic():
    mod = _load()
    out = mod.route(task="live trading gate", high_risk=True)
    assert out["plan"]["pattern"] == "critique"
    critic = [leg for leg in out["plan"]["legs"] if leg["role"] == "critic"]
    assert critic and critic[0]["tools_allowed"] is False
    assert all(p["ok"] for p in out["principles"] if p["id"] == "isolated_review")


def test_cascade_has_gate_and_early_exit_flag():
    mod = _load()
    out = mod.route(task="multi-file refactor")
    assert out["plan"]["pattern"] == "cascade"
    assert out["plan"]["cascade_early_exit"] is True
    roles = {leg["role"] for leg in out["plan"]["legs"]}
    assert "gate" in roles


def test_five_principles_present():
    mod = _load()
    out = mod.route(task="status")
    ids = {p["id"] for p in out["principles"]}
    assert ids == {
        "complete_accounting",
        "bounded_execution",
        "isolated_review",
        "fail_safe_apply",
        "validated_routing",
    }
    assert out["ok"] is True


def test_cli_and_ralph():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "hydrafusion_route.py"),
            "--task",
            "cash fee-yes",
            "--multi-constraint",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["plan"]["pattern"] == "critique"

    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--hydrafusion-route",
            "--task",
            "docs only rename",
            "--throwaway",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r2.returncode == 0, r2.stderr
    d2 = json.loads(r2.stdout)
    assert d2["tick"] == "hydrafusion_route"
    assert d2["plan"]["pattern"] == "single"

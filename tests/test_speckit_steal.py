"""Tests for github/spec-kit FORMAT steals (constitution, converge, bug AFT)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_constitution_file_has_binding_principles():
    text = (ROOT / "docs" / "CONSTITUTION.md").read_text()
    assert "Cash Truth Before Grades" in text
    assert "fee-yes" in text
    assert "live_blocked" in text
    assert "Anti-Babysitting" in text
    assert "Spec → Plan → Tasks → Implement → Converge" in text


def test_constitution_checks_fail_on_empty():
    mod = _load("speckit_converge", ROOT / "scripts" / "speckit_converge.py")
    checks = mod._constitution_checks("")
    assert checks
    assert all(c["ok"] is False for c in checks)


def test_constitution_checks_pass_on_real_file():
    mod = _load("speckit_converge", ROOT / "scripts" / "speckit_converge.py")
    text = (ROOT / "docs" / "CONSTITUTION.md").read_text()
    checks = mod._constitution_checks(text)
    assert all(c["ok"] for c in checks)


def test_bug_aft_ladder(tmp_path, monkeypatch):
    mod = _load("speckit_bug_aft", ROOT / "scripts" / "speckit_bug_aft.py")
    monkeypatch.setattr(mod, "BUGS", tmp_path / "bugs")
    slug = "ruff-up017"
    mod.assess(slug, "CI failed UP017", "timezone.utc vs UTC", "gh run log")
    try:
        mod.fix(slug, "use datetime.UTC", ["scripts/ralph_gsd_tick.py"])
    except FileNotFoundError as err:
        raise AssertionError("assess should unlock fix") from err
    mod.test_step(slug, "ruff check", "All checks passed", True)
    st = mod.status(slug)
    assert st["complete"] is True
    assert st["test_pass"] is True


def test_bug_aft_requires_assess_before_fix(tmp_path, monkeypatch):
    mod = _load("speckit_bug_aft", ROOT / "scripts" / "speckit_bug_aft.py")
    monkeypatch.setattr(mod, "BUGS", tmp_path / "bugs")
    try:
        mod.fix("x", "nope", [])
        raise AssertionError("expected FileNotFoundError")
    except FileNotFoundError:
        pass


def test_converge_cli_json():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "speckit_converge.py"), "--no-append"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "speckit_converge"
    assert data["status"] in {"converged", "gaps_found"}
    assert "ship_lock" in data
    assert data["cash_ok"] is False  # fee-yes still unmet
    assert any(t.get("blocks_overall_aplus") for t in data["remaining_tasks"])

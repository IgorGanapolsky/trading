"""Tests for obra/superpowers FORMAT steals (verify-complete, plan-write)."""

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


def test_verify_complete_blocks_bad_claim():
    mod = _load(
        "superpowers_verify_complete",
        ROOT / "scripts" / "superpowers_verify_complete.py",
    )
    result = mod.run_proof(
        "false is true",
        [sys.executable, "-c", "raise SystemExit(1)"],
        require_substr=[],
    )
    assert result["ok"] is False
    assert result["exit_code"] == 1
    assert "BLOCKED" in result["gate"]


def test_verify_complete_passes_with_evidence():
    mod = _load(
        "superpowers_verify_complete",
        ROOT / "scripts" / "superpowers_verify_complete.py",
    )
    result = mod.run_proof(
        "python prints ok",
        [sys.executable, "-c", "print('PASS_TOKEN')"],
        require_substr=["PASS_TOKEN"],
    )
    assert result["ok"] is True
    assert "ONLY THEN" in result["gate"]


def test_verify_complete_requires_substr():
    mod = _load(
        "superpowers_verify_complete",
        ROOT / "scripts" / "superpowers_verify_complete.py",
    )
    result = mod.run_proof(
        "needs token",
        [sys.executable, "-c", "print('nope')"],
        require_substr=["PASS_TOKEN"],
    )
    assert result["ok"] is False
    assert "PASS_TOKEN" in result["missing_substr"]


def test_plan_write_bite_sized(tmp_path, monkeypatch):
    mod = _load("superpowers_plan_write", ROOT / "scripts" / "superpowers_plan_write.py")
    monkeypatch.setattr(mod, "PLAN", tmp_path / "plan.md")
    path = mod.write_plan(
        "demo",
        [
            {
                "id": "T1",
                "title": "Do thing",
                "files": ["scripts/x.py"],
                "steps": ["edit", "test"],
                "verify": "pytest -q",
            }
        ],
    )
    text = path.read_text()
    assert "## T1:" in text
    assert "`scripts/x.py`" in text
    assert "pytest -q" in text
    assert "YAGNI" in text


def test_bug_assess_has_systematic_phases():
    mod = _load("speckit_bug_aft", ROOT / "scripts" / "speckit_bug_aft.py")
    # use real bugs dir under tmp via monkeypatch in caller — read template via assess
    import tempfile

    with tempfile.TemporaryDirectory() as td:
        from pathlib import Path as P

        mod.BUGS = P(td) / "bugs"
        path = mod.assess("x", "fail", "cause", "ev")
        text = path.read_text()
        assert "NO FIXES WITHOUT ROOT CAUSE" in text
        assert "Phase 1" in text
        assert "Phases 2–4" in text


def test_constitution_mentions_evidence_over_claims():
    text = (ROOT / "docs" / "CONSTITUTION.md").read_text()
    assert "Evidence over claims" in text
    assert "superpowers_verify_complete" in text


def test_verify_complete_cli_single():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "superpowers_verify_complete.py"),
            "--claim",
            "echo works",
            "--command",
            f"{sys.executable} -c \"print('OK')\"",
            "--require",
            "OK",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr + r.stdout
    data = json.loads(r.stdout)
    assert data["ok"] is True

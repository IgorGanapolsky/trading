"""Tests for BMAD SPEC.md + readiness FORMAT steal."""

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


def test_spec_md_has_five_elements():
    text = (ROOT / "docs" / "SPEC.md").read_text()
    for heading in (
        "## Why",
        "## Capabilities",
        "## Constraints",
        "## Non-goals",
        "## Success signal",
    ):
        assert heading in text, heading
    assert "fee-yes" in text.lower()
    assert "Non-goals" in text
    assert "Quick Flow" in text or "quick" in text.lower()


def test_validate_spec_fails_empty():
    mod = _load("bmad_readiness", ROOT / "scripts" / "bmad_readiness.py")
    checks = mod.validate_spec("")
    assert any(not c["ok"] for c in checks)


def test_validate_spec_passes_real():
    mod = _load("bmad_readiness", ROOT / "scripts" / "bmad_readiness.py")
    text = (ROOT / "docs" / "SPEC.md").read_text()
    checks = mod.validate_spec(text)
    assert all(c["ok"] for c in checks)


def test_parse_planning_depth_quick_flow():
    mod = _load("bmad_readiness", ROOT / "scripts" / "bmad_readiness.py")
    depth = mod.parse_planning_depth((ROOT / "docs" / "SPEC.md").read_text())
    assert "quick" in depth.lower() or "Quick" in depth


def test_readiness_cli_ready():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "bmad_readiness.py"),
            "--no-append",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "bmad_readiness"
    assert data["ready"] is True
    assert data["status"] == "ready"
    assert data["cash_ok"] is False  # ship lock stands
    assert data["quick_flow_allowed"] is True


def test_constitution_mentions_bmad_spec():
    text = (ROOT / "docs" / "CONSTITUTION.md").read_text()
    assert "SPEC.md" in text
    assert "bmad_readiness" in text

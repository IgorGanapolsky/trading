"""Tests for DAIR/ETH AGENTS.md health FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "agents_md_health.py"
    spec = importlib.util.spec_from_file_location("agents_md_health", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_live_repo_has_additive_markers():
    mod = _load()
    out = mod.evaluate(root=ROOT, max_chars=50_000, max_readme_overlap=0.95)
    assert out["framework"] == "agents_md_health"
    assert out["files"], "expected Agents.md / CLAUDE.md present"
    assert any(f["additive_markers"] >= 1 for f in out["files"])


def test_flags_oversized_and_llm_fluff(tmp_path: Path):
    mod = _load()
    (tmp_path / "README.md").write_text(
        "Trading platform for SPY options paper validation with broker sync.\n" * 40
    )
    fluff = (
        "This repository provides a comprehensive overview of the codebase. "
        "Directory structure includes src, scripts, and tests. "
        "Here is a complete guide to getting started with the project. "
        + (" filler word pack " * 400)
    )
    (tmp_path / "Agents.md").write_text(fluff)
    out = mod.evaluate(root=tmp_path, max_chars=2000, max_readme_overlap=0.2)
    assert out["ok"] is False
    metrics = {b["metric"] for b in out["breaches"]}
    assert (
        "chars" in metrics or "readme_overlap" in metrics or "llm_tells_without_additive" in metrics
    )


def test_cli():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "agents_md_health.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["stolen_format"].startswith("DAIR.AI")
    assert "2602.11988" in data["source"]["paper"]

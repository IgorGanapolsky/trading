"""Tests for ops daily brief (narrow workflows + recommend-first)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "ops_daily_brief.py"
    spec = importlib.util.spec_from_file_location("ops_daily_brief", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "CONSUMER_AGENT_ECONOMICS.md").read_text()
    assert "precision" in text.lower()
    assert "tiered" in text.lower() or "decision ladder" in text.lower()
    assert "recommend" in text.lower()


def test_brief_recommend_only_and_budget():
    mod = _load()
    out = mod.build_brief(alert_budget=3, log_candidates=False)
    assert out["framework"] == "ops_daily_brief"
    assert out["autonomy_default"] == "recommend_only"
    assert "auto-send" in " ".join(out["never"])
    assert len(out["alerts_shown"]) <= 3
    for a in out["alerts_shown"]:
        assert a["autonomy"] == "recommend_only"
        assert a["provenance"]
        assert a["tier"] in {"rules", "cheap", "extract", "premium"}


def test_cli_and_ralph():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ops_daily_brief.py"),
            "--no-log",
            "--alert-budget",
            "5",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["habit"] == "ops_daily_brief"

    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--ops-brief",
            "--no-log",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r2.returncode == 0, r2.stderr
    d2 = json.loads(r2.stdout)
    assert d2["tick"] == "ops_brief"

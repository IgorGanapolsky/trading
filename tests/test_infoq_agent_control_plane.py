"""Tests for InfoQ control-plane doctor CLI."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_cli():
    path = Path(__file__).resolve().parents[1] / "scripts" / "infoq_agent_control_plane.py"
    spec = importlib.util.spec_from_file_location("infoq_agent_control_plane", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doctor_green_path(capsys):
    mod = _load_cli()
    rc = mod.main(
        [
            "--goal",
            "doctor",
            "--in-scope",
            "gist challenges flux pr-risk",
            "--out-scope",
            "Harness webinar",
            "--acs",
            "tests pass|CLI fail-closed",
            "--paths",
            "src/ops/context_gist.py,tests/test_context_gist.py,docs/INFOQ_CONTROL_PLANE.md",
            "--iv-rank-proxy",
            "40",
            "--inventory-clean",
            "--graph",
            "dry_run_readiness",
        ]
    )
    out = capsys.readouterr().out
    report = json.loads(out)
    assert rc == 0
    assert report["ok"] is True
    assert report["score"] == 5
    assert report["failing"] == []


def test_doctor_fails_on_low_ivr(capsys):
    mod = _load_cli()
    rc = mod.main(
        [
            "--acs",
            "a|b",
            "--in-scope",
            "x",
            "--out-scope",
            "y",
            "--iv-rank-proxy",
            "10",
            "--paths",
            "docs/INFOQ_CONTROL_PLANE.md,tests/test_context_gist.py",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert report["ok"] is False
    assert "entry_challenges" in report["failing"]


def test_doctor_fails_billed_copilot(capsys):
    mod = _load_cli()
    rc = mod.main(
        [
            "--acs",
            "a|b",
            "--in-scope",
            "x",
            "--out-scope",
            "y",
            "--paths",
            "docs/INFOQ_CONTROL_PLANE.md",
            "--propose-billed-copilot",
            "--iv-rank-proxy",
            "40",
        ]
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 1
    assert "pr_risk" in report["failing"]

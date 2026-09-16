"""Tests for FlashREINFORCE FORMAT steal: profile, don't clone, don't swap GRPO."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "rollout_cost_profile.py"
    spec = importlib.util.spec_from_file_location("rollout_cost_profile", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _row(**kw):
    base = {
        "family": "spy_put_credit_dry_run",
        "duration_s": 10.0,
        "queue_s": 0.5,
        "tokens": 100,
        "tool_calls": 2,
        "success": True,
        "verified": True,
        "cost_usd": 1.0,
        "idle_s": 0.0,
    }
    base.update(kw)
    return base


def test_profile_stragglers_and_cost_per_solved(tmp_path: Path):
    mod = _load()
    rows = [
        _row(duration_s=10, cost_usd=1.0),
        _row(duration_s=11, cost_usd=1.0),
        _row(duration_s=12, cost_usd=1.0),
        _row(duration_s=40, cost_usd=1.0),  # straggler > 2x median
    ]
    report = mod.profile(rows)
    assert report["n"] == 4
    assert report["n_solved"] == 4
    assert report["cost_per_solved_task"] == 1.0
    assert report["straggler_pct"] == 0.25
    assert report["grpo_status"] == "optional_research_not_production"
    assert "half_rollouts_is_not_half_gpu_hours" in report["refuses"]
    assert report["gpu_hours_measured"] is False
    assert report["gpu_hours_per_solved"] is None


def test_does_not_invent_gpu_hours_from_rollout_count():
    mod = _load()
    rows = [_row(), _row()]
    report = mod.profile(rows)
    assert report["gpu_hours_per_solved"] is None
    assert "do_not_infer_gpu_hours_from_rollout_count" in report["refuses"]


def test_tool_use_collapse_blocks_promotion():
    mod = _load()
    baseline = mod.profile([_row(tool_calls=3, cost_usd=1.0) for _ in range(4)])
    collapsed = mod.profile(
        [_row(tool_calls=0, cost_usd=0.5, success=True, verified=True) for _ in range(4)]
    )
    gate = mod.compare(baseline, collapsed)
    assert gate["promote"] is False
    assert gate["tool_use_retention_ok"] is False
    assert "tool_use_collapsed" in gate["reasons"]


def test_fifteen_percent_cost_cut_promotes_when_tools_kept():
    mod = _load()
    baseline = mod.profile([_row(cost_usd=1.0, tool_calls=2) for _ in range(4)])
    cheaper = mod.profile([_row(cost_usd=0.80, tool_calls=2) for _ in range(4)])
    gate = mod.compare(baseline, cheaper)
    assert gate["promote"] is True
    assert gate["cost_cut_frac"] == pytest.approx(0.2)
    assert gate["tool_use_retention_ok"] is True


def test_half_rollouts_alone_does_not_promote():
    """Same cost/success/tools, fewer rows — not a GPU-hour claim, not a promote."""
    mod = _load()
    baseline = mod.profile([_row(cost_usd=1.0) for _ in range(8)])
    half = mod.profile([_row(cost_usd=1.0) for _ in range(4)])
    gate = mod.compare(baseline, half)
    assert gate["promote"] is False
    assert "half_rollouts_is_not_half_gpu_hours" in gate["refuses"]


def test_cli_profile_and_compare(tmp_path: Path):
    base = tmp_path / "base.jsonl"
    cand = tmp_path / "cand.jsonl"
    base.write_text(
        "\n".join(json.dumps(_row(cost_usd=1.0, tool_calls=2)) for _ in range(4)) + "\n",
        encoding="utf-8",
    )
    cand.write_text(
        "\n".join(json.dumps(_row(cost_usd=0.7, tool_calls=2)) for _ in range(4)) + "\n",
        encoding="utf-8",
    )
    script = ROOT / "scripts" / "rollout_cost_profile.py"
    r = subprocess.run(
        [sys.executable, str(script), "profile", "--jsonl", str(base)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["task_family"] == "spy_put_credit_dry_run"
    assert "v-LD_XChPkA" in data["source"]["youtube_music"]
    r2 = subprocess.run(
        [
            sys.executable,
            str(script),
            "compare",
            "--baseline",
            str(base),
            "--candidate",
            str(cand),
            "--strict",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r2.returncode == 0, r2.stderr
    gate = json.loads(r2.stdout)
    assert gate["promote"] is True

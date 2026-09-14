"""Tests for Superpowers vs GSD vs Compound Engineering FORMAT steals."""

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


def test_checkpoint_pick_default_superpowers():
    mod = _load("checkpoint_pick", ROOT / "scripts" / "checkpoint_pick.py")
    out = mod.pick(undo_cost="medium", multi_session=False, repeat_correction=False)
    assert out["recommend"] == "superpowers"
    assert "verify-complete" in out["cli"]


def test_checkpoint_pick_gsd_for_multi_session():
    mod = _load("checkpoint_pick", ROOT / "scripts" / "checkpoint_pick.py")
    out = mod.pick(undo_cost="high", multi_session=True, repeat_correction=False)
    assert out["recommend"] == "gsd"
    assert "goal_backward" in out["cli"]


def test_checkpoint_pick_adds_compound_on_repeat():
    mod = _load("checkpoint_pick", ROOT / "scripts" / "checkpoint_pick.py")
    out = mod.pick(undo_cost="medium", multi_session=False, repeat_correction=True)
    assert "compound" in out["recommend"]
    assert out["compound_note"]


def test_checkpoint_pick_quick_one_sentence():
    mod = _load("checkpoint_pick", ROOT / "scripts" / "checkpoint_pick.py")
    out = mod.pick(
        undo_cost="low",
        multi_session=False,
        repeat_correction=False,
        one_sentence_diff=True,
    )
    assert out["recommend"] == "quick"


def test_compound_lesson_records_and_detects_repeat(tmp_path, monkeypatch):
    mod = _load("compound_lesson", ROOT / "scripts" / "compound_lesson.py")
    monkeypatch.setattr(mod, "COMPOUND", tmp_path / "COMPOUND.md")
    first = mod.record(
        slug="ruff-up017",
        correction="use datetime.UTC",
        prevention="ruff UP017 in CI",
        evidence="gh run log",
    )
    assert first["ok"] is True
    second = mod.record(
        slug="ruff-up017",
        correction="use datetime.UTC again",
        prevention="same",
        evidence="again",
    )
    assert second["ok"] is False
    assert second["repeat"] is True
    forced = mod.record(
        slug="ruff-up017",
        correction="note",
        prevention="promote to rule",
        evidence="x",
        force=True,
    )
    assert forced["ok"] is True


def test_goal_backward_harness_cli():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "goal_backward_verify.py"), "--goal", "harness"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    # May take a bit; must succeed for harness
    assert r.returncode == 0, r.stderr + r.stdout[-2000:]
    data = json.loads(r.stdout)
    assert data["framework"] == "goal_backward_verify"
    assert data["ok"] is True
    assert data["passed"] == data["total"]
    assert data["total"] >= 4

"""Tests for LinkedIn multi-teacher distillation FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "multi_teacher_distill.py"
    spec = importlib.util.spec_from_file_location("multi_teacher_distill", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "MULTI_TEACHER_DISTILL.md").read_text()
    assert "teacher" in text.lower()
    assert "cache" in text.lower()
    assert "8" in text or "offline" in text.lower()


def test_second_pass_uses_cache(tmp_path: Path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "CACHE_ROOT", tmp_path / "cache")
    examples = mod.demo_examples()
    first = mod.distill(examples, mode="auto")
    assert first["ok"] is True
    assert first["teacher_calls"] > 0
    second = mod.distill(examples, mode="auto")
    assert second["ok"] is True
    assert second["teacher_calls"] == 0
    assert second["cache_hits"] > 0
    assert second["estimated_speedup_vs_naive"] >= 1.0
    # Student ranks cash/kill above unrelated
    ranking = second["student_ranking"]
    assert ranking[0]["example_id"] in {"ex1", "ex2"}


def test_offline_fails_when_cold(tmp_path: Path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "CACHE_ROOT", tmp_path / "cold")
    out = mod.distill(mod.demo_examples(), mode="offline")
    assert out["ok"] is False
    assert out.get("error") == "offline_cache_incomplete"


def test_pluggable_teacher_version_isolation(tmp_path: Path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "CACHE_ROOT", tmp_path / "iso")
    examples = mod.demo_examples()[:1]
    mod.distill(examples, teacher_ids=["relevance"], mode="online")
    # bump version → cache miss
    mod.DEFAULT_TEACHERS["relevance"] = mod.Teacher(
        "relevance", "v2", mod.relevance_teacher
    )
    out = mod.distill(examples, teacher_ids=["relevance"], mode="auto")
    assert out["teacher_calls"] == 1


def test_cli_demo():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "multi_teacher_distill.py"),
            "--demo",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "multi_teacher_distill"
    assert data["cache_amortization"]["second_calls"] == 0

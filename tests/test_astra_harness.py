"""Tests for GPT-6 Astra harness FORMAT steal (notes + gate)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "ASTRA_HARNESS.md").read_text()
    assert "searchable" in text.lower() or "notes" in text.lower()
    assert "Astra" in text or "astra" in text


def test_notes_search_across_windows(tmp_path: Path):
    mod = _load("astra_session_notes")
    path = tmp_path / "notes.jsonl"
    mod.append_note(
        text="put credit kill switch gate", kind="requirement", window_id="w1", path=path
    )
    mod.append_note(text="pytest hydrafusion passed", kind="test_result", window_id="w2", path=path)
    hits = mod.search_notes("kill switch", path=path)
    assert hits and hits[0]["window_id"] == "w1"
    hits2 = mod.search_notes("hydrafusion", path=path)
    assert hits2 and hits2[0]["kind"] == "test_result"


def test_gate_blocks_astra_primary():
    mod = _load("astra_harness_gate")
    out = mod.evaluate(primary_model="gpt-6-astra")
    assert out["ok"] is False
    assert "no_astra_api_primary" in out["hard_fails"]


def test_gate_blocks_offensive():
    mod = _load("astra_harness_gate")
    out = mod.evaluate(proposed_action="develop exploit against browser")
    assert out["ok"] is False
    assert "offensive_cyber_blocked" in out["hard_fails"]


def test_gate_flags_consequential_confirm():
    mod = _load("astra_harness_gate")
    out = mod.evaluate(proposed_action="email_send")
    assert out["ok"] is True
    c = next(x for x in out["checks"] if x["id"] == "consequential_confirmation")
    assert c["needs_confirm"] is True


def test_cli_and_ralph():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "astra_harness_gate.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "astra_harness_gate"

    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--astra-gate",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r2.returncode == 0, r2.stderr
    d2 = json.loads(r2.stdout)
    assert d2["tick"] == "astra_gate"

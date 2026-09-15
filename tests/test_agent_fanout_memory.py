"""Tests for AgentZip fan-out memory FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "agent_fanout_memory.py"
    spec = importlib.util.spec_from_file_location("agent_fanout_memory", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "AGENT_FANOUT_MEMORY.md").read_text()
    assert "2609.11294" in text
    assert "template" in text.lower()
    assert "prefetch" in text.lower()


def test_shared_context_fingerprint():
    mod = _load()
    ctx = mod.shared_context_fingerprint(ROOT)
    assert ctx["fingerprint"]
    assert len(ctx["fingerprint"]) == 16
    assert ctx["files"]


def test_evaluate_over_budget(monkeypatch):
    mod = _load()
    primary = str(ROOT.resolve())
    fake = [
        {"path": primary, "head": "aaa", "branch": "main"},
        {"path": str(ROOT / ".worktrees" / "fake-a"), "head": "bbb", "branch": "a"},
        {"path": str(ROOT / ".worktrees" / "fake-b"), "head": "bbb", "branch": "b"},
        {"path": str(ROOT / ".worktrees" / "fake-c"), "head": "ccc", "branch": "c"},
    ]
    monkeypatch.setattr(mod, "list_worktrees", lambda repo=None: fake)
    monkeypatch.setattr(mod, "template_sha", lambda repo=None: "bbb")
    monkeypatch.setattr(
        mod, "host_memory_gb", lambda: {"ok": True, "total_gb": 36.0, "free_gb_est": 20.0}
    )
    out = mod.evaluate(repo=ROOT, max_worktrees=2, min_free_gb=4.0, gb_per_sandbox=1.5)
    assert out["sandboxes"] == 3
    assert out["sandboxes_on_template"] == 2
    assert out["ok"] is False
    assert any(b["metric"] == "sandbox_count" for b in out["breaches"])


def test_cli_json():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "agent_fanout_memory.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "agent_fanout_memory"
    assert "AgentZip" in data["stolen_format"]
    assert "prefetch_on_restore" in data
    assert data["shared_context"]["fingerprint"]


def test_ralph_fanout_memory_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--fanout-memory",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tick"] == "fanout_memory"

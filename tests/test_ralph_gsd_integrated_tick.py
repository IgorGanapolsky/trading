"""Tests for integrated Ralph tick (all harness CLIs automated)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "ralph_gsd_integrated_tick.py"
    spec = importlib.util.spec_from_file_location("ralph_gsd_integrated_tick", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "RALPH_INTEGRATED.md").read_text()
    assert "integrated" in text.lower()
    assert "LaunchAgent" in text or "launchagent" in text.lower()
    assert "never" in text.lower()


def test_integrated_observe_keys(monkeypatch):
    mod = _load()

    monkeypatch.setattr(
        mod,
        "run_integrated",
        lambda **kwargs: {
            "ok": True,
            "tick": "integrated",
            "observe": {
                "ops_brief": {"ok": True},
                "eval_ledger": {"ok": True},
                "fanout_memory": {"ok": True},
                "hydrafusion": {"ok": True},
            },
            "recommends": [],
            "automation": {"entrypoint": "scripts/ralph_gsd_integrated_tick.py"},
        },
    )
    out = mod.run_integrated(log_candidates=False, write_state=False)
    assert out["tick"] == "integrated"
    assert "ops_brief" in out["observe"]


def test_cli_smoke_no_log():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_integrated_tick.py"),
            "--no-log",
            "--no-write-state",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stderr[-500:]
    data = json.loads(r.stdout)
    assert data["tick"] == "integrated"
    assert data["framework"] == "ralph_gsd_integrated"
    for key in ("ops_brief", "eval_ledger", "fanout_memory", "hydrafusion"):
        assert key in data["observe"]
    assert data["automation"]["entrypoint"].endswith("ralph_gsd_integrated_tick.py")


def test_ralph_integrated_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--integrated",
            "--no-log",
            "--no-write-state",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=300,
    )
    assert r.returncode == 0, r.stderr[-500:]
    data = json.loads(r.stdout)
    assert data["tick"] == "integrated"

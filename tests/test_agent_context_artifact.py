"""Wisdom.ai FORMAT: agent context packs; Wisdom SKU is wrong-fit."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "agent_context_artifact.py"
    spec = importlib.util.spec_from_file_location("agent_context_artifact", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _good() -> dict:
    return {
        "id": "put-credit-operator",
        "consumer": "agent",
        "goal": "Paper spy_put_credit dry-run with kill switch.",
        "constraints": ["paper_only", "live_blocked"],
        "sources": [{"path": "data/runtime/strategy_kill_switch.json", "role": "durable"}],
        "freshness_max_hours": 24,
        "verifier": "scripts/audit_active_scope.py --json",
        "wrong_fit": ["wisdom_ai", "palantir_foundry"],
    }


def test_good_pack_ok():
    mod = _load()
    report = mod.lint(_good())
    assert report["ok"] is True
    assert "do_not_clone_wisdom_ai" in report["refuses"]


def test_human_dashboard_fails():
    mod = _load()
    pack = _good()
    pack["consumer"] = "human_dashboard"
    report = mod.lint(pack)
    assert report["ok"] is False
    assert "consumer_must_be_agent" in report["errors"]


def test_missing_wrong_fit_fails():
    mod = _load()
    pack = _good()
    pack["wrong_fit"] = ["looker"]
    report = mod.lint(pack)
    assert "must_declare_wisdom_ai_wrong_fit" in report["errors"]


def test_cli_lint(tmp_path: Path):
    pack = tmp_path / "pack.json"
    pack.write_text(json.dumps(_good()), encoding="utf-8")
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "agent_context_artifact.py"),
            "lint",
            "--pack",
            str(pack),
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert "lRuI0imju0Y" in data["sources"][0]

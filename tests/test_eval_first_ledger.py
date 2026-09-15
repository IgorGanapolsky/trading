"""Tests for eval-first ledger (always-on assistant FORMAT)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "eval_first_ledger.py"
    spec = importlib.util.spec_from_file_location("eval_first_ledger", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_precision_by_workflow(tmp_path: Path):
    mod = _load()
    ledger = tmp_path / "ledger.jsonl"
    mod.LEDGER = ledger  # type: ignore[attr-defined]
    # monkey via path arg
    for row in [
        {"kind": "candidate", "workflow": "cash_fee_yes", "title": "a", "provenance": "p"},
        {"kind": "action", "workflow": "cash_fee_yes", "action": "approved"},
        {"kind": "action", "workflow": "cash_fee_yes", "action": "dismissed"},
        {"kind": "action", "workflow": "cash_fee_yes", "action": "approved"},
    ]:
        mod.append_event(row, path=ledger)
    events = mod.load_events(path=ledger)
    report = mod.precision_by_workflow(events)
    assert report["cash_fee_yes"]["judged"] == 3
    assert report["cash_fee_yes"]["precision"] == round(2 / 3, 4)


def test_rejects_unknown_workflow(tmp_path: Path):
    mod = _load()
    try:
        mod.append_event(
            {"kind": "candidate", "workflow": "do_anything", "title": "x", "provenance": "y"},
            path=tmp_path / "l.jsonl",
        )
        raise AssertionError("expected ValueError")
    except ValueError:
        pass


def test_cli_summary():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "eval_first_ledger.py"), "summary"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "eval_first_ledger"
    assert "Xa1jm2VWEHk" in data["source"]["youtube_music"]

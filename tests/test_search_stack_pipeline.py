"""Tests for LinkedIn search-stack FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "search_stack_pipeline.py"
    spec = importlib.util.spec_from_file_location("search_stack_pipeline", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "SEARCH_STACK.md").read_text()
    assert "LinkedIn" in text
    assert "depth" in text.lower() or "ranking" in text.lower()


def test_understand_routes_entity_vs_semantic():
    mod = _load()
    u1 = mod.understand_query("TradeGateway")
    assert u1["route"] == "keyword"
    u2 = mod.understand_query("why did put credit kill switch fire")
    assert u2["route"] == "semantic"
    assert "risk" in u2["facets"] or "strategy" in u2["facets"]


def test_depth_controller_caps():
    mod = _load()
    assert mod.ranking_depth_controller(100, max_deep=25) == 25
    assert mod.ranking_depth_controller(3, max_deep=25) == 3


def test_explain_and_grade():
    mod = _load()
    snip = mod.explain_snippet("kill switch", "The kill switch blocks new iron condor entries.\nOther line")
    assert "kill" in snip.lower() or "**" in snip
    g = mod.policy_grade("kill switch put credit", "scripts/spy_put_credit.py", snip)
    assert 0 <= g["grade"] <= 4


def test_pipeline_and_cache(tmp_path: Path, monkeypatch):
    mod = _load()
    monkeypatch.setattr(mod, "CACHE_DIR", tmp_path / "cache")
    out1 = mod.run_pipeline("put credit stop loss", root=ROOT, limit=5, use_cache=True)
    assert out1["ok"] is True
    assert out1["understanding"]["query"]
    assert "results" in out1
    out2 = mod.run_pipeline("put credit stop loss", root=ROOT, limit=5, use_cache=True)
    assert out2.get("cache_hit") is True


def test_cli_and_ralph():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "search_stack_pipeline.py"),
            "kill switch",
            "--limit",
            "5",
            "--no-cache",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr[-400:]
    data = json.loads(r.stdout)
    assert data["framework"] == "search_stack_pipeline"

    r2 = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--search-stack",
            "--task",
            "put credit expectancy",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r2.returncode == 0, r2.stderr[-400:]
    d2 = json.loads(r2.stdout)
    assert d2["tick"] == "search_stack"

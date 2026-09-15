"""Tests for TNS LLM response-cache FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "llm_response_cache.py"
    spec = importlib.util.spec_from_file_location("llm_response_cache", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    # dataclasses need the module registered before exec (3.11+)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "LLM_RESPONSE_CACHE.md").read_text()
    assert "exact-match" in text.lower() or "exact match" in text.lower()
    assert "prompt" in text.lower() and "cache" in text.lower()
    assert "fingerprint" in text.lower()


def test_fingerprint_stable_and_scope_sensitive():
    mod = _load()
    a = mod.fingerprint("What is SPY DTE?", context="rules", model="m1", scope="ops")
    b = mod.fingerprint("What is SPY DTE?", context="rules", model="m1", scope="ops")
    c = mod.fingerprint("What is SPY DTE?", context="rules", model="m1", scope="other")
    assert a == b
    assert a != c


def test_exact_hit_skips_second_model_call(tmp_path: Path):
    mod = _load()
    cache = mod.ResponseCache(root=tmp_path)
    n = {"c": 0}

    def call():
        n["c"] += 1
        return "answer-v1"

    r1 = mod.cached_completion("summarize kill switch", call, category="docs", cache=cache)
    r2 = mod.cached_completion("summarize kill switch", call, category="docs", cache=cache)
    assert r1["from_cache"] is False
    assert r2["from_cache"] is True
    assert n["c"] == 1
    assert r2["response"] == "answer-v1"


def test_market_category_never_cached(tmp_path: Path):
    mod = _load()
    cache = mod.ResponseCache(root=tmp_path)
    out = cache.set("what is SPY price now", "650.12", category="market")
    assert out.get("skipped") is True
    got = cache.get("what is SPY price now", category="market")
    assert got.get("skipped") is True


def test_refuse_poison_empty(tmp_path: Path):
    mod = _load()
    cache = mod.ResponseCache(root=tmp_path)
    out = cache.set("hello", "   ", category="docs")
    assert out.get("invalid") is True


def test_shadow_mode_logs_but_misses(tmp_path: Path):
    mod = _load()
    cache = mod.ResponseCache(root=tmp_path, shadow=False)
    cache.set("q", "cached", category="docs")
    shadow = mod.ResponseCache(root=tmp_path, shadow=True)
    got = shadow.get("q", category="docs")
    assert got.get("shadow_hit") is True
    assert got.get("hit") is False


def test_cli_demo():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "llm_response_cache.py"), "demo"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["second_from_cache"] is True
    assert data["model_calls"] == 1

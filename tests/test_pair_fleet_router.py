"""Tests for NVIDIA PAIR FORMAT fleet router."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "pair_fleet_router.py"
    spec = importlib.util.spec_from_file_location("pair_fleet_router", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "PAIR_FLEET.md").read_text()
    assert "PAIR" in text
    assert "independent" in text.lower()
    assert "S25" in text or "Galaxy" in text or "phone" in text.lower()


def test_select_prefers_pair_proxy():
    mod = _load()
    inv = {
        "nodes": [
            {
                "id": "s25-termux-ollama",
                "kind": "elastic_phone",
                "ready": True,
                "models": ["qwen2.5:3b-hermes-64k"],
                "latency_ms": 10,
                "base_url": "http://192.168.12.237:11434",
            },
            {
                "id": "mac-pair-local",
                "kind": "nvidia_pair_proxy",
                "ready": True,
                "models": ["qwen2.5:3b-hermes-64k"],
                "latency_ms": 50,
                "base_url": "http://127.0.0.1:11434",
            },
        ]
    }
    node = mod.select_node(inv, model="qwen2.5:3b-hermes-64k")
    assert node is not None
    assert node["id"] == "mac-pair-local"


def test_inventory_cli():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "pair_fleet_router.py"), "inventory"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "pair_fleet_router"
    assert "nodes" in data
    # Mac PAIR should be ready in this environment
    assert data["ready_count"] >= 1


def test_chat_routes_when_pair_up():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "pair_fleet_router.py"),
            "chat",
            "--model",
            "qwen2.5:3b-hermes-64k",
            "--prompt",
            "Reply with exactly: PAIR_OK",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["ok"] is True
    assert "PAIR_OK" in (data.get("content") or "")
    assert data["node"]["id"]

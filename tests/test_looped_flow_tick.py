"""Tests for Looped Flows FORMAT steal (local objectives — not ML training)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "looped_flow_tick.py"
    spec = importlib.util.spec_from_file_location("looped_flow_tick", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "LOOPED_FLOW.md").read_text()
    assert "2609.11801" in text
    assert "local" in text.lower()
    assert "noise" in text.lower()
    assert "finer" in text.lower() or "loop-steps" in text


def test_noise_and_local_objective():
    mod = _load()
    results = [
        {"id": "A", "must_be_true": "first", "ok": True},
        {"id": "B", "must_be_true": "second fails", "ok": False},
        {"id": "C", "must_be_true": "third", "ok": False},
    ]
    assert mod._noise(results) == 2 / 3
    local = mod._local_objective(results)
    assert local is not None
    assert local["id"] == "B"


def test_loop_denoises_with_injected_verify():
    mod = _load()
    state = {"n": 0}

    def verify():
        # Step 0: 2 fails; step 1+: 0 fails (denoised)
        state["n"] += 1
        if state["n"] == 1:
            conds = [
                {"id": "X", "must_be_true": "a", "ok": False},
                {"id": "Y", "must_be_true": "b", "ok": False},
            ]
        else:
            conds = [
                {"id": "X", "must_be_true": "a", "ok": True},
                {"id": "Y", "must_be_true": "b", "ok": True},
            ]
        return {
            "ok": all(c["ok"] for c in conds),
            "conditions": conds,
            "passed": sum(1 for c in conds if c["ok"]),
            "total": len(conds),
        }

    out = mod.run_loop(goal="harness", steps=4, shared_seed="unit", verify_fn=verify)
    assert out["framework"] == "looped_flow_tick"
    assert "Looped Flows" in out["stolen_format"]
    assert out["residual_id"]
    assert out["steps_run"] == 2  # early stop when ok
    assert out["noise_levels"][0] == 1.0
    assert out["final_noise"] == 0.0
    assert out["ok"] is True
    assert out["noise_nonincreasing"] is True


def test_shared_seed_stable_residual():
    mod = _load()

    def verify():
        return {
            "ok": True,
            "conditions": [{"id": "Z", "must_be_true": "z", "ok": True}],
            "passed": 1,
            "total": 1,
        }

    a = mod.run_loop(goal="cash", steps=1, shared_seed="same", verify_fn=verify)
    b = mod.run_loop(goal="cash", steps=1, shared_seed="same", verify_fn=verify)
    assert a["residual_id"] == b["residual_id"]


def test_cli_json_one_step():
    # One live step is enough smoke; avoid 3× full harness pytest wall-clock in CI unit job
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "looped_flow_tick.py"),
            "--goal",
            "cash",
            "--loop-steps",
            "1",
            "--seed",
            "cli-smoke",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "looped_flow_tick"
    assert data["steps_run"] == 1
    assert data["shared_noise_seed"] == "cli-smoke"
    assert len(data["trajectory"]) == 1
    assert data["trajectory"][0]["local_objective"] is not None or data["ok"]


def test_ralph_looped_flow_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--looped-flow",
            "--goal-backward",
            "cash",
            "--loop-steps",
            "1",
            "--seed",
            "ralph-smoke",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tick"] == "looped_flow"
    assert data["framework"] == "looped_flow_tick"

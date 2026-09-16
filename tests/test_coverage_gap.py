"""VS coverage FORMAT: baseline gaps, skip no-behavior, same-scope remeasure."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "coverage_gap.py"
    spec = importlib.util.spec_from_file_location("coverage_gap", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _cov(files: dict, total: float = 40.0) -> dict:
    return {
        "files": {p: {"summary": {"percent_covered": pct}} for p, pct in files.items()},
        "totals": {"percent_covered": total},
    }


def test_baseline_ranks_gaps_and_skips_enum(tmp_path: Path):
    mod = _load()
    enum_path = tmp_path / "mode.py"
    enum_path.write_text("from enum import Enum\nclass Mode(Enum):\n    A = 1\n", encoding="utf-8")
    logic_path = tmp_path / "logic.py"
    logic_path.write_text("def run(x):\n    return x + 1\n", encoding="utf-8")
    cov = _cov({str(enum_path): 0.0, str(logic_path): 10.0})
    report = mod.baseline(cov, floor=50.0, source_root=tmp_path)
    paths = [g["path"] for g in report["gaps"]]
    assert str(logic_path) in paths
    assert str(enum_path) not in paths
    assert report["skipped_no_behavior"]
    assert report["global_100_is_not_a_gate"] is True
    assert "do_not_claim_repo_wide_100_percent" in report["refuses"]


def test_compare_same_scope_detects_regression():
    mod = _load()
    before = _cov({"src/risk/gate.py": 80.0, "src/other.py": 10.0})
    after = _cov({"src/risk/gate.py": 70.0, "src/other.py": 90.0})
    scoped = mod.compare(before, after, scope="src/risk/")
    assert scoped["n_regressed"] == 1
    assert scoped["ok"] is False
    whole = mod.compare(before, after, scope="")
    assert whole["n_improved"] == 1
    assert whole["n_regressed"] == 1


def test_cli_baseline_and_compare(tmp_path: Path):
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(_cov({"src/a.py": 20.0})), encoding="utf-8")
    after.write_text(json.dumps(_cov({"src/a.py": 80.0})), encoding="utf-8")
    script = ROOT / "scripts" / "coverage_gap.py"
    r = subprocess.run(
        [sys.executable, str(script), "baseline", "--json", str(before), "--floor", "50"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["n_gaps"] == 1
    assert "today-i-will-improve-test-coverage" in data["source"]
    r2 = subprocess.run(
        [
            sys.executable,
            str(script),
            "compare",
            "--before",
            str(before),
            "--after",
            str(after),
            "--scope",
            "src/a.py",
            "--strict",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r2.returncode == 0, r2.stderr
    gate = json.loads(r2.stdout)
    assert gate["n_improved"] == 1
    assert gate["ok"] is True

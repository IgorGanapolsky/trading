"""Tests for TNS/GitClear duplication-health FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "dup_health.py"
    spec = importlib.util.spec_from_file_location("dup_health", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists():
    text = (ROOT / "docs" / "DUP_HEALTH.md").read_text()
    assert "duplication" in text.lower()
    assert "moved" in text.lower()
    assert "GitClear" in text or "Maintainability" in text
    assert "side quest" in text.lower() or "refactor" in text.lower()


def test_finds_cross_file_duplicate_blocks(tmp_path: Path):
    mod = _load()
    block = "\n".join([f"    x = {i} + 1" for i in range(12)])
    a = tmp_path / "a.py"
    b = tmp_path / "b.py"
    a.write_text(f"def one():\n{block}\n    return x\n")
    b.write_text(f"def two():\n{block}\n    return x\n")
    out = mod.find_duplicate_blocks([a, b], min_lines=10, root=tmp_path)
    assert out["duplicate_block_groups"] >= 1
    assert any(g["cross_file"] for g in out["top_groups"])


def test_no_dup_on_unique_files(tmp_path: Path):
    mod = _load()
    a = tmp_path / "unique_a.py"
    b = tmp_path / "unique_b.py"
    a.write_text("def alpha(n):\n    return n * 2\n")
    b.write_text("def beta(n):\n    return n + 3\n")
    out = mod.find_duplicate_blocks([a, b], min_lines=10, root=tmp_path)
    assert out["duplicate_block_groups"] == 0


def test_evaluate_ok_on_scripts_subset():
    mod = _load()
    # Narrow path keeps CI fast and avoids flagging entire historical corpus
    out = mod.evaluate(
        root=ROOT,
        paths=["scripts/sdd_targeting.py", "scripts/dup_health.py"],
        min_lines=12,
        max_blocks_per_million=5000.0,
    )
    assert out["framework"] == "dup_health"
    assert "TNS" in out["stolen_format"] or "GitClear" in out["stolen_format"]
    assert "duplication" in out
    assert out["practices"]["prefer"].startswith("extract")


def test_breach_when_threshold_zero(tmp_path: Path):
    mod = _load()
    block = "\n".join([f"    y = {i}" for i in range(15)])
    a = tmp_path / "c1.py"
    b = tmp_path / "c2.py"
    a.write_text(f"def c1():\n{block}\n")
    b.write_text(f"def c2():\n{block}\n")
    out = mod.evaluate(
        root=tmp_path,
        paths=[str(a), str(b)],
        min_lines=10,
        max_blocks_per_million=0.0,
    )
    assert out["ok"] is False
    assert any(b["metric"] == "blocks_per_million" for b in out["breaches"])


def test_cli_json():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "dup_health.py"),
            "--path",
            "scripts/sdd_targeting.py",
            "--path",
            "scripts/dup_health.py",
            "--min-lines",
            "12",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "dup_health"
    assert data["duplication"]["files_scanned"] >= 1


def test_ralph_dup_health_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--dup-health",
            "--path",
            "scripts/sdd_targeting.py",
            "--min-lines",
            "12",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tick"] == "dup_health"
    assert data["framework"] == "dup_health"

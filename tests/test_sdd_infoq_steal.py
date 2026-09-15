"""Tests for InfoQ Spec-Driven Development FORMAT steal (targeting + attribution)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str):
    path = ROOT / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_governance_doc_has_control_points_and_raci():
    text = (ROOT / "docs" / "SPEC_GOVERNANCE.md").read_text()
    assert "When Spec-Driven Development Pays off" in text
    assert "attribution" in text.lower()
    assert "Responsible" in text
    assert "Accountable" in text
    for phrase in ("Spec authoring", "Drift detection", "Reconciliation"):
        assert phrase in text


def test_spec_named_invariants_table():
    text = (ROOT / "docs" / "SPEC.md").read_text()
    for iid in (
        "INV_cash_grade_honesty",
        "INV_cash_ship_lock",
        "INV_live_blocked",
        "INV_no_autosend",
        "INV_dial_path",
        "INV_ic_killed",
        "INV_sdd_targeting",
        "INV_attribution",
    ):
        assert iid in text


def test_targeting_full_for_cash_multi_constraint():
    mod = _load("sdd_targeting")
    out = mod.target(task="cash fee-yes grade honesty", multi_constraint=True)
    assert out["tier"] == "full"
    assert "guided_gen" in out["control_points_required"]
    assert out["ok"] is True


def test_targeting_skip_throwaway():
    mod = _load("sdd_targeting")
    out = mod.target(task="fix a typo", throwaway=True)
    assert out["tier"] == "skip"
    assert out["control_points_required"] == []


def test_targeting_skip_one_shot():
    mod = _load("sdd_targeting")
    out = mod.target(task="rename local var", one_shot_reliable=True)
    assert out["tier"] == "skip"


def test_targeting_quick_medium():
    mod = _load("sdd_targeting")
    out = mod.target(task="refresh docs README blurb")
    assert out["tier"] == "quick"
    assert out["control_points_required"] == ["author", "verify"]


def test_parse_invariants_from_spec():
    mod = _load("spec_drift_review")
    invs = mod.parse_invariants((ROOT / "docs" / "SPEC.md").read_text())
    ids = {i["id"] for i in invs}
    assert "INV_cash_grade_honesty" in ids
    assert "INV_attribution" in ids
    assert len(invs) >= 8


def test_attribution_on_cash_grade_drift():
    mod = _load("spec_drift_review")
    inv = {
        "id": "INV_cash_grade_honesty",
        "invariant": "Overall letter must not be A while cash unmet",
        "probe": "scorecard",
    }
    finding = mod.check_invariant(
        inv,
        {"overall": {"letter": "A+"}, "cash_fee_yes": {"ok": False}},
        {},
    )
    assert finding is not None
    assert finding["invariant_id"] == "INV_cash_grade_honesty"
    assert "attribution" in finding


def test_no_drift_when_honest_f_grade():
    mod = _load("spec_drift_review")
    inv = {
        "id": "INV_cash_grade_honesty",
        "invariant": "Overall letter must not be A while cash unmet",
        "probe": "scorecard",
    }
    finding = mod.check_invariant(
        inv,
        {"overall": {"letter": "F"}, "cash_fee_yes": {"ok": False}},
        {},
    )
    assert finding is None


def test_sdd_targeting_cli():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sdd_targeting.py"),
            "--task",
            "risk kill switch",
            "--regulated",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tier"] == "full"
    assert data["framework"] == "sdd_targeting"


def test_spec_drift_cli_json():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "spec_drift_review.py"),
            "--no-log",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "spec_drift_review"
    assert "InfoQ" in data["stolen_format"]
    assert data["invariants_checked"] >= 8
    assert data["attribution_rate"] is not None
    assert data["raci"]["human_accountable"].startswith("reconcile")


def test_ralph_sdd_target_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--sdd-target",
            "--task",
            "cash fee-yes",
            "--multi-constraint",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tick"] == "sdd_target"
    assert data["tier"] == "full"


def test_ralph_spec_drift_flag():
    r = subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "ralph_gsd_tick.py"),
            "--spec-drift",
            "--no-log",
        ],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["tick"] == "spec_drift"
    assert data["framework"] == "spec_drift_review"

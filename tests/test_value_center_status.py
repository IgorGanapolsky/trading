"""Tests for InfoQ value-center five-questions FORMAT steal."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _load():
    path = ROOT / "scripts" / "value_center_status.py"
    spec = importlib.util.spec_from_file_location("value_center_status", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_doc_exists_with_five_questions():
    text = (ROOT / "docs" / "VALUE_CENTER.md").read_text()
    assert "What value am I delivering" in text
    assert "How do we coordinate" in text
    assert "How do we fit together" in text
    assert "What's out there for us" in text or "Whats out there" in text
    assert "Who are we" in text
    assert "coherence" in text.lower()


def test_false_commercial_value_is_gap():
    mod = _load()
    out = mod.build_value_center(
        {"overall": {"letter": "A+"}, "cash_fee_yes": {"ok": False}},
        [],
        {"fee_yes_count": 0, "live_cash_usd": 0},
    )
    assert out["agency_coherence"]["coherent"] is False
    assert any(g["id"] == "false_commercial_value" for g in out["agency_coherence"]["gaps"])
    assert out["residual"] == "cash_fee_yes"


def test_coherent_when_cash_ok():
    mod = _load()
    out = mod.build_value_center(
        {"overall": {"letter": "B"}, "cash_fee_yes": {"ok": True}},
        [],
        {"fee_yes_count": 1, "live_cash_usd": 100},
    )
    assert out["agency_coherence"]["coherent"] is True
    assert out["residual"] == "maintain"
    assert out["purpose_is_what_we_do"]["cleared_non_owner_cash"] is True


def test_cleared_cash_requires_cash_ok_gate():
    mod = _load()
    out = mod.build_value_center(
        {"overall": {"letter": "C"}, "cash_fee_yes": {"ok": False}},
        [{"number": 1, "title": "x", "mergeStateStatus": "CLEAN"}],
        {"fee_yes_count": 2, "live_cash_usd": 250},
    )
    purpose = out["purpose_is_what_we_do"]
    assert purpose["cleared_non_owner_cash"] is False
    assert purpose["raw_live_cash_usd"] == 250
    assert purpose["raw_fee_yes_count"] == 2
    assert out["residual"] == "cash_fee_yes"


def test_evidence_unavailable_is_coherence_gap():
    mod = _load()
    out = mod.build_value_center(
        {"error": "scorecard_missing"},
        {"error": "timeout"},
        {"fee_yes_count": 0, "live_cash_usd": 0},
    )
    gaps = out["agency_coherence"]["gaps"]
    assert out["agency_coherence"]["coherent"] is False
    assert any(g["id"] == "evidence_unavailable" for g in gaps)
    assert sum(1 for g in gaps if g["id"] == "evidence_unavailable") >= 2


def test_questions_present():
    mod = _load()
    out = mod.build_value_center({}, [], {})
    for key in (
        "what_value_am_i_delivering",
        "how_do_we_coordinate",
        "how_do_we_fit_together",
        "whats_out_there_for_us",
        "who_are_we",
    ):
        assert key in out["questions"]
        assert "answer" in out["questions"][key]


def test_cli_json():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "value_center_status.py")],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        timeout=180,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["framework"] == "value_center"
    assert "InfoQ" in data["stolen_format"]
    assert data["agency_coherence"]["prefer"] == "coherence_over_pure_autonomy"

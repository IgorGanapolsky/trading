"""Tests for adaptive scan profile behavior in iron condor scanner."""

from __future__ import annotations

import json

from scripts.iron_condor_scanner import calculate_strikes, load_scan_profile


def test_load_scan_profile_defaults_to_baseline_when_state_missing(tmp_path):
    profile = load_scan_profile(tmp_path / "missing_state.json")
    assert profile["mode"] == "baseline"
    assert profile["allow_vix_override"] is False


def test_load_scan_profile_enables_adaptive_without_hard_blockers(tmp_path):
    state_path = tmp_path / "system_state.json"
    payload = {
        "north_star_weekly_gate": {
            "cadence_kpi": {
                "passed": False,
                "meets_qualified_setups": False,
            },
            "cadence_enforcement": {
                "adaptive_scan_required": True,
                "adaptive_scan_profile": {
                    "target_delta": 0.18,
                    "min_dte": 21,
                    "max_dte": 45,
                    "allow_vix_override": True,
                },
            },
            "no_trade_diagnostic": {"blocked_categories": ["liquidity"]},
        }
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    profile = load_scan_profile(state_path)
    assert profile["mode"] == "adaptive"
    assert profile["target_delta"] == 0.18
    assert profile["min_dte"] == 21
    assert profile["allow_vix_override"] is True


def test_load_scan_profile_stays_baseline_with_hard_blockers(tmp_path):
    state_path = tmp_path / "system_state.json"
    payload = {
        "north_star_weekly_gate": {
            "cadence_kpi": {
                "passed": False,
                "meets_qualified_setups": False,
            },
            "cadence_enforcement": {"adaptive_scan_required": True},
            "no_trade_diagnostic": {"blocked_categories": ["ai_credit_stress"]},
        }
    }
    state_path.write_text(json.dumps(payload), encoding="utf-8")

    profile = load_scan_profile(state_path)
    assert profile["mode"] == "baseline"


def test_calculate_strikes_tightens_with_higher_delta():
    price = 600.0
    baseline = calculate_strikes(price, target_delta=0.15)
    adaptive = calculate_strikes(price, target_delta=0.18)
    assert adaptive["short_put"] > baseline["short_put"]
    assert adaptive["short_call"] < baseline["short_call"]

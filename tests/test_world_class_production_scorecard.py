"""Smoke tests for world-class production scorecard."""

from __future__ import annotations

from scripts.world_class_production_scorecard import build_world_class_card, _grade


def test_grade_bands():
    assert _grade(9.5) == "A+"
    assert _grade(5.0) == "C"
    assert _grade(1.0) == "F"


def test_build_card_has_required_keys():
    card = build_world_class_card()
    assert card["schema_version"].startswith("world-class-production")
    assert card["goal"]["near_term_after_tax_monthly_usd"] == 1000.0
    assert "truth" in card
    assert "economics_for_1000_mo" in card
    assert "dimensions" in card
    assert len(card["dimensions"]) >= 6
    assert "priority_actions" in card
    # Must not claim profitable with insufficient sample under normal repo state
    assert "overall" in card
    assert "grade" in card["overall"]
    assert "process_ops_score_0_10" in card["overall"]
    assert "cash_engine_score_0_10" in card["overall"]
    # Dual-axis: process can be A+ while cash is not
    names = {d["name"] for d in card["dimensions"]}
    assert "live_capital_discipline" in names
    assert "cash_engine_output" in names
    assert "validation_factory_readiness" in names
    assert "sample_velocity" in names
    # Must not claim cash engine ready without EDGE
    if card["truth"].get("kill_verdict") != "EDGE_CANDIDATE":
        assert card["overall"]["cash_engine_score_0_10"] < 8.0
        assert card["truth"].get("claim_profitable") is False

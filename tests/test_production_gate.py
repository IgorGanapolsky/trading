"""Tests for production_gate control plane."""

from __future__ import annotations

from src.risk.production_gate import evaluate_production_gate, _grade


def test_grade_a_plus_threshold():
    assert _grade(9.6) == "A+"
    assert _grade(9.0) == "A"


def test_evaluate_returns_structure():
    result = evaluate_production_gate(
        require_fresh_state=False,
        require_clean_inventory=False,
        require_put_credit_active=True,
        for_live=False,
    )
    d = result.to_dict()
    assert "checks" in d
    assert "allow_new_risk" in d
    assert "allow_live_capital" in d
    assert d["grade"] in {"A+", "A", "A-", "B+", "B", "B-", "C", "C-", "D", "F"}
    # Live must not be allowed without EDGE + live_blocked false
    if d["allow_live_capital"]:
        assert any(c["id"] == "edge_cohort" for c in d["checks"])


def test_live_for_live_blocks_without_edge():
    result = evaluate_production_gate(for_live=True, require_fresh_state=False, require_clean_inventory=False)
    # With current repo state (insufficient sample), live must be false
    assert result.allow_live_capital is False

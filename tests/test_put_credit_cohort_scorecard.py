"""Unit tests for put-credit cohort scorecard (edge honesty)."""

from __future__ import annotations

from scripts.put_credit_cohort_scorecard import summarize_closed, summarize_open


def test_summarize_closed_insufficient_sample():
    rows = [
        {
            "strategy": "spy_put_credit",
            "status": "closed",
            "realized_pnl": 10.0,
        }
    ]
    out = summarize_closed(rows)
    assert out["closed_n"] == 1
    assert out["wins"] == 1
    assert out["kill_criteria"]["verdict"] == "INSUFFICIENT_SAMPLE"
    assert out["kill_criteria"]["sample_sufficient"] is False
    assert out["desk_grade"]["verdict"] == "INSUFFICIENT_DESK_GRADE_SAMPLE"
    assert out["expectancy_lower_95"] is None


def test_summarize_closed_ignores_iron_condor():
    rows = [
        {"strategy": "iron_condor", "status": "closed", "realized_pnl": -50.0},
        {"strategy": "spy_put_credit", "status": "closed", "realized_pnl": 12.0},
    ]
    out = summarize_closed(rows)
    assert out["closed_n"] == 1
    assert out["total_realized_pnl"] == 12.0


def test_summarize_closed_edge_candidate_at_n30():
    wins = [{"strategy": "spy_put_credit", "status": "closed", "realized_pnl": 20.0}] * 20
    losses = [{"strategy": "spy_put_credit", "status": "closed", "realized_pnl": -10.0}] * 10
    out = summarize_closed(wins + losses)
    assert out["closed_n"] == 30
    assert out["kill_criteria"]["sample_sufficient"] is True
    assert out["expectancy"] is not None and out["expectancy"] > 0
    assert out["profit_factor"] is not None and out["profit_factor"] > 1
    assert out["kill_criteria"]["verdict"] == "EDGE_CANDIDATE"
    assert out["desk_grade"]["verdict"] == "INSUFFICIENT_DESK_GRADE_SAMPLE"


def test_summarize_closed_requires_confident_edge_for_desk_grade():
    wins = [{"strategy": "spy_put_credit", "status": "closed", "realized_pnl": 40.0}] * 95
    losses = [{"strategy": "spy_put_credit", "status": "closed", "realized_pnl": -100.0}] * 5
    out = summarize_closed(wins + losses)
    assert out["closed_n"] == 100
    assert out["expectancy_lower_95"] is not None and out["expectancy_lower_95"] > 0
    assert out["profit_factor"] >= 1.2
    assert out["desk_grade"]["verdict"] == "DESK_GRADE_CANDIDATE"


def test_summarize_open_skips_closed():
    entries = {
        "PCS_open": {"status": "open", "expiry": "2026-08-28", "credit": 0.5},
        "PCS_done": {"status": "closed", "expiry": "2026-08-21", "credit": 0.4},
    }
    out = summarize_open(entries)
    assert out["open_n"] == 1
    assert out["entries"][0]["key"] == "PCS_open"

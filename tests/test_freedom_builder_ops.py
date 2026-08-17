"""Tests for Freedom Builder welcome-pack ops (process only)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.analytics.freedom_builder_ops import (
    build_full_ops_report,
    monthly_income_report,
    portfolio_transparency,
    render_start_here_markdown,
    render_wednesday_markdown,
    scenario_10k,
    score_plan,
    start_here_pack,
    wednesday_free_issue,
)


def _scorecard(**overrides):
    base = {
        "paper_only": True,
        "live_blocked": True,
        "open": {
            "open_n": 1,
            "entries": [
                {
                    "key": "PCS_test",
                    "signature": "SPY_2026-09-25_P737-742",
                    "expiry": "2026-09-25",
                    "credit": 0.65,
                    "quantity": 1,
                    "entry_time": "2026-08-11T15:23:00+00:00",
                    "regime": {"vix": 15.3},
                }
            ],
        },
        "closed": {
            "closed_n": 2,
            "expectancy": 28.0,
            "profit_factor": None,
            "total_realized_pnl": 56.0,
            "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE", "pass_all": None},
        },
        "progress": {"pct_to_gate": 6.7, "remaining_to_gate": 28},
        "honesty": {"claim_profitable": False, "note": "test"},
        "research_protocol": {"n_closed": 2, "critic": {"pass": True}},
    }
    base.update(overrides)
    return base


def test_plan_scores_high_on_clean_lab():
    out = score_plan(scorecard=_scorecard(), inventory_clean=True)
    assert out["max_score"] == 100
    assert out["total_score"] >= 90
    assert out["band"] in {"strong", "good"}
    assert out["not_etf_scoring"] is True
    assert out["honesty"]["not_stock_picks"] is True
    letters = {d["letter"] for d in out["dimensions"]}
    assert letters == {"P", "L", "A", "N"}


def test_plan_penalizes_multi_lot_and_claim():
    card = _scorecard(
        honesty={"claim_profitable": True},
        open={
            "open_n": 1,
            "entries": [{"quantity": 5, "credit": 0.5, "signature": "X"}],
        },
    )
    # force no edge
    card["closed"]["kill_criteria"] = {"verdict": "INSUFFICIENT_SAMPLE"}
    out = score_plan(scorecard=card, inventory_clean=False)
    assert out["total_score"] < 90
    limits = next(d for d in out["dimensions"] if d["letter"] == "L")
    assert limits["checks"]["one_lot_only"] is False
    numbers = next(d for d in out["dimensions"] if d["letter"] == "N")
    assert numbers["checks"]["claim_profitable_false_until_edge"] is False


def test_scenario_10k_buckets_and_lab_capacity():
    out = scenario_10k(stake=10_000)
    assert out["stake"] == 10_000
    total = sum(b["allocated"] for b in out["three_buckets"]["buckets"])
    assert total == pytest.approx(10_000)
    assert out["lab"]["allocated"] == 3500.0
    assert out["lab"]["structures_risk_capacity_if_fully_deployed"] == 7  # 3500/500
    assert out["lab"]["concurrent_if_funded"] == 2
    assert "Does not authorize live trading" in out["what_this_does_not_mean"][1]


def test_scenario_rejects_nonpositive():
    with pytest.raises(ValueError):
        scenario_10k(stake=0)


def test_portfolio_transparency_computes_credit_math():
    out = portfolio_transparency(_scorecard(), paper_equity=30_000.0)
    assert out["open_n"] == 1
    pos = out["positions"][0]
    assert pos["max_profit_if_expire_worthless_usd"] == 65.0
    assert pos["max_loss_if_max_width_planning_usd"] == 435.0
    assert pos["yield_claim"] is None
    assert out["honesty"]["not_dividend_report"] is True


def test_monthly_income_exact_cents():
    rows = [
        {"id": "a", "exit_date": "2026-08-05", "realized_pnl": 28.0},
        {"id": "b", "exit_time": "2026-08-10T12:00:00+00:00", "realized_pnl": 28.01},
        {"id": "c", "exit_date": "2026-07-01", "realized_pnl": 99.0},  # other month
    ]
    out = monthly_income_report(rows, year=2026, month=8, now=datetime(2026, 8, 17, tzinfo=UTC))
    assert out["n_closed"] == 2
    assert out["total_realized_pnl_cents"] == 2800 + 2801  # 28.00 + 28.01
    assert out["total_realized_pnl"] == 56.01
    assert out["honesty"]["no_marketing_rounding"] is True
    assert out["period"]["label"] == "2026-08"


def test_start_here_ordered():
    pack = start_here_pack()
    orders = [s["order"] for s in pack["steps"]]
    assert orders == sorted(orders)
    assert pack["steps"][0]["id"] == "three_bucket"
    md = render_start_here_markdown(pack)
    assert "3-Bucket" in md or "three" in md.lower() or "Bucket" in md


def test_wednesday_issue_complete():
    issue = wednesday_free_issue(
        _scorecard(),
        paper_equity=30_000,
        closed_rows=[
            {"id": "a", "exit_date": "2026-08-05", "realized_pnl": 28.0},
        ],
        now=datetime(2026, 8, 17, tzinfo=UTC),
    )
    assert issue["complete_on_its_own"] is True
    assert issue["frameworks"]["plan"]["total_score"] >= 0
    assert "working" in issue["honest_market_take"]
    md = render_wednesday_markdown(issue)
    assert "PLAN" in md
    assert "Portfolio" in md


def test_full_report_bundle():
    r = build_full_ops_report(_scorecard(), paper_equity=30_000.0, stake=10_000)
    assert r["schema_version"] == "freedom-builder-ops/1"
    assert "start_here" in r and "plan" in r and "wednesday_issue" in r
    assert r["honesty"]["not_stock_picks"] is True

"""Tests for EYL-style earned milestones + weekly accountability."""

from __future__ import annotations

import json
from pathlib import Path

from src.analytics.put_credit_milestones import (
    build_weekly_accountability_packet,
    evaluate_milestones,
    render_weekly_markdown,
)


def test_milestones_none_at_zero():
    out = evaluate_milestones({"closed_n": 0, "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"}})
    assert out["highest_earned"] == "None"
    assert out["earned_count"] == 0
    assert all(not m["earned"] for m in out["milestones"])


def test_milestones_foundation_and_process():
    out = evaluate_milestones({"closed_n": 12, "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"}})
    earned_ids = {m["id"] for m in out["milestones"] if m["earned"]}
    assert "m0_started" in earned_ids
    assert "m1_process_ten" in earned_ids
    assert "m2_evidence_thirty" not in earned_ids
    assert out["highest_earned"] == "Process"


def test_edge_candidate_requires_verdict():
    base = {"closed_n": 35, "kill_criteria": {"verdict": "NO_EDGE_KILL", "pass_all": False}}
    out = evaluate_milestones(base)
    edge = next(m for m in out["milestones"] if m["id"] == "m3_edge_candidate")
    assert edge["earned"] is False
    assert out["highest_earned"] == "Evidence"

    good = evaluate_milestones(
        {"closed_n": 35, "kill_criteria": {"verdict": "EDGE_CANDIDATE", "pass_all": True}}
    )
    edge2 = next(m for m in good["milestones"] if m["id"] == "m3_edge_candidate")
    assert edge2["earned"] is True
    assert good["highest_earned"] == "Edge Candidate"


def test_weekly_packet_and_markdown():
    scorecard = {
        "active_family": "spy_put_credit",
        "paper_only": True,
        "live_blocked": True,
        "open": {"open_n": 2},
        "closed": {
            "closed_n": 2,
            "win_rate_pct": 100.0,
            "profit_factor": None,
            "expectancy": 17.0,
            "total_realized_pnl": 34.0,
            "kill_criteria": {"verdict": "INSUFFICIENT_SAMPLE"},
        },
        "progress": {"pct_to_gate": 6.7, "remaining_to_gate": 28},
        "honesty": {"note": "do not claim"},
        "research_protocol": {
            "n_closed": 2,
            "split_sizes": {"development": 1, "validation": 1, "holdout": 0},
            "critic": {"pass": True},
            "langchain_adopted": False,
        },
    }
    packet = build_weekly_accountability_packet(scorecard)
    assert packet["not_a_signal_service"] is True
    assert packet["milestones"]["highest_earned"] == "Foundation"
    assert packet["metrics"]["closed_n"] == 2
    md = render_weekly_markdown(packet)
    assert "weekly accountability" in md.lower()
    assert "Foundation" in md
    assert "not a signal service" in md.lower()


def test_scorecard_embeds_milestones(tmp_path: Path):
    from scripts import put_credit_cohort_scorecard as sc

    trades = tmp_path / "trades.json"
    trades.write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "strategy": "spy_put_credit",
                        "status": "closed",
                        "exit_time": "2026-07-10T15:00:00+00:00",
                        "realized_pnl": 17.0,
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "e.json").write_text("{}", encoding="utf-8")
    (tmp_path / "k.json").write_text(
        json.dumps({"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True}),
        encoding="utf-8",
    )
    card = sc.build_scorecard(
        trades_path=trades,
        entries_path=tmp_path / "e.json",
        kill_path=tmp_path / "k.json",
    )
    assert card["schema_version"] == "put-credit-cohort-scorecard/3"
    assert "milestones" in card
    assert card["milestones"]["highest_earned"] == "Foundation"
    assert card["milestones"]["risk_framework"]["not_a_signal_service"] is True

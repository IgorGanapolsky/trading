"""Unit tests for put-credit cohort scorecard (edge honesty)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.put_credit_cohort_scorecard import (
    build_scorecard,
    summarize_closed,
    summarize_open,
)


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


def test_summarize_open_skips_closed():
    entries = {
        "PCS_open": {"status": "open", "expiry": "2026-08-28", "credit": 0.5},
        "PCS_done": {"status": "closed", "expiry": "2026-08-21", "credit": 0.4},
    }
    out = summarize_open(entries)
    assert out["open_n"] == 1
    assert out["entries"][0]["key"] == "PCS_open"


def test_scorecard_sources_count_trades_key_not_closed_trades(tmp_path: Path) -> None:
    """AGENT-661: trades.json uses trades[], summarize_closed returns closed_n."""
    trades_path = tmp_path / "trades.json"
    trades_path.write_text(
        json.dumps(
            {
                "trades": [
                    {
                        "strategy": "spy_put_credit",
                        "status": "closed",
                        "exit_time": "2026-07-10T15:00:00+00:00",
                        "realized_pnl": 17.0,
                    },
                    {
                        "strategy": "spy_put_credit",
                        "status": "closed",
                        "exit_time": "2026-07-17T15:00:00+00:00",
                        "realized_pnl": 39.0,
                    },
                    {
                        "strategy": "iron_condor",
                        "status": "closed",
                        "exit_time": "2026-06-01T15:00:00+00:00",
                        "realized_pnl": -50.0,
                    },
                ]
            }
        ),
        encoding="utf-8",
    )
    entries_path = tmp_path / "entries.json"
    entries_path.write_text("{}", encoding="utf-8")
    kill_path = tmp_path / "kill.json"
    kill_path.write_text(
        json.dumps({"active_family": "spy_put_credit", "paper_only": True, "live_blocked": True}),
        encoding="utf-8",
    )
    card = build_scorecard(trades_path=trades_path, entries_path=entries_path, kill_path=kill_path)
    assert card["closed"]["sources"]["trades_json"] == 2
    assert card["closed"]["sources"]["entries_json"] == 0
    assert card["closed"]["closed_n"] == 2

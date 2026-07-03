"""Tests for scripts/deep_research_ml_rag.py."""

from __future__ import annotations

from pathlib import Path

from scripts import deep_research_ml_rag as deep


def test_validation_snapshot_flags_protocol_and_negative_expectancy():
    entries = {
        "IC_260515": {
            "date": "2026-04-10T15:29:45",
            "validation_phase": True,
            "selection_method": "live_delta",
            "profile_name": "spy-core",
            "quantity": 1,
        },
        "IC_260731": {
            "date": "2026-06-24T15:52:54+00:00",
            "selection_method": "unknown",
            "profile_name": "unknown",
            "quantity": 1,
            "backfilled": "reconstructed",
        },
    }
    trades = {
        "trades": [
            {"entry_date": "2026-04-10", "realized_pnl": -126},
            {"entry_date": "2026-04-15", "realized_pnl": 100},
        ]
    }

    result = deep.validation_snapshot(entries, trades)

    assert result["entries"] == 2
    assert result["closed_trades"] == 2
    assert result["remaining_for_30_trade_gate"] == 28
    assert result["expectancy_per_trade"] == -13.0
    assert result["profit_factor"] == 0.7937
    assert len(result["protocol_violations"]) == 3


def test_model_drift_snapshot_recommends_empirical_priors():
    model = {"iron_condor": {"alpha": 86, "beta": 15}}
    stats = {"wins": 30, "losses": 148, "win_rate_pct": 16.76}

    result = deep.model_drift_snapshot(model, stats)

    assert result["model_expected_win_rate_pct"] == 85.15
    assert result["realized_win_rate_pct"] == 16.76
    assert result["drift_alert"] is True
    assert result["empirical_alpha"] == 31
    assert result["empirical_beta"] == 149


def test_latest_reconciliation_snapshot_uses_newest_report(tmp_path: Path):
    older = tmp_path / "reconciliation_2026-07-01.json"
    newer = tmp_path / "reconciliation_2026-07-02.json"
    older.write_text('{"date":"2026-07-01","alert_fired":false,"delta_dollars":0}')
    newer.write_text(
        '{"date":"2026-07-02","alert_fired":true,'
        '"broker_realized_pnl":4587,"paired_realized_pnl":-3931,'
        '"delta_dollars":8518,"threshold_dollars":150}'
    )

    result = deep.latest_reconciliation_snapshot(tmp_path)

    assert result["status"] == "ok"
    assert result["date"] == "2026-07-02"
    assert result["alert_fired"] is True
    assert result["delta_dollars"] == 8518


def test_render_markdown_contains_decision_and_references():
    packet = {
        "date": "2026-07-03",
        "decision": "BLOCKED",
        "profit_claim": "No profit claim.",
        "blockers": ["negative expectancy"],
        "ledger": {
            "closed_trades": 179,
            "wins": 30,
            "losses": 148,
            "win_rate_pct": 16.76,
            "profit_factor": 0.7,
            "expectancy_per_trade": -32.21,
            "total_realized_pnl": -5766,
        },
        "validation": {
            "entries": 3,
            "closed_trades": 3,
            "expectancy_per_trade": -63,
            "profit_factor": 0.35,
            "protocol_violations": ["method unknown"],
        },
        "model_drift": {
            "model_expected_win_rate_pct": 85.15,
            "realized_win_rate_pct": 16.76,
            "drift_pct": 68.39,
            "empirical_alpha": 31,
            "empirical_beta": 149,
        },
        "reconciliation": {
            "path": "data/reports/reconciliation_2026-07-02.json",
            "alert_fired": True,
            "delta_dollars": 8518,
            "threshold_dollars": 150,
        },
        "loss_clusters": [
            {
                "id": "ten_wide_wings",
                "sample_size": 162,
                "total_pnl": -7974,
                "expectancy_per_trade": -49.22,
            }
        ],
        "rag": {
            "query": "negative expectancy",
            "lesson_count": 285,
            "matches": [{"id": "lesson", "score": 0.5, "severity": "high"}],
        },
        "next_hypotheses": [
            {"id": "regime_filtered_ic", "status": "research_only", "test": "Backtest regimes"}
        ],
        "research_references": deep.RESEARCH_REFERENCES[:1],
    }

    markdown = deep.render_markdown(packet)

    assert "`BLOCKED`" in markdown
    assert "negative expectancy" in markdown
    assert "Cboe" in markdown
    assert "regime_filtered_ic" in markdown

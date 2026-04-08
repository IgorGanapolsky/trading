from __future__ import annotations

import json
from pathlib import Path

from src.analytics.trade_setup_audit import (
    build_trade_setup_audit,
    render_trade_setup_audit_markdown,
    write_trade_setup_audit_artifacts,
)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_build_trade_setup_audit_collapses_partial_exits_and_tracks_reentry(tmp_path: Path) -> None:
    repo = tmp_path
    _write_json(
        repo / "data" / "trades.json",
        {
            "meta": {"last_sync": "2026-04-08T17:00:00Z"},
            "stats": {"closed_trades": 4, "last_updated": "2026-04-08T17:00:00Z"},
            "trades": [
                {
                    "id": "a-1",
                    "status": "closed",
                    "entry_date": "2026-04-01",
                    "exit_date": "2026-04-01",
                    "entry_time": "2026-04-01T14:00:00+00:00",
                    "exit_time": "2026-04-01T14:30:00+00:00",
                    "entry_credit": 300.0,
                    "exit_debit": 380.0,
                    "realized_pnl": -80.0,
                    "outcome": "loss",
                    "quantity": 2.0,
                    "signature": "SPY_2026-05-08_P610-620_C710-720",
                    "legs": {
                        "underlying": "SPY",
                        "expiry": "2026-05-08",
                        "put_strikes": [610.0, 620.0],
                        "call_strikes": [710.0, 720.0],
                    },
                    "source": "alpaca_parent_lot->alpaca_close_inventory",
                },
                {
                    "id": "a-2",
                    "status": "closed",
                    "entry_date": "2026-04-01",
                    "exit_date": "2026-04-02",
                    "entry_time": "2026-04-01T14:00:00+00:00",
                    "exit_time": "2026-04-02T14:00:00+00:00",
                    "entry_credit": 300.0,
                    "exit_debit": 0.0,
                    "realized_pnl": 20.0,
                    "outcome": "win",
                    "quantity": None,
                    "signature": "SPY_2026-05-08_P610-620_C710-720",
                    "legs": {
                        "underlying": "SPY",
                        "expiry": "2026-05-08",
                        "put_strikes": [610.0, 620.0],
                        "call_strikes": [710.0, 720.0],
                    },
                    "source": "alpaca_parent_lot->alpaca_close_inventory",
                },
                {
                    "id": "b-1",
                    "status": "closed",
                    "entry_date": "2026-04-02",
                    "exit_date": "2026-04-05",
                    "entry_time": "2026-04-02T15:00:00+00:00",
                    "exit_time": "2026-04-05T15:00:00+00:00",
                    "entry_credit": 200.0,
                    "exit_debit": 150.0,
                    "realized_pnl": 50.0,
                    "outcome": "win",
                    "quantity": 1.0,
                    "signature": "SPY_2026-05-15_P615-625_C715-725",
                    "legs": {
                        "underlying": "SPY",
                        "expiry": "2026-05-15",
                        "put_strikes": [615.0, 625.0],
                        "call_strikes": [715.0, 725.0],
                    },
                    "source": "alpaca_parent->alpaca_leg_cluster",
                },
                {
                    "id": "c-1",
                    "status": "closed",
                    "entry_date": "2026-04-02",
                    "exit_date": "2026-04-02",
                    "entry_time": "2026-04-02T17:00:00+00:00",
                    "exit_time": "2026-04-02T17:20:00+00:00",
                    "entry_credit": 180.0,
                    "exit_debit": 210.0,
                    "realized_pnl": -30.0,
                    "outcome": "loss",
                    "quantity": 1.0,
                    "signature": "SPY_2026-05-15_P615-625_C715-725",
                    "legs": {
                        "underlying": "SPY",
                        "expiry": "2026-05-15",
                        "put_strikes": [615.0, 625.0],
                        "call_strikes": [715.0, 725.0],
                    },
                    "source": "alpaca_parent->alpaca_leg_cluster",
                },
            ],
        },
    )
    (repo / "data" / "feedback").mkdir(parents=True, exist_ok=True)
    (repo / "data" / "feedback" / "trade_trajectories.jsonl").write_text(
        json.dumps(
            {
                "event_type": "outcome",
                "strategy": "iron_condor",
                "metadata": {"selection_method": "live_delta", "put_delta": -0.15},
            }
        )
        + "\n",
        encoding="utf-8",
    )

    audit = build_trade_setup_audit(repo)

    assert audit["available"] is True
    assert audit["row_level"]["closed_rows"] == 4
    assert audit["setup_level"]["distinct_setups"] == 3
    assert audit["setup_level"]["partial_exit_groups"] == 1
    assert audit["setup_level"]["partial_exit_extra_rows"] == 1
    assert audit["setup_level"]["wins"] == 1
    assert audit["setup_level"]["losses"] == 2
    assert audit["setup_level"]["win_rate_pct"] == 33.33
    assert audit["setup_level"]["total_pnl"] == -40.0

    hold_buckets = {row["bucket"]: row for row in audit["hold_time_breakdown"]}
    assert hold_buckets["<1h"]["setups"] == 1
    assert hold_buckets["1-3d"]["setups"] == 1
    assert hold_buckets[">3d"]["setups"] == 1

    qty_buckets = {row["bucket"]: row for row in audit["quantity_breakdown"]}
    assert qty_buckets["1"]["setups"] == 2
    assert qty_buckets["2"]["setups"] == 1
    assert qty_buckets["2"]["total_pnl"] == -60.0

    assert audit["same_day_signature_clusters"][0]["entry_date"] == "2026-04-02"
    assert audit["same_day_signature_clusters"][0]["setups"] == 2
    assert audit["same_day_signature_clusters"][0]["total_pnl"] == 20.0

    assert audit["duplicate_setup_groups"][0]["rows"] == 2
    assert audit["duplicate_setup_groups"][0]["total_pnl"] == -60.0

    assert audit["delta_provenance"]["trajectory_outcome_events"] == 1
    assert audit["delta_provenance"]["trajectory_events_with_actual_delta"] == 1
    assert audit["delta_provenance"]["trajectory_events_with_selection_method"] == 1
    assert audit["delta_provenance"]["coverage_available"] is True


def test_write_trade_setup_audit_artifacts_writes_json_and_markdown(tmp_path: Path) -> None:
    repo = tmp_path
    _write_json(
        repo / "data" / "trades.json",
        {
            "meta": {"last_sync": "2026-04-08T17:00:00Z"},
            "stats": {"closed_trades": 1, "last_updated": "2026-04-08T17:00:00Z"},
            "trades": [
                {
                    "id": "only",
                    "status": "closed",
                    "entry_date": "2026-04-01",
                    "exit_date": "2026-04-01",
                    "entry_time": "2026-04-01T14:00:00+00:00",
                    "exit_time": "2026-04-01T14:30:00+00:00",
                    "entry_credit": 250.0,
                    "exit_debit": 210.0,
                    "realized_pnl": 40.0,
                    "outcome": "win",
                    "quantity": 1.0,
                    "signature": "SPY_2026-05-08_P610-620_C710-720",
                    "legs": {
                        "underlying": "SPY",
                        "expiry": "2026-05-08",
                        "put_strikes": [610.0, 620.0],
                        "call_strikes": [710.0, 720.0],
                    },
                    "source": "alpaca_parent->alpaca_leg_cluster",
                }
            ],
        },
    )

    json_out = repo / "artifacts" / "trade_setup_audit" / "latest.json"
    markdown_out = repo / "artifacts" / "trade_setup_audit" / "latest.md"

    audit = write_trade_setup_audit_artifacts(
        repo,
        json_out=json_out,
        markdown_out=markdown_out,
    )

    assert audit["available"] is True
    assert json.loads(json_out.read_text(encoding="utf-8"))["setup_level"]["distinct_setups"] == 1

    markdown = markdown_out.read_text(encoding="utf-8")
    assert "# Trade Setup Audit" in markdown
    assert "## Summary" in markdown
    assert "## Delta Provenance" in markdown
    assert render_trade_setup_audit_markdown(audit) == markdown

"""Tests for the autonomous SQLite analytics builder."""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from pathlib import Path

from src.analytics.sqlite_analytics import build_analytics_artifacts


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def test_build_analytics_artifacts_creates_views_and_summary(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "data" / "performance_log.json",
        [
            {
                "date": "2026-03-11",
                "timestamp": "2026-03-11T21:00:00Z",
                "equity": 101000.0,
                "cash": 99000.0,
                "buying_power": 198000.0,
                "account_type": "PAPER",
            },
            {
                "date": "2026-03-12",
                "timestamp": "2026-03-12T21:00:00Z",
                "equity": 101160.0,
                "cash": 99160.0,
                "buying_power": 198320.0,
                "account_type": "PAPER",
            },
        ],
    )
    _write_json(
        tmp_path / "data" / "verification_reports.json",
        [
            {
                "date": "2026-03-11",
                "traded": False,
                "orders": 0,
                "structures": 0,
                "fills": 0,
                "positions": 2,
                "equity": 101000.0,
                "last_equity": 101000.0,
                "daily_pnl": 0.0,
                "total_pnl": 1000.0,
            },
            {
                "date": "2026-03-13",
                "traded": True,
                "orders": 4,
                "structures": 1,
                "fills": 7,
                "positions": 3,
                "equity": 101200.0,
                "last_equity": 101000.0,
                "daily_pnl": 40.0,
                "total_pnl": 1200.0,
            },
        ],
    )
    _write_json(
        tmp_path / "data" / "system_state.json",
        {
            "last_updated": "2026-03-13T20:00:00+00:00",
            "paper_account": {
                "equity": 101200.0,
                "cash": 99200.0,
                "buying_power": 198400.0,
                "daily_change": 40.0,
                "total_pl": 1200.0,
                "last_equity": 101160.0,
                "positions_count": 3,
            },
            "north_star": {
                "monthly_after_tax_target": 6000.0,
                "probability_score": 49.7,
                "probability_label": "low",
                "monthly_target_progress_pct": 2.05,
                "estimated_monthly_after_tax_from_expectancy": 1234.56,
                "target_capital": 300000.0,
                "updated_at": "2026-03-13T20:00:00+00:00",
            },
            "north_star_weekly_gate": {
                "updated_at": "2026-03-13T20:00:00+00:00",
                "sample_size": 3,
                "win_rate_pct": 60.0,
                "expectancy_per_trade": -40.0,
                "mode": "validation",
                "cadence_kpi": {
                    "qualified_setups_observed": 1,
                    "passed": False,
                },
            },
        },
    )
    _write_json(
        tmp_path / "data" / "trades.json",
        {
            "meta": {"version": "2.0"},
            "stats": {"closed_trades": 2},
            "trades": [
                {
                    "id": "trade-1",
                    "symbol": "SPY",
                    "strategy": "iron_condor",
                    "status": "closed",
                    "entry_date": "2026-03-01",
                    "exit_date": "2026-03-06",
                    "realized_pnl": 41.0,
                    "outcome": "win",
                    "source": "alpaca",
                },
                {
                    "id": "trade-2",
                    "symbol": "SPY",
                    "strategy": "iron_condor",
                    "status": "closed",
                    "entry_date": "2026-03-08",
                    "exit_date": "2026-03-13",
                    "realized_pnl": -15.0,
                    "outcome": "loss",
                    "source": "alpaca",
                },
            ],
        },
    )
    _write_json(
        tmp_path / "data" / "north_star_weekly_history.json",
        [
            {
                "week_start": "2026-03-02",
                "updated_at": "2026-03-06T20:00:00+00:00",
                "sample_size": 2,
                "win_rate_pct": 50.0,
                "expectancy_per_trade": -55.0,
                "mode": "validation",
                "qualified_setups": 2,
                "cadence_passed": True,
            }
        ],
    )

    db_path = tmp_path / "artifacts" / "devloop" / "trading_analytics.sqlite"
    summary_json = tmp_path / "artifacts" / "devloop" / "sql_analytics_summary.json"
    summary_md = tmp_path / "artifacts" / "devloop" / "sql_analytics_summary.md"
    published_summary_json = tmp_path / "docs" / "data" / "sql_analytics_summary.json"
    rag_summary_md = tmp_path / "docs" / "_reports" / "sql-analytics-summary.md"

    summary = build_analytics_artifacts(
        tmp_path,
        db_path=db_path,
        summary_json_path=summary_json,
        summary_md_path=summary_md,
        published_summary_json_path=published_summary_json,
        rag_summary_md_path=rag_summary_md,
    )

    assert db_path.exists()
    assert summary_json.exists()
    assert summary_md.exists()
    assert published_summary_json.exists()
    assert rag_summary_md.exists()

    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        latest_account = conn.execute(
            "SELECT * FROM account_daily_pop ORDER BY snapshot_date DESC LIMIT 1"
        ).fetchone()
        assert latest_account is not None
        assert latest_account["snapshot_date"] == "2026-03-13"
        assert latest_account["prev_equity"] == 101160.0
        assert latest_account["equity_change_vs_prev_snapshot"] == 40.0
        assert latest_account["resolved_daily_pnl"] == 40.0
        assert latest_account["orders_today"] == 4

        latest_trade = conn.execute(
            "SELECT * FROM closed_trades_pop ORDER BY trade_date DESC LIMIT 1"
        ).fetchone()
        assert latest_trade is not None
        assert latest_trade["trade_date"] == "2026-03-13"
        assert latest_trade["realized_pnl"] == -15.0
        assert latest_trade["prev_realized_pnl"] == 41.0
        assert latest_trade["realized_pnl_delta"] == -56.0
        assert latest_trade["cumulative_realized_pnl"] == 26.0

        latest_north_star = conn.execute(
            "SELECT * FROM north_star_progress ORDER BY week_start DESC LIMIT 1"
        ).fetchone()
        assert latest_north_star is not None
        assert latest_north_star["week_start"] == "2026-03-09"
        assert latest_north_star["expectancy_per_trade"] == -40.0
        assert latest_north_star["prev_expectancy_per_trade"] == -55.0
        assert latest_north_star["expectancy_delta"] == 15.0
        assert latest_north_star["probability_label"] == "low"

    assert summary["account_daily_pop"]["snapshot_date"] == "2026-03-13"
    assert summary["closed_trade_pop"]["trade_date"] == "2026-03-13"
    assert summary["north_star_progress"]["week_start"] == "2026-03-09"
    assert "North Star weekly gate is blocked" in "\n".join(summary["highlights"])
    assert "SQL Analytics Summary" in summary_md.read_text(encoding="utf-8")
    assert (
        json.loads(published_summary_json.read_text(encoding="utf-8"))["account_daily_pop"][
            "snapshot_date"
        ]
        == "2026-03-13"
    )
    rag_text = rag_summary_md.read_text(encoding="utf-8")
    assert "Automated SQL Analytics Summary" in rag_text
    assert 'image: "/assets/snapshots/progress_latest.png"' in rag_text
    assert "How did today compare to the previous snapshot?" in rag_text
    assert "What changed week over week on the North Star?" in rag_text
    assert (
        "https://github.com/IgorGanapolsky/trading/blob/main/docs/data/sql_analytics_summary.json"
        in rag_text
    )


def test_build_sqlite_analytics_cli_bootstraps_repo_root(tmp_path: Path) -> None:
    _write_json(
        tmp_path / "data" / "performance_log.json",
        [
            {
                "date": "2026-03-11",
                "timestamp": "2026-03-11T21:00:00Z",
                "equity": 101000.0,
                "cash": 99000.0,
                "buying_power": 198000.0,
                "account_type": "PAPER",
            }
        ],
    )
    _write_json(
        tmp_path / "data" / "verification_reports.json",
        [
            {
                "date": "2026-03-11",
                "traded": False,
                "orders": 0,
                "structures": 0,
                "fills": 0,
                "positions": 0,
                "equity": 101000.0,
                "last_equity": 101000.0,
                "daily_pnl": 0.0,
                "total_pnl": 1000.0,
            }
        ],
    )
    _write_json(
        tmp_path / "data" / "system_state.json",
        {
            "last_updated": "2026-03-11T20:00:00+00:00",
            "paper_account": {
                "equity": 101000.0,
                "cash": 99000.0,
                "buying_power": 198000.0,
                "daily_change": 0.0,
                "total_pl": 1000.0,
                "last_equity": 101000.0,
                "positions_count": 0,
            },
            "north_star": {
                "monthly_after_tax_target": 6000.0,
                "probability_score": 50.0,
                "probability_label": "medium",
                "monthly_target_progress_pct": 10.0,
                "estimated_monthly_after_tax_from_expectancy": 1500.0,
                "target_capital": 300000.0,
                "updated_at": "2026-03-11T20:00:00+00:00",
            },
            "north_star_weekly_gate": {
                "updated_at": "2026-03-11T20:00:00+00:00",
                "sample_size": 1,
                "win_rate_pct": 100.0,
                "expectancy_per_trade": 40.0,
                "mode": "validation",
                "cadence_kpi": {
                    "qualified_setups_observed": 1,
                    "passed": True,
                },
            },
        },
    )
    _write_json(
        tmp_path / "data" / "trades.json",
        {"meta": {"version": "2.0"}, "stats": {"closed_trades": 0}, "trades": []},
    )
    _write_json(tmp_path / "data" / "north_star_weekly_history.json", [])

    db_path = tmp_path / "artifacts" / "devloop" / "trading_analytics.sqlite"
    summary_json = tmp_path / "artifacts" / "devloop" / "sql_analytics_summary.json"
    summary_md = tmp_path / "artifacts" / "devloop" / "sql_analytics_summary.md"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "build_sqlite_analytics.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script_path),
            "--repo-root",
            str(tmp_path),
            "--db-out",
            str(db_path),
            "--summary-json-out",
            str(summary_json),
            "--summary-md-out",
            str(summary_md),
        ],
        check=True,
        cwd=tmp_path,
        capture_output=True,
        text=True,
    )

    assert db_path.exists()
    assert summary_json.exists()
    assert summary_md.exists()
    assert "SQLite analytics DB written to:" in result.stdout

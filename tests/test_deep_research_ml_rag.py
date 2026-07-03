"""Tests for scripts/deep_research_ml_rag.py."""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

from scripts import deep_research_ml_rag as deep


def _sample_packet() -> dict:
    return {
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
        "market_research": {
            "source": "https://example.test/vix",
            "vix": {"vix": 18.0, "regime": "normal", "vix_trend": "falling"},
            "trade_implication": "Advisory only.",
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


def test_latest_reconciliation_snapshot_missing_report(tmp_path: Path):
    result = deep.latest_reconciliation_snapshot(tmp_path)

    assert result == {"status": "missing", "alert_fired": True}


def test_as_float_and_finite_helpers_handle_bad_values():
    assert deep.as_float("12.5") == 12.5
    assert deep.as_float(None, default=7.0) == 7.0
    assert deep.finite(float("inf")) == "inf"
    assert deep.finite(1.23456) == 1.2346


def test_render_markdown_contains_decision_and_references():
    packet = _sample_packet()

    markdown = deep.render_markdown(packet)

    assert "`BLOCKED`" in markdown
    assert "negative expectancy" in markdown
    assert "Cboe" in markdown
    assert "regime_filtered_ic" in markdown


def test_build_packet_combines_blockers_and_mocked_research(monkeypatch):
    trades_data = {
        "stats": {
            "closed_trades": 2,
            "wins": 1,
            "losses": 1,
            "win_rate_pct": 50.0,
            "profit_factor": 0.5,
            "expectancy_per_trade": -25,
            "total_realized_pnl": -50,
        },
        "trades": [
            {"entry_date": "2026-04-10", "realized_pnl": -100},
            {"entry_date": "2026-04-11", "realized_pnl": 50},
        ],
    }

    def fake_load_json(path: Path, default):
        if path.name == "ic_entries.json":
            return {
                "IC_260515": {
                    "date": "2026-04-10",
                    "selection_method": "snapshot",
                    "profile_name": "legacy",
                    "quantity": 2,
                }
            }
        if path.name == "trade_confidence_model.json":
            return {"iron_condor": {"alpha": 90, "beta": 10}}
        if path.name == "research_state.json":
            return {"regime": "mocked"}
        return default

    monkeypatch.setattr(deep.ml_update, "load_trades", lambda: trades_data)
    monkeypatch.setattr(
        deep.ml_update,
        "check_trading_gate",
        lambda stats: {"should_trade": False, "block_reason": "gate blocked"},
    )
    monkeypatch.setattr(
        deep.ml_update,
        "analyze_loss_clusters",
        lambda payload: [{"id": "cluster", "sample_size": 2, "total_pnl": -50, "expectancy_per_trade": -25}],
    )
    monkeypatch.setattr(deep, "load_json", fake_load_json)
    monkeypatch.setattr(
        deep,
        "latest_reconciliation_snapshot",
        lambda: {"status": "ok", "alert_fired": True, "delta_dollars": 2335},
    )
    monkeypatch.setattr(
        deep,
        "rag_snapshot",
        lambda query: {"query": query, "lesson_count": 1, "matches": []},
    )
    monkeypatch.setattr(
        deep,
        "market_research_snapshot",
        lambda: {"source": "mock", "vix": {"regime": "normal"}, "trade_implication": "mock"},
    )

    packet = deep.build_packet(today=date(2026, 7, 3))

    assert packet["decision"] == "BLOCKED"
    assert packet["ledger"]["closed_trades"] == 2
    assert packet["validation"]["protocol_violations"]
    assert packet["model_drift"]["drift_alert"] is True
    assert "gate blocked" in packet["blockers"]
    assert any("reconciliation breach" in item for item in packet["blockers"])


def test_write_outputs_supports_dry_run_and_real_files(tmp_path: Path, monkeypatch):
    packet = _sample_packet()
    reports = tmp_path / "reports"
    lessons = tmp_path / "lessons"
    monkeypatch.setattr(deep, "PROJECT_ROOT", tmp_path)
    monkeypatch.setattr(deep, "REPORT_DIR", reports)
    monkeypatch.setattr(deep, "LESSONS_DIR", lessons)

    dry_paths = deep.write_outputs(packet, dry_run=True)

    assert dry_paths["json"] == "reports/deep_research_ml_rag_2026-07-03.json"
    assert not reports.exists()
    assert not lessons.exists()

    paths = deep.write_outputs(packet, dry_run=False)

    json_path = tmp_path / paths["json"]
    markdown_path = tmp_path / paths["markdown"]
    lesson_path = tmp_path / paths["rag_lesson"]
    assert json.loads(json_path.read_text())["decision"] == "BLOCKED"
    assert "# Deep Research ML RAG Packet" in markdown_path.read_text()
    assert lesson_path.read_text() == markdown_path.read_text()


def test_main_returns_blocked_exit_code_and_prints_outputs(monkeypatch, capsys):
    packet = _sample_packet()
    monkeypatch.setattr(sys, "argv", ["deep_research_ml_rag.py", "--date", "2026-07-03", "--dry-run"])
    monkeypatch.setattr(deep, "build_packet", lambda today: packet)
    monkeypatch.setattr(
        deep,
        "write_outputs",
        lambda packet, dry_run=False: {"json": "packet.json", "markdown": "packet.md"},
    )

    exit_code = deep.main()

    assert exit_code == 2
    assert '"decision": "BLOCKED"' in capsys.readouterr().out

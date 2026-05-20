"""Tests for AlphaMetricsTracker — analytics layer after Thursday-bias retirement.

The prior schema had `thursday_gate_blocks` and `thursday_win_rate` baked in.
Both fields and the regime split that fed them were retired 2026-05-20 after
the May 19 edge audit disproved the Thursday hypothesis (Bonferroni adj_p=0.190).
"""

from __future__ import annotations

import json

import pytest

from src.analytics.alpha_metrics_tracker import AlphaMetricsTracker


@pytest.fixture()
def tracker(tmp_path):
    t = AlphaMetricsTracker(repo_root=tmp_path)
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    return t


class TestSchemaShape:
    def test_default_schema_has_no_thursday_fields(self, tracker):
        m = tracker.metrics
        defense = m["defense_alpha"]
        weekday = m["weekday_performance"]
        # No baked-in Thursday gate counter
        assert "thursday_gate_blocks" not in defense
        # Gate blocks is generic dict
        assert defense["gate_blocks"] == {}
        # All 5 weekdays present as equal columns
        assert set(weekday["win_rate"].keys()) == {"mon", "tue", "wed", "thu", "fri"}
        assert set(weekday["sample_size"].keys()) == {"mon", "tue", "wed", "thu", "fri"}
        # Old top-level keys not present
        assert "thursday_win_rate" not in weekday
        assert "monday_win_rate" not in weekday
        assert "other_days_win_rate" not in weekday


class TestRecordBlock:
    def test_record_block_increments_named_gate(self, tracker):
        tracker.record_block("dte", estimated_loss=100.0)
        tracker.record_block("dte", estimated_loss=50.0)
        tracker.record_block("vix")
        gb = tracker.metrics["defense_alpha"]["gate_blocks"]
        assert gb == {"dte": 2, "vix": 1}
        assert tracker.metrics["defense_alpha"]["blocked_trades_total"] == 3
        assert tracker.metrics["defense_alpha"]["estimated_loss_prevented"] == 150.0

    def test_record_block_persists(self, tracker):
        tracker.record_block("dte", estimated_loss=100.0)
        reloaded = AlphaMetricsTracker(repo_root=tracker.repo_root)
        assert reloaded.metrics["defense_alpha"]["gate_blocks"]["dte"] == 1


class TestWeekdayStats:
    def test_all_weekdays_treated_equally(self, tracker):
        trades = [
            {"entry_date": "2026-05-04T10:00", "realized_pnl": 100},  # Mon win
            {"entry_date": "2026-05-04T10:00", "realized_pnl": -50},  # Mon loss
            {"entry_date": "2026-05-05T10:00", "realized_pnl": -50},  # Tue loss
            {"entry_date": "2026-05-06T10:00", "realized_pnl": 100},  # Wed win
            {"entry_date": "2026-05-07T10:00", "realized_pnl": 100},  # Thu win
            {"entry_date": "2026-05-08T10:00", "realized_pnl": -50},  # Fri loss
        ]
        tracker.update_weekday_stats(trades)
        wr = tracker.metrics["weekday_performance"]["win_rate"]
        ss = tracker.metrics["weekday_performance"]["sample_size"]
        assert wr == {"mon": 50.0, "tue": 0.0, "wed": 100.0, "thu": 100.0, "fri": 0.0}
        assert ss == {"mon": 2, "tue": 1, "wed": 1, "thu": 1, "fri": 1}

    def test_empty_trades_keep_default_zeros(self, tracker):
        tracker.update_weekday_stats([])
        wr = tracker.metrics["weekday_performance"]["win_rate"]
        assert all(v == 0.0 for v in wr.values())

    def test_legacy_alias_works(self, tracker):
        # update_regime_stats is the back-compat alias; should not crash
        tracker.update_regime_stats(
            [{"entry_date": "2026-05-07T10:00", "realized_pnl": 100}]
        )
        assert tracker.metrics["weekday_performance"]["win_rate"]["thu"] == 100.0


class TestLegacyMigration:
    def test_migrate_old_schema_strips_thursday_bias(self, tmp_path):
        # Write a file in the old schema with the disproved 60% Thursday number
        legacy = {
            "last_updated": "2026-05-15T12:18:34.129093",
            "defense_alpha": {
                "blocked_trades_total": 7,
                "thursday_gate_blocks": 3,
                "dte_gate_blocks": 2,
                "vix_gate_blocks": 2,
                "estimated_loss_prevented": 100.0,
            },
            "regime_performance": {
                "thursday_win_rate": 60.0,
                "monday_win_rate": 13.33,
                "other_days_win_rate": 18.18,
            },
            "ml_alignment": {"rag_penalties_applied": 2, "policy_compliance_rate": 0.0},
        }
        (tmp_path / "data").mkdir()
        (tmp_path / "data" / "alpha_metrics.json").write_text(json.dumps(legacy))

        t = AlphaMetricsTracker(repo_root=tmp_path)
        defense = t.metrics["defense_alpha"]
        # blocked_trades_total preserved
        assert defense["blocked_trades_total"] == 7
        # Thursday counter dropped, others migrated to gate_blocks dict
        assert "thursday_gate_blocks" not in defense
        assert defense["gate_blocks"] == {"dte": 2, "vix": 2}
        # Disproved Thursday win rate not propagated
        weekday = t.metrics["weekday_performance"]
        assert "thursday_win_rate" not in weekday
        assert weekday["win_rate"]["thu"] == 0.0  # reset to default — old number discarded
        # ML alignment preserved
        assert t.metrics["ml_alignment"]["rag_penalties_applied"] == 2

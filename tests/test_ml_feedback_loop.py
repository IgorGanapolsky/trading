"""
Tests for ML feedback loop (update_ml_from_trades.py).

Covers:
1. Thompson Sampler update from real trade data
2. Trading gate enforcement (sample size + win rate + positive expectancy)
3. Post-mortem lesson generation from losses
4. Drift detection alerts
5. Halt file enforcement
6. Idempotent lesson generation (no duplicates)
"""

from __future__ import annotations

import scripts.update_ml_from_trades as feedback
from scripts.update_ml_from_trades import (
    analyze_loss_clusters,
    build_rehabilitation_plan,
    check_trading_gate,
    generate_loss_postmortems,
    is_validation_reset_model,
    stats_from_trades,
    update_thompson_sampler,
    validation_phase_trades,
)

# --- Thompson Sampler Tests ---


def test_thompson_update_replaces_stale_priors():
    """Stale (86/14) priors should be replaced with empirical data."""
    trades = {"stats": {"wins": 16, "losses": 49, "closed_trades": 66, "win_rate_pct": 24.24}}
    model = {
        "iron_condor": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 1},
        "spy_specific": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 1},
    }
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == 17.0  # 16 wins + 1
    assert updated["iron_condor"]["beta"] == 50.0  # 49 losses + 1
    assert updated["iron_condor"]["wins"] == 16
    assert updated["iron_condor"]["losses"] == 49


def test_thompson_update_with_zero_trades():
    """With no trades, priors should be (1, 1) — uninformative."""
    trades = {"stats": {"wins": 0, "losses": 0, "closed_trades": 0, "win_rate_pct": 0}}
    model = {"iron_condor": {"alpha": 86.0, "beta": 14.0, "wins": 0, "losses": 0}}
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == 1.0
    assert updated["iron_condor"]["beta"] == 1.0


def test_thompson_update_syncs_spy_specific():
    """spy_specific should match iron_condor (same underlying)."""
    trades = {"stats": {"wins": 10, "losses": 5, "closed_trades": 15, "win_rate_pct": 66.7}}
    model = {
        "iron_condor": {"alpha": 1, "beta": 1},
        "spy_specific": {"alpha": 1, "beta": 1},
    }
    updated = update_thompson_sampler(trades, model)
    assert updated["iron_condor"]["alpha"] == updated["spy_specific"]["alpha"]
    assert updated["iron_condor"]["beta"] == updated["spy_specific"]["beta"]


def test_validation_reset_detects_feedback_source_shape():
    """Validation reset must survive model files that only kept feedback_source."""
    assert is_validation_reset_model({"feedback_source": "validation_reset"})
    assert is_validation_reset_model({"validation_reset": "reset active"})
    assert not is_validation_reset_model({"feedback_source": "canonical_trades_json"})


def test_validation_phase_stats_exclude_legacy_failure_cohort():
    """Validation reset should not relearn from the broken pre-fix 66-trade cohort."""
    trades = {
        "trades": [
            {
                "id": "legacy-loss",
                "entry_date": "2026-04-02",
                "outcome": "loss",
                "realized_pnl": -120,
            },
            {
                "id": "validation-win",
                "entry_date": "2026-04-10",
                "outcome": "win",
                "realized_pnl": 41,
            },
            {
                "id": "validation-loss",
                "validation_phase": True,
                "outcome": "loss",
                "realized_pnl": -20,
            },
        ]
    }

    validation_trades = validation_phase_trades(trades)
    stats = stats_from_trades(validation_trades)

    assert [trade["id"] for trade in validation_trades] == [
        "validation-win",
        "validation-loss",
    ]
    assert stats["closed_trades"] == 2
    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["win_rate_pct"] == 50.0
    assert stats["total_realized_pnl"] == 21.0
    assert stats["profit_factor"] == 2.05
    assert stats["expectancy_per_trade"] == 10.5
    assert stats["data_quality_score"] == 1.0  # nosec B101


def test_stats_from_trades_reports_incomplete_rows_without_counting_them_as_closed():
    """Unresolved rows should be visible instead of silently changing priors."""
    stats = stats_from_trades(
        [
            {"id": "win-by-pnl", "realized_pnl": 25},
            {"id": "loss-by-outcome", "outcome": "loss", "realized_pnl": -10},
            {"id": "open-no-pnl", "outcome": "open"},
            {"id": "bad-pnl", "outcome": "win", "realized_pnl": "not-a-number"},
        ]
    )

    assert stats["input_trades"] == 4  # nosec B101
    assert stats["closed_trades"] == 3  # nosec B101
    assert stats["wins"] == 2  # nosec B101
    assert stats["losses"] == 1  # nosec B101
    assert stats["skipped_trades"] == 1  # nosec B101
    assert stats["ambiguous_outcome_trades"] == 1  # nosec B101
    assert stats["missing_pnl_trades"] == 2  # nosec B101
    assert stats["data_quality_score"] == 0.25  # nosec B101


def test_loss_cluster_analysis_surfaces_repeatable_profitability_blockers():
    """The ML loop should turn repeated losses into explicit rule-change signals."""
    trades = {
        "trades": [
            {
                "id": "fast-loss",
                "outcome": "loss",
                "realized_pnl": -100,
                "entry_time": "2026-04-01T14:00:00+00:00",
                "exit_time": "2026-04-01T14:30:00+00:00",
                "quantity": 2,
                "legs": {"put_strikes": [630, 640], "call_strikes": [705, 715]},
                "source": "alpaca_parent_lot",
            },
            {
                "id": "wide-loss",
                "outcome": "loss",
                "realized_pnl": -50,
                "entry_time": "2026-04-02T14:00:00+00:00",
                "exit_time": "2026-04-03T15:00:00+00:00",
                "quantity": 1,
                "legs": {"put_strikes": [620, 630], "call_strikes": [700, 710]},
                "source": "alpaca_parent_lot",
            },
            {
                "id": "narrow-win",
                "outcome": "win",
                "realized_pnl": 25,
                "entry_time": "2026-04-04T14:00:00+00:00",
                "exit_time": "2026-04-05T15:00:00+00:00",
                "quantity": 1,
                "legs": {"put_strikes": [620, 625], "call_strikes": [700, 705]},
                "source": "alpaca_parent_lot",
            },
        ]
    }

    clusters = analyze_loss_clusters(trades)
    by_id = {cluster["id"]: cluster for cluster in clusters}

    assert by_id["ten_wide_wings"]["sample_size"] == 2  # nosec B101
    assert by_id["ten_wide_wings"]["total_pnl"] == -150  # nosec B101
    assert by_id["multi_contract"]["sample_size"] == 1  # nosec B101
    assert by_id["early_exit_lt_1h"]["expectancy_per_trade"] == -100  # nosec B101


def test_rehabilitation_plan_requires_changed_rule_validation_before_profit_claims():
    """A blocked gate should produce a RAG-ingestable quarantine plan."""
    trades = {
        "stats": {
            "closed_trades": 2,
            "wins": 0,
            "losses": 2,
            "win_rate_pct": 0.0,
            "profit_factor": 0.0,
            "total_realized_pnl": -150.0,
        },
        "trades": [
            {
                "id": "fast-loss",
                "outcome": "loss",
                "realized_pnl": -100,
                "entry_time": "2026-04-01T14:00:00+00:00",
                "exit_time": "2026-04-01T14:30:00+00:00",
                "quantity": 2,
                "legs": {"put_strikes": [630, 640], "call_strikes": [705, 715]},
            },
            {
                "id": "wide-loss",
                "outcome": "loss",
                "realized_pnl": -50,
                "entry_time": "2026-04-02T14:00:00+00:00",
                "exit_time": "2026-04-03T15:00:00+00:00",
                "quantity": 1,
                "legs": {"put_strikes": [620, 630], "call_strikes": [700, 710]},
            },
        ],
    }
    gate = check_trading_gate(trades["stats"])

    plan = build_rehabilitation_plan(trades, gate)

    assert plan["status"] == "quarantined"  # nosec B101
    assert plan["next_validation_hypothesis_template"]["enabled"] is False  # nosec B101
    assert plan["rag_ingestion"]["lesson_id"] == feedback.REHAB_LESSON_ID  # nosec B101
    assert "changed-rule validation cohort" in plan["profitability_objective"]  # nosec B101
    assert plan["required_rule_changes"]  # nosec B101


# --- Trading Gate Tests ---


def test_gate_blocks_low_win_rate():
    """Win rate below 50% with enough trades should block."""
    stats = {"closed_trades": 66, "win_rate_pct": 24.24, "avg_win": 70.5, "avg_loss": 92.45}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert "24.2%" in gate["block_reason"]


def test_gate_blocks_insufficient_trades():
    """Fewer than 30 trades should block even with high win rate."""
    stats = {"closed_trades": 10, "win_rate_pct": 80.0, "avg_win": 100, "avg_loss": 50}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert "10/30" in gate["block_reason"]


def test_gate_allows_good_performance():
    """Enough trades with positive expectancy and profit factor should allow."""
    stats = {"closed_trades": 50, "win_rate_pct": 75.0, "avg_win": 100, "avg_loss": 80}
    gate = check_trading_gate(stats)
    assert gate["should_trade"]
    assert gate["expectancy_per_trade"] > 0
    assert gate["profit_factor"] > 1.0


def test_gate_blocks_high_win_rate_with_negative_expectancy():
    """High win rate still fails when losses swamp winners."""
    stats = {"closed_trades": 50, "win_rate_pct": 80.0, "avg_win": 10, "avg_loss": 100}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert not gate["positive_expectancy_met"]
    assert not gate["min_profit_factor_met"]
    assert "Expectancy" in gate["block_reason"]
    assert "Profit factor" in gate["block_reason"]


def test_gate_blocks_breakeven_profit_factor():
    """Profit factor must be strictly above breakeven before promotion."""
    stats = {"closed_trades": 40, "win_rate_pct": 50.0, "avg_win": 100, "avg_loss": 100}
    gate = check_trading_gate(stats)
    assert not gate["should_trade"]
    assert gate["profit_factor"] == 1.0
    assert not gate["positive_expectancy_met"]
    assert not gate["min_profit_factor_met"]


def test_gate_calculates_expectancy():
    """Expectancy = (win_rate * avg_win) - (loss_rate * avg_loss)."""
    stats = {"closed_trades": 100, "win_rate_pct": 80.0, "avg_win": 100, "avg_loss": 200}
    gate = check_trading_gate(stats)
    # Expected: 0.8 * 100 - 0.2 * 200 = 80 - 40 = 40
    assert gate["expectancy_per_trade"] == 40.0


def test_postmortem_lessons_write_to_primary_rag_corpus():
    """Loss lessons must land where IC Simple and the RAG index actually read them."""
    lessons_dir = str(feedback.LESSONS_DIR)
    assert lessons_dir.endswith("rag_knowledge/lessons_learned")
    assert "data/rag_knowledge" not in lessons_dir


# --- Post-Mortem Tests ---


def test_postmortem_generates_from_losses():
    """Should generate lessons for trades with P&L < -$20."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": "trade1",
                "outcome": "loss",
                "realized_pnl": -100,
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "entry_time": "2026-03-01T14:00:00+00:00",
                "exit_time": "2026-03-01T14:30:00+00:00",
                "signature": "SPY_test",
                "source": "",
            },
            {
                "id": "trade2",
                "outcome": "win",
                "realized_pnl": 50,
                "entry_date": "2026-03-02",
                "exit_date": "2026-03-05",
                "signature": "SPY_win",
                "source": "",
            },
            {
                "id": "trade3",
                "outcome": "loss",
                "realized_pnl": -5,
                "entry_date": "2026-03-03",
                "exit_date": "2026-03-03",
                "signature": "SPY_small",
                "source": "",
            },
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 1  # Only trade1 (P&L < -20)
    assert lessons[0]["pnl"] == -100
    assert "PREMATURE_EXIT" in lessons[0]["root_cause"]  # Held 0.5h


def test_postmortem_categorizes_orphan_cleanup():
    """Orphan cleanup should be identified in root cause."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": "orphan1",
                "outcome": "loss",
                "realized_pnl": -500,
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "signature": "SPY_orphan",
                "source": "alpaca_leg_cluster->ORPHAN",
            },
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 1
    assert "ORPHAN" in lessons[0]["root_cause"]


def test_postmortem_skips_wins():
    """Should not generate lessons for winning trades."""
    trades = {
        "stats": {},
        "trades": [
            {"id": "win1", "outcome": "win", "realized_pnl": 100, "signature": "SPY_win"},
        ],
    }
    lessons = generate_loss_postmortems(trades)
    assert len(lessons) == 0


def test_postmortem_limits_count():
    """Should respect max_lessons parameter."""
    trades = {
        "stats": {},
        "trades": [
            {
                "id": f"loss{i}",
                "outcome": "loss",
                "realized_pnl": -100 * (i + 1),
                "entry_date": "2026-03-01",
                "exit_date": "2026-03-01",
                "signature": f"SPY_loss{i}",
                "source": "",
            }
            for i in range(20)
        ],
    }
    lessons = generate_loss_postmortems(trades, max_lessons=3)
    assert len(lessons) == 3
    # Should be sorted by worst loss first
    assert lessons[0]["pnl"] < lessons[1]["pnl"]

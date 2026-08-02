"""Tests for scripts/update_ml_from_trades.py."""

from __future__ import annotations

import sys
from datetime import datetime, UTC
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import update_ml_from_trades as umt


def test_stats_from_trades_quarantines_unpaired_orders():
    """Unmatched orders remain diagnostics, never completed-trade labels."""
    trades = [
        {"outcome": "win", "realized_pnl": 150.0},
        {"outcome": "loss", "realized_pnl": -100.0},
    ]
    cohort_unpaired = {
        "unpaired_cohort_wins": 2,
        "unpaired_cohort_losses": 1,
        "unpaired_cohort_gross_profit": 80.0,
        "unpaired_cohort_gross_loss": 30.0,
        "unpaired_in_cohort_pnl": 50.0,
    }

    stats = umt.stats_from_trades(trades, cohort_unpaired)

    assert stats["wins"] == 1
    assert stats["losses"] == 1
    assert stats["closed_trades"] == 2
    assert stats["win_rate_pct"] == 50.0
    assert stats["gross_profit"] == 150.0
    assert stats["gross_loss"] == 100.0
    assert stats["total_realized_pnl"] == 50.0
    assert stats["profit_factor"] == 1.5
    assert stats["expectancy_per_trade"] == 25.0
    assert stats["metric_unit"] == "paired_closed_structure"
    assert stats["quarantined_unpaired_wins"] == 2
    assert stats["quarantined_unpaired_losses"] == 1
    assert stats["quarantined_unpaired_pnl"] == 50.0


def test_failed_mature_put_credit_cohort_writes_non_bypassable_halt(tmp_path):
    gate = umt.check_trading_gate(
        {
            "closed_trades": 30,
            "wins": 5,
            "losses": 25,
            "win_rate_pct": 16.67,
            "gross_profit": 250.0,
            "gross_loss": 1_500.0,
            "total_realized_pnl": -1_250.0,
            "expectancy_per_trade": -41.67,
            "profit_factor": 0.17,
        }
    )
    gate["active_strategy_family"] = "spy_put_credit"
    gate["evidence_dataset_sha256"] = "verified-cohort-hash"

    policy = umt.apply_active_cohort_policy(
        gate,
        active_family="spy_put_credit",
        validation_reset=True,
        evidence_issues=[],
    )

    assert policy["cohort_mature"] is True
    assert policy["allow_validation_entries"] is False
    assert policy["allow_paper_validation"] is False
    assert policy["hard_halt_required"] is True

    halt_file = tmp_path / "data" / "TRADING_HALTED"
    assert umt._write_active_cohort_halt(
        halt_file,
        policy,
        now=datetime(2026, 7, 23, tzinfo=UTC),
    )
    reason = halt_file.read_text(encoding="utf-8")
    assert reason.startswith("ACTIVE COHORT GATE BLOCKED: spy_put_credit")
    assert "Verified trades: 30" in reason

    from src.safety.mandatory_trade_gate import _is_ml_gate_halt_reason

    assert _is_ml_gate_halt_reason(reason) is False


def test_immature_clean_put_credit_cohort_retains_one_lot_validation():
    gate = umt.check_trading_gate(
        {
            "closed_trades": 29,
            "wins": 0,
            "losses": 29,
            "win_rate_pct": 0.0,
            "expectancy_per_trade": -10.0,
            "profit_factor": 0.0,
        }
    )

    policy = umt.apply_active_cohort_policy(
        gate,
        active_family="spy_put_credit",
        validation_reset=True,
        evidence_issues=[],
    )

    assert policy["cohort_mature"] is False
    assert policy["allow_validation_entries"] is True
    assert policy["allow_paper_validation"] is True
    assert policy["hard_halt_required"] is False


def test_active_cohort_halt_never_overwrites_crisis_halt(tmp_path):
    halt_file = tmp_path / "data" / "TRADING_HALTED"
    halt_file.parent.mkdir(parents=True)
    halt_file.write_text("CRISIS MODE: drawdown circuit", encoding="utf-8")

    written = umt._write_active_cohort_halt(
        halt_file,
        {
            "active_strategy_family": "spy_put_credit",
            "block_reason": "failed",
            "total_trades": 30,
        },
    )

    assert written is False
    assert halt_file.read_text(encoding="utf-8") == "CRISIS MODE: drawdown circuit"

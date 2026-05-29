"""Unit tests for `scripts/update_ml_from_trades.py` gate computation.

Verifies that singleton (post-cohort unpaired) P/L is folded into the gate's
expectancy and profit-factor denominators per LL-354, while paired-only
win-rate is preserved.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.update_ml_from_trades import check_trading_gate


PAIRED_STATS = {
    "total_trades": 163,
    "closed_trades": 163,
    "open_trades": 0,
    "wins": 19,
    "losses": 143,
    "breakeven": 1,
    "win_rate_pct": 11.66,
    "avg_win": 71.63,
    "avg_loss": 65.69,
    "profit_factor": 0.14,
    "total_pnl": -8033.0,
    "total_realized_pnl": -8033.0,
    "gross_profit": 1361.0,
    "gross_loss": 9394.0,
    "unpaired_realized_pnl": 574.0,
    "unpaired_in_cohort_pnl": -127.0,
    "unpaired_order_count": 7,
    "unpaired_cohort_start": "2026-04-09",
}


def test_gate_folds_singleton_pnl_into_expectancy() -> None:
    gate = check_trading_gate(PAIRED_STATS)
    # paired total -8033, singleton -127, denominator 163
    assert gate["realized_pnl_paired"] == -8033.0
    assert gate["realized_pnl_including_singletons"] == -8160.0
    assert gate["singleton_adjustment"] == -127.0
    assert gate["singleton_order_count"] == 7
    assert gate["singleton_cohort_start"] == "2026-04-09"
    # -8160 / 163 = -50.06 (vs. paired-only -49.28)
    assert gate["expectancy_per_trade"] == pytest.approx(-50.06, abs=0.01)


def test_gate_preserves_paired_only_win_rate() -> None:
    """Singletons must NOT shift the win-rate denominator (LL-354 rationale)."""
    gate = check_trading_gate(PAIRED_STATS)
    assert gate["win_rate"] == 11.66
    assert gate["total_trades"] == 163  # paired closed_trades, not orders


def test_gate_folds_negative_singleton_into_profit_factor() -> None:
    gate = check_trading_gate(PAIRED_STATS)
    # gross_profit 1361 / (gross_loss 9394 + |−127|) = 1361 / 9521 ≈ 0.1430
    assert gate["profit_factor"] == pytest.approx(0.14, abs=0.005)
    assert gate["min_profit_factor_met"] is False


def test_gate_blocks_when_broker_truth_is_negative() -> None:
    gate = check_trading_gate(PAIRED_STATS)
    assert gate["should_trade"] is False
    assert "Win rate" in gate["block_reason"]


def test_gate_handles_missing_singleton_keys() -> None:
    """Backward-compat: trades.json without PR #4076 fields still works."""
    stats = {k: v for k, v in PAIRED_STATS.items() if not k.startswith("unpaired_")}
    gate = check_trading_gate(stats)
    assert gate["singleton_adjustment"] == 0.0
    assert gate["realized_pnl_paired"] == gate["realized_pnl_including_singletons"]
    # Falls back to paired-only expectancy ≈ -8033/163 = -49.28
    assert gate["expectancy_per_trade"] == pytest.approx(-49.28, abs=0.01)


def test_halt_file_content_includes_broker_truth_numbers(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """End-to-end: main() writes the new multi-line halt-file format."""
    import scripts.update_ml_from_trades as mod

    project_root = tmp_path
    (project_root / "data").mkdir()
    (project_root / "models" / "ml").mkdir(parents=True)
    (project_root / "data" / "trades.json").write_text(
        json.dumps({"stats": PAIRED_STATS, "trades": []})
    )

    monkeypatch.setattr(mod, "PROJECT_ROOT", project_root)
    monkeypatch.setattr(mod, "TRADES_FILE", project_root / "data" / "trades.json")
    monkeypatch.setattr(mod, "MODEL_FILE", project_root / "models" / "ml" / "trade_confidence_model.json")
    monkeypatch.setattr(mod, "LESSONS_DIR", project_root / "rag_knowledge" / "lessons_learned")
    monkeypatch.setattr(mod, "REHAB_PLAN_FILE", project_root / "data" / "runtime" / "edge_rehabilitation_plan.json")

    mod.main(dry_run=False)

    halt_file = project_root / "data" / "TRADING_HALTED"
    assert halt_file.exists(), "halt file should be written when gate blocks"
    content = halt_file.read_text()

    # Pattern check used by src/safety/mandatory_trade_gate.py::_is_ml_gate_halt_reason
    normalized = content.upper()
    assert "ML GATE BLOCKED" in normalized
    assert "WIN RATE" in normalized

    # Broker-truth surface
    assert "Realized P/L (paired): $-8033.00" in content
    assert "Realized P/L (broker-truth): $-8160.00" in content
    assert "Singleton adjustment: $-127.00 over 7 orders since 2026-04-09" in content

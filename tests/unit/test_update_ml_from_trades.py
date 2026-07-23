"""Tests for scripts/update_ml_from_trades.py."""

from __future__ import annotations

import sys
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

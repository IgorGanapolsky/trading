"""Tests for scripts/update_ml_from_trades.py."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import update_ml_from_trades as umt


def test_stats_from_trades_with_unpaired_folding():
    """Verify that stats_from_trades correctly folds cohort unpaired statistics
    into wins, losses, win_rate_pct, gross_profit, gross_loss, total_realized_pnl,
    profit_factor, and expectancy_per_trade.
    """
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

    # Paired trades: 1 W ($150), 1 L (-$100). Total: 2 trades, P/L: $50
    # Unpaired: 2 W ($80), 1 L (-$30). Total: 3 trades, P/L: $50
    # Folded Total: 3 W ($230), 2 L (-$130). Total: 5 trades, P/L: $100
    assert stats["wins"] == 3
    assert stats["losses"] == 2
    assert stats["closed_trades"] == 5
    assert stats["win_rate_pct"] == 60.0  # 3/5 * 100
    assert stats["gross_profit"] == 230.0
    assert stats["gross_loss"] == 130.0
    assert stats["total_realized_pnl"] == 100.0
    assert stats["profit_factor"] == round(230.0 / 130.0, 2)
    assert stats["expectancy_per_trade"] == 20.0  # 100.0 / 5

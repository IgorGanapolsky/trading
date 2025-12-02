import numpy as np
from scripts.run_backtest_matrix import (
    aggregate_summary,
    longest_positive_streak,
)


def test_longest_positive_streak_counts_consecutive_days():
    series = np.array([0.01, -0.02, 0.005, 0.003, 0.004, -0.001, 0.002])
    streak = longest_positive_streak(series)
    assert streak == 3


def test_aggregate_summary_tracks_minimums():
    summaries = [
        {
            "scenario": "bull",
            "win_rate_pct": 65.0,
            "sharpe_ratio": 1.9,
            "max_drawdown_pct": 5.0,
            "longest_profitable_streak": 40,
            "status": "pass",
        },
        {
            "scenario": "bear",
            "win_rate_pct": 58.0,
            "sharpe_ratio": 1.4,
            "max_drawdown_pct": 12.0,
            "longest_profitable_streak": 25,
            "status": "needs_improvement",
        },
    ]
    aggregate = aggregate_summary(summaries)
    metrics = aggregate["aggregate_metrics"]
    assert metrics["min_win_rate"] == 58.0
    assert metrics["min_sharpe_ratio"] == 1.4
    assert metrics["max_drawdown"] == 12.0
    assert metrics["min_profitable_streak"] == 25
    assert metrics["passes"] == 1

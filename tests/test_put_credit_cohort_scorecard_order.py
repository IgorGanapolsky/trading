"""Greptile #4280 P2: rolling window must be time-ordered."""

from scripts.put_credit_cohort_scorecard import summarize_closed


def test_rolling_uses_chronological_last_n_not_json_order():
    # Deliberately reverse chronological in list order
    rows = [
        {
            "strategy": "spy_put_credit",
            "status": "closed",
            "exit_time": f"2026-06-{i:02d}T15:00:00+00:00",
            "realized_pnl": float(i),
        }
        for i in range(1, 25)
    ]
    rows = list(reversed(rows))  # newest first in input
    out = summarize_closed(rows)
    assert out["closed_n"] == 24
    rolling = out["rolling_20"]["last"]
    assert rolling is not None
    # last 20 by time are exits 5..24 with pnls 5..24; sum = (5+24)*20/2 = 290
    assert rolling["total_realized_pnl"] == 290.0

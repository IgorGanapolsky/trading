"""Golden-answer and property evals for the put-credit cohort scorecard.

Incident source (2026-07-27): rolling_20 sliced trades in JSON file order
instead of chronological order (Greptile #4280 P2) — the same scorecard that
feeds the n>=30 / expectancy>0 / PF>1 live-money kill gate. These evals pin
the metric math to known answers and assert order-invariance, so a future
regression in gate-critical arithmetic fails CI instead of corrupting the
go-live decision.
"""

from __future__ import annotations

import random

from scripts.put_credit_cohort_scorecard import summarize_closed


def _row(
    pnl: float,
    exit_time: str | None,
    status: str = "closed",
    strategy: str = "spy_put_credit",
):
    return {
        "strategy": strategy,
        "status": status,
        "exit_time": exit_time,
        "realized_pnl": pnl,
    }


GOLDEN_ROWS = [
    _row(50.0, "2026-06-01T15:00:00+00:00"),
    _row(50.0, "2026-06-02T15:00:00+00:00"),
    _row(-100.0, "2026-06-03T15:00:00+00:00"),
    _row(25.0, "2026-06-04T15:00:00+00:00"),
]


class TestGoldenAnswers:
    def test_known_pnl_series_produces_exact_metrics(self):
        out = summarize_closed(GOLDEN_ROWS)
        assert out["closed_n"] == 4
        assert out["wins"] == 3
        assert out["losses"] == 1
        assert out["breakeven"] == 0
        assert out["win_rate_pct"] == 75.0
        assert out["total_realized_pnl"] == 25.0
        assert out["expectancy"] == 6.25  # 25 / 4
        assert out["profit_factor"] == 1.25  # 125 gross win / 100 gross loss
        assert out["avg_win"] == 41.67  # 125 / 3 rounded
        assert out["avg_loss"] == -100.0

    def test_all_wins_reports_infinite_profit_factor(self):
        rows = [
            _row(10.0, "2026-06-01T15:00:00+00:00"),
            _row(20.0, "2026-06-02T15:00:00+00:00"),
        ]
        out = summarize_closed(rows)
        assert out["profit_factor"] == float("inf")
        assert out["win_rate_pct"] == 100.0

    def test_empty_input_yields_zero_sample_not_fabrication(self):
        out = summarize_closed([])
        assert out["closed_n"] == 0
        assert out["expectancy"] is None
        assert out["profit_factor"] is None
        assert out["total_realized_pnl"] == 0.0
        assert out["kill_criteria"]["verdict"] == "INSUFFICIENT_SAMPLE"


class TestOrderInvariance:
    """summarize_closed output must not depend on input row order."""

    def _rows(self):
        return [
            _row(float(i if i % 3 else -i), f"2026-06-{i:02d}T15:00:00+00:00") for i in range(1, 25)
        ]

    def test_shuffled_inputs_produce_identical_output(self):
        baseline = summarize_closed(sorted(self._rows(), key=lambda r: r["exit_time"]))
        reversed_out = summarize_closed(list(reversed(self._rows())))
        shuffled = self._rows()
        random.Random(42).shuffle(shuffled)
        shuffled_out = summarize_closed(shuffled)
        assert baseline == reversed_out == shuffled_out

    def test_rolling_window_selects_chronologically_newest_trades(self):
        """Order-invariance alone would also pass under a deterministic but
        WRONG ordering (e.g. newest-first, making rolling pick the oldest 20).
        Pin the exact window: chronological last 20 of days 5..24 sums to
        290 - 2*(6+9+12+15+18+21+24) = 80.0 with this fixture's sign rule."""
        shuffled = self._rows()
        random.Random(7).shuffle(shuffled)
        rolling = summarize_closed(shuffled)["rolling_20"]["last"]
        assert rolling is not None
        assert rolling["total_realized_pnl"] == 80.0


class TestScopeFilters:
    def test_open_rows_and_foreign_strategies_are_excluded(self):
        # An open position has no exit evidence yet; exit_time is authoritative
        # for closedness, so the open row must not carry one.
        rows = GOLDEN_ROWS + [
            _row(999.0, None, status="open"),
            _row(999.0, "2026-06-06T15:00:00+00:00", strategy="ic_simple"),
        ]
        out = summarize_closed(rows)
        assert out["closed_n"] == 4
        assert out["total_realized_pnl"] == 25.0

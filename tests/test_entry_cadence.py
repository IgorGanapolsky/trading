"""Tests for the validation-cadence alarm.

The bug this guards against: every entry session between 2026-07-24 and
2026-08-10 was refused, and every workflow run still reported success. These
tests pin the behaviour that makes a stall visible.
"""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "scripts" / "check_entry_cadence.py"
_spec = importlib.util.spec_from_file_location("check_entry_cadence", MODULE_PATH)
assert _spec and _spec.loader
cadence = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cadence)


def _trades(closed: int) -> dict:
    return {"stats": {"by_strategy": {"spy_put_credit": {"closed_trades": closed}}}}


def _entries(*timestamps: str) -> list[dict]:
    return [{"entry_time": ts} for ts in timestamps]


class TestTradingDaysBetween:
    def test_skips_the_weekend(self):
        # Fri 2026-08-07 -> Mon 2026-08-10 is one trading day, not three.
        assert cadence.trading_days_between(date(2026, 8, 7), date(2026, 8, 10)) == 1

    def test_same_day_is_zero(self):
        assert cadence.trading_days_between(date(2026, 8, 10), date(2026, 8, 10)) == 0

    def test_future_start_never_goes_negative(self):
        assert cadence.trading_days_between(date(2026, 8, 12), date(2026, 8, 10)) == 0

    def test_counts_a_full_week(self):
        assert cadence.trading_days_between(date(2026, 8, 3), date(2026, 8, 10)) == 5

    def test_skips_market_holidays(self):
        # Fri 2026-05-22 -> Fri 2026-05-29 with Memorial Day Mon 2026-05-25.
        # Trading days: 26,27,28,29 = 4 (Mon holiday excluded).
        assert cadence.trading_days_between(date(2026, 5, 22), date(2026, 5, 29)) == 4
        # Thanksgiving Thu 2026-11-26: Wed->Fri is one session (Fri), not two.
        assert cadence.trading_days_between(date(2026, 11, 25), date(2026, 11, 27)) == 1


class TestEvaluate:
    def test_the_real_regression_is_caught(self):
        """The exact production state on 2026-08-10: last entry 07-24, n=2."""
        report = cadence.evaluate(
            entries_payload=_entries(
                "2026-07-23T15:37:08.050702+00:00",
                "2026-07-24T16:58:19.813683+00:00",
            ),
            trades_payload=_trades(2),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["stalled"] is True
        # Fri 2026-07-24 -> Mon 2026-08-10 is 11 weekdays.
        assert report["stall_trading_days"] == 11
        assert report["cohort_closed"] == 2

    def test_recent_entry_is_healthy(self):
        report = cadence.evaluate(
            entries_payload=_entries("2026-08-07T15:00:00+00:00"),
            trades_payload=_trades(2),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["stalled"] is False
        assert report["stall_trading_days"] == 1

    def test_boundary_is_inclusive(self):
        """Exactly at the threshold must alarm, not sit one day under it."""
        report = cadence.evaluate(
            entries_payload=_entries("2026-08-03T15:00:00+00:00"),
            trades_payload=_trades(2),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["stall_trading_days"] == 5
        assert report["stalled"] is True

    def test_one_day_under_threshold_stays_quiet(self):
        report = cadence.evaluate(
            entries_payload=_entries("2026-08-04T15:00:00+00:00"),
            trades_payload=_trades(2),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["stall_trading_days"] == 4
        assert report["stalled"] is False

    def test_completed_cohort_stops_alarming(self):
        """Once n>=30 the cadence no longer gates anything."""
        report = cadence.evaluate(
            entries_payload=_entries("2026-01-02T15:00:00+00:00"),
            trades_payload=_trades(30),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["cohort_complete"] is True
        assert report["stalled"] is False

    def test_empty_journal_is_a_stall(self):
        report = cadence.evaluate(
            entries_payload=[],
            trades_payload=_trades(0),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        assert report["stalled"] is True
        assert report["stall_trading_days"] is None
        assert report["last_entry_time"] is None


class TestPayloadShapes:
    """The journal has appeared as a list and as a dict in different revisions."""

    @pytest.mark.parametrize(
        "payload",
        [
            [{"entry_time": "2026-08-07T15:00:00+00:00"}],
            {"entries": [{"entry_time": "2026-08-07T15:00:00+00:00"}]},
            {"entries": {"a": {"entry_time": "2026-08-07T15:00:00+00:00"}}},
        ],
    )
    def test_every_known_shape_parses(self, payload):
        rows = cadence._entry_rows(payload)
        assert cadence.latest_entry_time(rows) is not None

    def test_falls_back_to_filled_at(self):
        rows = cadence._entry_rows([{"filled_at": "2026-08-07T15:00:00+00:00"}])
        assert cadence.latest_entry_time(rows) is not None

    def test_unparseable_timestamps_are_ignored_not_fatal(self):
        rows = cadence._entry_rows([{"entry_time": "not-a-date"}, {"entry_time": None}])
        assert cadence.latest_entry_time(rows) is None

    def test_naive_timestamps_are_treated_as_utc(self):
        rows = cadence._entry_rows([{"entry_time": "2026-08-07T15:00:00"}])
        assert cadence.latest_entry_time(rows) is not None

    def test_latest_wins_when_out_of_order(self):
        rows = cadence._entry_rows(
            _entries("2026-08-07T15:00:00+00:00", "2026-07-01T15:00:00+00:00")
        )
        assert cadence.latest_entry_time(rows).date() == date(2026, 8, 7)


class TestCohortSize:
    def test_counts_only_the_active_strategy(self):
        """Killed iron-condor rows must never inflate the successor cohort."""
        payload = {
            "stats": {
                "by_strategy": {
                    "iron_condor": {"closed_trades": 161},
                    "spy_put_credit": {"closed_trades": 2},
                }
            }
        }
        assert cadence.cohort_size(payload) == 2

    def test_excludes_non_validation_closed_rows(self):
        payload = {
            "trades": [
                {
                    "strategy": "spy_put_credit",
                    "status": "closed",
                    "realized_pnl": 10,
                    "validation_phase": True,
                },
                {
                    "strategy": "spy_put_credit",
                    "status": "closed",
                    "realized_pnl": -50,
                    "validation_phase": False,
                },
            ]
        }
        assert cadence.cohort_size(payload) == 1

    @pytest.mark.parametrize(
        "payload",
        [{}, {"stats": None}, {"stats": {}}, {"stats": {"by_strategy": None}}, [], "x"],
    )
    def test_malformed_ledgers_degrade_to_zero(self, payload):
        assert cadence.cohort_size(payload) == 0


class TestValidationEntryFilter:
    def test_excluded_entry_does_not_reset_stall(self):
        report = cadence.evaluate(
            entries_payload=[
                {"entry_time": "2026-07-20T15:00:00+00:00", "validation_phase": True},
                {"entry_time": "2026-08-07T15:00:00+00:00", "validation_phase": False},
            ],
            trades_payload=_trades(2),
            today=date(2026, 8, 10),
            max_stall_days=5,
        )
        # Last *validation* entry is 2026-07-20 → stalled past 5 trading days.
        assert report["stalled"] is True
        assert report["last_entry_time"].startswith("2026-07-20")

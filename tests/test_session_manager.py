"""
Tests for SessionManager - Critical for Operational Security

CREATED: Jan 13, 2026
REASON: Prevent trading on weekends/holidays which could result in order
        failures or unexpected behavior.

These tests verify:
1. is_us_market_day() correctly identifies weekends
2. is_us_market_day() correctly identifies US holidays
3. is_us_market_day() returns True on regular trading days
4. SessionManager builds correct session profiles
5. Weekend mode triggers appropriate configuration changes
"""

from __future__ import annotations

import os
from datetime import date
from unittest.mock import MagicMock, patch

import pytest

# Skip if holidays module not available (sandbox environments)
holidays = pytest.importorskip("holidays", reason="holidays module required for this test")

from src.orchestrator.session_manager import (
    SessionManager,
    _get_us_holidays,
    is_us_market_day,
)


class TestIsUsMarketDay:
    """Test the is_us_market_day() function for weekend/holiday detection."""

    # Weekend Tests
    def test_saturday_is_not_market_day(self):
        """Saturday should NOT be a market day."""
        saturday = date(2026, 1, 10)  # A Saturday
        assert saturday.weekday() == 5, "Verify this is a Saturday"
        assert is_us_market_day(saturday) is False

    def test_sunday_is_not_market_day(self):
        """Sunday should NOT be a market day."""
        sunday = date(2026, 1, 11)  # A Sunday
        assert sunday.weekday() == 6, "Verify this is a Sunday"
        assert is_us_market_day(sunday) is False

    def test_multiple_weekends(self):
        """Test multiple weekends throughout the year."""
        weekends = [
            date(2026, 1, 3),  # Saturday
            date(2026, 1, 4),  # Sunday
            date(2026, 3, 7),  # Saturday
            date(2026, 3, 8),  # Sunday
            date(2026, 6, 13),  # Saturday
            date(2026, 6, 14),  # Sunday
            date(2026, 12, 5),  # Saturday
            date(2026, 12, 6),  # Sunday
        ]
        for weekend_date in weekends:
            assert is_us_market_day(weekend_date) is False, (
                f"{weekend_date} (weekday={weekend_date.weekday()}) should not be a market day"
            )

    # US Holiday Tests
    def test_mlk_day_is_not_market_day(self):
        """Martin Luther King Jr. Day should NOT be a market day."""
        # MLK Day is the third Monday of January
        mlk_day_2026 = date(2026, 1, 19)
        assert mlk_day_2026.weekday() == 0, "Verify this is a Monday"
        assert is_us_market_day(mlk_day_2026) is False

    def test_presidents_day_is_not_market_day(self):
        """Presidents Day should NOT be a market day."""
        # Presidents Day is the third Monday of February
        presidents_day_2026 = date(2026, 2, 16)
        assert presidents_day_2026.weekday() == 0, "Verify this is a Monday"
        assert is_us_market_day(presidents_day_2026) is False

    def test_memorial_day_is_not_market_day(self):
        """Memorial Day should NOT be a market day."""
        # Memorial Day is the last Monday of May
        memorial_day_2026 = date(2026, 5, 25)
        assert memorial_day_2026.weekday() == 0, "Verify this is a Monday"
        assert is_us_market_day(memorial_day_2026) is False

    def test_independence_day_is_not_market_day(self):
        """Independence Day should NOT be a market day."""
        # July 4th - if it falls on weekend, observed on Friday/Monday
        # In 2026, July 4th is a Saturday, observed on Friday July 3rd
        independence_day_2026 = date(2026, 7, 3)  # Observed
        assert is_us_market_day(independence_day_2026) is False

    def test_labor_day_is_not_market_day(self):
        """Labor Day should NOT be a market day."""
        # Labor Day is the first Monday of September
        labor_day_2026 = date(2026, 9, 7)
        assert labor_day_2026.weekday() == 0, "Verify this is a Monday"
        assert is_us_market_day(labor_day_2026) is False

    def test_thanksgiving_is_not_market_day(self):
        """Thanksgiving Day should NOT be a market day."""
        # Thanksgiving is the fourth Thursday of November
        thanksgiving_2026 = date(2026, 11, 26)
        assert thanksgiving_2026.weekday() == 3, "Verify this is a Thursday"
        assert is_us_market_day(thanksgiving_2026) is False

    def test_christmas_day_is_not_market_day(self):
        """Christmas Day should NOT be a market day."""
        # December 25th - if it falls on weekend, observed on Friday/Monday
        # In 2026, Christmas is a Friday
        christmas_2026 = date(2026, 12, 25)
        assert christmas_2026.weekday() == 4, "Verify this is a Friday"
        assert is_us_market_day(christmas_2026) is False

    def test_new_years_day_is_not_market_day(self):
        """New Year's Day should NOT be a market day."""
        # January 1st
        new_years_2026 = date(2026, 1, 1)
        assert is_us_market_day(new_years_2026) is False

    # Regular Trading Day Tests
    def test_monday_is_market_day(self):
        """Regular Monday (non-holiday) should be a market day."""
        # Monday Jan 5, 2026 - not a holiday
        monday = date(2026, 1, 5)
        assert monday.weekday() == 0, "Verify this is a Monday"
        assert is_us_market_day(monday) is True

    def test_tuesday_is_market_day(self):
        """Regular Tuesday should be a market day."""
        tuesday = date(2026, 1, 6)
        assert tuesday.weekday() == 1, "Verify this is a Tuesday"
        assert is_us_market_day(tuesday) is True

    def test_wednesday_is_market_day(self):
        """Regular Wednesday should be a market day."""
        wednesday = date(2026, 1, 7)
        assert wednesday.weekday() == 2, "Verify this is a Wednesday"
        assert is_us_market_day(wednesday) is True

    def test_thursday_is_market_day(self):
        """Regular Thursday should be a market day."""
        thursday = date(2026, 1, 8)
        assert thursday.weekday() == 3, "Verify this is a Thursday"
        assert is_us_market_day(thursday) is True

    def test_friday_is_market_day(self):
        """Regular Friday should be a market day."""
        friday = date(2026, 1, 9)
        assert friday.weekday() == 4, "Verify this is a Friday"
        assert is_us_market_day(friday) is True

    def test_regular_trading_week(self):
        """A full week of regular trading days."""
        # Jan 5-9, 2026 is a regular trading week
        trading_days = [
            date(2026, 1, 5),  # Monday
            date(2026, 1, 6),  # Tuesday
            date(2026, 1, 7),  # Wednesday
            date(2026, 1, 8),  # Thursday
            date(2026, 1, 9),  # Friday
        ]
        for trading_day in trading_days:
            assert is_us_market_day(trading_day) is True, (
                f"{trading_day} (weekday={trading_day.weekday()}) should be a market day"
            )

    def test_defaults_to_today(self):
        """When no date is provided, should use today's date."""
        # Just verify it doesn't crash and returns a boolean
        result = is_us_market_day()
        assert isinstance(result, bool)


class TestHolidayCache:
    """Test the holiday caching mechanism."""

    def test_get_us_holidays_returns_holiday_base(self):
        """_get_us_holidays should return a holidays.HolidayBase object."""
        import holidays

        result = _get_us_holidays(2026)
        assert isinstance(result, holidays.HolidayBase)

    def test_holiday_cache_reuse(self):
        """Calling _get_us_holidays twice should return same cached object."""
        result1 = _get_us_holidays(2027)
        result2 = _get_us_holidays(2027)
        assert result1 is result2, "Should return cached instance"

    def test_different_years_different_objects(self):
        """Different years should have different holiday objects."""
        result_2025 = _get_us_holidays(2025)
        result_2026 = _get_us_holidays(2026)
        assert result_2025 is not result_2026


class TestSessionManager:
    """Test the SessionManager class."""

    @pytest.fixture
    def manager(self):
        """Create a SessionManager with default settings."""
        return SessionManager(
            default_tickers=["AAPL", "MSFT", "GOOGL"],
            weekend_proxy_symbols="BITO,RWCR",
        )

    def test_init_normalizes_tickers(self):
        """Tickers should be stripped and uppercased."""
        manager = SessionManager(
            default_tickers=["  aapl  ", "msft", " Googl"],
        )
        assert manager.default_tickers == ["AAPL", "MSFT", "GOOGL"]

    def test_init_filters_empty_tickers(self):
        """Empty ticker strings should be filtered out."""
        manager = SessionManager(
            default_tickers=["AAPL", "", "  ", "MSFT"],
        )
        assert manager.default_tickers == ["AAPL", "MSFT"]

    def test_init_weekend_proxy_from_env(self):
        """weekend_proxy_symbols should fall back to env var."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_SYMBOLS": "SPY,QQQ"}):
            manager = SessionManager(
                default_tickers=["AAPL"],
                weekend_proxy_symbols=None,
            )
            assert manager.weekend_proxy_symbols == "SPY,QQQ"

    def test_current_profile_initially_none(self, manager):
        """current_profile should be None before build_session_profile."""
        assert manager.current_profile is None


class TestSessionManagerBuildProfile:
    """Test SessionManager.build_session_profile() method."""

    @pytest.fixture
    def manager(self):
        """Create a SessionManager with default settings."""
        return SessionManager(
            default_tickers=["AAPL", "MSFT", "GOOGL"],
            weekend_proxy_symbols="BITO,RWCR",
        )

    def test_build_session_profile_market_day(self, manager):
        """On a market day, should return market_hours session type."""
        # Monday Jan 5, 2026 - regular trading day
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            profile = manager.build_session_profile()

            assert profile["session_type"] == "market_hours"
            assert profile["is_market_day"] is True
            assert profile["tickers"] == ["AAPL", "MSFT", "GOOGL"]
            assert profile["momentum_overrides"] == {}

    def test_build_session_profile_weekend(self, manager):
        """On a weekend, should return weekend session type."""
        # Saturday Jan 10, 2026
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            profile = manager.build_session_profile()

            assert profile["session_type"] == "weekend"
            assert profile["is_market_day"] is False
            assert profile["tickers"] == ["BITO", "RWCR"]
            assert "rsi_overbought" in profile["momentum_overrides"]
            assert "macd_threshold" in profile["momentum_overrides"]
            assert "volume_min" in profile["momentum_overrides"]

    def test_build_session_profile_holiday(self, manager):
        """On a holiday, should return weekend session type."""
        # MLK Day 2026 - Monday Jan 19, 2026
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 19)

            profile = manager.build_session_profile()

            assert profile["session_type"] == "weekend"
            assert profile["is_market_day"] is False

    def test_build_session_profile_stores_profile(self, manager):
        """build_session_profile should store the profile in current_profile."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            profile = manager.build_session_profile()

            assert manager.current_profile is profile

    def test_build_session_profile_includes_date(self, manager):
        """Profile should include the date in ISO format."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            profile = manager.build_session_profile()

            assert profile["date"] == "2026-01-05"

    def test_rl_threshold_market_day(self, manager):
        """Market day should use default RL threshold (0.45)."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            profile = manager.build_session_profile()

            assert profile["rl_threshold"] == 0.45

    def test_rl_threshold_weekend(self, manager):
        """Weekend should use higher RL threshold (0.55)."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            profile = manager.build_session_profile()

            assert profile["rl_threshold"] == 0.55

    def test_rl_threshold_from_env(self, manager):
        """RL threshold should be configurable via environment variable."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)
            with patch.dict(os.environ, {"RL_CONFIDENCE_THRESHOLD": "0.60"}):
                profile = manager.build_session_profile()

                assert profile["rl_threshold"] == 0.60


class TestSessionManagerHelperMethods:
    """Test SessionManager helper methods."""

    @pytest.fixture
    def manager(self):
        """Create a SessionManager with default settings."""
        return SessionManager(
            default_tickers=["AAPL", "MSFT"],
            weekend_proxy_symbols="BITO",
        )

    def test_get_active_tickers_builds_profile_if_none(self, manager):
        """get_active_tickers should build profile if none exists."""
        assert manager.current_profile is None

        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            tickers = manager.get_active_tickers()

            assert manager.current_profile is not None
            assert tickers == ["AAPL", "MSFT"]

    def test_get_active_tickers_uses_existing_profile(self, manager):
        """get_active_tickers should use existing profile if available."""
        # Pre-set a profile
        manager._current_profile = {"tickers": ["SPY", "QQQ"]}

        tickers = manager.get_active_tickers()

        assert tickers == ["SPY", "QQQ"]

    def test_is_weekend_mode_true_on_weekend(self, manager):
        """is_weekend_mode should return True on weekends."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            result = manager.is_weekend_mode()

            assert result is True

    def test_is_weekend_mode_false_on_market_day(self, manager):
        """is_weekend_mode should return False on market days."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            result = manager.is_weekend_mode()

            assert result is False

    def test_get_rl_threshold_market_day(self, manager):
        """get_rl_threshold should return 0.45 on market days."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            threshold = manager.get_rl_threshold()

            assert threshold == 0.45

    def test_get_rl_threshold_weekend(self, manager):
        """get_rl_threshold should return 0.55 on weekends."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            threshold = manager.get_rl_threshold()

            assert threshold == 0.55


class TestMaybeReallocateForWeekend:
    """Test SessionManager.maybe_reallocate_for_weekend() method."""

    @pytest.fixture
    def manager(self):
        """Create a SessionManager."""
        return SessionManager(
            default_tickers=["AAPL"],
            weekend_proxy_symbols="BITO",
        )

    def test_reallocate_disabled_via_env(self, manager):
        """Reallocation should be skipped when env var is false."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_REALLOCATE": "false"}):
            mock_dca = MagicMock()
            mock_telemetry = MagicMock()

            result = manager.maybe_reallocate_for_weekend(mock_dca, mock_telemetry)

            assert result is None
            mock_dca.reallocate_all_to_bucket.assert_not_called()

    def test_reallocate_enabled_by_default(self, manager):
        """Reallocation should happen when env var is not set (defaults to true)."""
        with patch.dict(os.environ, {}, clear=False):
            # Ensure the env var is not set
            os.environ.pop("WEEKEND_PROXY_REALLOCATE", None)

            mock_dca = MagicMock()
            mock_dca.reallocate_all_to_bucket.return_value = 1000.0
            mock_telemetry = MagicMock()

            manager.maybe_reallocate_for_weekend(mock_dca, mock_telemetry)

            mock_dca.reallocate_all_to_bucket.assert_called_once_with("weekend")

    def test_reallocate_records_telemetry(self, manager):
        """Reallocation should record telemetry event."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_REALLOCATE": "true"}):
            mock_dca = MagicMock()
            mock_dca.reallocate_all_to_bucket.return_value = 500.0
            mock_telemetry = MagicMock()

            manager.maybe_reallocate_for_weekend(mock_dca, mock_telemetry)

            mock_telemetry.record.assert_called_once_with(
                event_type="weekend.reallocate",
                payload={"bucket": "weekend", "reallocated_budget": 500.0},
            )

    def test_reallocate_handles_missing_method(self, manager):
        """Reallocation should handle DCA without reallocate_all_to_bucket."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_REALLOCATE": "true"}):
            mock_dca = MagicMock(spec=[])  # No methods
            mock_telemetry = MagicMock()

            # Should not raise
            result = manager.maybe_reallocate_for_weekend(mock_dca, mock_telemetry)

            assert result is None

    def test_reallocate_with_none_telemetry(self, manager):
        """Reallocation should handle None telemetry gracefully."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_REALLOCATE": "true"}):
            mock_dca = MagicMock()
            mock_dca.reallocate_all_to_bucket.return_value = 100.0

            # Should not raise with None telemetry
            result = manager.maybe_reallocate_for_weekend(mock_dca, None)

            assert result is None


class TestWeekendMomentumOverrides:
    """Test weekend momentum parameter overrides."""

    @pytest.fixture
    def manager(self):
        """Create a SessionManager."""
        return SessionManager(
            default_tickers=["AAPL"],
            weekend_proxy_symbols="BITO",
        )

    def test_weekend_momentum_defaults(self, manager):
        """Weekend mode should set default momentum overrides."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            profile = manager.build_session_profile()

            # Check default values
            assert profile["momentum_overrides"]["rsi_overbought"] == 65.0
            assert profile["momentum_overrides"]["macd_threshold"] == -0.05
            assert profile["momentum_overrides"]["volume_min"] == 0.5

    def test_weekend_momentum_from_env(self, manager):
        """Weekend momentum overrides should be configurable via env vars."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)
            with patch.dict(
                os.environ,
                {
                    "WEEKEND_RSI_OVERBOUGHT": "70.0",
                    "WEEKEND_MACD_THRESHOLD": "-0.10",
                    "WEEKEND_VOLUME_MIN": "0.3",
                },
            ):
                profile = manager.build_session_profile()

                assert profile["momentum_overrides"]["rsi_overbought"] == 70.0
                assert profile["momentum_overrides"]["macd_threshold"] == -0.10
                assert profile["momentum_overrides"]["volume_min"] == 0.3

    def test_market_day_no_momentum_overrides(self, manager):
        """Market day should have no momentum overrides."""
        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 5)

            profile = manager.build_session_profile()

            assert profile["momentum_overrides"] == {}


class TestEmptyProxyList:
    """Test behavior when proxy list is empty or defaults."""

    def test_empty_weekend_proxy_uses_env_default(self):
        """Empty weekend proxy should fall back to env var default BITO,RWCR."""
        with patch.dict(os.environ, {"WEEKEND_PROXY_SYMBOLS": "BITO,RWCR"}):
            manager = SessionManager(
                default_tickers=["AAPL"],
                weekend_proxy_symbols="",
            )

            with patch("src.orchestrator.session_manager.datetime") as mock_dt:
                mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

                profile = manager.build_session_profile()

                # Empty string falls back to env default "BITO,RWCR"
                assert profile["tickers"] == ["BITO", "RWCR"]

    def test_whitespace_only_proxy_uses_fallback(self):
        """Whitespace-only proxy symbols should result in fallback to BITO."""
        manager = SessionManager(
            default_tickers=["AAPL"],
            weekend_proxy_symbols="   ",
        )

        with patch("src.orchestrator.session_manager.datetime") as mock_dt:
            mock_dt.now.return_value.date.return_value = date(2026, 1, 10)

            profile = manager.build_session_profile()

            # Whitespace-only results in empty list, then defaults to ["BITO"]
            assert profile["tickers"] == ["BITO"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

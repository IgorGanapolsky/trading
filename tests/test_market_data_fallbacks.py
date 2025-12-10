"""
Unit tests for MarketDataProvider fallback logic and self-healing capabilities.

Tests cover:
- Exponential backoff retries
- Fallback chain: yfinance -> Alpaca -> Alpha Vantage -> cache
- Health logging and metadata tracking
- Configuration validation
- Error handling and recovery
"""

import json
import os
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, Mock, patch

import pandas as pd
import pytest
from src.utils.market_data import (
    DataSource,
    FetchAttempt,
    MarketDataProvider,
    MarketDataResult,
)


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Provide a temporary cache directory for testing."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    return cache_dir


@pytest.fixture
def mock_provider(temp_cache_dir):
    """Create a MarketDataProvider with mocked dependencies."""
    with patch.dict(
        os.environ,
        {
            "MARKET_DATA_CACHE_DIR": str(temp_cache_dir),
            "YFINANCE_MAX_RETRIES": "2",
            "ALPACA_MAX_RETRIES": "2",
            "ALPHAVANTAGE_MAX_RETRIES": "2",
            "YFINANCE_INITIAL_BACKOFF_SECONDS": "0.1",
            "ALPACA_INITIAL_BACKOFF_SECONDS": "0.1",
        },
    ):
        provider = MarketDataProvider()
        provider._alpaca_api = None  # Disable Alpaca for most tests
        provider.alpha_vantage_key = None  # Disable Alpha Vantage for most tests
        yield provider


class TestMarketDataResult:
    """Test MarketDataResult dataclass and metadata tracking."""

    def test_result_initialization(self):
        """Test basic initialization of MarketDataResult."""
        result = MarketDataResult(
            data=pd.DataFrame({"Close": [100, 101, 102]}),
            source=DataSource.YFINANCE,
        )
        assert result.source == DataSource.YFINANCE
        assert len(result.data) == 3
        assert result.total_attempts == 0
        assert result.total_latency_ms == 0.0

    def test_add_attempt_tracking(self):
        """Test that attempts are tracked correctly."""
        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)

        # Add successful attempt
        result.add_attempt(
            FetchAttempt(
                source=DataSource.YFINANCE,
                timestamp=time.time(),
                success=True,
                rows_fetched=50,
                latency_ms=123.45,
            )
        )

        assert result.total_attempts == 1
        assert result.total_latency_ms == 123.45
        assert len(result.attempts) == 1
        assert result.attempts[0].success is True

        # Add failed attempt
        result.add_attempt(
            FetchAttempt(
                source=DataSource.ALPACA,
                timestamp=time.time(),
                success=False,
                error_message="Connection timeout",
                latency_ms=5000.0,
            )
        )

        assert result.total_attempts == 2
        assert result.total_latency_ms == 123.45 + 5000.0
        assert len(result.attempts) == 2
        assert result.attempts[1].success is False

    def test_result_to_dict(self):
        """Test serialization to dictionary for logging."""
        result = MarketDataResult(
            data=pd.DataFrame({"Close": [100, 101]}),
            source=DataSource.ALPACA,
        )
        result.add_attempt(
            FetchAttempt(
                source=DataSource.YFINANCE,
                timestamp=time.time(),
                success=False,
                error_message="HTTP 403",
                latency_ms=50.0,
            )
        )
        result.add_attempt(
            FetchAttempt(
                source=DataSource.ALPACA,
                timestamp=time.time(),
                success=True,
                rows_fetched=2,
                latency_ms=100.0,
            )
        )

        result_dict = result.to_dict()

        assert result_dict["source"] == "alpaca"
        assert result_dict["rows"] == 2
        assert result_dict["total_attempts"] == 2
        assert result_dict["total_latency_ms"] == 150.0
        assert len(result_dict["attempts"]) == 2
        assert result_dict["attempts"][0]["success"] is False
        assert result_dict["attempts"][1]["success"] is True


class TestYFinanceFallback:
    """Test yfinance retry logic with exponential backoff."""

    def test_yfinance_success_first_attempt(self, mock_provider):
        """Test successful fetch on first attempt."""
        mock_data = pd.DataFrame(
            {
                "Open": [100],
                "High": [101],
                "Low": [99],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.date_range("2025-01-01", periods=1),
        )

        with patch.object(mock_provider, "_fetch_yfinance", return_value=mock_data):
            result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
            data = mock_provider._fetch_yfinance_with_retries(
                "SPY", datetime.now(), datetime.now(), result
            )

            assert data is not None
            assert len(data) == 1
            assert result.total_attempts == 1
            assert result.attempts[0].success is True
            assert result.attempts[0].source == DataSource.YFINANCE

    def test_yfinance_retry_then_success(self, mock_provider):
        """Test retry logic with eventual success."""
        mock_data = pd.DataFrame(
            {
                "Open": [100],
                "High": [101],
                "Low": [99],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.date_range("2025-01-01", periods=1),
        )

        call_count = 0

        def mock_fetch(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Simulated network failure")
            return mock_data

        with patch.object(mock_provider, "_fetch_yfinance", side_effect=mock_fetch):
            result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
            data = mock_provider._fetch_yfinance_with_retries(
                "SPY", datetime.now(), datetime.now(), result
            )

            assert data is not None
            assert result.total_attempts == 2
            assert result.attempts[0].success is False
            assert result.attempts[1].success is True

    def test_yfinance_all_retries_fail(self, mock_provider):
        """Test exhausting all retries without success."""
        with patch.object(
            mock_provider,
            "_fetch_yfinance",
            side_effect=Exception("Persistent failure"),
        ):
            result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
            data = mock_provider._fetch_yfinance_with_retries(
                "SPY", datetime.now(), datetime.now(), result
            )

            assert data is None
            # Note: YFINANCE_MAX_RETRIES is class attribute loaded at import, not from fixture env
            assert result.total_attempts >= 2  # At least 2 retries
            assert all(not attempt.success for attempt in result.attempts)

    def test_yfinance_exponential_backoff(self, mock_provider):
        """Test that exponential backoff is applied between retries."""
        with patch.object(mock_provider, "_fetch_yfinance", side_effect=Exception("Fail")):
            start_time = time.time()
            result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
            mock_provider._fetch_yfinance_with_retries(
                "SPY", datetime.now(), datetime.now(), result
            )
            elapsed = time.time() - start_time

            # First retry: 0.1s backoff
            # Total should be >= 0.1s (allowing some tolerance for execution time)
            assert elapsed >= 0.09


class TestAlpacaFallback:
    """Test Alpaca API retry logic."""

    def test_alpaca_not_initialized(self, mock_provider):
        """Test behavior when Alpaca API is not available."""
        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
        data = mock_provider._fetch_alpaca_with_retries("SPY", 30, result)

        assert data is None
        assert result.total_attempts == 1
        assert result.attempts[0].source == DataSource.ALPACA
        assert result.attempts[0].success is False
        assert "not initialized" in result.attempts[0].error_message.lower()

    def test_alpaca_success(self, mock_provider):
        """Test successful Alpaca API fetch."""
        mock_api = MagicMock()
        mock_bar = Mock()
        mock_bar.timestamp = datetime(2025, 1, 1)
        # Mock attributes accessed via dot notation in _fetch_alpaca
        mock_bar.open = 100.0
        mock_bar.high = 101.0
        mock_bar.low = 99.0
        mock_bar.close = 100.5
        mock_bar.volume = 1000

        mock_response = Mock()
        mock_response.data = {"SPY": [mock_bar]}
        mock_api.get_stock_bars.return_value = mock_response
        mock_provider._alpaca_api = mock_api

        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
        data = mock_provider._fetch_alpaca_with_retries("SPY", 30, result)

        assert data is not None
        assert len(data) == 1
        assert result.total_attempts == 1
        assert result.attempts[0].success is True

    def test_alpaca_retry_then_success(self, mock_provider):
        """Test Alpaca retry logic."""
        mock_api = MagicMock()
        call_count = 0

        def mock_get_bars(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Timeout")

            mock_bar = Mock()
            mock_bar.timestamp = datetime(2025, 1, 1)
            mock_bar.open = 100.0
            mock_bar.high = 101.0
            mock_bar.low = 99.0
            mock_bar.close = 100.5
            mock_bar.volume = 1000

            mock_response = Mock()
            mock_response.data = {"SPY": [mock_bar]}
            return mock_response

        mock_api.get_stock_bars.side_effect = mock_get_bars
        mock_provider._alpaca_api = mock_api

        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
        data = mock_provider._fetch_alpaca_with_retries("SPY", 30, result)

        assert data is not None
        assert result.total_attempts == 2


class TestAlphaVantageFallback:
    """Test Alpha Vantage fallback logic."""

    def test_alpha_vantage_no_key(self, mock_provider):
        """Test behavior when Alpha Vantage key is not configured."""
        result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
        data = mock_provider._fetch_alpha_vantage_with_retries("SPY", result)

        assert data is None
        # An attempt should be added recording the failure
        assert result.total_attempts == 1
        assert result.attempts[0].success is False

    def test_alpha_vantage_success(self, mock_provider):
        """Test successful Alpha Vantage fetch."""
        mock_provider.alpha_vantage_key = "test_key"
        mock_data = pd.DataFrame(
            {
                "Open": [100],
                "High": [101],
                "Low": [99],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.date_range("2025-01-01", periods=1),
        )

        with patch.object(mock_provider, "_fetch_alpha_vantage", return_value=mock_data):
            result = MarketDataResult(data=pd.DataFrame(), source=DataSource.UNKNOWN)
            data = mock_provider._fetch_alpha_vantage_with_retries("SPY", result)

            assert data is not None
            assert len(data) == 1
            assert result.total_attempts == 1
            assert result.attempts[0].success is True


class TestCachedDataFallback:
    """Test cached data fallback logic."""

    def test_load_cached_data_not_found(self, mock_provider):
        """Test behavior when no cached data exists."""
        data, age = mock_provider._load_cached_data_with_age("SPY", 30)
        assert data is None
        assert age is None

    def test_load_cached_data_success(self, mock_provider, temp_cache_dir):
        """Test loading valid cached data."""
        # Create cached data file
        cache_file = temp_cache_dir / "SPY_2025-01-01.csv"
        mock_data = pd.DataFrame(
            {
                "Open": [100],
                "High": [101],
                "Low": [99],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.DatetimeIndex([datetime(2025, 1, 1)], name="Date"),
        )
        mock_data.to_csv(cache_file)

        # Touch file to set recent modification time
        os.utime(cache_file, None)

        data, age = mock_provider._load_cached_data_with_age("SPY", 1)

        assert data is not None
        assert len(data) == 1
        assert age is not None
        assert age < 1.0  # Less than 1 hour old

    def test_load_cached_data_too_old(self, mock_provider, temp_cache_dir):
        """Test that stale cached data is rejected."""
        # Create cached data file
        cache_file = temp_cache_dir / "SPY_2025-01-01.csv"
        mock_data = pd.DataFrame(
            {
                "Open": [100],
                "High": [101],
                "Low": [99],
                "Close": [100.5],
                "Volume": [1000],
            },
            index=pd.DatetimeIndex([datetime(2025, 1, 1)], name="Date"),
        )
        mock_data.to_csv(cache_file)

        # Set modification time to 8 days ago (beyond CACHE_MAX_AGE_DAYS=7)
        old_time = time.time() - (8 * 24 * 3600)
        os.utime(cache_file, (old_time, old_time))

        data, age = mock_provider._load_cached_data_with_age("SPY", 1)

        assert data is None
        assert age is None


class TestFullFallbackChain:
    """Test complete fallback chain integration."""

    def test_fallback_chain_yfinance_success(self, mock_provider):
        """Test that yfinance success prevents fallback attempts."""
        mock_data = pd.DataFrame(
            {
                "Open": [100] * 30,
                "High": [101] * 30,
                "Low": [99] * 30,
                "Close": [100.5] * 30,
                "Volume": [1000] * 30,
            },
            index=pd.date_range("2025-01-01", periods=30),
        )

        with patch.object(mock_provider, "_fetch_yfinance", return_value=mock_data):
            result = mock_provider.get_daily_bars("SPY", 30)

            assert result.source == DataSource.YFINANCE
            assert len(result.data) == 30
            # Only yfinance should have been attempted
            assert all(a.source == DataSource.YFINANCE for a in result.attempts)

    def test_alpaca_priority_over_yfinance(self, mock_provider):
        """Test that Alpaca is prioritized over yfinance."""
        # Mock Alpaca API
        mock_api = MagicMock()
        mock_bars = []
        for i in range(30):
            mock_bar = Mock()
            mock_bar.timestamp = datetime(2025, 1, 1) + timedelta(days=i)
            mock_bar.open = 100.0
            mock_bar.high = 101.0
            mock_bar.low = 99.0
            mock_bar.close = 100.5
            mock_bar.volume = 1000
            mock_bars.append(mock_bar)

        mock_response = Mock()
        mock_response.data = {"SPY": mock_bars}
        mock_api.get_stock_bars.return_value = mock_response
        mock_provider._alpaca_api = mock_api

        with patch.object(
            mock_provider, "_fetch_yfinance", side_effect=Exception("yfinance failed")
        ):
            result = mock_provider.get_daily_bars("SPY", 30)

            assert result.source == DataSource.ALPACA
            assert len(result.data) == 30
            # Alpaca is prioritized, so yfinance should NOT be attempted if Alpaca succeeds
            sources = [a.source for a in result.attempts]
            assert DataSource.ALPACA in sources
            assert DataSource.YFINANCE not in sources

    def test_fallback_chain_all_fail(self, mock_provider):
        """Test complete failure when all sources are unavailable."""
        with patch.object(
            mock_provider, "_fetch_yfinance", side_effect=Exception("yfinance failed")
        ):
            with pytest.raises(ValueError) as exc_info:
                mock_provider.get_daily_bars("SPY", 30)

            error_message = str(exc_info.value)
            assert "Failed to fetch" in error_message
            assert "SPY" in error_message


class TestHealthLogging:
    """Test health logging functionality."""

    def test_health_log_written(self, mock_provider):
        """Test that health log is written after fetch."""
        mock_data = pd.DataFrame(
            {
                "Open": [100] * 30,
                "High": [101] * 30,
                "Low": [99] * 30,
                "Close": [100.5] * 30,
                "Volume": [1000] * 30,
            },
            index=pd.date_range("2025-01-01", periods=30),
        )

        with patch.object(mock_provider, "_fetch_yfinance", return_value=mock_data):
            mock_provider.get_daily_bars("SPY", 30)

            # Check that health log file was created
            health_log = mock_provider._health_log_file
            assert health_log.exists()

            # Verify log content
            with open(health_log) as f:
                log_lines = f.readlines()
                assert len(log_lines) >= 1
                last_entry = json.loads(log_lines[-1])
                assert last_entry["symbol"] == "SPY"
                assert last_entry["source"] == "yfinance"
                assert last_entry["rows"] == 30


class TestConfiguration:
    """Test configuration loading from environment variables."""

    def test_configuration_from_env(self):
        """Test that configuration is loaded from environment variables."""
        with patch.dict(
            os.environ,
            {
                "YFINANCE_MAX_RETRIES": "5",
                "ALPACA_MAX_RETRIES": "4",
                "ALPHAVANTAGE_MAX_RETRIES": "3",
                "YFINANCE_INITIAL_BACKOFF_SECONDS": "2.5",
                "CACHE_MAX_AGE_DAYS": "14",
            },
        ):
            provider = MarketDataProvider()

            assert provider.YFINANCE_MAX_RETRIES == 5
            assert provider.ALPACA_MAX_RETRIES == 4
            assert provider.ALPHAVANTAGE_MAX_RETRIES == 3
            assert provider.YFINANCE_INITIAL_BACKOFF_SECONDS == 2.5
            assert provider.CACHE_MAX_AGE_DAYS == 14

    def test_configuration_defaults(self):
        """Test that defaults are used when env vars are not set."""
        with patch.dict(os.environ, {}, clear=True):
            provider = MarketDataProvider()

            # Verify defaults
            assert provider.YFINANCE_MAX_RETRIES == 3
            assert provider.ALPACA_MAX_RETRIES == 3
            assert provider.CACHE_MAX_AGE_DAYS == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

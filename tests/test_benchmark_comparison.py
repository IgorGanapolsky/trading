"""
Tests for Benchmark Comparison Module

Tests the benchmark comparison functionality including:
- BenchmarkComparator class
- Alpha/Beta calculation
- Buy-and-hold comparison
- Data caching

Author: Trading System
Created: 2025-12-09
"""

import tempfile
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from src.backtesting.benchmark_comparison import (
    BenchmarkComparator,
    BenchmarkComparisonResult,
    BenchmarkMetrics,
    compare_to_benchmark,
)
from src.backtesting.data_cache import OHLCVDataCache


class TestBenchmarkMetrics:
    """Tests for BenchmarkMetrics dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        metrics = BenchmarkMetrics(
            symbol="SPY",
            name="S&P 500",
            strategy_return=15.0,
            benchmark_return=10.0,
            excess_return=5.0,
            outperformance_ratio=1.05,
            alpha=3.0,
            beta=1.1,
            r_squared=0.85,
            information_ratio=0.5,
            tracking_error=2.0,
            strategy_max_drawdown=8.0,
            benchmark_max_drawdown=10.0,
            relative_drawdown=0.8,
            pct_days_outperformed=55.0,
            best_outperformance_day=2.5,
            worst_underperformance_day=-1.8,
            max_consecutive_outperformance=5,
            strategy_sharpe=1.5,
            benchmark_sharpe=1.2,
        )

        result = metrics.to_dict()

        assert result["symbol"] == "SPY"
        assert result["excess_return"] == 5.0
        assert result["alpha"] == 3.0
        assert result["beta"] == 1.1


class TestBenchmarkComparisonResult:
    """Tests for BenchmarkComparisonResult dataclass."""

    def test_generate_report(self):
        """Test report generation."""
        primary = BenchmarkMetrics(
            symbol="SPY",
            name="S&P 500",
            strategy_return=15.0,
            benchmark_return=10.0,
            excess_return=5.0,
            outperformance_ratio=1.05,
            alpha=3.0,
            beta=1.1,
            r_squared=0.85,
            information_ratio=0.5,
            tracking_error=2.0,
            strategy_max_drawdown=8.0,
            benchmark_max_drawdown=10.0,
            relative_drawdown=0.8,
            pct_days_outperformed=55.0,
            best_outperformance_day=2.5,
            worst_underperformance_day=-1.8,
            max_consecutive_outperformance=5,
            strategy_sharpe=1.5,
            benchmark_sharpe=1.2,
        )

        result = BenchmarkComparisonResult(
            strategy_name="Test Strategy",
            start_date="2024-01-01",
            end_date="2024-12-31",
            trading_days=252,
            primary_benchmark=primary,
            buy_hold_return=10.0,
            buy_hold_sharpe=1.2,
            buy_hold_max_drawdown=10.0,
        )

        report = result.generate_report()

        assert "BENCHMARK COMPARISON REPORT" in report
        assert "Test Strategy" in report
        assert "S&P 500" in report
        assert "OUTPERFORMED" in report
        assert "Alpha" in report

    def test_to_dict(self):
        """Test serialization."""
        primary = BenchmarkMetrics(
            symbol="SPY",
            name="S&P 500",
            strategy_return=15.0,
            benchmark_return=10.0,
            excess_return=5.0,
            outperformance_ratio=1.05,
            alpha=3.0,
            beta=1.1,
            r_squared=0.85,
            information_ratio=0.5,
            tracking_error=2.0,
            strategy_max_drawdown=8.0,
            benchmark_max_drawdown=10.0,
            relative_drawdown=0.8,
            pct_days_outperformed=55.0,
            best_outperformance_day=2.5,
            worst_underperformance_day=-1.8,
            max_consecutive_outperformance=5,
            strategy_sharpe=1.5,
            benchmark_sharpe=1.2,
        )

        result = BenchmarkComparisonResult(
            strategy_name="Test",
            start_date="2024-01-01",
            end_date="2024-12-31",
            trading_days=252,
            primary_benchmark=primary,
        )

        data = result.to_dict()

        assert data["strategy_name"] == "Test"
        assert data["trading_days"] == 252
        assert "primary_benchmark" in data


class TestBenchmarkComparator:
    """Tests for BenchmarkComparator class."""

    @pytest.fixture
    def sample_equity_curve(self):
        """Generate sample equity curve for testing."""
        np.random.seed(42)
        initial = 100000

        # Generate dates
        dates = []
        equity = [initial]
        current = date(2024, 1, 2)

        for _ in range(100):
            while current.weekday() >= 5:  # Skip weekends
                current += timedelta(days=1)
            dates.append(current.strftime("%Y-%m-%d"))
            # Random walk with slight upward bias
            change = np.random.normal(0.0005, 0.01)
            equity.append(equity[-1] * (1 + change))
            current += timedelta(days=1)

        return equity, dates

    def test_calculate_returns(self):
        """Test return calculation."""
        comparator = BenchmarkComparator()
        values = [100, 105, 110, 108]
        returns = comparator._calculate_returns(values)

        assert len(returns) == 3
        assert np.isclose(returns[0], 0.05)
        assert np.isclose(returns[1], 0.05 / 1.05, rtol=0.01)

    def test_calculate_sharpe(self):
        """Test Sharpe ratio calculation."""
        comparator = BenchmarkComparator(risk_free_rate=0.0)

        # Perfect positive returns
        returns = np.array([0.01, 0.01, 0.01, 0.01, 0.01])
        sharpe = comparator._calculate_sharpe(returns)
        assert sharpe > 0

        # Negative returns
        returns = np.array([-0.01, -0.01, -0.01])
        sharpe = comparator._calculate_sharpe(returns)
        assert sharpe < 0

    def test_calculate_max_drawdown(self):
        """Test max drawdown calculation."""
        comparator = BenchmarkComparator()

        # 10% drawdown
        values = [100, 105, 95, 100]
        dd = comparator._calculate_max_drawdown(values)
        assert np.isclose(dd, (105 - 95) / 105 * 100, rtol=0.01)

        # No drawdown (always increasing)
        values = [100, 101, 102, 103]
        dd = comparator._calculate_max_drawdown(values)
        assert dd == 0.0


class TestOHLCVDataCache:
    """Tests for OHLCV data caching."""

    @pytest.fixture
    def temp_cache_dir(self):
        """Create temporary cache directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_ohlcv_data(self):
        """Generate sample OHLCV data."""
        dates = pd.date_range(start="2024-01-01", periods=100, freq="B")
        np.random.seed(42)

        close = 100 + np.cumsum(np.random.randn(100) * 2)
        high = close + np.random.rand(100) * 2
        low = close - np.random.rand(100) * 2
        open_price = close + np.random.randn(100) * 0.5
        volume = np.random.randint(1000000, 10000000, 100)

        df = pd.DataFrame(
            {
                "Open": open_price,
                "High": high,
                "Low": low,
                "Close": close,
                "Volume": volume,
            },
            index=dates,
        )

        return df

    def test_cache_initialization(self, temp_cache_dir):
        """Test cache directory creation."""
        OHLCVDataCache(cache_dir=temp_cache_dir)

        assert (temp_cache_dir / "bronze").exists()
        assert (temp_cache_dir / "silver").exists()
        assert (temp_cache_dir / "gold").exists()
        assert (temp_cache_dir / "metadata").exists()

    def test_put_and_get(self, temp_cache_dir, sample_ohlcv_data):
        """Test storing and retrieving data."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        # Store data
        success = cache.put("SPY", sample_ohlcv_data, "test", "bronze")
        assert success

        # Retrieve data
        retrieved = cache.get("SPY", "2024-01-01", "2024-12-31", "bronze")
        assert retrieved is not None
        assert len(retrieved) == len(sample_ohlcv_data)

    def test_data_validation(self, temp_cache_dir):
        """Test data quality validation."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        # Good data
        good_data = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [102, 103],
                "Low": [99, 100],
                "Close": [101, 102],
                "Volume": [1000, 1100],
            },
            index=pd.date_range("2024-01-01", periods=2),
        )

        score = cache._validate_data(good_data)
        assert score > 0.8

        # Bad data (High < Low)
        bad_data = pd.DataFrame(
            {
                "Open": [100, 101],
                "High": [99, 100],  # Less than Low
                "Low": [102, 103],
                "Close": [101, 102],
                "Volume": [1000, 1100],
            },
            index=pd.date_range("2024-01-01", periods=2),
        )

        score = cache._validate_data(bad_data)
        assert score < 0.8

    def test_promote_data(self, temp_cache_dir, sample_ohlcv_data):
        """Test data promotion between tiers."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        # Store in bronze
        cache.put("SPY", sample_ohlcv_data, "test", "bronze")

        # Promote to silver
        success = cache.promote("SPY", "bronze", "silver")
        assert success

        # Verify silver data exists
        silver_data = cache.get("SPY", "2024-01-01", "2024-12-31", "silver")
        assert silver_data is not None

    def test_list_cached_symbols(self, temp_cache_dir, sample_ohlcv_data):
        """Test listing cached symbols."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        # Store multiple symbols
        cache.put("SPY", sample_ohlcv_data, "test", "silver")
        cache.put("QQQ", sample_ohlcv_data, "test", "silver")
        cache.put("VOO", sample_ohlcv_data, "test", "silver")

        symbols = cache.list_cached_symbols("silver")
        assert len(symbols) == 3
        assert "SPY" in symbols
        assert "QQQ" in symbols

    def test_invalidate_cache(self, temp_cache_dir, sample_ohlcv_data):
        """Test cache invalidation."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        # Store data
        cache.put("SPY", sample_ohlcv_data, "test", "silver")
        assert cache.get("SPY", "2024-01-01", "2024-12-31", "silver") is not None

        # Invalidate
        success = cache.invalidate("SPY", "silver")
        assert success

        # Verify gone
        assert cache.get("SPY", "2024-01-01", "2024-12-31", "silver") is None

    def test_cache_info(self, temp_cache_dir, sample_ohlcv_data):
        """Test cache information retrieval."""
        cache = OHLCVDataCache(cache_dir=temp_cache_dir)

        cache.put("SPY", sample_ohlcv_data, "yfinance", "silver")

        info = cache.get_cache_info("SPY", "silver")

        assert info is not None
        assert info["symbol"] == "SPY"
        assert info["source"] == "yfinance"
        assert info["row_count"] == len(sample_ohlcv_data)
        assert info["is_fresh"] is True


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    def test_compare_to_benchmark_empty_data(self):
        """Test error handling for empty data."""
        with pytest.raises(ValueError):
            compare_to_benchmark([], [], "SPY")

    def test_compare_to_benchmark_mismatched_lengths(self):
        """Test error handling for mismatched lengths."""
        with pytest.raises(ValueError):
            compare_to_benchmark([100, 101, 102], ["2024-01-01", "2024-01-02"], "SPY")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

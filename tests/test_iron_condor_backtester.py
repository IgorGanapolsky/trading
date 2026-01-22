"""Tests for iron condor backtester."""

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

# Skip all tests if dependencies not available
pytest.importorskip("numpy")
pytest.importorskip("pandas")
pytest.importorskip("scipy")

import numpy as np
import pandas as pd


class TestIronCondorConfig:
    """Test IronCondorConfig dataclass."""

    def test_default_config(self):
        """Test default configuration values."""
        from scripts.backtest.iron_condor_backtester import IronCondorConfig

        config = IronCondorConfig()
        assert config.underlying_symbol == "SPY"
        assert config.short_delta == 0.16
        assert config.wing_width == 5.0
        assert config.dte_min == 30
        assert config.dte_max == 45
        assert config.profit_target_pct == 0.50
        assert config.stop_loss_pct == 2.00
        assert config.max_dte == 7

    def test_config_to_dict(self):
        """Test config serialization."""
        from scripts.backtest.iron_condor_backtester import IronCondorConfig

        config = IronCondorConfig(underlying_symbol="XSP", short_delta=0.20)
        d = config.to_dict()
        assert d["underlying_symbol"] == "XSP"
        assert d["short_delta"] == 0.20

    def test_config_from_dict(self):
        """Test config deserialization."""
        from scripts.backtest.iron_condor_backtester import IronCondorConfig

        d = {"underlying_symbol": "SPX", "wing_width": 10.0}
        config = IronCondorConfig.from_dict(d)
        assert config.underlying_symbol == "SPX"
        assert config.wing_width == 10.0
        assert config.short_delta == 0.16  # Default preserved


class TestOptionsMath:
    """Test Black-Scholes math functions."""

    def test_black_scholes_put(self):
        """Test put option pricing."""
        from scripts.backtest.iron_condor_backtester import black_scholes_price

        # ATM put with typical SPY params
        price = black_scholes_price(S=590, K=590, T=30 / 365, r=0.05, sigma=0.18, option_type="put")
        assert price > 0
        assert price < 20  # Reasonable range for SPY

    def test_black_scholes_call(self):
        """Test call option pricing."""
        from scripts.backtest.iron_condor_backtester import black_scholes_price

        price = black_scholes_price(S=590, K=590, T=30 / 365, r=0.05, sigma=0.18, option_type="call")
        assert price > 0
        assert price < 20

    def test_black_scholes_expired(self):
        """Test expired option pricing (intrinsic value)."""
        from scripts.backtest.iron_condor_backtester import black_scholes_price

        # ITM put at expiration
        put_price = black_scholes_price(S=580, K=590, T=0, r=0.05, sigma=0.18, option_type="put")
        assert put_price == 10  # Intrinsic value

        # OTM put at expiration
        put_price = black_scholes_price(S=600, K=590, T=0, r=0.05, sigma=0.18, option_type="put")
        assert put_price == 0

    def test_strike_from_delta(self):
        """Test strike calculation from delta."""
        from scripts.backtest.iron_condor_backtester import strike_from_delta

        # 16 delta put should be below spot
        put_strike = strike_from_delta(
            S=590, T=30 / 365, r=0.05, sigma=0.18, delta=-0.16, option_type="put"
        )
        assert put_strike < 590

        # 16 delta call should be above spot
        call_strike = strike_from_delta(
            S=590, T=30 / 365, r=0.05, sigma=0.18, delta=0.16, option_type="call"
        )
        assert call_strike > 590


class TestIronCondorResult:
    """Test IronCondorResult dataclass."""

    def test_result_to_dict(self):
        """Test result serialization."""
        from scripts.backtest.iron_condor_backtester import IronCondorResult

        result = IronCondorResult(
            status="profit_target",
            pnl=150.0,
            entry_date=date(2026, 1, 15),
            exit_date=date(2026, 1, 22),
            dte_at_entry=30,
            dte_at_exit=7,
            short_put_strike=575,
            long_put_strike=570,
            short_call_strike=605,
            long_call_strike=610,
            credit_received=200.0,
            underlying_at_entry=590.0,
            underlying_at_exit=592.0,
            put_side_pnl=100.0,
            call_side_pnl=50.0,
            exit_reason="profit_target",
        )

        d = result.to_dict()
        assert d["status"] == "profit_target"
        assert d["pnl"] == 150.0
        assert d["entry_date"] == "2026-01-15"
        assert d["exit_date"] == "2026-01-22"


class TestIronCondorBacktester:
    """Test IronCondorBacktester class."""

    @pytest.fixture
    def mock_bars(self):
        """Create mock price data."""
        dates = pd.date_range("2025-12-01", "2026-01-22", freq="B")  # Business days
        return pd.DataFrame({
            "timestamp": dates,
            "open": np.random.uniform(585, 595, len(dates)),
            "high": np.random.uniform(590, 600, len(dates)),
            "low": np.random.uniform(580, 590, len(dates)),
            "close": np.random.uniform(585, 595, len(dates)),
            "volume": np.random.randint(50000000, 100000000, len(dates)),
        })

    def test_estimate_iv(self, mock_bars):
        """Test IV estimation from historical data."""
        from scripts.backtest.iron_condor_backtester import IronCondorBacktester

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = MagicMock()

            iv = backtester.estimate_iv(mock_bars)
            assert 0.10 <= iv <= 0.40  # Realistic SPY IV range

    def test_estimate_iv_insufficient_data(self):
        """Test IV estimation with insufficient data."""
        from scripts.backtest.iron_condor_backtester import IronCondorBacktester

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = MagicMock()

            # Single row
            bars = pd.DataFrame({"close": [590]})
            iv = backtester.estimate_iv(bars)
            assert iv == 0.18  # Default

    def test_calculate_summary_empty(self):
        """Test summary calculation with no results."""
        from scripts.backtest.iron_condor_backtester import IronCondorBacktester, IronCondorConfig

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = IronCondorConfig()

            summary = backtester._calculate_summary([], date(2026, 1, 1), date(2026, 1, 22))
            assert summary["total_trades"] == 0
            assert "error" in summary

    def test_calculate_summary_with_results(self):
        """Test summary calculation with results."""
        from scripts.backtest.iron_condor_backtester import (
            IronCondorBacktester,
            IronCondorConfig,
            IronCondorResult,
        )

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = IronCondorConfig()

            results = [
                IronCondorResult(
                    status="profit_target", pnl=150, entry_date=date(2026, 1, 1),
                    exit_date=date(2026, 1, 8), dte_at_entry=30, dte_at_exit=7,
                    short_put_strike=575, long_put_strike=570, short_call_strike=605,
                    long_call_strike=610, credit_received=200, underlying_at_entry=590,
                    underlying_at_exit=592, put_side_pnl=100, call_side_pnl=50,
                    exit_reason="profit_target"
                ),
                IronCondorResult(
                    status="profit_target", pnl=100, entry_date=date(2026, 1, 8),
                    exit_date=date(2026, 1, 15), dte_at_entry=30, dte_at_exit=7,
                    short_put_strike=575, long_put_strike=570, short_call_strike=605,
                    long_call_strike=610, credit_received=200, underlying_at_entry=590,
                    underlying_at_exit=588, put_side_pnl=50, call_side_pnl=50,
                    exit_reason="profit_target"
                ),
                IronCondorResult(
                    status="stop_loss", pnl=-300, entry_date=date(2026, 1, 15),
                    exit_date=date(2026, 1, 18), dte_at_entry=30, dte_at_exit=12,
                    short_put_strike=575, long_put_strike=570, short_call_strike=605,
                    long_call_strike=610, credit_received=200, underlying_at_entry=590,
                    underlying_at_exit=570, put_side_pnl=-300, call_side_pnl=0,
                    exit_reason="stop_loss"
                ),
            ]

            summary = backtester._calculate_summary(results, date(2026, 1, 1), date(2026, 1, 22))

            assert summary["total_trades"] == 3
            assert summary["wins"] == 2
            assert summary["losses"] == 1
            assert summary["win_rate"] == pytest.approx(2 / 3)
            assert summary["total_pnl"] == -50
            assert summary["exit_reasons"]["profit_target"] == 2
            assert summary["exit_reasons"]["stop_loss"] == 1


class TestGenerateRAGLessons:
    """Test RAG lesson generation."""

    def test_generate_lessons_empty(self):
        """Test lesson generation with no results."""
        from scripts.backtest.iron_condor_backtester import IronCondorBacktester, IronCondorConfig

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = IronCondorConfig()

            lessons = backtester.generate_rag_lessons([], {})
            assert lessons == []

    def test_generate_lessons_with_results(self):
        """Test lesson generation with results."""
        from scripts.backtest.iron_condor_backtester import (
            IronCondorBacktester,
            IronCondorConfig,
            IronCondorResult,
        )

        with patch.object(IronCondorBacktester, "__init__", lambda x, *args, **kwargs: None):
            backtester = IronCondorBacktester.__new__(IronCondorBacktester)
            backtester.config = IronCondorConfig()

            results = [
                IronCondorResult(
                    status="profit_target", pnl=150, entry_date=date(2026, 1, 1),
                    exit_date=date(2026, 1, 8), dte_at_entry=30, dte_at_exit=7,
                    short_put_strike=575, long_put_strike=570, short_call_strike=605,
                    long_call_strike=610, credit_received=200, underlying_at_entry=590,
                    underlying_at_exit=592, put_side_pnl=100, call_side_pnl=50,
                    exit_reason="profit_target"
                ),
            ]

            summary = {
                "total_trades": 1,
                "win_rate": 1.0,
                "total_pnl": 150,
                "avg_pnl": 150,
                "profit_factor": float("inf"),
                "sharpe_ratio": 1.5,
                "start_date": "2026-01-01",
                "end_date": "2026-01-22",
                "exit_reasons": {"profit_target": 1, "stop_loss": 0, "time_exit": 0, "expired": 0},
            }

            lessons = backtester.generate_rag_lessons(results, summary)

            assert len(lessons) == 1
            assert lessons[0]["type"] == "BACKTEST_SUMMARY"
            assert "Iron Condor" in lessons[0]["title"]
            assert "100.0%" in lessons[0]["content"]  # Win rate

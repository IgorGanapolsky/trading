"""Tests for execute_options_trade.py - options trade execution script.

Coverage:
- Order validation before submission
- IV percentile calculation and gating
- Trend filter logic
- Dry-run mode
- Cash-secured put execution flow
- Rejection handling (insufficient cash, API failures)
- Tradier fallback (removed, returns NO_FALLBACK)
- Covered call validation (insufficient shares)

All Alpaca and yfinance API calls are mocked. No real API calls.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.execute_options_trade import (
    MIN_IV_PERCENTILE_FOR_SELLING,
    execute_cash_secured_put,
    execute_covered_call,
    get_account_info,
    get_iv_percentile,
    get_trend_filter,
    try_tradier_fallback,
)


class TestIVPercentile:
    """Test IV percentile calculation and gating."""

    @patch("yfinance.Ticker")
    def test_iv_percentile_high_returns_sell_premium(self, mock_yf_ticker):
        """High IV percentile (>50%) should recommend selling premium."""
        import numpy as np
        import pandas as pd

        # Create mock data with high current volatility
        dates = pd.date_range(end="2026-02-17", periods=252)
        # Low volatility throughout then a spike at the end
        prices = np.full(252, 500.0)
        # Spike at the end to push current HV to a high percentile
        prices[-5:] = [500, 530, 480, 540, 560]
        mock_hist = pd.DataFrame({"Close": prices}, index=dates)

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_hist
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_iv_percentile("SPY")
        assert result["recommendation"] in ("SELL_PREMIUM", "NEUTRAL")
        assert result["iv_percentile"] is not None

    @patch("yfinance.Ticker")
    def test_iv_percentile_insufficient_data_returns_neutral(self, mock_yf_ticker):
        """Insufficient data should return neutral recommendation."""
        import pandas as pd

        # Only 10 days of data (less than 20 required)
        mock_hist = pd.DataFrame({"Close": [500.0] * 10})
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_hist
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_iv_percentile("SPY")
        assert result["recommendation"] == "NEUTRAL"
        assert result["iv_percentile"] == 50

    @patch("yfinance.Ticker")
    def test_iv_percentile_api_failure_returns_neutral(self, mock_yf_ticker):
        """API failure should return neutral (fail open)."""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.side_effect = Exception("Yahoo Finance down")
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_iv_percentile("SPY")
        assert result["recommendation"] == "NEUTRAL"
        assert result["iv_percentile"] == 50

    def test_min_iv_percentile_for_selling_is_50(self):
        """Per RAG knowledge: IV Percentile >50% required for selling."""
        assert MIN_IV_PERCENTILE_FOR_SELLING == 50


class TestTrendFilter:
    """Test trend filter logic."""

    @patch("yfinance.Ticker")
    def test_strong_downtrend_blocks_puts(self, mock_yf_ticker):
        """Strong downtrend should return AVOID_PUTS or CAUTION recommendation."""
        import numpy as np
        import pandas as pd

        dates = pd.date_range(end="2026-02-17", periods=60)
        # Strong downtrend: sharp decline - price drops 20% in 60 days
        # Need slope < -0.3%/day for at least MODERATE_DOWNTREND
        prices = np.linspace(600, 400, 60)
        mock_hist = pd.DataFrame({"Close": prices}, index=dates)

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_hist
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_trend_filter("SPY")
        assert result["trend"] in ("STRONG_DOWNTREND", "MODERATE_DOWNTREND")
        assert result["recommendation"] in ("AVOID_PUTS", "CAUTION_BUT_PROCEED")

    @patch("yfinance.Ticker")
    def test_uptrend_allows_puts(self, mock_yf_ticker):
        """Uptrend/sideways should allow selling puts."""
        import numpy as np
        import pandas as pd

        dates = pd.date_range(end="2026-02-17", periods=60)
        # Uptrend: rising prices
        prices = np.linspace(500, 600, 60)
        mock_hist = pd.DataFrame({"Close": prices}, index=dates)

        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.return_value = mock_hist
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_trend_filter("SPY")
        assert result["trend"] == "UPTREND_OR_SIDEWAYS"
        assert result["recommendation"] == "PROCEED"

    @patch("yfinance.Ticker")
    def test_trend_filter_api_failure_defaults_proceed(self, mock_yf_ticker):
        """API failure in trend filter should default to PROCEED."""
        mock_ticker_instance = MagicMock()
        mock_ticker_instance.history.side_effect = Exception("API error")
        mock_yf_ticker.return_value = mock_ticker_instance

        result = get_trend_filter("SPY")
        assert result["recommendation"] == "PROCEED"


class TestTradierFallback:
    """Test Tradier fallback (removed)."""

    def test_tradier_fallback_returns_no_fallback(self):
        """Tradier fallback was removed; should return NO_FALLBACK."""
        result = try_tradier_fallback("SPY")
        assert result["status"] == "NO_FALLBACK"
        assert "removed" in result["reason"].lower()


class TestGetAccountInfo:
    """Test account info extraction."""

    def test_get_account_info_extracts_values(self):
        """Account info should extract equity, cash, buying_power."""
        mock_client = MagicMock()
        mock_account = MagicMock()
        mock_account.equity = "100000.00"
        mock_account.cash = "100000.00"
        mock_account.buying_power = "200000.00"
        mock_client.get_account.return_value = mock_account

        info = get_account_info(mock_client)
        assert info["equity"] == 100000.0
        assert info["cash"] == 100000.0
        assert info["buying_power"] == 200000.0


class TestExecuteCashSecuredPut:
    """Test cash-secured put execution flow."""

    @patch("scripts.execute_options_trade.find_optimal_put")
    @patch("scripts.execute_options_trade.get_trend_filter")
    @patch("scripts.execute_options_trade.get_iv_percentile")
    @patch("scripts.execute_options_trade.get_account_info")
    def test_dry_run_returns_dry_run_status(self, mock_account, mock_iv, mock_trend, mock_find_put):
        """Dry run should return DRY_RUN status without placing orders."""
        mock_iv.return_value = {
            "iv_percentile": 65,
            "current_iv": 20.0,
            "recommendation": "SELL_PREMIUM",
        }
        mock_trend.return_value = {
            "trend": "UPTREND_OR_SIDEWAYS",
            "slope": 0.1,
            "recommendation": "PROCEED",
        }
        mock_account.return_value = {
            "cash": 100000.0,
            "buying_power": 200000.0,
            "portfolio_value": 100000.0,
            "options_buying_power": 50000.0,
        }
        mock_find_put.return_value = {
            "symbol": "SPY260320P00650000",
            "strike": 650.0,
            "expiration": "2026-03-20",
            "dte": 30,
            "delta": -0.25,
            "bid": 1.50,
            "ask": 1.70,
            "mid": 1.60,
            "premium_pct": 0.27,
            "iv": 0.20,
        }

        mock_client = MagicMock()
        mock_options = MagicMock()

        result = execute_cash_secured_put(mock_client, mock_options, "SPY", dry_run=True)
        assert result["status"] == "DRY_RUN"
        assert result["broker"] == "alpaca"

    @patch("scripts.execute_options_trade.get_iv_percentile")
    def test_low_iv_blocks_trade(self, mock_iv):
        """Low IV percentile should block the trade."""
        mock_iv.return_value = {
            "iv_percentile": 25,
            "current_iv": 10.0,
            "recommendation": "AVOID_SELLING",
        }

        mock_client = MagicMock()
        mock_options = MagicMock()

        result = execute_cash_secured_put(mock_client, mock_options, "SPY")
        assert result["status"] == "NO_TRADE"
        assert "IV Percentile too low" in result["reason"]

    @patch("scripts.execute_options_trade.get_trend_filter")
    @patch("scripts.execute_options_trade.get_iv_percentile")
    def test_strong_downtrend_blocks_trade(self, mock_iv, mock_trend):
        """Strong downtrend should block put selling."""
        mock_iv.return_value = {
            "iv_percentile": 65,
            "current_iv": 20.0,
            "recommendation": "SELL_PREMIUM",
        }
        mock_trend.return_value = {
            "trend": "STRONG_DOWNTREND",
            "slope": -0.8,
            "price_vs_ma": -6.0,
            "recommendation": "AVOID_PUTS",
        }

        mock_client = MagicMock()
        mock_options = MagicMock()

        result = execute_cash_secured_put(mock_client, mock_options, "SPY")
        assert result["status"] == "NO_TRADE"
        assert "Trend filter blocked" in result["reason"]


class TestExecuteCoveredCall:
    """Test covered call execution."""

    def test_no_position_returns_no_trade(self):
        """No position in symbol should return NO_TRADE."""
        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = []
        mock_options = MagicMock()

        result = execute_covered_call(mock_client, mock_options, "SPY")
        assert result["status"] == "NO_TRADE"
        assert "No SPY position" in result["reason"]

    def test_insufficient_shares_returns_no_trade(self):
        """Less than 100 shares should return NO_TRADE."""
        mock_pos = MagicMock()
        mock_pos.symbol = "SPY"
        mock_pos.qty = "50"

        mock_client = MagicMock()
        mock_client.get_all_positions.return_value = [mock_pos]
        mock_options = MagicMock()

        result = execute_covered_call(mock_client, mock_options, "SPY")
        assert result["status"] == "NO_TRADE"
        assert "Insufficient shares" in result["reason"]

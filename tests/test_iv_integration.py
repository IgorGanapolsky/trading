"""
Tests for IV Data Integration Module

Tests cover:
- IVDataFetcher: option chain fetching, IV calculations, metrics
- VolatilitySurface: surface building, interpolation, arbitrage detection
- IVAlerts: alert triggering and formatting
- BlackScholesIV: IV calculation from option prices

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.options.iv_data_integration import (
    BlackScholesIV,
    IVAlerts,
    IVDataFetcher,
    IVMetrics,
    IVRegime,
    VolatilitySurface,
    VolatilitySurfacePoint,
)

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mock_alpaca_client():
    """Mock AlpacaOptionsClient"""
    with patch("src.options.iv_data_integration.AlpacaOptionsClient") as mock_client:
        # Mock get_option_chain response
        mock_instance = mock_client.return_value
        mock_instance.get_option_chain.return_value = [
            {
                "symbol": "SPY251219C00600000",
                "latest_quote_bid": 1.50,
                "latest_quote_ask": 1.55,
                "latest_trade_price": 1.52,
                "implied_volatility": 0.18,
                "greeks": {
                    "delta": 0.52,
                    "gamma": 0.015,
                    "theta": -0.05,
                    "vega": 0.12,
                    "rho": 0.02,
                },
            },
            {
                "symbol": "SPY251219P00600000",
                "latest_quote_bid": 1.45,
                "latest_quote_ask": 1.50,
                "latest_trade_price": 1.48,
                "implied_volatility": 0.20,
                "greeks": {
                    "delta": -0.48,
                    "gamma": 0.015,
                    "theta": -0.05,
                    "vega": 0.12,
                    "rho": -0.02,
                },
            },
            {
                "symbol": "SPY260116C00600000",
                "latest_quote_bid": 2.10,
                "latest_quote_ask": 2.15,
                "latest_trade_price": 2.12,
                "implied_volatility": 0.22,
                "greeks": {
                    "delta": 0.55,
                    "gamma": 0.012,
                    "theta": -0.04,
                    "vega": 0.15,
                    "rho": 0.03,
                },
            },
        ]
        yield mock_client


@pytest.fixture
def mock_iv_history(tmp_path):
    """Create mock IV history file"""
    iv_cache_dir = tmp_path / "iv_cache"
    iv_cache_dir.mkdir()

    iv_history = []
    base_date = datetime.now() - timedelta(days=252)
    for i in range(252):
        iv_history.append(
            {
                "date": (base_date + timedelta(days=i)).strftime("%Y-%m-%d"),
                "iv": 0.15 + 0.1 * np.sin(i / 50),  # Oscillating IV
                "price": 580.0 + 20 * np.sin(i / 50),
            }
        )

    history_file = iv_cache_dir / "SPY_iv_history.json"
    with open(history_file, "w") as f:
        json.dump(iv_history, f)

    return str(iv_cache_dir)


@pytest.fixture
def fetcher(mock_alpaca_client, mock_iv_history):
    """IVDataFetcher with mocked dependencies"""
    return IVDataFetcher(paper=True, cache_dir=mock_iv_history, cache_ttl_minutes=60)


# ============================================================================
# BLACK-SCHOLES IV TESTS
# ============================================================================


class TestBlackScholesIV:
    """Test Black-Scholes IV calculation"""

    def test_call_price_calculation(self):
        """Test theoretical call price calculation"""
        S = 100.0  # Stock price
        K = 100.0  # Strike (ATM)
        T = 0.25  # 3 months
        r = 0.05  # 5% risk-free rate
        sigma = 0.20  # 20% IV

        price = BlackScholesIV.calculate_call_price(S, K, T, r, sigma)

        # ATM call with 20% IV should be around $4-5
        assert 3.0 < price < 6.0
        assert isinstance(price, float)

    def test_put_price_calculation(self):
        """Test theoretical put price calculation"""
        S = 100.0
        K = 100.0
        T = 0.25
        r = 0.05
        sigma = 0.20

        price = BlackScholesIV.calculate_put_price(S, K, T, r, sigma)

        # ATM put should be similar to call (put-call parity)
        call_price = BlackScholesIV.calculate_call_price(S, K, T, r, sigma)
        assert abs(price - call_price) < 1.0  # Within $1 due to interest rate

    def test_iv_calculation_from_call_price(self):
        """Test IV calculation from option price"""
        S = 100.0
        K = 100.0
        T = 0.25
        r = 0.05
        target_iv = 0.25  # 25%

        # Calculate theoretical price at 25% IV
        option_price = BlackScholesIV.calculate_call_price(S, K, T, r, target_iv)

        # Calculate IV back from price
        calculated_iv = BlackScholesIV.calculate_iv(option_price, S, K, T, r, "CALL")

        assert calculated_iv is not None
        assert abs(calculated_iv - target_iv) < 0.01  # Within 1%

    def test_iv_calculation_from_put_price(self):
        """Test IV calculation for puts"""
        S = 100.0
        K = 105.0  # OTM put
        T = 0.5
        r = 0.05
        target_iv = 0.30

        option_price = BlackScholesIV.calculate_put_price(S, K, T, r, target_iv)
        calculated_iv = BlackScholesIV.calculate_iv(option_price, S, K, T, r, "PUT")

        assert calculated_iv is not None
        assert abs(calculated_iv - target_iv) < 0.01

    def test_iv_calculation_edge_cases(self):
        """Test IV calculation edge cases"""
        # Zero time to expiration
        iv = BlackScholesIV.calculate_iv(5.0, 100.0, 100.0, 0.0, 0.05, "CALL")
        assert iv is None

        # Zero option price
        iv = BlackScholesIV.calculate_iv(0.0, 100.0, 100.0, 0.25, 0.05, "CALL")
        assert iv is None

        # Deep ITM (price > intrinsic value is impossible)
        iv = BlackScholesIV.calculate_iv(50.0, 100.0, 90.0, 0.25, 0.05, "CALL")
        # Should still return a value (high IV)
        assert iv is None or iv > 0


# ============================================================================
# IV DATA FETCHER TESTS
# ============================================================================


class TestIVDataFetcher:
    """Test IVDataFetcher functionality"""

    def test_initialization(self, fetcher):
        """Test fetcher initializes correctly"""
        assert fetcher is not None
        assert fetcher.alpaca_client is not None
        assert os.path.exists(fetcher.cache_dir)

    def test_get_option_chain(self, fetcher):
        """Test option chain retrieval and parsing"""
        chain = fetcher.get_option_chain("SPY", use_cache=False)

        assert len(chain) > 0
        assert all(isinstance(c, dict) for c in chain)

        # Check required fields
        required_fields = ["symbol", "strike", "expiration", "dte", "option_type", "iv"]
        for contract in chain:
            for field in required_fields:
                assert field in contract

    def test_option_symbol_parsing(self, fetcher):
        """Test OCC option symbol parsing"""
        # SPY Dec 19, 2025 $600 Call
        result = fetcher._parse_option_symbol("SPY251219C00600000")
        assert result is not None
        strike, exp_date, option_type = result
        assert strike == 600.0
        assert exp_date.year == 2025
        assert exp_date.month == 12
        assert exp_date.day == 19
        assert option_type == "CALL"

        # Test PUT
        result = fetcher._parse_option_symbol("AAPL260116P00180000")
        assert result is not None
        strike, exp_date, option_type = result
        assert strike == 180.0
        assert option_type == "PUT"

    def test_atm_iv_calculation(self, fetcher):
        """Test ATM IV retrieval"""
        atm_iv = fetcher.get_atm_iv("SPY", dte_target=30)

        assert atm_iv is not None
        assert 0.0 < atm_iv < 2.0  # Reasonable IV range (0-200%)

    def test_iv_percentile_calculation(self, fetcher):
        """Test IV percentile calculation"""
        # Mock current IV
        with patch.object(fetcher, "get_atm_iv", return_value=0.20):
            percentile = fetcher.calculate_iv_percentile("SPY", lookback_days=252)

            assert 0 <= percentile <= 100
            # With oscillating history (0.15-0.25), 0.20 should be around 50th percentile
            assert 40 <= percentile <= 60

    def test_iv_skew_calculation(self, fetcher):
        """Test put/call IV skew calculation"""
        skew = fetcher.get_iv_skew("SPY", dte_target=30)

        # Skew should be negative (puts more expensive) or near zero
        assert -0.5 < skew < 0.5
        # In our mock data, put IV (0.20) > call IV (0.18), so skew should be positive
        assert skew > 0

    def test_term_structure_calculation(self, fetcher):
        """Test term structure retrieval"""
        term_structure = fetcher.get_term_structure("SPY")

        assert isinstance(term_structure, dict)
        assert len(term_structure) > 0

        # Keys should be DTEs (integers)
        assert all(isinstance(k, int) for k in term_structure)
        # Values should be IVs (floats)
        assert all(isinstance(v, float) for v in term_structure.values())

    def test_term_structure_slope(self, fetcher):
        """Test term structure slope calculation"""
        # Normal term structure (increasing)
        term_structure = {7: 0.18, 14: 0.19, 30: 0.21, 60: 0.23}
        slope = fetcher.calculate_term_structure_slope(term_structure)
        assert slope > 0  # Positive slope

        # Inverted term structure (fear)
        inverted = {7: 0.25, 14: 0.23, 30: 0.20, 60: 0.18}
        slope = fetcher.calculate_term_structure_slope(inverted)
        assert slope < 0  # Negative slope

    def test_iv_regime_detection(self, fetcher):
        """Test IV regime classification"""
        # Mock different percentiles
        with patch.object(fetcher, "calculate_iv_percentile") as mock_percentile:
            # Extreme low
            mock_percentile.return_value = 5.0
            regime = fetcher.detect_iv_regime("SPY")
            assert regime == IVRegime.EXTREME_LOW

            # Low
            mock_percentile.return_value = 25.0
            regime = fetcher.detect_iv_regime("SPY")
            assert regime == IVRegime.LOW

            # Normal
            mock_percentile.return_value = 50.0
            regime = fetcher.detect_iv_regime("SPY")
            assert regime == IVRegime.NORMAL

            # High
            mock_percentile.return_value = 75.0
            regime = fetcher.detect_iv_regime("SPY")
            assert regime == IVRegime.HIGH

            # Extreme high
            mock_percentile.return_value = 95.0
            regime = fetcher.detect_iv_regime("SPY")
            assert regime == IVRegime.EXTREME_HIGH

    def test_comprehensive_iv_metrics(self, fetcher):
        """Test get_iv_metrics returns complete metrics"""
        metrics = fetcher.get_iv_metrics("SPY", use_cache=False)

        assert isinstance(metrics, IVMetrics)
        assert metrics.symbol == "SPY"
        assert metrics.current_iv >= 0
        assert 0 <= metrics.iv_percentile <= 100
        assert 0 <= metrics.iv_rank <= 100
        assert metrics.iv_regime in IVRegime
        assert metrics.recommendation in ["BUY_VOL", "SELL_VOL", "NEUTRAL"]

    def test_iv_snapshot_saving(self, fetcher, tmp_path):
        """Test saving IV snapshots for history"""
        # Use temp directory
        fetcher.cache_dir = str(tmp_path)

        # Save snapshot
        fetcher.save_iv_snapshot("TEST", 0.25, 100.0)

        # Verify file exists
        snapshot_file = tmp_path / "TEST_iv_history.json"
        assert snapshot_file.exists()

        # Load and verify
        with open(snapshot_file) as f:
            data = json.load(f)

        assert len(data) == 1
        assert data[0]["iv"] == 0.25
        assert data[0]["price"] == 100.0

        # Save another snapshot
        fetcher.save_iv_snapshot("TEST", 0.27, 102.0)

        with open(snapshot_file) as f:
            data = json.load(f)

        assert len(data) == 2


# ============================================================================
# VOLATILITY SURFACE TESTS
# ============================================================================


class TestVolatilitySurface:
    """Test VolatilitySurface functionality"""

    def test_surface_building(self, fetcher):
        """Test volatility surface construction"""
        surface_builder = VolatilitySurface(fetcher)
        surface = surface_builder.build_surface("SPY")

        assert len(surface) > 0
        assert all(isinstance(p, VolatilitySurfacePoint) for p in surface)

        # Check fields
        for point in surface:
            assert point.strike > 0
            assert point.dte >= 0
            assert point.iv > 0
            assert point.option_type in ["CALL", "PUT"]

    def test_iv_interpolation(self, fetcher):
        """Test IV interpolation"""
        surface_builder = VolatilitySurface(fetcher)

        # Create simple surface
        surface = [
            VolatilitySurfacePoint(strike=590, dte=7, iv=0.18),
            VolatilitySurfacePoint(strike=600, dte=7, iv=0.19),
            VolatilitySurfacePoint(strike=610, dte=7, iv=0.20),
            VolatilitySurfacePoint(strike=590, dte=30, iv=0.20),
            VolatilitySurfacePoint(strike=600, dte=30, iv=0.21),
            VolatilitySurfacePoint(strike=610, dte=30, iv=0.22),
        ]

        # Interpolate at (595, 15)
        interp_iv = surface_builder.interpolate_iv(surface, target_strike=595, target_dte=15)

        assert interp_iv is not None
        assert 0.18 < interp_iv < 0.22  # Should be within range

    def test_arbitrage_detection(self, fetcher):
        """Test arbitrage opportunity detection"""
        surface_builder = VolatilitySurface(fetcher)

        # Create surface with calendar arbitrage (front > back)
        surface = [
            VolatilitySurfacePoint(strike=600, dte=7, iv=0.30),  # Front month high
            VolatilitySurfacePoint(strike=600, dte=30, iv=0.20),  # Back month low (arbitrage!)
        ]

        opportunities = surface_builder.detect_arbitrage_opportunities(surface)

        assert len(opportunities) > 0
        assert opportunities[0]["type"] == "calendar_spread_arbitrage"
        assert opportunities[0]["strike"] == 600


# ============================================================================
# IV ALERTS TESTS
# ============================================================================


class TestIVAlerts:
    """Test IVAlerts functionality"""

    def test_high_percentile_alert(self, fetcher):
        """Test high IV percentile alert triggering"""
        alerts_system = IVAlerts(fetcher)

        # Mock high percentile
        with patch.object(fetcher, "get_iv_metrics") as mock_metrics:
            mock_metrics.return_value = IVMetrics(
                symbol="SPY",
                timestamp=datetime.now(),
                current_iv=0.30,
                current_price=600.0,
                atm_iv=0.30,
                iv_percentile=85.0,  # High
                iv_rank=80.0,
                mean_iv_252d=0.20,
                std_iv_252d=0.05,
                iv_52w_high=0.35,
                iv_52w_low=0.15,
                iv_regime=IVRegime.HIGH,
                put_call_iv_skew=0.02,
                term_structure_slope=0.001,
                recommendation="SELL_VOL",
            )

            alerts = alerts_system.check_all_alerts("SPY")

            # Should trigger SELL_VOL alert
            assert len(alerts) > 0
            sell_vol_alerts = [a for a in alerts if a.alert_type == "SELL_VOL"]
            assert len(sell_vol_alerts) == 1
            assert sell_vol_alerts[0].urgency in ["HIGH", "CRITICAL"]

    def test_low_percentile_alert(self, fetcher):
        """Test low IV percentile alert triggering"""
        alerts_system = IVAlerts(fetcher)

        with patch.object(fetcher, "get_iv_metrics") as mock_metrics:
            mock_metrics.return_value = IVMetrics(
                symbol="SPY",
                timestamp=datetime.now(),
                current_iv=0.12,
                current_price=600.0,
                atm_iv=0.12,
                iv_percentile=15.0,  # Low
                iv_rank=20.0,
                mean_iv_252d=0.20,
                std_iv_252d=0.05,
                iv_52w_high=0.35,
                iv_52w_low=0.10,
                iv_regime=IVRegime.LOW,
                put_call_iv_skew=-0.02,
                term_structure_slope=0.001,
                recommendation="BUY_VOL",
            )

            alerts = alerts_system.check_all_alerts("SPY")

            buy_vol_alerts = [a for a in alerts if a.alert_type == "BUY_VOL"]
            assert len(buy_vol_alerts) == 1

    def test_skew_alert(self, fetcher):
        """Test extreme IV skew alert"""
        alerts_system = IVAlerts(fetcher)

        with patch.object(fetcher, "get_iv_metrics") as mock_metrics:
            mock_metrics.return_value = IVMetrics(
                symbol="SPY",
                timestamp=datetime.now(),
                current_iv=0.20,
                current_price=600.0,
                atm_iv=0.20,
                iv_percentile=50.0,
                iv_rank=50.0,
                mean_iv_252d=0.20,
                std_iv_252d=0.05,
                iv_52w_high=0.30,
                iv_52w_low=0.15,
                iv_regime=IVRegime.NORMAL,
                put_call_iv_skew=-0.08,  # Extreme skew
                term_structure_slope=0.001,
                recommendation="NEUTRAL",
            )

            alerts = alerts_system.check_all_alerts("SPY")

            skew_alerts = [a for a in alerts if a.alert_type == "IV_SKEW"]
            assert len(skew_alerts) == 1

    def test_term_inversion_alert(self, fetcher):
        """Test term structure inversion alert"""
        alerts_system = IVAlerts(fetcher)

        with patch.object(fetcher, "get_iv_metrics") as mock_metrics:
            mock_metrics.return_value = IVMetrics(
                symbol="SPY",
                timestamp=datetime.now(),
                current_iv=0.25,
                current_price=600.0,
                atm_iv=0.25,
                iv_percentile=60.0,
                iv_rank=65.0,
                mean_iv_252d=0.20,
                std_iv_252d=0.05,
                iv_52w_high=0.30,
                iv_52w_low=0.15,
                iv_regime=IVRegime.NORMAL,
                put_call_iv_skew=-0.02,
                term_structure_slope=-0.002,  # Inverted!
                recommendation="SELL_VOL",
            )

            alerts = alerts_system.check_all_alerts("SPY")

            inversion_alerts = [a for a in alerts if a.alert_type == "TERM_INVERSION"]
            assert len(inversion_alerts) == 1
            assert inversion_alerts[0].urgency == "HIGH"

    def test_alert_report_formatting(self, fetcher):
        """Test alert report formatting"""
        alerts_system = IVAlerts(fetcher)

        with patch.object(fetcher, "get_iv_metrics") as mock_metrics:
            mock_metrics.return_value = IVMetrics(
                symbol="SPY",
                timestamp=datetime.now(),
                current_iv=0.30,
                current_price=600.0,
                atm_iv=0.30,
                iv_percentile=85.0,
                iv_rank=80.0,
                mean_iv_252d=0.20,
                std_iv_252d=0.05,
                iv_52w_high=0.35,
                iv_52w_low=0.15,
                iv_regime=IVRegime.HIGH,
                put_call_iv_skew=0.02,
                term_structure_slope=0.001,
                recommendation="SELL_VOL",
            )

            alerts = alerts_system.check_all_alerts("SPY")
            report = alerts_system.format_alert_report(alerts)

            assert isinstance(report, str)
            assert "IV TRADING ALERTS" in report
            assert "SPY" in report
            assert "SELL_VOL" in report


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestIntegration:
    """End-to-end integration tests"""

    def test_full_iv_analysis_workflow(self, fetcher):
        """Test complete IV analysis workflow"""
        symbol = "SPY"

        # Step 1: Get metrics
        metrics = fetcher.get_iv_metrics(symbol)
        assert metrics.symbol == symbol

        # Step 2: Check alerts
        alerts_system = IVAlerts(fetcher)
        alerts = alerts_system.check_all_alerts(symbol)
        # Alerts may or may not trigger depending on mock data
        assert isinstance(alerts, list)

        # Step 3: Build surface
        surface_builder = VolatilitySurface(fetcher)
        surface = surface_builder.build_surface(symbol)
        assert len(surface) > 0

        # Step 4: Check for arbitrage
        opportunities = surface_builder.detect_arbitrage_opportunities(surface)
        assert isinstance(opportunities, list)


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

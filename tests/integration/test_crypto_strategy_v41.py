"""
Test Crypto Strategy v4.1 - Trend + Momentum Confirmation

Tests to prevent catching falling knives (LL-040).
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta


def calc_rsi(prices: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI (Relative Strength Index)"""
    delta = prices.diff()
    gain = delta.where(delta > 0, 0).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    return 100 - (100 / (1 + rs))


def is_valid_entry(price: float, ma50: float, rsi: float) -> bool:
    """
    v4.1 Entry Logic: Both conditions must be true
    - price > 50-day MA (trend confirmation)
    - RSI > 50 (momentum confirmation)
    """
    above_ma = price > ma50
    rsi_bullish = rsi > 50
    return above_ma and rsi_bullish


class TestRSICalculation:
    """Test RSI calculation accuracy"""

    def test_rsi_uptrend_bullish(self):
        """RSI should be > 50 in uptrend"""
        # Create uptrending prices
        prices = pd.Series([100 + i * 2 for i in range(60)])
        rsi = calc_rsi(prices)
        assert rsi.iloc[-1] > 50, f"RSI should be bullish in uptrend, got {rsi.iloc[-1]}"

    def test_rsi_downtrend_bearish(self):
        """RSI should be < 50 in downtrend"""
        # Create downtrending prices
        prices = pd.Series([200 - i * 2 for i in range(60)])
        rsi = calc_rsi(prices)
        assert rsi.iloc[-1] < 50, f"RSI should be bearish in downtrend, got {rsi.iloc[-1]}"

    def test_rsi_bounds(self):
        """RSI should be between 0 and 100"""
        np.random.seed(42)
        prices = pd.Series([100 + np.random.randn() * 5 for _ in range(60)])
        rsi = calc_rsi(prices)
        valid_rsi = rsi.dropna()
        assert valid_rsi.min() >= 0, "RSI should not be below 0"
        assert valid_rsi.max() <= 100, "RSI should not be above 100"


class TestEntryLogic:
    """Test v4.1 entry logic - prevent catching falling knives"""

    def test_both_conditions_required(self):
        """Entry requires BOTH MA above AND RSI bullish"""
        # All combinations
        assert is_valid_entry(price=100, ma50=90, rsi=55) == True   # Both true
        assert is_valid_entry(price=100, ma50=110, rsi=55) == False  # MA false
        assert is_valid_entry(price=100, ma50=90, rsi=45) == False   # RSI false
        assert is_valid_entry(price=100, ma50=110, rsi=45) == False  # Both false

    def test_falling_knife_rejected(self):
        """Should NOT buy in downtrend (LL-040)"""
        # Simulating falling knife: price below MA, RSI < 50
        price = 88000  # BTC example
        ma50 = 96000   # Price below MA
        rsi = 42       # Bearish momentum

        assert is_valid_entry(price, ma50, rsi) == False, \
            "Should reject falling knife (below MA + weak RSI)"

    def test_weak_rally_rejected(self):
        """Should NOT buy weak rally (price above MA but RSI < 50)"""
        price = 100
        ma50 = 95    # Price above MA
        rsi = 48     # Weak momentum

        assert is_valid_entry(price, ma50, rsi) == False, \
            "Should reject weak rally (RSI < 50 even if above MA)"

    def test_confirmed_uptrend_accepted(self):
        """Should buy confirmed uptrend (both signals aligned)"""
        price = 105000
        ma50 = 95000   # Price above MA
        rsi = 58       # Bullish momentum

        assert is_valid_entry(price, ma50, rsi) == True, \
            "Should accept confirmed uptrend"


class TestSkipReasons:
    """Test proper skip reason differentiation"""

    def get_skip_reason(self, trend_data: dict) -> str:
        """Determine skip reason based on trend data"""
        above_ma_only = [k for k, v in trend_data.items() if v.get("above_ma")]
        rsi_only = [k for k, v in trend_data.items() if v.get("rsi_bullish")]

        if not above_ma_only:
            return "All below 50-day MA"
        elif not rsi_only:
            return "All RSI below 50"
        else:
            return "No trend+momentum alignment"

    def test_skip_reason_below_ma(self):
        """Skip reason should identify MA failure"""
        trend_data = {
            "BTC-USD": {"above_ma": False, "rsi_bullish": True},
            "ETH-USD": {"above_ma": False, "rsi_bullish": False},
        }
        assert self.get_skip_reason(trend_data) == "All below 50-day MA"

    def test_skip_reason_weak_rsi(self):
        """Skip reason should identify RSI failure"""
        trend_data = {
            "BTC-USD": {"above_ma": True, "rsi_bullish": False},
            "ETH-USD": {"above_ma": False, "rsi_bullish": False},
        }
        assert self.get_skip_reason(trend_data) == "All RSI below 50"

    def test_skip_reason_no_alignment(self):
        """Skip reason should identify misalignment"""
        trend_data = {
            "BTC-USD": {"above_ma": True, "rsi_bullish": False},
            "ETH-USD": {"above_ma": False, "rsi_bullish": True},
        }
        assert self.get_skip_reason(trend_data) == "No trend+momentum alignment"


class TestFearGreedSizing:
    """Test Fear & Greed used for sizing only, NOT timing"""

    def get_size_multiplier(self, fear_greed: int) -> float:
        """Get position size multiplier based on Fear & Greed"""
        if fear_greed <= 25:
            return 1.5   # Extreme fear = larger position
        elif fear_greed <= 40:
            return 1.25  # Fear = slightly larger
        elif fear_greed <= 60:
            return 1.0   # Neutral = normal
        elif fear_greed <= 75:
            return 0.75  # Greed = smaller
        else:
            return 0.0   # Extreme greed = skip

    def test_extreme_fear_increases_size(self):
        """Extreme fear should increase position, not trigger entry"""
        mult = self.get_size_multiplier(20)
        assert mult == 1.5, "Extreme fear should give 1.5x multiplier"

    def test_extreme_greed_skips(self):
        """Extreme greed should skip entirely"""
        mult = self.get_size_multiplier(80)
        assert mult == 0.0, "Extreme greed should skip (0x multiplier)"

    def test_sizing_independent_of_entry(self):
        """
        CRITICAL: F&G affects SIZE, not ENTRY decision.
        Entry is determined by MA + RSI only.
        """
        # Even with extreme fear (F&G=15), should NOT enter if below MA
        fear_greed = 15
        price = 88000
        ma50 = 96000
        rsi = 42

        size_mult = self.get_size_multiplier(fear_greed)
        can_enter = is_valid_entry(price, ma50, rsi)

        assert size_mult == 1.5, "Should have 1.5x size in extreme fear"
        assert can_enter == False, "Should NOT enter despite fear (below MA + weak RSI)"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

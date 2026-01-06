#!/usr/bin/env python3
"""
Tests for CoreStrategy - MACD calculation and R:R ratio fixes.

Created: Jan 6, 2026
Coverage: Tests for fixes in commit a087da4
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestCoreStrategyParameters:
    """Test strategy parameters are correctly configured."""

    def test_take_profit_is_six_percent(self):
        """TAKE_PROFIT_PCT should be 6% (was 4%, fixed Jan 6 2026)."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert strategy.TAKE_PROFIT_PCT == 0.06, (
            f"TAKE_PROFIT_PCT should be 0.06 (6%), got {strategy.TAKE_PROFIT_PCT}"
        )

    def test_stop_loss_is_two_percent(self):
        """STOP_LOSS_PCT should be 2%."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert strategy.STOP_LOSS_PCT == 0.02, (
            f"STOP_LOSS_PCT should be 0.02 (2%), got {strategy.STOP_LOSS_PCT}"
        )

    def test_rr_ratio_is_three_to_one(self):
        """R:R ratio should be 3:1 (was 2:1, fixed Jan 6 2026)."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        rr_ratio = strategy.TAKE_PROFIT_PCT / strategy.STOP_LOSS_PCT
        assert rr_ratio == 3.0, f"R:R ratio should be 3.0, got {rr_ratio}"

    def test_positive_expectancy_at_thirty_percent_win_rate(self):
        """Strategy should have positive expectancy at 30% win rate."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        win_rate = 0.30

        # Expected value = (win% * TP) - (loss% * SL)
        expected_value = (
            win_rate * strategy.TAKE_PROFIT_PCT - (1 - win_rate) * strategy.STOP_LOSS_PCT
        )

        assert expected_value > 0, (
            f"Expected value at 30% win rate should be positive, got {expected_value}"
        )

    def test_breakeven_at_twentyfive_percent_win_rate(self):
        """Strategy should break even at 25% win rate (3:1 R:R)."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        win_rate = 0.25

        expected_value = (
            win_rate * strategy.TAKE_PROFIT_PCT - (1 - win_rate) * strategy.STOP_LOSS_PCT
        )

        # Should be approximately 0 (break-even)
        assert abs(expected_value) < 0.001, (
            f"Expected value at 25% win rate should be ~0, got {expected_value}"
        )


class TestMACDCalculation:
    """Test MACD calculation is correct."""

    def test_macd_returns_three_values(self):
        """MACD calculation should return (macd_line, signal_line, histogram)."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        # Generate sample price data (50 periods minimum for MACD)
        prices = [100 + i * 0.5 for i in range(50)]

        result = strategy._calculate_macd(prices)

        assert len(result) == 3, f"MACD should return 3 values, got {len(result)}"
        macd_line, signal_line, histogram = result
        assert isinstance(macd_line, (int, float)), "MACD line should be numeric"
        assert isinstance(signal_line, (int, float)), "Signal line should be numeric"
        assert isinstance(histogram, (int, float)), "Histogram should be numeric"

    def test_macd_histogram_equals_macd_minus_signal(self):
        """Histogram should equal MACD line minus signal line."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        prices = [100 + i * 0.5 for i in range(50)]

        macd_line, signal_line, histogram = strategy._calculate_macd(prices)

        expected_histogram = macd_line - signal_line
        assert abs(histogram - expected_histogram) < 0.0001, (
            f"Histogram {histogram} should equal MACD {macd_line} - Signal {signal_line}"
        )

    def test_signal_line_not_simple_multiplier(self):
        """Signal line should NOT be macd_line * 0.9 (old broken implementation)."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        prices = [100 + i * 0.5 for i in range(50)]

        macd_line, signal_line, histogram = strategy._calculate_macd(prices)

        # Old broken implementation used macd_line * 0.9
        broken_signal = macd_line * 0.9

        # Signal line should be different from the broken implementation
        # (unless by coincidence, which is rare)
        # This is a regression test for the Jan 6 2026 fix
        if len(prices) >= strategy.MACD_SLOW + strategy.MACD_SIGNAL:
            # Only test when we have enough data for proper signal line
            assert signal_line != broken_signal or abs(signal_line) < 0.001, (
                "Signal line appears to use old broken implementation (macd * 0.9)"
            )

    def test_macd_with_uptrend_data(self):
        """MACD should be positive in uptrend."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        # Strong uptrend: each price higher than previous
        prices = [100 + i * 2 for i in range(50)]

        macd_line, signal_line, histogram = strategy._calculate_macd(prices)

        # In strong uptrend, MACD should be positive
        assert macd_line > 0, f"MACD should be positive in uptrend, got {macd_line}"

    def test_macd_with_downtrend_data(self):
        """MACD should be negative in downtrend."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        # Strong downtrend: each price lower than previous
        prices = [200 - i * 2 for i in range(50)]

        macd_line, signal_line, histogram = strategy._calculate_macd(prices)

        # In strong downtrend, MACD should be negative
        assert macd_line < 0, f"MACD should be negative in downtrend, got {macd_line}"


class TestCoreStrategyInitialization:
    """Test strategy initialization."""

    def test_default_universe(self):
        """Strategy should have default universe."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert len(strategy.universe) > 0, "Strategy should have default universe"

    def test_custom_universe(self):
        """Strategy should accept custom universe."""
        from src.strategies.core_strategy import CoreStrategy

        custom = ["AAPL", "MSFT"]
        strategy = CoreStrategy(universe=custom)
        assert strategy.universe == custom

    def test_paper_mode_default(self):
        """Strategy should default to paper mode."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert strategy.paper is True

    def test_macd_parameters(self):
        """Strategy should have correct MACD parameters."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert strategy.MACD_FAST == 12, "MACD fast period should be 12"
        assert strategy.MACD_SLOW == 26, "MACD slow period should be 26"
        assert strategy.MACD_SIGNAL == 9, "MACD signal period should be 9"


class TestStrategyName:
    """Test strategy identification."""

    def test_strategy_name(self):
        """Strategy should have correct name."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        assert strategy.name == "core_momentum"

    def test_get_config_returns_dict(self):
        """get_config should return configuration dict."""
        from src.strategies.core_strategy import CoreStrategy

        strategy = CoreStrategy()
        config = strategy.get_config()

        assert isinstance(config, dict)
        assert "name" in config
        assert "macd" in config
        assert config["macd"]["fast"] == 12
        assert config["macd"]["slow"] == 26
        assert config["macd"]["signal"] == 9


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

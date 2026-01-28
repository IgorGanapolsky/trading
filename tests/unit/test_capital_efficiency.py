"""Tests for capital_efficiency.py - Strategy Viability by Account Size.

This module tests the capital efficiency calculator that determines
which options strategies are viable based on account size.

CRITICAL for preventing alpha destruction through fees and sequence risk.
"""

import pytest
from unittest.mock import MagicMock

from src.risk.capital_efficiency import (
    CapitalEfficiencyCalculator,
    CapitalProfile,
    StrategyViability,
    StrategyTier,
    get_capital_calculator,
)


class TestStrategyViability:
    """Tests for StrategyViability dataclass."""

    def test_creates_viable_strategy(self):
        """Should create a viable strategy result."""
        viability = StrategyViability(
            strategy_name="Iron Condor",
            is_viable=True,
            reason="Capital requirements met",
            min_capital_required=10000,
            current_capital=30000,
            capital_gap=0,
            days_to_viable=0,
        )
        assert viability.is_viable is True
        assert viability.capital_gap == 0

    def test_creates_blocked_strategy(self):
        """Should create a blocked strategy with gap."""
        viability = StrategyViability(
            strategy_name="Iron Condor",
            is_viable=False,
            reason="Need $10,000 (have $5,000)",
            min_capital_required=10000,
            current_capital=5000,
            capital_gap=5000,
            days_to_viable=500,
            recommended_alternative="vertical_spread",
        )
        assert viability.is_viable is False
        assert viability.capital_gap == 5000
        assert viability.recommended_alternative == "vertical_spread"


class TestCapitalProfile:
    """Tests for CapitalProfile dataclass."""

    def test_creates_profile(self):
        """Should create a capital profile."""
        profile = CapitalProfile(
            account_equity=30000,
            daily_deposit_rate=10.0,
            current_tier=StrategyTier.TIER_4_SPREADS,
            viable_strategies=["iron_condor", "vertical_spread"],
            blocked_strategies={"delta_neutral": "Need $50,000"},
            next_tier=StrategyTier.TIER_5_FULL_OPTIONS,
            days_to_next_tier=2000,
            warnings=["Delta-neutral disabled"],
        )
        assert profile.account_equity == 30000
        assert "iron_condor" in profile.viable_strategies
        assert profile.current_tier == StrategyTier.TIER_4_SPREADS


class TestCapitalEfficiencyCalculator:
    """Tests for CapitalEfficiencyCalculator class."""

    @pytest.fixture
    def calculator(self):
        """Create calculator with default rate."""
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_creates_calculator(self, calculator):
        """Should create calculator with deposit rate."""
        assert calculator.daily_deposit_rate == 10.0

    def test_thresholds_defined(self, calculator):
        """Should have all thresholds defined."""
        assert calculator.THRESHOLDS["min_batch"] == 200
        assert calculator.THRESHOLDS["iron_condor_min"] == 10000
        assert calculator.THRESHOLDS["pdt_threshold"] == 25000
        assert calculator.THRESHOLDS["delta_hedge_min"] == 50000

    def test_strategies_defined(self, calculator):
        """Should have key strategies defined."""
        assert "iron_condor" in calculator.STRATEGIES
        assert "vertical_spread" in calculator.STRATEGIES
        assert "covered_call" in calculator.STRATEGIES
        assert "equity_accumulation" in calculator.STRATEGIES


class TestAnalyzeCapital:
    """Tests for analyze_capital method."""

    @pytest.fixture
    def calculator(self):
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_tier_1_small_account(self, calculator):
        """Small accounts should be TIER_1_ACCUMULATION."""
        profile = calculator.analyze_capital(500)
        assert profile.current_tier == StrategyTier.TIER_1_ACCUMULATION
        assert "equity_accumulation" in profile.viable_strategies

    def test_tier_2_covered_calls(self, calculator):
        """$1k-$5k accounts should support covered calls."""
        profile = calculator.analyze_capital(2000)
        assert profile.current_tier == StrategyTier.TIER_2_COVERED_CALLS
        assert "covered_call" in profile.viable_strategies

    def test_tier_3_defined_risk(self, calculator):
        """$5k-$25k accounts should support vertical spreads."""
        profile = calculator.analyze_capital(10000)
        assert profile.current_tier == StrategyTier.TIER_3_DEFINED_RISK
        assert "vertical_spread" in profile.viable_strategies

    def test_tier_4_spreads(self, calculator):
        """$25k+ accounts should support iron condors."""
        profile = calculator.analyze_capital(30000)
        assert profile.current_tier == StrategyTier.TIER_4_SPREADS
        assert "iron_condor" in profile.viable_strategies

    def test_tier_5_full_options(self, calculator):
        """$50k+ accounts should support delta hedging."""
        profile = calculator.analyze_capital(60000)
        assert profile.current_tier == StrategyTier.TIER_5_FULL_OPTIONS
        assert "delta_neutral" in profile.viable_strategies

    def test_generates_warnings_below_min_batch(self, calculator):
        """Should warn when below minimum batch size."""
        profile = calculator.analyze_capital(100)
        assert any("minimum batch" in w for w in profile.warnings)

    def test_calculates_days_to_next_tier(self, calculator):
        """Should calculate days to next tier."""
        profile = calculator.analyze_capital(10000)
        # Should calculate days to reach $25k (next tier)
        assert profile.next_tier == StrategyTier.TIER_4_SPREADS
        assert profile.days_to_next_tier > 0


class TestCheckStrategyViability:
    """Tests for check_strategy_viability method."""

    @pytest.fixture
    def calculator(self):
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_iron_condor_viable_at_30k(self, calculator):
        """Iron condors should be viable at $30k."""
        viability = calculator.check_strategy_viability("iron_condor", 30000)
        assert viability.is_viable is True

    def test_iron_condor_blocked_at_5k(self, calculator):
        """Iron condors should be blocked at $5k."""
        viability = calculator.check_strategy_viability("iron_condor", 5000)
        assert viability.is_viable is False
        assert viability.capital_gap == 5000
        assert viability.days_to_viable == 500  # $5k gap / $10 per day

    def test_unknown_strategy_returns_not_viable(self, calculator):
        """Unknown strategies should return not viable."""
        viability = calculator.check_strategy_viability("unknown_strategy", 30000)
        assert viability.is_viable is False
        assert "Unknown strategy" in viability.reason

    def test_iv_rank_constraint_blocks_strategy(self, calculator):
        """Low IV rank should block premium selling strategies."""
        # Iron condor needs IV rank >= 30
        viability = calculator.check_strategy_viability(
            "iron_condor", 30000, iv_rank=15
        )
        assert viability.is_viable is False
        assert "IV Rank" in viability.reason

    def test_iv_rank_constraint_passes(self, calculator):
        """Sufficient IV rank should allow premium selling."""
        viability = calculator.check_strategy_viability(
            "iron_condor", 30000, iv_rank=50
        )
        assert viability.is_viable is True


class TestCalculateSequenceRisk:
    """Tests for calculate_sequence_risk method."""

    @pytest.fixture
    def calculator(self):
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_high_risk_small_account(self, calculator):
        """Small accounts should have HIGH sequence risk."""
        risk = calculator.calculate_sequence_risk("iron_condor", 5000)
        assert risk["risk_level"] == "HIGH"
        assert risk["single_loss_impact_pct"] > 10

    def test_low_risk_large_account(self, calculator):
        """Large accounts should have LOW sequence risk."""
        risk = calculator.calculate_sequence_risk("iron_condor", 100000)
        assert risk["risk_level"] == "LOW"
        assert risk["single_loss_impact_pct"] < 5

    def test_calculates_recovery_days(self, calculator):
        """Should calculate days to recover from loss."""
        risk = calculator.calculate_sequence_risk("iron_condor", 30000)
        # Collateral is $500, 2x stop loss = $1000 loss
        # At $10/day, recovery = 100 days
        assert risk["days_to_recover"] == 100

    def test_unknown_strategy_returns_error(self, calculator):
        """Unknown strategies should return error dict."""
        risk = calculator.calculate_sequence_risk("unknown", 30000)
        assert "error" in risk


class TestShouldEnableDeltaHedging:
    """Tests for should_enable_delta_hedging method."""

    @pytest.fixture
    def calculator(self):
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_enabled_at_50k(self, calculator):
        """Delta hedging should be enabled at $50k+."""
        result = calculator.should_enable_delta_hedging(60000)
        assert result["enabled"] is True
        assert result["max_net_delta"] == 60
        assert result["target_delta"] == 25

    def test_disabled_below_50k(self, calculator):
        """Delta hedging should be disabled below $50k."""
        result = calculator.should_enable_delta_hedging(30000)
        assert result["enabled"] is False
        assert "capital_gap" in result
        assert result["capital_gap"] == 20000

    def test_calculates_days_to_enable(self, calculator):
        """Should calculate days until delta hedging is viable."""
        result = calculator.should_enable_delta_hedging(30000)
        # $20k gap / $10 per day = 2000 days
        assert result["days_to_enable"] == 2000


class TestGetOptimalStrategy:
    """Tests for get_optimal_strategy_for_capital method."""

    @pytest.fixture
    def calculator(self):
        return CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    def test_accumulation_for_tiny_account(self, calculator):
        """Tiny accounts below $500 should get equity_accumulation."""
        result = calculator.get_optimal_strategy_for_capital(200)
        assert result["optimal_strategy"] == "equity_accumulation"

    def test_iron_condor_for_neutral_30k(self, calculator):
        """$30k neutral outlook should get iron_condor."""
        result = calculator.get_optimal_strategy_for_capital(
            30000, market_outlook="neutral"
        )
        assert result["optimal_strategy"] == "iron_condor"

    def test_bullish_outlook_strategies(self, calculator):
        """Bullish outlook should prefer equity or covered calls."""
        result = calculator.get_optimal_strategy_for_capital(
            30000, market_outlook="bullish"
        )
        assert result["optimal_strategy"] in ["equity_accumulation", "covered_call", "vertical_spread"]

    def test_includes_warnings(self, calculator):
        """Result should include warnings."""
        result = calculator.get_optimal_strategy_for_capital(30000)
        assert "warnings" in result


class TestGetCapitalCalculator:
    """Tests for singleton getter."""

    def test_returns_calculator(self):
        """Should return a CapitalEfficiencyCalculator instance."""
        calc = get_capital_calculator()
        assert isinstance(calc, CapitalEfficiencyCalculator)

    def test_returns_same_instance(self):
        """Should return the same singleton instance."""
        calc1 = get_capital_calculator()
        calc2 = get_capital_calculator()
        assert calc1 is calc2

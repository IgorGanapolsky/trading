"""
Capital Efficiency Calculator - Strategy Viability by Account Size

This module determines which options strategies are mathematically viable
based on current account size and accumulation rate.

CRITICAL INSIGHT:
- Delta-neutral rebalancing requires frequent adjustments = high fees
- Iron condors require $100+ collateral per contract
- Small accounts (<$25k) cannot efficiently hedge
- $10/day accumulation means ~20 days per Iron Condor

This calculator prevents the AI from attempting strategies that will
destroy alpha through fees and sequence risk.

Author: AI Trading System
Date: December 2, 2025
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class StrategyTier(Enum):
    """Strategy complexity tiers by capital requirement."""

    TIER_1_ACCUMULATION = "accumulation"  # <$1k: Just accumulate, no options
    TIER_2_COVERED_CALLS = "covered_calls"  # $1k-$5k: Covered calls only (need 100 shares)
    TIER_3_DEFINED_RISK = "defined_risk"  # $5k-$25k: Vertical spreads, no hedging
    TIER_4_SPREADS = "spreads"  # $25k-$50k: Iron condors, limited hedging
    TIER_5_FULL_OPTIONS = "full_options"  # $50k+: Full options suite with delta management


@dataclass
class StrategyViability:
    """Result of strategy viability check."""

    strategy_name: str
    is_viable: bool
    reason: str
    min_capital_required: float
    current_capital: float
    capital_gap: float
    days_to_viable: int  # At $10/day accumulation rate
    recommended_alternative: str | None = None


@dataclass
class CapitalProfile:
    """Current capital situation analysis."""

    account_equity: float
    daily_deposit_rate: float
    current_tier: StrategyTier
    viable_strategies: list[str]
    blocked_strategies: dict[str, str]  # strategy -> reason
    next_tier: StrategyTier | None
    days_to_next_tier: int
    warnings: list[str]


class CapitalEfficiencyCalculator:
    """
    Calculates which strategies are viable for current account size.

    Key Thresholds (derived from real-world constraints):
    - $200: Minimum batch size (avoid fee erosion)
    - $1,000: First covered call possible (need ~10 shares of $100 stock)
    - $5,000: Vertical spreads viable (enough margin)
    - $25,000: PDT rule threshold, iron condors viable
    - $50,000: Delta-neutral rebalancing becomes efficient
    """

    # Capital thresholds (HARD CODED - based on real market constraints)
    THRESHOLDS = {
        "min_batch": 200,
        "covered_call_min": 1000,  # Need 100 shares of something
        "vertical_spread_min": 5000,  # Margin requirement
        "iron_condor_min": 10000,  # Need multiple legs + collateral
        "pdt_threshold": 25000,  # Pattern Day Trader rule
        "delta_hedge_min": 50000,  # Delta-neutral requires frequent adjustment
    }

    # Strategy definitions with capital requirements
    STRATEGIES = {
        "equity_accumulation": {
            "name": "Equity Accumulation (ETFs/Stocks)",
            "min_capital": 0,
            "tier": StrategyTier.TIER_1_ACCUMULATION,
            "description": "Buy and hold index ETFs (SPY, QQQ, VTI)",
            "collateral_per_trade": 0,  # Just buying shares
            "monthly_fee_impact": 0.001,  # ~0.1% for fractional shares
        },
        "covered_call": {
            "name": "Covered Call",
            "min_capital": 1000,
            "tier": StrategyTier.TIER_2_COVERED_CALLS,
            "description": "Own 100 shares, sell OTM call",
            "collateral_per_trade": 1000,  # ~100 shares at $10
            "monthly_fee_impact": 0.005,  # Options commissions
        },
        "cash_secured_put": {
            "name": "Cash-Secured Put",
            "min_capital": 2000,
            "tier": StrategyTier.TIER_2_COVERED_CALLS,
            "description": "Sell OTM put, keep cash to buy shares",
            "collateral_per_trade": 2000,  # Strike * 100 shares
            "monthly_fee_impact": 0.005,
        },
        "vertical_spread": {
            "name": "Vertical Spread (Credit/Debit)",
            "min_capital": 5000,
            "tier": StrategyTier.TIER_3_DEFINED_RISK,
            "description": "Defined risk spread (bull put, bear call)",
            "collateral_per_trade": 500,  # Width of spread
            "monthly_fee_impact": 0.01,  # Two legs
        },
        "iron_condor": {
            "name": "Iron Condor",
            "min_capital": 10000,
            "tier": StrategyTier.TIER_4_SPREADS,
            "description": "Neutral strategy: sell OTM put spread + call spread",
            "collateral_per_trade": 500,  # Max of the two spreads
            "monthly_fee_impact": 0.02,  # Four legs
            "sequence_risk": 0.15,  # One bad trade can wipe 15% easily
        },
        "delta_neutral": {
            "name": "Delta-Neutral Rebalancing",
            "min_capital": 50000,
            "tier": StrategyTier.TIER_5_FULL_OPTIONS,
            "description": "Continuous delta hedging with underlying",
            "collateral_per_trade": 5000,  # Need to buy/sell shares frequently
            "monthly_fee_impact": 0.03,  # High turnover
            "reason_threshold": "Frequent adjustments destroy alpha at small scale",
        },
        "straddle_strangle": {
            "name": "Straddle/Strangle",
            "min_capital": 25000,
            "tier": StrategyTier.TIER_4_SPREADS,
            "description": "Volatility plays (long or short)",
            "collateral_per_trade": 2000,
            "monthly_fee_impact": 0.02,
        },
    }

    # IV Rank constraints for premium selling
    IV_CONSTRAINTS = {
        "iron_condor": {"min_iv_rank": 30, "optimal_iv_rank": 50},
        "vertical_spread": {"min_iv_rank": 20, "optimal_iv_rank": 40},
        "covered_call": {"min_iv_rank": 20, "optimal_iv_rank": 30},
        "cash_secured_put": {"min_iv_rank": 20, "optimal_iv_rank": 30},
        "straddle_strangle_short": {"min_iv_rank": 50, "optimal_iv_rank": 70},
    }

    def __init__(self, daily_deposit_rate: float = 10.0):
        """
        Initialize calculator.

        Args:
            daily_deposit_rate: Daily deposit amount (default: $10)
        """
        self.daily_deposit_rate = daily_deposit_rate
        logger.info(
            f"Capital Efficiency Calculator initialized (deposit rate: ${daily_deposit_rate}/day)"
        )

    def analyze_capital(self, account_equity: float) -> CapitalProfile:
        """
        Analyze current capital and determine viable strategies.

        Args:
            account_equity: Current account value

        Returns:
            CapitalProfile with viable/blocked strategies
        """
        logger.info(f"Analyzing capital efficiency for ${account_equity:.2f}")

        # Determine current tier
        current_tier = self._determine_tier(account_equity)

        # Check each strategy
        viable_strategies = []
        blocked_strategies = {}
        warnings = []

        for strategy_id, _strategy in self.STRATEGIES.items():
            viability = self.check_strategy_viability(strategy_id, account_equity)
            if viability.is_viable:
                viable_strategies.append(strategy_id)
            else:
                blocked_strategies[strategy_id] = viability.reason

        # Determine next tier
        next_tier = None
        days_to_next_tier = 0

        tier_order = list(StrategyTier)
        current_tier_idx = tier_order.index(current_tier)
        if current_tier_idx < len(tier_order) - 1:
            next_tier = tier_order[current_tier_idx + 1]
            next_threshold = self._get_tier_threshold(next_tier)
            capital_gap = next_threshold - account_equity
            days_to_next_tier = int(capital_gap / self.daily_deposit_rate) if capital_gap > 0 else 0

        # Generate warnings
        if account_equity < self.THRESHOLDS["min_batch"]:
            warnings.append(
                f"Account below minimum batch (${self.THRESHOLDS['min_batch']}). "
                "All deposits will accumulate, no trades executed."
            )

        if "iron_condor" in viable_strategies and account_equity < self.THRESHOLDS["pdt_threshold"]:
            warnings.append(
                "Iron condors viable but SEQUENCE RISK is high. "
                "One 2x loss wipes ~20 days of deposits."
            )

        if account_equity < self.THRESHOLDS["delta_hedge_min"]:
            warnings.append(
                f"Delta-neutral rebalancing DISABLED (need ${self.THRESHOLDS['delta_hedge_min']:,}). "
                "Use defined-risk strategies only."
            )

        return CapitalProfile(
            account_equity=account_equity,
            daily_deposit_rate=self.daily_deposit_rate,
            current_tier=current_tier,
            viable_strategies=viable_strategies,
            blocked_strategies=blocked_strategies,
            next_tier=next_tier,
            days_to_next_tier=days_to_next_tier,
            warnings=warnings,
        )

    def check_strategy_viability(
        self, strategy_id: str, account_equity: float, iv_rank: float | None = None
    ) -> StrategyViability:
        """
        Check if a specific strategy is viable.

        Args:
            strategy_id: Strategy identifier
            account_equity: Current account value
            iv_rank: Current IV Rank (for premium selling strategies)

        Returns:
            StrategyViability result
        """
        if strategy_id not in self.STRATEGIES:
            return StrategyViability(
                strategy_name=strategy_id,
                is_viable=False,
                reason=f"Unknown strategy: {strategy_id}",
                min_capital_required=0,
                current_capital=account_equity,
                capital_gap=0,
                days_to_viable=0,
            )

        strategy = self.STRATEGIES[strategy_id]
        min_capital = strategy["min_capital"]
        capital_gap = max(0, min_capital - account_equity)
        days_to_viable = int(capital_gap / self.daily_deposit_rate) if capital_gap > 0 else 0

        # Check capital requirement
        if account_equity < min_capital:
            return StrategyViability(
                strategy_name=strategy["name"],
                is_viable=False,
                reason=f"Need ${min_capital:,} (have ${account_equity:,.2f})",
                min_capital_required=min_capital,
                current_capital=account_equity,
                capital_gap=capital_gap,
                days_to_viable=days_to_viable,
                recommended_alternative=self._get_alternative(strategy_id, account_equity),
            )

        # Check IV rank for premium selling strategies
        if iv_rank is not None and strategy_id in self.IV_CONSTRAINTS:
            constraints = self.IV_CONSTRAINTS[strategy_id]
            min_iv = constraints["min_iv_rank"]
            if iv_rank < min_iv:
                return StrategyViability(
                    strategy_name=strategy["name"],
                    is_viable=False,
                    reason=f"IV Rank {iv_rank:.0f}% < {min_iv}% minimum. Cannot sell premium effectively when premium is cheap.",
                    min_capital_required=min_capital,
                    current_capital=account_equity,
                    capital_gap=0,
                    days_to_viable=0,
                    recommended_alternative="Wait for IV expansion or use debit strategies",
                )

        return StrategyViability(
            strategy_name=strategy["name"],
            is_viable=True,
            reason="Capital and IV requirements met",
            min_capital_required=min_capital,
            current_capital=account_equity,
            capital_gap=0,
            days_to_viable=0,
        )

    def calculate_sequence_risk(
        self, strategy_id: str, account_equity: float, num_positions: int = 1
    ) -> dict[str, Any]:
        """
        Calculate sequence risk for a strategy.

        Sequence risk = probability that a string of losses wipes out
        a disproportionate amount of the small account.

        Args:
            strategy_id: Strategy to analyze
            account_equity: Current account value
            num_positions: Number of concurrent positions

        Returns:
            Risk analysis dict
        """
        if strategy_id not in self.STRATEGIES:
            return {"error": f"Unknown strategy: {strategy_id}"}

        strategy = self.STRATEGIES[strategy_id]

        # Assume 2x stop loss (per McMillan)
        max_loss_per_trade = strategy["collateral_per_trade"] * 2

        # Calculate impact
        single_loss_impact = max_loss_per_trade / account_equity if account_equity > 0 else 1.0
        days_to_recover = max_loss_per_trade / self.daily_deposit_rate

        # Risk assessment
        risk_level = "LOW"
        if single_loss_impact > 0.10:
            risk_level = "HIGH"
        elif single_loss_impact > 0.05:
            risk_level = "MEDIUM"

        return {
            "strategy": strategy["name"],
            "max_loss_per_trade": max_loss_per_trade,
            "single_loss_impact_pct": single_loss_impact * 100,
            "days_to_recover": days_to_recover,
            "risk_level": risk_level,
            "recommendation": (
                f"CAUTION: One loss = {single_loss_impact * 100:.1f}% of account = {days_to_recover:.0f} days of deposits"
                if risk_level != "LOW"
                else "Acceptable risk level"
            ),
        }

    def should_enable_delta_hedging(self, account_equity: float) -> dict[str, Any]:
        """
        Determine if delta-neutral hedging should be enabled.

        Args:
            account_equity: Current account value

        Returns:
            Dict with decision and reasoning
        """
        threshold = self.THRESHOLDS["delta_hedge_min"]

        if account_equity >= threshold:
            return {
                "enabled": True,
                "reason": f"Account ${account_equity:,.2f} >= ${threshold:,} threshold",
                "max_net_delta": 60,
                "target_delta": 25,
            }
        else:
            capital_gap = threshold - account_equity
            days_to_enable = int(capital_gap / self.daily_deposit_rate)

            return {
                "enabled": False,
                "reason": (
                    f"Account ${account_equity:,.2f} < ${threshold:,} threshold. "
                    f"Delta hedging would destroy alpha through fees. "
                    f"Use defined-risk strategies instead."
                ),
                "capital_gap": capital_gap,
                "days_to_enable": days_to_enable,
                "recommendation": "Hold positions to expiry or stop-loss. Do not dynamically hedge.",
            }

    def get_optimal_strategy_for_capital(
        self,
        account_equity: float,
        iv_rank: float | None = None,
        market_outlook: str = "neutral",
    ) -> dict[str, Any]:
        """
        Get the optimal strategy for current capital level.

        Args:
            account_equity: Current account value
            iv_rank: Current IV Rank
            market_outlook: 'bullish', 'bearish', 'neutral'

        Returns:
            Optimal strategy recommendation
        """
        profile = self.analyze_capital(account_equity)

        # Filter viable strategies by market outlook
        outlook_strategies = {
            "bullish": ["equity_accumulation", "covered_call", "vertical_spread"],
            "bearish": ["vertical_spread", "cash_secured_put"],
            "neutral": ["iron_condor", "covered_call", "cash_secured_put", "vertical_spread"],
        }

        preferred = outlook_strategies.get(market_outlook, outlook_strategies["neutral"])

        # Find best viable strategy
        for strategy_id in preferred:
            if strategy_id in profile.viable_strategies:
                viability = self.check_strategy_viability(strategy_id, account_equity, iv_rank)
                if viability.is_viable:
                    return {
                        "optimal_strategy": strategy_id,
                        "name": self.STRATEGIES[strategy_id]["name"],
                        "reason": f"Best viable strategy for ${account_equity:,.2f} with {market_outlook} outlook",
                        "tier": profile.current_tier.value,
                        "warnings": profile.warnings,
                        "sequence_risk": self.calculate_sequence_risk(strategy_id, account_equity),
                    }

        # Fallback to accumulation
        return {
            "optimal_strategy": "equity_accumulation",
            "name": "Equity Accumulation",
            "reason": f"No options strategies viable at ${account_equity:,.2f}. Accumulate until ${self.THRESHOLDS['covered_call_min']:,}",
            "tier": StrategyTier.TIER_1_ACCUMULATION.value,
            "warnings": profile.warnings,
            "days_to_first_option": int(
                (self.THRESHOLDS["covered_call_min"] - account_equity) / self.daily_deposit_rate
            ),
        }

    def _determine_tier(self, account_equity: float) -> StrategyTier:
        """Determine strategy tier based on capital."""
        if account_equity >= self.THRESHOLDS["delta_hedge_min"]:
            return StrategyTier.TIER_5_FULL_OPTIONS
        elif account_equity >= self.THRESHOLDS["pdt_threshold"]:
            return StrategyTier.TIER_4_SPREADS
        elif account_equity >= self.THRESHOLDS["vertical_spread_min"]:
            return StrategyTier.TIER_3_DEFINED_RISK
        elif account_equity >= self.THRESHOLDS["covered_call_min"]:
            return StrategyTier.TIER_2_COVERED_CALLS
        else:
            return StrategyTier.TIER_1_ACCUMULATION

    def _get_tier_threshold(self, tier: StrategyTier) -> float:
        """Get capital threshold for a tier."""
        tier_thresholds = {
            StrategyTier.TIER_1_ACCUMULATION: 0,
            StrategyTier.TIER_2_COVERED_CALLS: self.THRESHOLDS["covered_call_min"],
            StrategyTier.TIER_3_DEFINED_RISK: self.THRESHOLDS["vertical_spread_min"],
            StrategyTier.TIER_4_SPREADS: self.THRESHOLDS["pdt_threshold"],
            StrategyTier.TIER_5_FULL_OPTIONS: self.THRESHOLDS["delta_hedge_min"],
        }
        return tier_thresholds.get(tier, 0)

    def _get_alternative(self, strategy_id: str, account_equity: float) -> str | None:
        """Get alternative strategy for insufficient capital."""
        tier = self._determine_tier(account_equity)

        alternatives = {
            StrategyTier.TIER_1_ACCUMULATION: "equity_accumulation",
            StrategyTier.TIER_2_COVERED_CALLS: "covered_call",
            StrategyTier.TIER_3_DEFINED_RISK: "vertical_spread",
            StrategyTier.TIER_4_SPREADS: "iron_condor",
        }

        return alternatives.get(tier, "equity_accumulation")


# Singleton instance
_calculator_instance = None


def get_capital_calculator(daily_deposit_rate: float = 10.0) -> CapitalEfficiencyCalculator:
    """Get or create CapitalEfficiencyCalculator instance."""
    global _calculator_instance
    if _calculator_instance is None:
        _calculator_instance = CapitalEfficiencyCalculator(daily_deposit_rate)
    return _calculator_instance


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    calc = CapitalEfficiencyCalculator(daily_deposit_rate=10.0)

    print("\n" + "=" * 70)
    print("CAPITAL EFFICIENCY ANALYSIS")
    print("=" * 70)

    # Test with current portfolio value
    test_capitals = [500, 1000, 5000, 10000, 25000, 50000, 100000]

    for capital in test_capitals:
        print(f"\n--- Account: ${capital:,} ---")
        profile = calc.analyze_capital(capital)

        print(f"Tier: {profile.current_tier.value}")
        print(
            f"Viable strategies: {', '.join(profile.viable_strategies) or 'None (accumulate only)'}"
        )

        if profile.next_tier:
            print(f"Next tier: {profile.next_tier.value} in {profile.days_to_next_tier} days")

        for warning in profile.warnings:
            print(f"⚠️ {warning}")

        # Check delta hedging
        delta_check = calc.should_enable_delta_hedging(capital)
        print(f"Delta hedging: {'ENABLED' if delta_check['enabled'] else 'DISABLED'}")

    # Test sequence risk
    print("\n" + "=" * 70)
    print("SEQUENCE RISK ANALYSIS (Iron Condor)")
    print("=" * 70)

    for capital in [5000, 10000, 25000, 50000]:
        risk = calc.calculate_sequence_risk("iron_condor", capital)
        print(f"\n${capital:,}: {risk['risk_level']} - {risk['recommendation']}")

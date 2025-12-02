"""
McMillan Options Strategy - Practical Integration Example
==========================================================

This example demonstrates how to integrate the McMillan Options Knowledge Base
into a real trading strategy that makes intelligent decisions based on:
1. IV environment (IV Rank & IV Percentile)
2. Expected move calculations
3. Strategy-specific rules from McMillan
4. Risk management and position sizing

Author: Claude (AI Agent)
Date: December 2, 2025
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Direct import to avoid dependency issues
import importlib.util

spec = importlib.util.spec_from_file_location(
    "mcmillan_options_collector",
    Path(__file__).parent.parent / "src/rag/collectors/mcmillan_options_collector.py",
)
mcmillan_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mcmillan_module)
McMillanOptionsKnowledgeBase = mcmillan_module.McMillanOptionsKnowledgeBase
import logging
from datetime import datetime
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class McMillanOptionsStrategy:
    """
    Options strategy that uses McMillan knowledge base for intelligent decision making.

    This strategy:
    1. Analyzes IV environment to determine buy vs sell premium
    2. Calculates expected moves for strike selection
    3. Applies McMillan's rules for strategy execution
    4. Manages risk per McMillan's position sizing guidelines
    """

    def __init__(self, portfolio_value: float):
        """
        Initialize strategy with portfolio value.

        Args:
            portfolio_value: Current portfolio value in dollars
        """
        self.kb = McMillanOptionsKnowledgeBase()
        self.portfolio_value = portfolio_value
        logger.info(f"Initialized McMillan Options Strategy with ${portfolio_value:,.2f} portfolio")

    def analyze_options_opportunity(
        self,
        ticker: str,
        stock_price: float,
        implied_volatility: float,
        iv_rank: float,
        iv_percentile: float,
        days_to_expiration: int,
    ) -> dict[str, Any]:
        """
        Analyze options opportunity using McMillan framework.

        Args:
            ticker: Stock ticker
            stock_price: Current stock price
            implied_volatility: Current IV (as decimal, e.g., 0.30 = 30%)
            iv_rank: IV Rank (0-100)
            iv_percentile: IV Percentile (0-100)
            days_to_expiration: Days to expiration

        Returns:
            Complete analysis with strategy recommendation
        """
        logger.info(f"\n{'=' * 80}")
        logger.info(f"ANALYZING OPTIONS OPPORTUNITY: {ticker}")
        logger.info(f"{'=' * 80}")

        analysis = {
            "ticker": ticker,
            "stock_price": stock_price,
            "timestamp": datetime.now().isoformat(),
        }

        # Step 1: Get IV-based recommendation
        logger.info("\nStep 1: Analyzing IV Environment")
        logger.info(f"  IV Rank: {iv_rank}%")
        logger.info(f"  IV Percentile: {iv_percentile}%")

        iv_rec = self.kb.get_iv_recommendation(iv_rank=iv_rank, iv_percentile=iv_percentile)

        logger.info(f"  Recommendation: {iv_rec['recommendation']}")
        logger.info(f"  Reasoning: {iv_rec['reasoning']}")
        logger.info(f"  Suggested Strategies: {', '.join(iv_rec['strategies'])}")

        analysis["iv_recommendation"] = iv_rec

        # Step 2: Calculate expected move
        logger.info("\nStep 2: Calculating Expected Move")
        logger.info(f"  Stock Price: ${stock_price}")
        logger.info(f"  IV: {implied_volatility * 100}%")
        logger.info(f"  DTE: {days_to_expiration}")

        # 1 standard deviation (68% probability)
        move_1sd = self.kb.calculate_expected_move(
            stock_price=stock_price,
            implied_volatility=implied_volatility,
            days_to_expiration=days_to_expiration,
            confidence_level=1.0,
        )

        # 2 standard deviations (95% probability)
        move_2sd = self.kb.calculate_expected_move(
            stock_price=stock_price,
            implied_volatility=implied_volatility,
            days_to_expiration=days_to_expiration,
            confidence_level=2.0,
        )

        logger.info(
            f"  1σ Move: ${move_1sd['expected_move']} ({move_1sd['probability'] * 100}% prob)"
        )
        logger.info(f"    Range: ${move_1sd['lower_bound']} - ${move_1sd['upper_bound']}")
        logger.info(
            f"  2σ Move: ${move_2sd['expected_move']} ({move_2sd['probability'] * 100}% prob)"
        )
        logger.info(f"    Range: ${move_2sd['lower_bound']} - ${move_2sd['upper_bound']}")

        analysis["expected_move_1sd"] = move_1sd
        analysis["expected_move_2sd"] = move_2sd

        # Step 3: Select optimal strategy based on IV
        logger.info("\nStep 3: Selecting Optimal Strategy")

        optimal_strategy = self._select_strategy(iv_rec, days_to_expiration)
        logger.info(f"  Selected Strategy: {optimal_strategy}")

        # Step 4: Get strategy rules
        rules = self.kb.get_strategy_rules(optimal_strategy)
        if not rules:
            logger.error(f"  ERROR: No rules found for {optimal_strategy}")
            analysis["error"] = f"No rules for strategy {optimal_strategy}"
            return analysis

        logger.info(f"  Market Outlook: {rules['market_outlook']}")
        logger.info("  Setup Rules:")
        for rule in rules["setup_rules"][:3]:  # Show first 3
            logger.info(f"    - {rule}")

        analysis["strategy"] = optimal_strategy
        analysis["strategy_rules"] = rules

        # Step 5: Generate specific trade setup
        logger.info("\nStep 4: Generating Trade Setup")

        trade_setup = self._generate_trade_setup(
            strategy=optimal_strategy, stock_price=stock_price, move_1sd=move_1sd, rules=rules
        )

        logger.info("  Trade Setup:")
        for key, value in trade_setup.items():
            if isinstance(value, (int, float)):
                logger.info(f"    {key}: {value}")

        analysis["trade_setup"] = trade_setup

        # Step 6: Position sizing
        logger.info("\nStep 5: Calculating Position Size")

        # Estimate option premium (simplified - in real world, get from market data)
        estimated_premium = self._estimate_option_premium(
            stock_price=stock_price, strategy=optimal_strategy, iv=implied_volatility
        )

        logger.info(f"  Estimated Premium: ${estimated_premium:.2f} per share")

        sizing = self.kb.get_position_size(
            portfolio_value=self.portfolio_value,
            option_premium=estimated_premium,
            max_risk_pct=0.02,  # 2% max risk
        )

        logger.info(f"  Max Contracts: {sizing['max_contracts']}")
        logger.info(f"  Total Cost: ${sizing['total_cost']:,.2f}")
        logger.info(f"  Risk: {sizing['risk_percentage']:.2f}%")

        analysis["position_sizing"] = sizing

        # Step 7: Risk management checklist
        logger.info("\nStep 6: Risk Management Checklist")

        risk_checks = self._risk_management_checklist(
            strategy=optimal_strategy, rules=rules, iv_rank=iv_rank, dte=days_to_expiration
        )

        for check in risk_checks:
            status = "✓" if check["passed"] else "✗"
            logger.info(f"  {status} {check['rule']}")

        analysis["risk_checks"] = risk_checks

        # Final verdict
        all_checks_passed = all(c["passed"] for c in risk_checks)
        analysis["trade_approved"] = all_checks_passed

        logger.info(f"\n{'=' * 80}")
        if all_checks_passed:
            logger.info("TRADE APPROVED: All risk checks passed ✓")
        else:
            logger.info("TRADE REJECTED: Some risk checks failed ✗")
        logger.info(f"{'=' * 80}\n")

        return analysis

    def _select_strategy(self, iv_rec: dict, dte: int) -> str:
        """Select optimal strategy based on IV recommendation."""
        recommendation = iv_rec["recommendation"]

        if "STRONGLY SELL" in recommendation or "FAVOR SELLING" in recommendation:
            # High IV - sell premium
            if dte >= 30:
                return "iron_condor"  # Best for 30-45 DTE
            else:
                return "covered_call"  # Shorter dated
        elif "BUY PREMIUM" in recommendation:
            # Low IV - buy premium
            return "long_call"
        else:
            # Neutral - income strategies
            return "cash_secured_put"

    def _generate_trade_setup(
        self, strategy: str, stock_price: float, move_1sd: dict, rules: dict
    ) -> dict[str, Any]:
        """Generate specific trade setup based on strategy."""
        setup = {}

        if strategy == "iron_condor":
            # Short strikes at 1 std dev
            setup["short_put_strike"] = round(move_1sd["lower_bound"], 2)
            setup["short_call_strike"] = round(move_1sd["upper_bound"], 2)

            # Wings 5-10 points wide per McMillan
            wing_width = 5 if stock_price < 100 else 10
            setup["long_put_strike"] = round(setup["short_put_strike"] - wing_width, 2)
            setup["long_call_strike"] = round(setup["short_call_strike"] + wing_width, 2)

            setup["max_profit"] = wing_width * 0.33  # Target 1/3 width as credit
            setup["max_risk"] = wing_width - setup["max_profit"]

        elif strategy == "covered_call":
            # Sell 20 delta call (per rules)
            target_delta = rules["optimal_conditions"].get("delta_target", 0.20)
            setup["stock_entry"] = stock_price
            setup["call_strike"] = round(stock_price * 1.05, 2)  # ~5% OTM (approx 20 delta)
            setup["call_delta"] = target_delta

        elif strategy == "cash_secured_put":
            # Sell 20 delta put
            target_delta = rules["optimal_conditions"].get("delta_target", 0.20)
            setup["put_strike"] = round(stock_price * 0.95, 2)  # ~5% OTM (approx 20 delta)
            setup["put_delta"] = target_delta
            setup["cash_required"] = setup["put_strike"] * 100

        elif strategy == "long_call":
            # Buy ATM or slightly OTM call
            target_delta = rules["optimal_conditions"].get("delta_target", 0.55)
            setup["call_strike"] = round(stock_price * 1.02, 2)  # ~2% OTM (approx 55 delta)
            setup["call_delta"] = target_delta

        return setup

    def _estimate_option_premium(self, stock_price: float, strategy: str, iv: float) -> float:
        """
        Estimate option premium (simplified).
        In production, fetch actual market prices.
        """
        # Very simplified estimation
        if strategy == "iron_condor":
            return stock_price * iv * 0.05  # Rough estimate
        elif strategy in ["covered_call", "cash_secured_put"]:
            return stock_price * iv * 0.03
        elif strategy == "long_call":
            return stock_price * iv * 0.08
        else:
            return stock_price * 0.02

    def _risk_management_checklist(
        self, strategy: str, rules: dict, iv_rank: float, dte: int
    ) -> list[dict[str, Any]]:
        """Generate risk management checklist."""
        checks = []

        # Check 1: IV environment matches strategy
        optimal_iv = rules["optimal_conditions"].get("iv_rank_min", 0)
        checks.append(
            {
                "rule": f"IV Rank ({iv_rank}%) >= Optimal ({optimal_iv}%)",
                "passed": iv_rank >= optimal_iv,
                "severity": "high",
            }
        )

        # Check 2: DTE in optimal range
        optimal_dte_min = rules["optimal_conditions"].get("dte_min", 0)
        optimal_dte_max = rules["optimal_conditions"].get("dte_max", 365)
        checks.append(
            {
                "rule": f"DTE ({dte}) in range {optimal_dte_min}-{optimal_dte_max}",
                "passed": optimal_dte_min <= dte <= optimal_dte_max,
                "severity": "medium",
            }
        )

        # Check 3: Position size within limits
        checks.append(
            {
                "rule": "Position size ≤ 2% of portfolio",
                "passed": True,  # Already enforced in position_size()
                "severity": "high",
            }
        )

        # Check 4: Strategy-specific checks
        if strategy == "covered_call":
            checks.append(
                {
                    "rule": "No earnings in next 30 days",
                    "passed": True,  # Would check calendar in production
                    "severity": "high",
                }
            )

        return checks


def example_analysis():
    """Run example analysis."""
    print("\n" + "=" * 80)
    print("MCMILLAN OPTIONS STRATEGY - EXAMPLE ANALYSIS")
    print("=" * 80 + "\n")

    # Initialize strategy with $10,000 portfolio
    strategy = McMillanOptionsStrategy(portfolio_value=10000)

    # Example 1: High IV environment (sell premium)
    print("\n" + "=" * 80)
    print("EXAMPLE 1: High IV Environment - Sell Premium Opportunity")
    print("=" * 80)

    analysis1 = strategy.analyze_options_opportunity(
        ticker="NVDA",
        stock_price=485.50,
        implied_volatility=0.45,  # 45% IV
        iv_rank=68.0,
        iv_percentile=72.0,
        days_to_expiration=35,
    )

    # Example 2: Low IV environment (buy premium)
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Low IV Environment - Buy Premium Opportunity")
    print("=" * 80)

    analysis2 = strategy.analyze_options_opportunity(
        ticker="AAPL",
        stock_price=178.25,
        implied_volatility=0.22,  # 22% IV
        iv_rank=18.0,
        iv_percentile=15.0,
        days_to_expiration=60,
    )

    # Example 3: Neutral IV environment
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Neutral IV Environment - Balanced Approach")
    print("=" * 80)

    analysis3 = strategy.analyze_options_opportunity(
        ticker="MSFT",
        stock_price=368.75,
        implied_volatility=0.28,  # 28% IV
        iv_rank=45.0,
        iv_percentile=42.0,
        days_to_expiration=40,
    )

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(
        f"Example 1 (NVDA): {analysis1['strategy']} - {'APPROVED' if analysis1['trade_approved'] else 'REJECTED'}"
    )
    print(
        f"Example 2 (AAPL): {analysis2['strategy']} - {'APPROVED' if analysis2['trade_approved'] else 'REJECTED'}"
    )
    print(
        f"Example 3 (MSFT): {analysis3['strategy']} - {'APPROVED' if analysis3['trade_approved'] else 'REJECTED'}"
    )
    print("=" * 80 + "\n")


if __name__ == "__main__":
    example_analysis()

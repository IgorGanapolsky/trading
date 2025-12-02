"""
McMillan Options Knowledge Base
================================

Comprehensive options knowledge from "Options as a Strategic Investment"
by Lawrence G. McMillan (5th Edition).

This module provides:
1. Core options theory (Greeks, volatility, pricing)
2. Strategy rules and guidelines
3. Risk management protocols
4. Calculators for expected moves, position sizing
5. IV-based decision frameworks

Author: Lawrence G. McMillan (knowledge source)
Implementation: Claude (AI Agent)
"""

import logging
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class GreekGuidance:
    """Guidance for interpreting a specific Greek."""

    name: str
    definition: str
    range: str
    interpretation: str
    trading_implications: str
    peak_conditions: str


@dataclass
class StrategyRules:
    """Complete ruleset for an options strategy."""

    strategy_name: str
    description: str
    market_outlook: str
    setup_rules: list[str]
    entry_criteria: list[str]
    position_sizing: list[str]
    exit_rules: list[str]
    risk_management: list[str]
    common_mistakes: list[str]
    optimal_conditions: dict[str, Any]


@dataclass
class VolatilityGuidance:
    """Volatility-based trading guidance."""

    iv_rank_min: float
    iv_rank_max: float
    iv_percentile_min: float
    iv_percentile_max: float
    recommendation: str
    reasoning: str
    strategies: list[str]


class McMillanOptionsKnowledgeBase:
    """
    Comprehensive options knowledge base based on McMillan's work.

    Key capabilities:
    - Greek interpretation and guidance
    - Strategy rules and setup criteria
    - Expected move calculations
    - IV-based recommendations
    - Risk management protocols
    - Position sizing formulas
    """

    def __init__(self):
        """Initialize knowledge base with all core knowledge."""
        self._initialize_greeks()
        self._initialize_strategies()
        self._initialize_volatility_guidance()
        self._initialize_risk_rules()
        logger.info("McMillan Options Knowledge Base initialized")

    # ============================================================================
    # SECTION 1: THE GREEKS
    # ============================================================================

    def _initialize_greeks(self):
        """Initialize Greek definitions and guidance."""
        self.greeks = {
            "delta": GreekGuidance(
                name="Delta",
                definition="Rate of change of option price with respect to underlying price",
                range="Calls: 0 to +1.0, Puts: -1.0 to 0",
                interpretation=(
                    "Delta measures how much an option's price moves per $1 move in the underlying. "
                    "A 0.50 delta call gains ~$0.50 per $1 stock increase. "
                    "Delta also approximates probability of expiring ITM."
                ),
                trading_implications=(
                    "High delta (>0.70): Behaves like stock, less time decay. "
                    "Low delta (<0.30): Cheaper, more leverage, faster decay. "
                    "ATM delta (~0.50): Balanced risk/reward for directional plays."
                ),
                peak_conditions="Delta is highest for deep ITM options and approaches 1.0 (calls) or -1.0 (puts)",
            ),
            "gamma": GreekGuidance(
                name="Gamma",
                definition="Rate of change of delta with respect to underlying price",
                range="0 to ~0.10 (highest for ATM options near expiration)",
                interpretation=(
                    "Gamma measures how quickly delta changes. High gamma means delta is unstable. "
                    "Gamma is highest for ATM options near expiration. "
                    "Long options have positive gamma (delta increases with favorable moves). "
                    "Short options have negative gamma (delta increases against you)."
                ),
                trading_implications=(
                    "High gamma = high risk/reward. Small moves create large P/L swings. "
                    "Gamma risk peaks in final 30 days before expiration. "
                    "Short gamma positions need active management as expiration approaches."
                ),
                peak_conditions="Gamma peaks for ATM options with 7-30 DTE",
            ),
            "theta": GreekGuidance(
                name="Theta",
                definition="Rate of time decay - daily option value loss due to passage of time",
                range="Negative for long options (you lose daily), positive for short options",
                interpretation=(
                    "Theta measures daily decay. An option with -$0.05 theta loses $5/day per contract. "
                    "Decay accelerates in final 30-45 days. "
                    "Weekend theta: Options lose 3 days of value over weekends."
                ),
                trading_implications=(
                    "Sell options: Collect theta, best when IV > historical levels. "
                    "Buy options: Fight theta, need quick moves. Avoid final 30 days unless expecting big move. "
                    "Optimal selling window: 30-45 DTE (balance premium vs gamma risk)."
                ),
                peak_conditions="Theta decay accelerates exponentially in final 30 days",
            ),
            "vega": GreekGuidance(
                name="Vega",
                definition="Sensitivity to 1% change in implied volatility",
                range="Always positive for long options, highest for ATM options",
                interpretation=(
                    "Vega measures IV sensitivity. +0.15 vega means +$15 per contract per 1% IV increase. "
                    "Long options benefit from IV expansion (vega positive). "
                    "Short options hurt by IV expansion (vega negative)."
                ),
                trading_implications=(
                    "High vega: Buy when IV low (IV Rank < 25), sell when IV high (IV Rank > 50). "
                    "Earnings vega crush: IV drops 20-40% post-earnings, devastating to long premium. "
                    "Time to expiration: Vega decreases as expiration approaches."
                ),
                peak_conditions="Vega highest for ATM options with 60-90 DTE",
            ),
            "rho": GreekGuidance(
                name="Rho",
                definition="Sensitivity to 1% change in interest rates",
                range="Positive for calls, negative for puts",
                interpretation=(
                    "Rho measures interest rate sensitivity. Generally minor impact except for LEAPS. "
                    "Higher rates → calls worth more (opportunity cost), puts worth less."
                ),
                trading_implications=(
                    "Usually negligible for <90 DTE options. "
                    "Relevant for LEAPS (1+ year to expiration). "
                    "2024-2025: Higher rate environment makes rho more relevant than 2010-2020."
                ),
                peak_conditions="Rho impact increases linearly with time to expiration",
            ),
        }

    def get_greek_guidance(self, greek_name: str) -> dict[str, Any]:
        """
        Get comprehensive guidance for a specific Greek.

        Args:
            greek_name: One of 'delta', 'gamma', 'theta', 'vega', 'rho'

        Returns:
            Dictionary with Greek guidance, or None if not found
        """
        greek_name = greek_name.lower()
        if greek_name not in self.greeks:
            logger.warning(f"Greek '{greek_name}' not found in knowledge base")
            return None

        guidance = self.greeks[greek_name]
        return asdict(guidance)

    # ============================================================================
    # SECTION 2: EXPECTED MOVE FORMULA
    # ============================================================================

    def calculate_expected_move(
        self,
        stock_price: float,
        implied_volatility: float,  # As decimal (e.g., 0.30 for 30%)
        days_to_expiration: int,
        confidence_level: float = 1.0,  # 1.0 = 1 std dev (68%), 2.0 = 2 std dev (95%)
    ) -> dict[str, Any]:
        """
        Calculate expected move using McMillan's formula.

        Formula: Expected Move = Stock Price × IV × √(DTE/365)

        This gives 1 standard deviation move (68% probability).
        For 2 std dev (95% probability), multiply by 2.

        Args:
            stock_price: Current stock price
            implied_volatility: IV as decimal (0.30 = 30% IV)
            days_to_expiration: Days until option expiration
            confidence_level: 1.0 = 1 std dev (68%), 2.0 = 2 std dev (95%)

        Returns:
            Dictionary with expected move data:
            {
                "expected_move": float,  # Dollar move
                "upper_bound": float,    # Stock price + move
                "lower_bound": float,    # Stock price - move
                "move_percentage": float, # Move as % of stock price
                "probability": float,     # Probability (68% for 1 std dev)
                "annual_iv": float,       # Annual IV used
                "dte": int
            }
        """
        if stock_price <= 0:
            raise ValueError("Stock price must be positive")
        if implied_volatility <= 0:
            raise ValueError("IV must be positive")
        if days_to_expiration <= 0:
            raise ValueError("DTE must be positive")

        # Calculate expected move for 1 standard deviation
        sqrt_time = math.sqrt(days_to_expiration / 365.0)
        one_std_move = stock_price * implied_volatility * sqrt_time

        # Scale to desired confidence level
        expected_move = one_std_move * confidence_level

        # Calculate bounds
        upper_bound = stock_price + expected_move
        lower_bound = stock_price - expected_move

        # Calculate move as percentage
        move_percentage = (expected_move / stock_price) * 100

        # Probability based on confidence level
        probability_map = {
            1.0: 0.68,  # 1 std dev
            1.5: 0.87,  # 1.5 std dev
            2.0: 0.95,  # 2 std dev
            2.5: 0.99,  # 2.5 std dev
        }
        probability = probability_map.get(confidence_level)

        return {
            "expected_move": round(expected_move, 2),
            "upper_bound": round(upper_bound, 2),
            "lower_bound": round(lower_bound, 2),
            "move_percentage": round(move_percentage, 2),
            "probability": probability,
            "confidence_level": confidence_level,
            "annual_iv": implied_volatility,
            "dte": days_to_expiration,
            "formula": f"{stock_price} × {implied_volatility} × √({days_to_expiration}/365) × {confidence_level}",
        }

    # ============================================================================
    # SECTION 3: STRATEGY RULES
    # ============================================================================

    def _initialize_strategies(self):
        """Initialize complete strategy rulesets."""
        self.strategies = {
            "covered_call": StrategyRules(
                strategy_name="Covered Call",
                description="Own 100 shares + sell 1 call against them",
                market_outlook="Neutral to slightly bullish. Generate income from sideways/slowly rising stock.",
                setup_rules=[
                    "Own 100 shares per call sold",
                    "Sell OTM call (15-30 delta optimal for income)",
                    "Target 30-45 DTE for optimal theta decay",
                    "Collect 1-2% of stock value in premium",
                ],
                entry_criteria=[
                    "Stock in uptrend or consolidation (not falling)",
                    "IV Rank > 30% (higher premium)",
                    "No earnings within expiration window",
                    "Strike price at or above your basis (avoid tax issues)",
                ],
                position_sizing=[
                    "Only sell calls on shares you own (no naked calls)",
                    "Max 30-50% of portfolio in covered calls",
                    "Keep some shares uncovered for upside participation",
                ],
                exit_rules=[
                    "Roll when option reaches 21 DTE and profitable (50%+ profit)",
                    "Let assignment happen if called away at profitable strike",
                    "Buy back if stock plunges and call nearly worthless",
                    "Close if stock approaching ex-dividend and calls ITM (assignment risk)",
                ],
                risk_management=[
                    "Risk: Capped upside (called away), full downside (own shares)",
                    "Set mental stop on stock 8-10% below entry",
                    "Avoid before earnings (assignment risk + IV crush wastes opportunity)",
                    "Don't sell calls on declining stocks (catching falling knife)",
                ],
                common_mistakes=[
                    "Selling ATM or ITM calls (too likely to be assigned)",
                    "Selling weekly calls (too much gamma risk)",
                    "Holding through earnings (assignment risk)",
                    "Selling calls below cost basis (tax trap)",
                ],
                optimal_conditions={
                    "iv_rank_min": 30,
                    "dte_min": 30,
                    "dte_max": 45,
                    "delta_target": 0.20,  # 20 delta = ~20% prob of assignment
                },
            ),
            "iron_condor": StrategyRules(
                strategy_name="Iron Condor",
                description="Sell OTM call spread + OTM put spread. Profit if stock stays in range.",
                market_outlook="Neutral. Expect stock to stay range-bound.",
                setup_rules=[
                    "Sell OTM put, buy further OTM put (bull put spread)",
                    "Sell OTM call, buy further OTM call (bear call spread)",
                    "Wings: 5-10 strikes wide ($5-10 for $100 stock)",
                    "Target 1/3 width of spread as credit (e.g., $1.50 credit on $5 wide spread)",
                ],
                entry_criteria=[
                    "IV Rank > 50% (critical - need high premium)",
                    "Stock in consolidation or low volatility environment",
                    "30-45 DTE optimal",
                    "Place short strikes 1 std dev from current price",
                ],
                position_sizing=[
                    "Max risk per trade: 2% of portfolio",
                    "Position size: 2% Portfolio / (Spread Width - Credit)",
                    "Example: $10k portfolio, $5 spread, $1.50 credit → max 5 contracts",
                ],
                exit_rules=[
                    "Close at 50% profit (best risk/reward per McMillan)",
                    "Close if one side tested (stock approaching short strike)",
                    "Roll untested side if > 21 DTE and profitable",
                    "Max loss: Close if down 2x credit received",
                ],
                risk_management=[
                    "Risk: Spread width - credit received",
                    "Example: $5 wide spread, $1.50 credit → $3.50 max risk",
                    "Never let both sides be tested simultaneously",
                    "Avoid before earnings (IV crush helps, but risk of big move)",
                ],
                common_mistakes=[
                    "Selling too close to current price (tested too often)",
                    "Trading low IV stocks (premium too small)",
                    "Holding to expiration (gamma risk)",
                    "Not closing winners at 50% (diminishing returns)",
                ],
                optimal_conditions={
                    "iv_rank_min": 50,
                    "iv_percentile_min": 50,
                    "dte_min": 30,
                    "dte_max": 45,
                    "delta_short_put": 0.16,  # 16 delta = ~1 std dev
                    "delta_short_call": 0.16,
                },
            ),
            "cash_secured_put": StrategyRules(
                strategy_name="Cash-Secured Put",
                description="Sell OTM put, keep cash to buy shares if assigned. Bullish strategy.",
                market_outlook="Bullish. Want to own stock at lower price, or collect premium if it doesn't drop.",
                setup_rules=[
                    "Sell OTM put at price you'd happily own stock",
                    "Keep cash to buy 100 shares if assigned",
                    "Target 20-30 delta put (16-30% prob of assignment)",
                    "30-45 DTE optimal for theta decay",
                ],
                entry_criteria=[
                    "Stock in uptrend or at support level",
                    "IV Rank > 30% (higher premium)",
                    "Strike at key support or your desired entry price",
                    "Avoid before earnings unless intentional",
                ],
                position_sizing=[
                    "Max 20-30% of portfolio in cash-secured puts",
                    "Ensure you have cash to buy shares if assigned",
                    "Size based on how much stock exposure you want",
                ],
                exit_rules=[
                    "Close at 50-80% profit",
                    "Roll down and out if stock drops (rescue trade)",
                    "Accept assignment if you want to own stock at that price",
                    "Buy back if stock rallies and put nearly worthless",
                ],
                risk_management=[
                    "Risk: Strike price - premium (full downside if stock crashes)",
                    "Assignment risk increases as expiration approaches",
                    "Understand you're buying stock if put goes ITM",
                    "Avoid on stocks you don't want to own",
                ],
                common_mistakes=[
                    "Selling puts on stocks you don't want to own",
                    "Selling ATM puts (too likely to be assigned)",
                    "Not keeping cash available (margin call if assigned)",
                    "Selling puts in downtrends (catching falling knife)",
                ],
                optimal_conditions={
                    "iv_rank_min": 30,
                    "dte_min": 30,
                    "dte_max": 45,
                    "delta_target": 0.20,
                },
            ),
            "long_call": StrategyRules(
                strategy_name="Long Call",
                description="Buy call option. Bullish strategy with limited risk, unlimited upside.",
                market_outlook="Bullish. Expect significant upward move in near term.",
                setup_rules=[
                    "Buy ATM or slightly OTM call (45-60 delta)",
                    "60-90 DTE minimum (avoid rapid theta decay)",
                    "Risk 1-2% of portfolio per trade",
                    "Target 2:1 reward:risk minimum",
                ],
                entry_criteria=[
                    "IV Rank < 50% (buy when IV low)",
                    "Stock at support or breaking resistance",
                    "Catalyst expected (earnings, product launch, etc.)",
                    "Strong technical setup (chart pattern, momentum)",
                ],
                position_sizing=[
                    "Risk no more than 2% of portfolio per trade",
                    "Size contracts based on premium, not number of contracts",
                    "Example: $10k portfolio → max $200 risk → ~2-3 contracts if premium $0.80",
                ],
                exit_rules=[
                    "Take profit at 100% gain or target price",
                    "Stop loss at 50% of premium paid",
                    "Close if thesis breaks (technical breakdown, news)",
                    "Don't hold past 30 DTE unless deep ITM",
                ],
                risk_management=[
                    "Risk: 100% of premium paid",
                    "Theta accelerates in final 30 days - close or roll",
                    "Need quick move - not for 'hope and pray' trades",
                    "IV crush post-earnings can offset gains",
                ],
                common_mistakes=[
                    "Buying too far OTM (lottery tickets)",
                    "Buying too close to expiration (<30 DTE)",
                    "Buying when IV high (expensive, IV crush hurts)",
                    "Risking too much (>2-3% per trade)",
                ],
                optimal_conditions={
                    "iv_rank_max": 50,
                    "dte_min": 60,
                    "delta_target": 0.55,
                },
            ),
            "protective_put": StrategyRules(
                strategy_name="Protective Put (Married Put)",
                description="Own 100 shares + buy 1 put for downside protection. Insurance strategy.",
                market_outlook="Bullish long-term but want downside protection for event or volatility.",
                setup_rules=[
                    "Own 100 shares",
                    "Buy OTM put (10-20 delta) for protection",
                    "Choose expiration based on protection period needed",
                    "Cost: 1-3% of stock value for quarterly protection",
                ],
                entry_criteria=[
                    "Own stock with large unrealized gains (protect profits)",
                    "Expecting volatility or uncertain event",
                    "Earnings protection: Buy put 1-2 weeks before earnings",
                    "Market uncertainty: Buy put during instability",
                ],
                position_sizing=[
                    "1 put per 100 shares owned",
                    "Cost is insurance premium (reduces returns)",
                    "Budget 1-2% of portfolio annually for protection",
                ],
                exit_rules=[
                    "Sell put if protection no longer needed",
                    "Let put expire worthless if stock doesn't fall (cost of insurance)",
                    "Exercise put if stock crashes below strike",
                    "Roll put forward to extend protection",
                ],
                risk_management=[
                    "Risk: Downside to strike price + put premium",
                    "Upside: Unlimited, but reduced by put premium cost",
                    "Consider put spread (sell lower put) to reduce cost",
                ],
                common_mistakes=[
                    "Buying ATM puts (too expensive, kills returns)",
                    "Over-insuring (too frequent put buying erodes returns)",
                    "Not buying enough protection (5-10% OTM = limited protection)",
                ],
                optimal_conditions={
                    "iv_rank_min": 20,  # Not too high (expensive)
                    "delta_target": 0.15,  # 15 delta = meaningful protection
                },
            ),
        }

    def get_strategy_rules(self, strategy_name: str) -> Optional[dict[str, Any]]:
        """
        Get complete ruleset for an options strategy.

        Args:
            strategy_name: One of 'covered_call', 'iron_condor', 'cash_secured_put',
                           'long_call', 'protective_put'

        Returns:
            Dictionary with complete strategy rules, or None if not found
        """
        strategy_name = strategy_name.lower().replace(" ", "_")
        if strategy_name not in self.strategies:
            logger.warning(f"Strategy '{strategy_name}' not found in knowledge base")
            return None

        rules = self.strategies[strategy_name]
        return asdict(rules)

    def list_strategies(self) -> list[str]:
        """Get list of all available strategies."""
        return list(self.strategies.keys())

    # ============================================================================
    # SECTION 4: VOLATILITY SMILE & IV GUIDANCE
    # ============================================================================

    def _initialize_volatility_guidance(self):
        """Initialize IV-based trading guidance."""
        self.volatility_guidance = [
            VolatilityGuidance(
                iv_rank_min=0.0,
                iv_rank_max=20.0,
                iv_percentile_min=0.0,
                iv_percentile_max=20.0,
                recommendation="BUY PREMIUM (long options)",
                reasoning=(
                    "IV is extremely low. Options are cheap. "
                    "Likely to mean-revert higher, giving vega tailwind. "
                    "Good for buying calls, puts, straddles, strangles."
                ),
                strategies=["long_call", "long_put", "long_straddle", "calendar_spread"],
            ),
            VolatilityGuidance(
                iv_rank_min=20.0,
                iv_rank_max=40.0,
                iv_percentile_min=20.0,
                iv_percentile_max=40.0,
                recommendation="NEUTRAL - Analyze Case by Case",
                reasoning=(
                    "IV is in middle range. No strong edge from volatility alone. "
                    "Make decisions based on other factors (technicals, fundamentals, catalyst). "
                    "Can buy or sell depending on setup."
                ),
                strategies=["covered_call", "cash_secured_put", "long_call", "protective_put"],
            ),
            VolatilityGuidance(
                iv_rank_min=40.0,
                iv_rank_max=60.0,
                iv_percentile_min=40.0,
                iv_percentile_max=60.0,
                recommendation="FAVOR SELLING PREMIUM",
                reasoning=(
                    "IV is elevated. Options are expensive relative to historical levels. "
                    "Good for premium selling strategies. "
                    "Mean reversion suggests IV will decline, benefiting sellers."
                ),
                strategies=["iron_condor", "covered_call", "cash_secured_put", "credit_spread"],
            ),
            VolatilityGuidance(
                iv_rank_min=60.0,
                iv_rank_max=100.0,
                iv_percentile_min=60.0,
                iv_percentile_max=100.0,
                recommendation="STRONGLY SELL PREMIUM",
                reasoning=(
                    "IV is very high. Options are very expensive. "
                    "Strong mean reversion edge. Excellent for premium selling. "
                    "Caution: High IV often precedes big moves, so manage risk carefully."
                ),
                strategies=["iron_condor", "straddle_short", "strangle_short", "credit_spread"],
            ),
        ]

    def get_iv_recommendation(self, iv_rank: float, iv_percentile: float) -> dict[str, Any]:
        """
        Get trading recommendation based on IV Rank and IV Percentile.

        Args:
            iv_rank: IV Rank (0-100)
            iv_percentile: IV Percentile (0-100)

        Returns:
            Dictionary with recommendation:
            {
                "recommendation": str,
                "reasoning": str,
                "strategies": List[str],
                "iv_rank": float,
                "iv_percentile": float,
                "confidence": str  # "high", "medium", "low"
            }
        """
        if not (0 <= iv_rank <= 100) or not (0 <= iv_percentile <= 100):
            raise ValueError("IV Rank and IV Percentile must be between 0 and 100")

        # Find matching guidance
        guidance = None
        for g in self.volatility_guidance:
            if (
                g.iv_rank_min <= iv_rank < g.iv_rank_max
                and g.iv_percentile_min <= iv_percentile < g.iv_percentile_max
            ):
                guidance = g
                break

        if not guidance:
            # Fallback to last guidance (highest IV range)
            guidance = self.volatility_guidance[-1]

        # Determine confidence based on agreement between IV Rank and Percentile
        (iv_rank + iv_percentile) / 2
        diff = abs(iv_rank - iv_percentile)

        if diff < 10:
            confidence = "high"
        elif diff < 20:
            confidence = "medium"
        else:
            confidence = "low"

        return {
            "recommendation": guidance.recommendation,
            "reasoning": guidance.reasoning,
            "strategies": guidance.strategies,
            "iv_rank": iv_rank,
            "iv_percentile": iv_percentile,
            "confidence": confidence,
            "note": "IV Rank and Percentile disagreement" if confidence == "low" else None,
        }

    # ============================================================================
    # SECTION 5: RISK MANAGEMENT & POSITION SIZING
    # ============================================================================

    def _initialize_risk_rules(self):
        """Initialize risk management protocols."""
        self.risk_rules = {
            "position_sizing": {
                "max_risk_per_trade": 0.02,  # 2% of portfolio
                "max_portfolio_allocation": {
                    "single_position": 0.10,  # 10% max in one position
                    "sector": 0.25,  # 25% max in one sector
                    "options": 0.30,  # 30% max in options total
                },
                "scaling": {
                    "initial_position": 0.50,  # Start with 50% of planned size
                    "add_if_profitable": 0.25,  # Add 25% if working
                    "final_add": 0.25,  # Final 25% if still working
                },
            },
            "stop_losses": {
                "long_options": {
                    "max_loss": 0.50,  # Exit at 50% loss
                    "trailing_stop": 0.25,  # Trail stop at 25% from peak
                },
                "short_options": {
                    "max_loss": 2.0,  # Exit if down 2x credit received
                    "mechanical_stop": True,
                },
                "stock": {
                    "max_loss": 0.08,  # 8% stop loss on stock positions
                    "volatility_adjusted": True,  # Widen stop for volatile stocks
                },
            },
            "tax_traps": {
                "wash_sale_rule": {
                    "period_days": 30,
                    "description": "Can't deduct loss if you buy 'substantially identical' security within 30 days before/after sale",
                    "avoidance": "Wait 31 days, or buy different strike/expiration",
                },
                "straddle_rules": {
                    "description": "Can't deduct loss on one leg if offsetting unrealized gain on other leg",
                    "impact": "Affects straddles, spreads, and hedged positions",
                },
                "qualified_covered_calls": {
                    "description": "Covered call must meet specific criteria or holding period resets",
                    "criteria": [
                        "Strike > prior day close (if 30+ DTE)",
                        "Strike > 85% of close (if 31-90 DTE)",
                        "Strike > 2 strikes below close (if >90 DTE)",
                    ],
                },
            },
            "assignment_risk": {
                "early_assignment_triggers": [
                    "Ex-dividend date approaching (calls)",
                    "Deep ITM options (>0.95 delta)",
                    "Day before expiration",
                ],
                "prevention": [
                    "Close or roll before ex-dividend",
                    "Don't hold deep ITM short options",
                    "Close positions by 3:00 PM ET on expiration day",
                ],
            },
        }

    def get_position_size(
        self, portfolio_value: float, option_premium: float, max_risk_pct: float = 0.02
    ) -> dict[str, Any]:
        """
        Calculate optimal position size based on risk.

        Args:
            portfolio_value: Total portfolio value
            option_premium: Premium per contract (e.g., $2.50 for $250 per contract)
            max_risk_pct: Max risk as decimal (default 0.02 = 2%)

        Returns:
            Dictionary with position sizing:
            {
                "max_contracts": int,
                "max_risk_dollars": float,
                "cost_per_contract": float,
                "total_cost": float,
                "risk_percentage": float
            }
        """
        max_risk_dollars = portfolio_value * max_risk_pct
        cost_per_contract = option_premium * 100  # Options are 100 shares
        max_contracts = int(max_risk_dollars / cost_per_contract)

        # Ensure at least 1 contract if affordable
        if max_contracts == 0 and cost_per_contract <= max_risk_dollars:
            max_contracts = 1

        total_cost = max_contracts * cost_per_contract
        actual_risk_pct = (total_cost / portfolio_value) if portfolio_value > 0 else 0

        return {
            "max_contracts": max_contracts,
            "max_risk_dollars": round(max_risk_dollars, 2),
            "cost_per_contract": round(cost_per_contract, 2),
            "total_cost": round(total_cost, 2),
            "risk_percentage": round(actual_risk_pct * 100, 2),
            "recommendation": (
                f"Trade up to {max_contracts} contracts to stay within {max_risk_pct * 100}% risk limit"
            ),
        }

    def get_risk_rules(self, category: str = None) -> dict[str, Any]:
        """
        Get risk management rules.

        Args:
            category: Optional category ('position_sizing', 'stop_losses', 'tax_traps', 'assignment_risk')
                     If None, returns all rules.

        Returns:
            Dictionary with risk rules
        """
        if category:
            if category not in self.risk_rules:
                logger.warning(f"Risk category '{category}' not found")
                return None
            return self.risk_rules[category]

        return self.risk_rules

    # ============================================================================
    # SECTION 6: HELPER METHODS & UTILITIES
    # ============================================================================

    def get_all_knowledge(self) -> dict[str, Any]:
        """
        Export entire knowledge base as dictionary.
        Useful for RAG ingestion or full context retrieval.

        Returns:
            Complete knowledge base dictionary
        """
        return {
            "greeks": {k: asdict(v) for k, v in self.greeks.items()},
            "strategies": {k: asdict(v) for k, v in self.strategies.items()},
            "volatility_guidance": [asdict(g) for g in self.volatility_guidance],
            "risk_rules": self.risk_rules,
            "metadata": {
                "source": "Options as a Strategic Investment by Lawrence G. McMillan",
                "edition": "5th Edition",
                "last_updated": datetime.now().isoformat(),
            },
        }

    def search_knowledge(self, query: str) -> list[dict[str, Any]]:
        """
        Search knowledge base for relevant information.

        Args:
            query: Search query (e.g., "iron condor setup", "gamma risk", "IV rank")

        Returns:
            List of relevant knowledge entries
        """
        query_lower = query.lower()
        results = []

        # Search Greeks
        for name, greek in self.greeks.items():
            if query_lower in name or query_lower in greek.definition.lower():
                results.append({"type": "greek", "name": name, "content": asdict(greek)})

        # Search Strategies
        for name, strategy in self.strategies.items():
            if (
                query_lower in name
                or query_lower in strategy.description.lower()
                or query_lower in strategy.market_outlook.lower()
            ):
                results.append({"type": "strategy", "name": name, "content": asdict(strategy)})

        # Search Volatility Guidance
        for guidance in self.volatility_guidance:
            if (
                query_lower in guidance.recommendation.lower()
                or query_lower in guidance.reasoning.lower()
            ):
                results.append({"type": "volatility_guidance", "content": asdict(guidance)})

        return results


# ============================================================================
# USAGE EXAMPLES & TESTS
# ============================================================================


def example_usage():
    """Demonstrate knowledge base usage."""
    kb = McMillanOptionsKnowledgeBase()

    print("=" * 80)
    print("MCMILLAN OPTIONS KNOWLEDGE BASE - EXAMPLES")
    print("=" * 80)

    # Example 1: Get Greek guidance
    print("\n1. DELTA GUIDANCE:")
    print("-" * 80)
    delta = kb.get_greek_guidance("delta")
    print(f"Definition: {delta['definition']}")
    print(f"Trading Implications: {delta['trading_implications']}")

    # Example 2: Calculate expected move
    print("\n2. EXPECTED MOVE CALCULATION:")
    print("-" * 80)
    move = kb.calculate_expected_move(
        stock_price=100.0,
        implied_volatility=0.30,  # 30% IV
        days_to_expiration=30,
        confidence_level=1.0,  # 1 std dev
    )
    print(f"Stock: ${move['expected_move']} expected move")
    print(
        f"Range: ${move['lower_bound']} - ${move['upper_bound']} ({move['probability'] * 100}% probability)"
    )

    # Example 3: Get strategy rules
    print("\n3. IRON CONDOR STRATEGY:")
    print("-" * 80)
    ic = kb.get_strategy_rules("iron_condor")
    print(f"Description: {ic['description']}")
    print("Setup Rules:")
    for rule in ic["setup_rules"]:
        print(f"  - {rule}")

    # Example 4: Get IV recommendation
    print("\n4. IV RECOMMENDATION:")
    print("-" * 80)
    iv_rec = kb.get_iv_recommendation(iv_rank=65.0, iv_percentile=68.0)
    print(f"Recommendation: {iv_rec['recommendation']}")
    print(f"Reasoning: {iv_rec['reasoning']}")
    print(f"Suggested Strategies: {', '.join(iv_rec['strategies'])}")

    # Example 5: Position sizing
    print("\n5. POSITION SIZING:")
    print("-" * 80)
    sizing = kb.get_position_size(
        portfolio_value=10000,
        option_premium=2.50,  # $250 per contract
        max_risk_pct=0.02,
    )
    print(f"Max Contracts: {sizing['max_contracts']}")
    print(f"Total Cost: ${sizing['total_cost']}")
    print(f"Risk: {sizing['risk_percentage']}%")

    print("\n" + "=" * 80)


# Alias for easier imports
McMillanKnowledge = McMillanOptionsKnowledgeBase


if __name__ == "__main__":
    example_usage()

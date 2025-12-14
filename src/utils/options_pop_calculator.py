"""
Options Probability of Profit (POP) Calculator

Provides accurate POP calculations for various options strategies:
1. Credit Spreads: POP = 1 - (premium_received / spread_width)
2. Delta-Based: POP ≈ 1 - |delta| for OTM options
3. Iron Condor: Both sides must profit
4. Hybrid: Confidence-weighted combination

Reference: Lawrence McMillan "Options as a Strategic Investment"
"""

import logging
import math
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class POPResult:
    """Result of POP calculation with metadata."""

    probability: float  # 0.0 to 1.0
    method: str  # "delta", "credit_formula", "hybrid", etc.
    confidence: float  # How confident we are in this POP
    details: dict[str, Any]


class OptionsPOPCalculator:
    """
    Probability of Profit calculations for options strategies.

    Methods:
    1. Delta-Based: Most accurate when Greeks available
       - POP ≈ 1 - |delta| for short OTM options
       - POP ≈ |delta| for long options (inverted)

    2. Credit Formula: When only premium/width known
       - POP = 1 - (premium / spread_width)

    3. Hybrid: Combines both for higher confidence
       - Weighted average with delta weighted more heavily
    """

    # Weights for hybrid calculation
    DELTA_WEIGHT = 0.6
    CREDIT_FORMULA_WEIGHT = 0.4

    @staticmethod
    def pop_from_delta(delta: float, is_short: bool = True) -> POPResult:
        """
        Calculate POP from option delta.

        For SHORT options (credit strategies):
        - POP ≈ 1 - |delta|
        - A 0.25 delta short put has ~75% POP

        For LONG options (debit strategies):
        - POP ≈ |delta|
        - A 0.70 delta long call has ~70% POP

        Args:
            delta: Option delta (-1 to +1)
            is_short: True if short position (credit), False if long (debit)

        Returns:
            POPResult with probability and metadata
        """
        abs_delta = abs(delta)

        if is_short:
            # Short options profit when OTM at expiration
            pop = 1.0 - abs_delta
        else:
            # Long options profit when ITM at expiration
            pop = abs_delta

        # Clamp to valid range
        pop = max(0.0, min(1.0, pop))

        return POPResult(
            probability=pop,
            method="delta",
            confidence=0.85,  # Delta is generally reliable
            details={
                "input_delta": delta,
                "abs_delta": abs_delta,
                "is_short": is_short,
                "formula": "1 - |delta|" if is_short else "|delta|",
            },
        )

    @staticmethod
    def pop_credit_spread(
        premium_received: float,
        spread_width: float,
    ) -> POPResult:
        """
        Calculate POP for credit spreads using premium formula.

        Formula: POP = 1 - (premium / width)

        This represents the breakeven probability:
        - If credit = $1.00 on $5 width spread
        - Breakeven is $4 loss ($5 - $1)
        - POP = 1 - (1/5) = 80%

        Args:
            premium_received: Net credit received (positive number)
            spread_width: Distance between strikes

        Returns:
            POPResult with probability and metadata
        """
        if spread_width <= 0:
            return POPResult(
                probability=0.0,
                method="credit_formula",
                confidence=0.0,
                details={"error": "Invalid spread width"},
            )

        if premium_received < 0:
            return POPResult(
                probability=0.0,
                method="credit_formula",
                confidence=0.0,
                details={"error": "Premium must be positive for credit spreads"},
            )

        pop = 1.0 - (premium_received / spread_width)
        pop = max(0.0, min(1.0, pop))

        return POPResult(
            probability=pop,
            method="credit_formula",
            confidence=0.70,  # Less reliable than delta
            details={
                "premium_received": premium_received,
                "spread_width": spread_width,
                "breakeven_distance": spread_width - premium_received,
                "formula": "1 - (premium / width)",
            },
        )

    @staticmethod
    def pop_iron_condor(
        put_spread_pop: float,
        call_spread_pop: float,
        method: str = "conservative",
    ) -> POPResult:
        """
        Calculate POP for iron condor (both spreads must profit).

        Methods:
        - "conservative": min(put_pop, call_pop) - lower but more realistic
        - "average": (put_pop + call_pop) / 2 - moderate estimate
        - "independent": put_pop * call_pop - assumes independence (usually too low)

        For iron condors, we typically want conservative because:
        - Only ONE side needs to fail for loss
        - Correlation between sides is high in directional moves

        Args:
            put_spread_pop: POP for the put credit spread
            call_spread_pop: POP for the call credit spread
            method: "conservative", "average", or "independent"

        Returns:
            POPResult with probability and metadata
        """
        if method == "conservative":
            pop = min(put_spread_pop, call_spread_pop)
            formula = "min(put_pop, call_pop)"
        elif method == "average":
            pop = (put_spread_pop + call_spread_pop) / 2
            formula = "(put_pop + call_pop) / 2"
        elif method == "independent":
            pop = put_spread_pop * call_spread_pop
            formula = "put_pop * call_pop"
        else:
            pop = min(put_spread_pop, call_spread_pop)
            formula = "min(put_pop, call_pop)"

        pop = max(0.0, min(1.0, pop))

        return POPResult(
            probability=pop,
            method=f"iron_condor_{method}",
            confidence=0.75,
            details={
                "put_spread_pop": put_spread_pop,
                "call_spread_pop": call_spread_pop,
                "calculation_method": method,
                "formula": formula,
            },
        )

    @classmethod
    def pop_with_confidence(
        cls,
        delta: float | None = None,
        premium: float | None = None,
        spread_width: float | None = None,
        is_short: bool = True,
    ) -> POPResult:
        """
        Calculate POP using all available data with confidence weighting.

        Uses hybrid approach:
        - If only delta available: Use delta method
        - If only premium/width available: Use credit formula
        - If both available: Weighted average (delta weighted 60%)

        Args:
            delta: Option delta (if available)
            premium: Net credit/debit (if available)
            spread_width: Strike width (if available)
            is_short: True if short position

        Returns:
            POPResult with probability and confidence
        """
        delta_result = None
        credit_result = None

        # Calculate delta-based POP if delta available
        if delta is not None:
            delta_result = cls.pop_from_delta(delta, is_short)

        # Calculate credit formula POP if premium and width available
        if premium is not None and spread_width is not None and spread_width > 0:
            credit_result = cls.pop_credit_spread(premium, spread_width)

        # Combine results
        if delta_result and credit_result:
            # Hybrid: weighted average
            hybrid_pop = (
                delta_result.probability * cls.DELTA_WEIGHT
                + credit_result.probability * cls.CREDIT_FORMULA_WEIGHT
            )
            hybrid_confidence = max(delta_result.confidence, credit_result.confidence)

            return POPResult(
                probability=hybrid_pop,
                method="hybrid",
                confidence=hybrid_confidence,
                details={
                    "delta_pop": delta_result.probability,
                    "credit_pop": credit_result.probability,
                    "delta_weight": cls.DELTA_WEIGHT,
                    "credit_weight": cls.CREDIT_FORMULA_WEIGHT,
                    "delta_details": delta_result.details,
                    "credit_details": credit_result.details,
                },
            )
        elif delta_result:
            return delta_result
        elif credit_result:
            return credit_result
        else:
            return POPResult(
                probability=0.50,  # Default 50/50
                method="default",
                confidence=0.0,
                details={"error": "Insufficient data for POP calculation"},
            )

    @staticmethod
    def pop_debit_spread(
        stock_price: float,
        breakeven: float,
        max_profit_strike: float,
        is_bullish: bool = True,
    ) -> POPResult:
        """
        Calculate POP for debit spreads using distance to breakeven.

        For bull call spread:
        - Breakeven = long_strike + debit_paid
        - POP depends on probability of reaching breakeven

        For bear put spread:
        - Breakeven = long_strike - debit_paid
        - POP depends on probability of falling to breakeven

        Args:
            stock_price: Current stock price
            breakeven: Breakeven price
            max_profit_strike: Strike where max profit achieved
            is_bullish: True for bull spreads, False for bear spreads

        Returns:
            POPResult with probability estimate
        """
        if is_bullish:
            # Bull spread: need price above breakeven
            distance_pct = (breakeven - stock_price) / stock_price
            # Simple heuristic: assume normal distribution, ~50% ATM
            # Each 1% move required reduces POP by ~3-5%
            pop = 0.50 - (distance_pct * 3.0)
        else:
            # Bear spread: need price below breakeven
            distance_pct = (stock_price - breakeven) / stock_price
            pop = 0.50 - (distance_pct * 3.0)

        pop = max(0.10, min(0.90, pop))  # Clamp to reasonable range

        return POPResult(
            probability=pop,
            method="debit_spread_distance",
            confidence=0.50,  # Less reliable heuristic
            details={
                "stock_price": stock_price,
                "breakeven": breakeven,
                "max_profit_strike": max_profit_strike,
                "distance_pct": distance_pct,
                "is_bullish": is_bullish,
            },
        )

    @staticmethod
    def pop_from_black_scholes_delta(
        stock_price: float,
        strike: float,
        time_to_expiry: float,  # in years
        volatility: float,  # annualized IV
        risk_free_rate: float = 0.05,
        option_type: str = "put",  # "call" or "put"
    ) -> POPResult:
        """
        Calculate delta and POP using Black-Scholes.

        This is the most accurate method when IV is known.

        Args:
            stock_price: Current stock price
            strike: Strike price
            time_to_expiry: Time to expiration in years
            volatility: Annualized implied volatility
            risk_free_rate: Risk-free rate (default 5%)
            option_type: "call" or "put"

        Returns:
            POPResult with calculated delta and POP
        """
        try:
            from scipy.stats import norm

            # Black-Scholes d1 calculation
            d1 = (
                math.log(stock_price / strike)
                + (risk_free_rate + 0.5 * volatility**2) * time_to_expiry
            ) / (volatility * math.sqrt(time_to_expiry))

            # Delta calculation
            if option_type.lower() == "call":
                delta = norm.cdf(d1)
            else:  # put
                delta = norm.cdf(d1) - 1

            # POP for short options
            pop = 1.0 - abs(delta)

            return POPResult(
                probability=pop,
                method="black_scholes",
                confidence=0.90,  # High confidence with proper inputs
                details={
                    "stock_price": stock_price,
                    "strike": strike,
                    "time_to_expiry_years": time_to_expiry,
                    "volatility": volatility,
                    "risk_free_rate": risk_free_rate,
                    "option_type": option_type,
                    "d1": d1,
                    "delta": delta,
                },
            )
        except ImportError:
            # Fallback if scipy not available
            logger.warning("scipy not available, using simple delta estimate")
            # Simple moneyness estimate
            moneyness = stock_price / strike
            if option_type.lower() == "put":
                delta = -0.5 if moneyness > 1.0 else -0.3
            else:
                delta = 0.5 if moneyness > 1.0 else 0.3

            return OptionsPOPCalculator.pop_from_delta(delta, is_short=True)


def calculate_pop_for_strategy(
    strategy_type: str,
    **kwargs: Any,
) -> POPResult:
    """
    Convenience function to calculate POP for any strategy type.

    Args:
        strategy_type: One of "bull_put", "bear_call", "iron_condor",
                      "bull_call", "bear_put", "covered_call", "cash_secured_put"
        **kwargs: Strategy-specific parameters

    Returns:
        POPResult with probability and confidence
    """
    calc = OptionsPOPCalculator()

    if strategy_type in ("bull_put", "bear_call", "credit_spread"):
        return calc.pop_with_confidence(
            delta=kwargs.get("short_delta"),
            premium=kwargs.get("net_credit"),
            spread_width=kwargs.get("width"),
            is_short=True,
        )

    elif strategy_type == "iron_condor":
        put_pop = kwargs.get("put_spread_pop", 0.70)
        call_pop = kwargs.get("call_spread_pop", 0.70)
        return calc.pop_iron_condor(put_pop, call_pop)

    elif strategy_type in ("bull_call", "bear_put", "debit_spread"):
        return calc.pop_debit_spread(
            stock_price=kwargs.get("stock_price", 0),
            breakeven=kwargs.get("breakeven", 0),
            max_profit_strike=kwargs.get("max_profit_strike", 0),
            is_bullish=strategy_type == "bull_call",
        )

    elif strategy_type == "covered_call":
        # Covered call POP is complex - depends on stock position
        delta = kwargs.get("call_delta", 0.30)
        return POPResult(
            probability=1.0 - delta,  # Probability call expires OTM
            method="covered_call",
            confidence=0.75,
            details={"call_delta": delta, "note": "POP of keeping shares + premium"},
        )

    elif strategy_type == "cash_secured_put":
        delta = kwargs.get("put_delta", 0.25)
        return calc.pop_from_delta(delta, is_short=True)

    else:
        return POPResult(
            probability=0.50,
            method="unknown",
            confidence=0.0,
            details={"error": f"Unknown strategy type: {strategy_type}"},
        )


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("\n=== Options POP Calculator Demo ===\n")

    # Example 1: Delta-based POP
    print("1. Delta-Based POP (Short 0.25 delta put)")
    result = OptionsPOPCalculator.pop_from_delta(delta=-0.25, is_short=True)
    print(f"   POP: {result.probability:.1%} (confidence: {result.confidence:.0%})")
    print(f"   Method: {result.method}")

    # Example 2: Credit spread formula
    print("\n2. Credit Spread POP ($1.00 credit on $5.00 width)")
    result = OptionsPOPCalculator.pop_credit_spread(premium_received=1.00, spread_width=5.00)
    print(f"   POP: {result.probability:.1%} (confidence: {result.confidence:.0%})")
    print(f"   Method: {result.method}")

    # Example 3: Hybrid calculation
    print("\n3. Hybrid POP (delta=-0.25, credit=$1.00, width=$5.00)")
    result = OptionsPOPCalculator.pop_with_confidence(
        delta=-0.25, premium=1.00, spread_width=5.00, is_short=True
    )
    print(f"   POP: {result.probability:.1%} (confidence: {result.confidence:.0%})")
    print(f"   Method: {result.method}")
    print(f"   Delta POP: {result.details['delta_pop']:.1%}")
    print(f"   Credit POP: {result.details['credit_pop']:.1%}")

    # Example 4: Iron Condor
    print("\n4. Iron Condor POP (put spread 75%, call spread 78%)")
    result = OptionsPOPCalculator.pop_iron_condor(
        put_spread_pop=0.75, call_spread_pop=0.78, method="conservative"
    )
    print(f"   POP: {result.probability:.1%} (using {result.details['calculation_method']})")

    # Example 5: Strategy convenience function
    print("\n5. Bull Put Spread via convenience function")
    result = calculate_pop_for_strategy("bull_put", short_delta=-0.20, net_credit=0.85, width=5.00)
    print(f"   POP: {result.probability:.1%}")

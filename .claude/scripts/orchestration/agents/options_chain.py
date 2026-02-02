"""
Options Chain Analysis Agent

Analyzes SPY options chain for iron condor setup:
- Implied volatility rank
- Optimal strike selection (15-20 delta)
- Expected premium collection
- Risk/reward calculation
"""

from typing import Any

from .base import BaseAgent


class OptionsChainAgent(BaseAgent):
    """Options chain analysis agent."""

    # Iron condor parameters
    TARGET_DELTA = 0.15  # 15 delta for short strikes
    WING_WIDTH = 5  # $5 wide spreads
    TARGET_DTE = 35  # 30-45 DTE sweet spot

    def __init__(self):
        super().__init__("options-chain")

    async def analyze(self) -> dict[str, Any]:
        """Analyze options chain for iron condor setup."""
        # In production, this would fetch real options data from Alpaca
        # Mock data representing typical SPY options

        # Current SPY price (example)
        spy_price = 595.50

        # IV Rank (0-100, higher = more premium)
        iv_rank = 35

        # Recommended strikes based on 15 delta
        put_short = 580  # ~15 delta put
        put_long = put_short - self.WING_WIDTH  # 575
        call_short = 610  # ~15 delta call
        call_long = call_short + self.WING_WIDTH  # 615

        # Expected premium (typical for SPY iron condor)
        expected_credit = 1.50  # Per share, so $150 per contract
        max_loss = self.WING_WIDTH - expected_credit  # $3.50

        # Probability of profit (based on delta)
        # 15 delta on each side = ~70% POP for iron condor
        prob_of_profit = 0.70

        # Risk/reward ratio
        risk_reward = expected_credit / max_loss

        # Signal calculation
        # Higher IV rank = better premium = higher signal
        iv_signal = iv_rank / 100

        # Risk/reward consideration
        rr_signal = min(1.0, risk_reward / 0.5)  # 0.5 R/R is baseline

        # Combined signal
        signal = (iv_signal * 0.6) + (rr_signal * 0.4)

        # Confidence based on IV rank clarity
        confidence = 0.75 if 20 <= iv_rank <= 60 else 0.6

        return {
            "signal": round(signal, 3),
            "confidence": round(confidence, 3),
            "data": {
                "ticker": "SPY",
                "underlying_price": spy_price,
                "iv_rank": iv_rank,
                "iv_interpretation": self._interpret_iv(iv_rank),
                "recommended_strikes": {
                    "put_short": put_short,
                    "put_long": put_long,
                    "call_short": call_short,
                    "call_long": call_long,
                },
                "target_dte": self.TARGET_DTE,
                "expected_credit": expected_credit,
                "max_loss": max_loss,
                "risk_reward_ratio": round(risk_reward, 2),
                "probability_of_profit": prob_of_profit,
                "setup_valid": self._validate_setup(spy_price, put_short, call_short),
                "recommendation": self._get_recommendation(iv_rank, risk_reward),
            },
        }

    def _interpret_iv(self, iv_rank: int) -> str:
        """Interpret IV rank."""
        if iv_rank >= 50:
            return "high_premium_opportunity"
        elif iv_rank >= 30:
            return "moderate_premium"
        else:
            return "low_premium_wait_for_spike"

    def _validate_setup(
        self, price: float, put_short: float, call_short: float
    ) -> bool:
        """Validate iron condor setup is balanced."""
        put_distance = price - put_short
        call_distance = call_short - price

        # Check roughly balanced (within 20%)
        if put_distance > 0 and call_distance > 0:
            ratio = put_distance / call_distance
            return 0.8 <= ratio <= 1.2
        return False

    def _get_recommendation(self, iv_rank: int, risk_reward: float) -> str:
        """Generate options recommendation."""
        if iv_rank >= 40 and risk_reward >= 0.4:
            return "excellent_setup_execute"
        elif iv_rank >= 25 and risk_reward >= 0.3:
            return "good_setup_proceed"
        elif iv_rank >= 15:
            return "acceptable_setup_monitor"
        else:
            return "wait_for_better_conditions"

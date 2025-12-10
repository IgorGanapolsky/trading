"""
Options IV Signal Generator

Generates options trading signals based on:
1. IV Rank - Only sell premium when IV is elevated (>30)
2. Trend Filter - Avoid selling calls in strong uptrends (ADX > 25 + bullish)
3. Strike Selection - Wider spreads in trending markets

From backtest analysis (Dec 2025):
- 75% win rate on iron condors
- All 5 losses were from "call_tested" scenarios in bull rallies
- Fix: Don't sell naked calls in strong uptrends, use wider call spreads

Reference: McMillan Options, TastyTrade mechanics
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class TrendDirection(Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class IVEnvironment(Enum):
    HIGH = "high"  # IV Rank > 50 - best for premium selling
    ELEVATED = "elevated"  # IV Rank 30-50 - good for premium selling
    LOW = "low"  # IV Rank < 30 - avoid premium selling


@dataclass
class OptionsSignal:
    """Signal for options trade execution."""

    symbol: str
    strategy: str  # "iron_condor", "cash_secured_put", "covered_call", "skip"
    iv_rank: float
    iv_environment: IVEnvironment
    trend_direction: TrendDirection
    adx_value: float
    call_spread_width: float  # Percentage width for call spread
    put_spread_width: float  # Percentage width for put spread
    confidence: float  # 0-1
    reasoning: str


class OptionsIVSignalGenerator:
    """
    Generate options trading signals based on IV and trend.

    Key improvements from Dec 2025 backtest analysis:
    1. IV Rank filter - only trade when IV > 30
    2. Trend-adjusted strikes - wider call spreads in uptrends
    3. Skip naked calls in strong bullish trends
    """

    def __init__(
        self,
        min_iv_rank: float = 30.0,
        max_adx_for_calls: float = 35.0,
        base_spread_width: float = 5.0,  # 5% spread width
        uptrend_call_multiplier: float = 1.5,  # Widen calls 50% in uptrends
    ):
        self.min_iv_rank = min_iv_rank
        self.max_adx_for_calls = max_adx_for_calls
        self.base_spread_width = base_spread_width
        self.uptrend_call_multiplier = uptrend_call_multiplier

    def calculate_iv_rank(self, current_iv: float, iv_52w_high: float, iv_52w_low: float) -> float:
        """
        Calculate IV Rank (0-100).

        IV Rank = (Current IV - 52w Low) / (52w High - 52w Low) * 100
        """
        if iv_52w_high == iv_52w_low:
            return 50.0  # Default to middle if no range

        iv_rank = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
        return max(0, min(100, iv_rank))

    def get_iv_environment(self, iv_rank: float) -> IVEnvironment:
        """Classify IV environment for strategy selection."""
        if iv_rank >= 50:
            return IVEnvironment.HIGH
        elif iv_rank >= 30:
            return IVEnvironment.ELEVATED
        else:
            return IVEnvironment.LOW

    def get_trend_direction(
        self, adx: float, plus_di: float, minus_di: float, rsi: float
    ) -> TrendDirection:
        """
        Determine trend direction using ADX and directional indicators.

        - ADX > 25 with +DI > -DI = Bullish trend
        - ADX > 25 with -DI > +DI = Bearish trend
        - ADX < 25 = Neutral/ranging
        """
        if adx < 20:
            return TrendDirection.NEUTRAL

        if plus_di > minus_di:
            # Confirm with RSI
            if rsi > 50:
                return TrendDirection.BULLISH
            return TrendDirection.NEUTRAL
        else:
            if rsi < 50:
                return TrendDirection.BEARISH
            return TrendDirection.NEUTRAL

    def generate_signal(
        self,
        symbol: str,
        current_iv: float,
        iv_52w_high: float,
        iv_52w_low: float,
        adx: float,
        plus_di: float,
        minus_di: float,
        rsi: float,
    ) -> OptionsSignal:
        """
        Generate options trading signal.

        Strategy selection logic:
        1. If IV Rank < 30: SKIP (premium too low)
        2. If strong uptrend (ADX > 35, bullish): Cash-secured put only (no calls!)
        3. If neutral/mild trend: Iron condor with standard widths
        4. If downtrend: Iron condor with wider put protection
        """
        iv_rank = self.calculate_iv_rank(current_iv, iv_52w_high, iv_52w_low)
        iv_env = self.get_iv_environment(iv_rank)
        trend = self.get_trend_direction(adx, plus_di, minus_di, rsi)

        # Base spread widths
        call_width = self.base_spread_width
        put_width = self.base_spread_width

        # Decision logic
        if iv_env == IVEnvironment.LOW:
            # Don't sell premium when IV is low
            return OptionsSignal(
                symbol=symbol,
                strategy="skip",
                iv_rank=iv_rank,
                iv_environment=iv_env,
                trend_direction=trend,
                adx_value=adx,
                call_spread_width=0,
                put_spread_width=0,
                confidence=0.0,
                reasoning=f"IV Rank {iv_rank:.1f}% < {self.min_iv_rank}% minimum. Premium too low.",
            )

        if trend == TrendDirection.BULLISH and adx > self.max_adx_for_calls:
            # Strong uptrend - don't sell calls (they'll get tested)
            # Only do cash-secured puts
            return OptionsSignal(
                symbol=symbol,
                strategy="cash_secured_put",
                iv_rank=iv_rank,
                iv_environment=iv_env,
                trend_direction=trend,
                adx_value=adx,
                call_spread_width=0,
                put_spread_width=put_width,
                confidence=0.75,
                reasoning=f"Strong uptrend (ADX={adx:.1f}, bullish). Selling puts only - calls would get tested.",
            )

        if trend == TrendDirection.BULLISH:
            # Mild uptrend - iron condor but widen call spread
            call_width *= self.uptrend_call_multiplier
            return OptionsSignal(
                symbol=symbol,
                strategy="iron_condor",
                iv_rank=iv_rank,
                iv_environment=iv_env,
                trend_direction=trend,
                adx_value=adx,
                call_spread_width=call_width,
                put_spread_width=put_width,
                confidence=0.65,
                reasoning=f"Mild uptrend. Iron condor with widened call spread ({call_width:.1f}% vs {put_width:.1f}%).",
            )

        if trend == TrendDirection.BEARISH:
            # Downtrend - iron condor but widen put spread
            put_width *= self.uptrend_call_multiplier
            return OptionsSignal(
                symbol=symbol,
                strategy="iron_condor",
                iv_rank=iv_rank,
                iv_environment=iv_env,
                trend_direction=trend,
                adx_value=adx,
                call_spread_width=call_width,
                put_spread_width=put_width,
                confidence=0.65,
                reasoning=f"Downtrend. Iron condor with widened put spread ({put_width:.1f}% vs {call_width:.1f}%).",
            )

        # Neutral - standard iron condor (best scenario)
        confidence = 0.80 if iv_env == IVEnvironment.HIGH else 0.70
        return OptionsSignal(
            symbol=symbol,
            strategy="iron_condor",
            iv_rank=iv_rank,
            iv_environment=iv_env,
            trend_direction=trend,
            adx_value=adx,
            call_spread_width=call_width,
            put_spread_width=put_width,
            confidence=confidence,
            reasoning=f"Neutral trend (ADX={adx:.1f}). Standard iron condor - optimal conditions.",
        )


def get_options_signal_generator() -> OptionsIVSignalGenerator:
    """Get singleton instance of options signal generator."""
    return OptionsIVSignalGenerator()

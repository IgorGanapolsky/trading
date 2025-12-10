"""
Bull/Bear Debate Agents - Multi-Perspective Trading Analysis

Based on UCLA/MIT TradingAgents research (Dec 2024) showing:
- 42% CAGR improvement with multi-agent debate
- Superior Sharpe ratio and risk management
- Reduced confirmation bias through opposing viewpoints

This module implements:
- BullAgent: Argues the bullish case for a trade
- BearAgent: Argues the bearish case for a trade
- DebateModerator: Synthesizes both perspectives into a final decision

Key insight: Forcing opposing viewpoints prevents confirmation bias
and produces more balanced, better-calibrated trading decisions.
"""

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Psychology integration
try:
    from src.coaching.mental_toughness_coach import get_position_size_modifier
    from src.coaching.mental_toughness_coach import (
        get_prompt_context as get_psychology_context,
    )

    PSYCHOLOGY_AVAILABLE = True
except ImportError:
    PSYCHOLOGY_AVAILABLE = False

    def get_psychology_context() -> str:
        return ""

    def get_position_size_modifier() -> float:
        return 1.0


@dataclass
class DebatePosition:
    """A position taken in the bull/bear debate."""

    agent: str  # "BULL" or "BEAR"
    conviction: float  # 0-1, how strongly they believe their case
    key_arguments: list[str]  # Top 3 arguments
    risk_factors: list[str]  # Key risks identified
    price_target: float | None  # Expected price (if any)
    time_horizon: str  # "short", "medium", "long"
    recommendation: str  # "BUY", "SELL", "HOLD"


@dataclass
class DebateOutcome:
    """Final outcome of the bull/bear debate."""

    winner: str  # "BULL", "BEAR", or "NEUTRAL"
    bull_position: DebatePosition
    bear_position: DebatePosition
    final_recommendation: str  # "BUY", "SELL", "HOLD"
    confidence: float  # 0-1
    position_size_modifier: float  # 0-1 based on debate clarity
    key_factors: list[str]  # Combined key factors
    dissenting_view: str  # Summary of the losing side's argument


class BullAgent:
    """
    Bull Agent: Argues the bullish case for a trade.

    Responsibilities:
    - Find reasons WHY the trade should be taken
    - Identify upside catalysts
    - Argue for larger position sizes
    - Counter bear arguments

    CRITICAL: Must find bullish case even in bearish setups.
    The debate only works if both sides argue strongly.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.name = "BULL"

    def analyze(self, symbol: str, market_data: dict[str, Any]) -> DebatePosition:
        """
        Generate bullish analysis for the symbol.

        Args:
            symbol: Stock ticker
            market_data: Technical and fundamental data

        Returns:
            DebatePosition with bullish arguments
        """
        # Extract key data points
        price = market_data.get("price", 0)
        rsi = market_data.get("rsi", 50)
        macd_hist = market_data.get("macd_histogram", 0)
        volume_ratio = market_data.get("volume_ratio", 1.0)
        trend = market_data.get("trend", "UNKNOWN")
        ma_50 = market_data.get("ma_50", price)
        ma_200 = market_data.get("ma_200", price)

        # Build bullish arguments based on data
        arguments = []
        conviction = 0.5  # Start neutral

        # Price vs moving averages
        if price > ma_50:
            arguments.append(f"Price ${price:.2f} above MA50 ${ma_50:.2f} confirms uptrend")
            conviction += 0.1
        elif price < ma_50 * 0.95:
            arguments.append(
                f"Oversold: Price ${price:.2f} is 5%+ below MA50 - reversion opportunity"
            )
            conviction += 0.05

        # RSI analysis (bullish perspective)
        if rsi < 30:
            arguments.append(f"RSI {rsi:.0f} indicates extreme oversold - bounce likely")
            conviction += 0.15
        elif rsi < 50:
            arguments.append(f"RSI {rsi:.0f} has room to expand - not overbought")
            conviction += 0.05

        # MACD analysis (bullish perspective)
        if macd_hist > 0:
            arguments.append(f"MACD histogram positive ({macd_hist:.4f}) - momentum building")
            conviction += 0.1
        elif macd_hist > -0.1:
            arguments.append("MACD approaching zero - potential bullish crossover incoming")
            conviction += 0.05

        # Volume analysis
        if volume_ratio > 1.5:
            arguments.append(f"Volume {volume_ratio:.1f}x average - institutional interest")
            conviction += 0.1

        # Golden cross check
        if ma_50 > ma_200:
            arguments.append("Golden cross (MA50 > MA200) - long-term bullish structure")
            conviction += 0.1

        # If no strong arguments found, add general bullish case
        if len(arguments) < 2:
            arguments.append("Market in overall uptrend - rising tide lifts all boats")
            arguments.append("Risk/reward favorable at current levels")

        # Cap conviction
        conviction = min(conviction, 0.95)

        # Identify risks (bulls must acknowledge risks too)
        risks = []
        if rsi > 70:
            risks.append("Overbought conditions may limit near-term upside")
        if trend == "BEARISH":
            risks.append("Current trend is bearish - fighting the trend")
        if volume_ratio < 0.7:
            risks.append("Low volume may not sustain price moves")

        return DebatePosition(
            agent="BULL",
            conviction=conviction,
            key_arguments=arguments[:3],
            risk_factors=risks[:2],
            price_target=price * 1.05 if conviction > 0.6 else None,
            time_horizon="short" if rsi < 30 else "medium",
            recommendation="BUY" if conviction > 0.55 else "HOLD",
        )


class BearAgent:
    """
    Bear Agent: Argues the bearish case / reasons NOT to trade.

    Responsibilities:
    - Find reasons WHY the trade should be avoided
    - Identify downside risks
    - Argue for smaller position sizes or no trade
    - Counter bull arguments

    CRITICAL: Must find bearish case even in bullish setups.
    The debate only works if both sides argue strongly.
    """

    def __init__(self, llm_client=None):
        self.llm_client = llm_client
        self.name = "BEAR"

    def analyze(self, symbol: str, market_data: dict[str, Any]) -> DebatePosition:
        """
        Generate bearish analysis for the symbol.

        Args:
            symbol: Stock ticker
            market_data: Technical and fundamental data

        Returns:
            DebatePosition with bearish arguments
        """
        # Extract key data points
        price = market_data.get("price", 0)
        rsi = market_data.get("rsi", 50)
        macd_hist = market_data.get("macd_histogram", 0)
        volume_ratio = market_data.get("volume_ratio", 1.0)
        trend = market_data.get("trend", "UNKNOWN")
        ma_50 = market_data.get("ma_50", price)
        ma_200 = market_data.get("ma_200", price)

        # Build bearish arguments based on data
        arguments = []
        conviction = 0.5  # Start neutral

        # Price vs moving averages (bearish perspective)
        if price < ma_50:
            arguments.append(f"Price ${price:.2f} below MA50 ${ma_50:.2f} - downtrend intact")
            conviction += 0.1
        elif price > ma_50 * 1.05:
            arguments.append("Overextended: Price 5%+ above MA50 - mean reversion risk")
            conviction += 0.05

        # RSI analysis (bearish perspective)
        if rsi > 70:
            arguments.append(f"RSI {rsi:.0f} indicates overbought - pullback likely")
            conviction += 0.15
        elif rsi > 50:
            arguments.append(f"RSI {rsi:.0f} elevated - limited upside room")
            conviction += 0.05

        # MACD analysis (bearish perspective)
        if macd_hist < 0:
            arguments.append(f"MACD histogram negative ({macd_hist:.4f}) - momentum fading")
            conviction += 0.1
        elif macd_hist < 0.1:
            arguments.append("MACD losing steam - potential bearish crossover")
            conviction += 0.05

        # Volume analysis (bearish perspective)
        if volume_ratio < 0.7:
            arguments.append(f"Volume {volume_ratio:.1f}x below average - weak conviction")
            conviction += 0.1
        elif volume_ratio > 2.0:
            arguments.append("Extreme volume may indicate distribution/selling")
            conviction += 0.05

        # Death cross check
        if ma_50 < ma_200:
            arguments.append("Death cross (MA50 < MA200) - long-term bearish structure")
            conviction += 0.1

        # Macro concerns (always valid)
        arguments.append("Macro uncertainty: Fed policy, geopolitical risks")

        # If no strong arguments found, add general bearish case
        if len(arguments) < 2:
            arguments.append("Capital preservation > chasing returns")
            arguments.append("Better opportunities may emerge - patience rewarded")

        # Cap conviction
        conviction = min(conviction, 0.95)

        # Identify risks to the bearish thesis
        risks = []
        if rsi < 30:
            risks.append("Extreme oversold may trigger technical bounce")
        if trend == "BULLISH":
            risks.append("Fighting the trend - may miss continued upside")
        if volume_ratio > 1.5:
            risks.append("High volume may sustain price moves against short")

        return DebatePosition(
            agent="BEAR",
            conviction=conviction,
            key_arguments=arguments[:3],
            risk_factors=risks[:2],
            price_target=price * 0.95 if conviction > 0.6 else None,
            time_horizon="short" if rsi > 70 else "medium",
            recommendation="SELL" if conviction > 0.6 else "HOLD",
        )


class DebateModerator:
    """
    Debate Moderator: Synthesizes bull/bear arguments into final decision.

    Key responsibilities:
    - Weight both perspectives fairly
    - Identify consensus and disagreement
    - Apply psychology context (position sizing based on state)
    - Produce final recommendation with confidence calibration

    The moderator is the key to making debates productive.
    It must:
    1. Not automatically favor either side
    2. Weight conviction levels appropriately
    3. Consider psychology state for position sizing
    4. Preserve dissenting view for review
    """

    def __init__(self):
        self.bull_agent = BullAgent()
        self.bear_agent = BearAgent()

    def conduct_debate(self, symbol: str, market_data: dict[str, Any]) -> DebateOutcome:
        """
        Conduct a bull/bear debate and produce final recommendation.

        Args:
            symbol: Stock ticker
            market_data: Technical and fundamental data

        Returns:
            DebateOutcome with synthesized recommendation
        """
        logger.info(f"Conducting Bull/Bear debate for {symbol}")

        # Get both perspectives
        bull_position = self.bull_agent.analyze(symbol, market_data)
        bear_position = self.bear_agent.analyze(symbol, market_data)

        logger.info(
            f"BULL conviction: {bull_position.conviction:.2f} | "
            f"BEAR conviction: {bear_position.conviction:.2f}"
        )

        # Determine winner based on conviction differential
        conviction_diff = bull_position.conviction - bear_position.conviction

        if conviction_diff > 0.15:
            winner = "BULL"
            final_rec = "BUY"
            confidence = bull_position.conviction * 0.8 + (1 - bear_position.conviction) * 0.2
            dissenting = f"BEAR cautions: {'; '.join(bear_position.key_arguments[:2])}"
        elif conviction_diff < -0.15:
            winner = "BEAR"
            final_rec = "SELL" if bear_position.conviction > 0.7 else "HOLD"
            confidence = bear_position.conviction * 0.8 + (1 - bull_position.conviction) * 0.2
            dissenting = f"BULL argues: {'; '.join(bull_position.key_arguments[:2])}"
        else:
            winner = "NEUTRAL"
            final_rec = "HOLD"
            confidence = 0.5
            dissenting = "Debate inconclusive - both sides have valid points"

        # Apply psychology-based position sizing
        psych_modifier = get_position_size_modifier() if PSYCHOLOGY_AVAILABLE else 1.0

        # Further reduce size if debate is close (uncertainty)
        debate_clarity = abs(conviction_diff)
        clarity_modifier = 0.5 + (debate_clarity * 2)  # 0.5 to 1.0 based on clarity
        clarity_modifier = min(clarity_modifier, 1.0)

        final_size_modifier = psych_modifier * clarity_modifier

        # Combine key factors
        key_factors = []
        if winner == "BULL":
            key_factors.extend(bull_position.key_arguments[:2])
            key_factors.append(
                f"Bear risk: {bear_position.risk_factors[0]}" if bear_position.risk_factors else ""
            )
        elif winner == "BEAR":
            key_factors.extend(bear_position.key_arguments[:2])
            key_factors.append(
                f"Bull case: {bull_position.key_arguments[0]}"
                if bull_position.key_arguments
                else ""
            )
        else:
            key_factors.extend(bull_position.key_arguments[:1])
            key_factors.extend(bear_position.key_arguments[:1])
            key_factors.append("Uncertainty high - small position or wait")

        # Filter empty strings
        key_factors = [f for f in key_factors if f]

        logger.info(
            f"Debate outcome: {winner} wins | Rec: {final_rec} | "
            f"Confidence: {confidence:.2f} | Size modifier: {final_size_modifier:.2f}"
        )

        return DebateOutcome(
            winner=winner,
            bull_position=bull_position,
            bear_position=bear_position,
            final_recommendation=final_rec,
            confidence=confidence,
            position_size_modifier=final_size_modifier,
            key_factors=key_factors,
            dissenting_view=dissenting,
        )


# Convenience function for quick debates
def quick_debate(symbol: str, market_data: dict[str, Any]) -> DebateOutcome:
    """
    Conduct a quick bull/bear debate for a symbol.

    Args:
        symbol: Stock ticker
        market_data: Dict with keys: price, rsi, macd_histogram, volume_ratio, trend, ma_50, ma_200

    Returns:
        DebateOutcome with recommendation
    """
    moderator = DebateModerator()
    return moderator.conduct_debate(symbol, market_data)

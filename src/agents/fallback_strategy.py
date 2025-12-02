"""
Fallback Strategy - Graceful Degradation when LLM fails

When Anthropic API is down or out of credits, we need to fall back to
traditional technical analysis without LLM reasoning.

This ensures the system NEVER stops working due to API issues.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FallbackStrategy:
    """
    Fallback to traditional technical analysis when LLM unavailable.

    Uses pure mathematical indicators:
    - MACD histogram > 0 = BUY signal
    - RSI < 30 = oversold BUY, RSI > 70 = overbought SELL
    - Volume > 1.2x average = confirmation
    - Price > MA50 = uptrend confirmation
    """

    @staticmethod
    def analyze_without_llm(data: dict[str, Any]) -> dict[str, Any]:
        """
        Pure technical analysis fallback (no LLM).

        Args:
            data: Market data with indicators

        Returns:
            Trading decision with reasoning
        """
        indicators = data.get("indicators", {})
        symbol = data.get("symbol", "UNKNOWN")

        # Extract indicators
        macd_histogram = indicators.get("macd_histogram", 0)
        rsi = indicators.get("rsi", 50)
        volume_ratio = indicators.get("volume_ratio", 1.0)
        price = indicators.get("price", 0)
        ma_50 = indicators.get("ma_50", 0)
        momentum_score = indicators.get("momentum_score", 0)

        # Decision logic (traditional technical analysis)
        score = 0
        reasons = []

        # MACD check (strongest signal)
        if macd_histogram > 0:
            score += 40
            reasons.append(f"✅ MACD bullish ({macd_histogram:.4f})")
        else:
            score -= 40
            reasons.append(f"❌ MACD bearish ({macd_histogram:.4f})")

        # RSI check
        if rsi < 30:
            score += 20
            reasons.append(f"✅ RSI oversold ({rsi:.1f})")
        elif rsi > 70:
            score -= 20
            reasons.append(f"❌ RSI overbought ({rsi:.1f})")
        else:
            score += 10
            reasons.append(f"➡️ RSI neutral ({rsi:.1f})")

        # Volume confirmation
        if volume_ratio > 1.2:
            score += 15
            reasons.append(f"✅ Strong volume ({volume_ratio:.2f}x)")
        elif volume_ratio < 0.8:
            score -= 10
            reasons.append(f"⚠️ Weak volume ({volume_ratio:.2f}x)")

        # Trend check
        if price > ma_50:
            score += 15
            reasons.append(f"✅ Above MA50 (${price:.2f} > ${ma_50:.2f})")
        else:
            score -= 15
            reasons.append(f"❌ Below MA50 (${price:.2f} < ${ma_50:.2f})")

        # Momentum
        if momentum_score > 70:
            score += 10
            reasons.append(f"✅ Strong momentum ({momentum_score:.0f}/100)")
        elif momentum_score < 30:
            score -= 10
            reasons.append(f"❌ Weak momentum ({momentum_score:.0f}/100)")

        # Final decision
        if score >= 50:
            action = "BUY"
            confidence = min(score / 100, 1.0)
        elif score <= -30:
            action = "SELL"
            confidence = min(abs(score) / 100, 1.0)
        else:
            action = "HOLD"
            confidence = 0.5

        reasoning = f"""
FALLBACK MODE: LLM unavailable, using pure technical analysis

SYMBOL: {symbol}
SCORE: {score}/100

ANALYSIS:
{chr(10).join(reasons)}

DECISION: {action} (Confidence: {confidence:.2f})
"""

        logger.warning(f"Fallback mode active for {symbol}: {action}")

        return {
            "action": action,
            "confidence": confidence,
            "score": score,
            "reasoning": reasoning,
            "mode": "FALLBACK",
            "indicators": indicators,
        }

    @staticmethod
    def research_fallback(data: dict[str, Any]) -> dict[str, Any]:
        """Fallback for ResearchAgent (no news/sentiment)."""
        return {
            "action": "HOLD",
            "confidence": 0.5,
            "strength": 5,
            "sentiment": 0.0,
            "thesis": "LLM unavailable - defaulting to HOLD",
            "risks": "Cannot analyze fundamentals without LLM",
            "mode": "FALLBACK",
        }

    @staticmethod
    def risk_fallback(portfolio_value: float, volatility: float) -> dict[str, Any]:
        """Fallback for RiskAgent (conservative sizing)."""
        # Ultra-conservative: 1% of portfolio, max $100
        position_size = min(portfolio_value * 0.01, 100.0)
        stop_loss = max(volatility * 2, 0.05)  # 2x volatility or 5% min

        return {
            "action": "APPROVE",
            "position_size": position_size,
            "stop_loss": stop_loss,
            "risk_score": 7,  # High risk due to no LLM analysis
            "position_approval": "REDUCE",
            "risks": "Conservative sizing due to LLM unavailability",
            "mode": "FALLBACK",
        }

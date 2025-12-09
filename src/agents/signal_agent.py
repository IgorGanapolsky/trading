"""
Signal Agent: Technical analysis + LLM reasoning

Responsibilities:
- MACD, RSI, Volume analysis
- Pattern recognition
- Momentum scoring
- Entry/exit signal generation

Enhanced with LLM reasoning for context-aware decisions
"""

import builtins
import contextlib
import logging
from typing import Any

import pandas as pd

from .base_agent import BaseAgent

# Psychology integration - inject bias mitigation into LLM prompts
try:
    from src.coaching.mental_toughness_coach import get_prompt_context as get_psychology_context

    PSYCHOLOGY_AVAILABLE = True
except ImportError:
    PSYCHOLOGY_AVAILABLE = False

    def get_psychology_context() -> str:
        return ""  # No-op if coaching not available

logger = logging.getLogger(__name__)


class SignalAgent(BaseAgent):
    """
    Signal Agent performs technical analysis enhanced with LLM reasoning.

    Combines:
    - Traditional indicators (MACD, RSI, Volume)
    - Pattern recognition
    - LLM contextual analysis
    """

    def __init__(self):
        super().__init__(
            name="SignalAgent", role="Technical analysis and momentum signal generation"
        )

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Generate trading signals from technical analysis.

        Args:
            data: Contains price history, volume, technical indicators

        Returns:
            Signal analysis with action recommendation
        """
        symbol = data.get("symbol", "UNKNOWN")
        price_data = data.get("price_history", pd.DataFrame())

        # Calculate technical indicators
        indicators = self._calculate_indicators(price_data)

        # Build signal analysis prompt
        memory_context = self.get_memory_context(limit=3)

        # Prompt following Anthropic best practices:
        # - XML tags for structure (Claude trained on XML)
        # - Motivation/context explaining WHY
        # - Clear examples aligned with desired behavior
        # - Weighted principles for decision framework
        prompt = f"""Analyze {symbol} technicals and provide a trading signal.

<context>
You are evaluating technical indicators to generate actionable trading signals.
Being decisive matters because hesitation in trading leads to missed opportunities or delayed exits.
Strong signals deserve high scores; weak/mixed signals deserve low scores.
</context>

<indicators>
Price: ${indicators.get("price", 0):.2f} | MACD Hist: {indicators.get("macd_histogram", 0):.4f} | RSI: {indicators.get("rsi", 50):.1f} | Volume: {indicators.get("volume_ratio", 1.0):.1f}x
Trend: {indicators.get("trend", "UNKNOWN")} | MA50: ${indicators.get("ma_50", 0):.2f} | Momentum: {indicators.get("momentum_score", 0):.0f}/100
</indicators>

{memory_context}

<principles>
These weights reflect empirical backtesting results:
- MACD histogram crossing zero = momentum shift (weight: 30%) - Most predictive of near-term moves
- RSI below 30 oversold (bullish), above 70 overbought (bearish) (weight: 25%) - Mean reversion signal
- Price above MA50 = uptrend confirmation (weight: 25%) - Trend-following filter
- Volume above 1.5x confirms moves, below 0.7x suggests false signal (weight: 20%) - Conviction validator
</principles>

<examples>
<example type="strong_buy">
STRENGTH: 8
DIRECTION: BULLISH
ENTRY_QUALITY: 7
RECOMMENDATION: BUY
CONFIDENCE: 0.82
FACTORS: MACD histogram positive crossover, RSI recovering from 28, volume 1.8x confirms breakout
</example>

<example type="hold_weak">
STRENGTH: 4
DIRECTION: NEUTRAL
ENTRY_QUALITY: 3
RECOMMENDATION: HOLD
CONFIDENCE: 0.45
FACTORS: Mixed signals - MACD flat, RSI neutral at 52, below-average volume suggests no conviction
</example>
</examples>

<psychology_context>
{get_psychology_context() if PSYCHOLOGY_AVAILABLE else ""}
</psychology_context>

<task>
Analyze {symbol} now and respond in this exact format:
STRENGTH: [1-10]
DIRECTION: [BULLISH/BEARISH/NEUTRAL]
ENTRY_QUALITY: [1-10]
RECOMMENDATION: [BUY/SELL/HOLD]
CONFIDENCE: [0-1]
FACTORS: [2-3 key factors driving your decision]
</task>"""

        # Get LLM analysis
        response = self.reason_with_llm(prompt)

        # Parse response
        analysis = self._parse_signal_response(response["reasoning"])
        analysis["indicators"] = indicators
        analysis["full_reasoning"] = response["reasoning"]

        # Log decision
        self.log_decision(analysis)

        return analysis

    def _calculate_indicators(self, price_data: pd.DataFrame) -> dict[str, Any]:
        """
        Calculate technical indicators from price data.

        Args:
            price_data: DataFrame with OHLCV data

        Returns:
            Dict of calculated indicators
        """
        if price_data.empty or len(price_data) < 30:
            return {
                "price": 0,
                "macd": 0,
                "macd_signal": 0,
                "macd_histogram": 0,
                "rsi": 50,
                "volume_ratio": 1.0,
                "ma_50": 0,
                "ma_200": 0,
                "price_vs_ma50": 0,
                "trend": "UNKNOWN",
                "momentum_score": 0,
            }

        close = price_data["Close"] if "Close" in price_data else price_data["close"]
        volume = price_data["Volume"] if "Volume" in price_data else price_data["volume"]

        # MACD
        ema_12 = close.ewm(span=12, adjust=False).mean()
        ema_26 = close.ewm(span=26, adjust=False).mean()
        macd_line = ema_12 - ema_26
        signal_line = macd_line.ewm(span=9, adjust=False).mean()
        histogram = macd_line - signal_line

        # RSI
        delta = close.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))

        # Moving averages
        ma_50 = close.rolling(window=50).mean()
        ma_200 = close.rolling(window=200).mean() if len(close) >= 200 else ma_50

        # Volume ratio
        avg_volume = volume.rolling(window=20).mean()
        volume_ratio = volume.iloc[-1] / avg_volume.iloc[-1] if avg_volume.iloc[-1] > 0 else 1.0

        # Current values
        current_price = close.iloc[-1]
        current_macd = macd_line.iloc[-1]
        current_signal = signal_line.iloc[-1]
        current_histogram = histogram.iloc[-1]
        current_rsi = rsi.iloc[-1]
        current_ma50 = ma_50.iloc[-1]
        current_ma200 = ma_200.iloc[-1]

        # Trend determination
        if current_price > current_ma50 > current_ma200:
            trend = "STRONG_UPTREND"
        elif current_price > current_ma50:
            trend = "UPTREND"
        elif current_price < current_ma50 < current_ma200:
            trend = "STRONG_DOWNTREND"
        elif current_price < current_ma50:
            trend = "DOWNTREND"
        else:
            trend = "SIDEWAYS"

        # Momentum score (0-100)
        momentum_score = 0
        if current_histogram > 0:
            momentum_score += 30
        if current_rsi > 50:
            momentum_score += 20
        if current_price > current_ma50:
            momentum_score += 25
        if volume_ratio > 1.2:
            momentum_score += 25

        return {
            "price": current_price,
            "macd": current_macd,
            "macd_signal": current_signal,
            "macd_histogram": current_histogram,
            "rsi": current_rsi,
            "volume_ratio": volume_ratio,
            "ma_50": current_ma50,
            "ma_200": current_ma200,
            "price_vs_ma50": (current_price - current_ma50) / current_ma50,
            "trend": trend,
            "momentum_score": momentum_score,
        }

    def _parse_signal_response(self, reasoning: str) -> dict[str, Any]:
        """Parse LLM response into structured signal."""
        lines = reasoning.split("\n")
        analysis = {
            "strength": 5,
            "direction": "NEUTRAL",
            "entry_quality": 5,
            "action": "HOLD",
            "confidence": 0.5,
            "factors": "",
        }

        for line in lines:
            line = line.strip()
            if line.startswith("STRENGTH:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["strength"] = int(line.split(":")[1].strip())
            elif line.startswith("DIRECTION:"):
                direction = line.split(":")[1].strip().upper()
                if direction in ["BULLISH", "BEARISH", "NEUTRAL"]:
                    analysis["direction"] = direction
            elif line.startswith("ENTRY_QUALITY:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["entry_quality"] = int(line.split(":")[1].strip())
            elif line.startswith("RECOMMENDATION:"):
                rec = line.split(":")[1].strip().upper()
                if rec in ["BUY", "SELL", "HOLD"]:
                    analysis["action"] = rec
            elif line.startswith("CONFIDENCE:"):
                with contextlib.suppress(builtins.BaseException):
                    analysis["confidence"] = float(line.split(":")[1].strip())
            elif line.startswith("FACTORS:"):
                analysis["factors"] = line.split(":", 1)[1].strip()

        return analysis

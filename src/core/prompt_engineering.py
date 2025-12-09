"""
Prompt Engineering Module for Time Series Analysis.

Implements best practices from MachineLearningMastery for LLM-based
time series analysis in trading contexts.

Key Strategies:
1. Temporal Context Header - Market session, regime, trend state
2. Structured JSON Schema - Standardized format for price/indicator data
3. Two-Pass Analysis - Feature extraction before prediction
4. Confidence Thresholds - Quantified uncertainty in responses

Reference: docs/prompt-engineering-time-series.md
Author: Trading System
Created: 2025-12-09
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import pytz

logger = logging.getLogger(__name__)


class MarketSession(Enum):
    """Market session types."""

    PRE_MARKET = "pre_market"  # 4:00-9:30 AM ET
    REGULAR = "regular"  # 9:30 AM - 4:00 PM ET
    AFTER_HOURS = "after_hours"  # 4:00-8:00 PM ET
    CLOSED = "closed"  # Outside trading hours


class DayType(Enum):
    """Trading day characteristics."""

    MONDAY = "monday"  # Often continuation from weekend
    TUESDAY = "tuesday"  # Historically lower volatility
    WEDNESDAY = "wednesday"  # Mid-week
    THURSDAY = "thursday"  # Pre-Friday positioning
    FRIDAY = "friday"  # End of week, often profit-taking
    WEEKEND = "weekend"  # Markets closed


@dataclass
class TemporalContext:
    """Temporal context for LLM prompts."""

    market_session: MarketSession
    day_type: DayType
    timestamp: str
    minutes_since_open: int | None
    minutes_until_close: int | None
    is_first_hour: bool
    is_last_hour: bool
    is_lunch_lull: bool  # 12:00-1:00 PM ET typically lower volume

    # Market regime (from RegimeDetector)
    volatility_regime: str | None = None
    trend_regime: str | None = None
    market_regime: str | None = None

    # Recent trend context
    trend_1d: str | None = None  # "up", "down", "flat"
    trend_5d: str | None = None
    trend_20d: str | None = None

    # Event context
    upcoming_events: list[str] = field(default_factory=list)


@dataclass
class MarketDataSchema:
    """Structured JSON schema for market data sent to LLMs."""

    symbol: str
    timeframe: str  # "1min", "5min", "1h", "1d"
    timestamp: str

    # OHLCV
    price: dict = field(default_factory=dict)  # open, high, low, close, volume

    # Technical Indicators
    indicators: dict = field(default_factory=dict)

    # Market Context
    context: dict = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string for LLM consumption."""
        return json.dumps(asdict(self), indent=2)

    @classmethod
    def from_market_data(
        cls,
        symbol: str,
        market_data: dict[str, Any],
        timeframe: str = "1d",
    ) -> "MarketDataSchema":
        """
        Create schema from raw market data dictionary.

        Args:
            symbol: Trading symbol
            market_data: Raw market data dict
            timeframe: Data timeframe

        Returns:
            Structured MarketDataSchema
        """
        # Extract price data
        price = {
            "open": market_data.get("open"),
            "high": market_data.get("high"),
            "low": market_data.get("low"),
            "close": market_data.get("close"),
            "volume": market_data.get("volume"),
            "vwap": market_data.get("vwap"),
        }

        # Extract technical indicators
        indicators = {
            "trend": {
                "macd": market_data.get("macd"),
                "macd_signal": market_data.get("macd_signal"),
                "macd_histogram": market_data.get("macd_histogram"),
                "sma_20": market_data.get("sma_20") or market_data.get("ma_20"),
                "sma_50": market_data.get("sma_50") or market_data.get("ma_50"),
                "ema_12": market_data.get("ema_12"),
                "ema_26": market_data.get("ema_26"),
                "adx": market_data.get("adx"),
            },
            "momentum": {
                "rsi": market_data.get("rsi"),
                "rsi_14": market_data.get("rsi_14"),
                "stochastic_k": market_data.get("stochastic_k"),
                "stochastic_d": market_data.get("stochastic_d"),
                "momentum": market_data.get("momentum"),
            },
            "volatility": {
                "atr": market_data.get("atr"),
                "atr_percent": market_data.get("atr_pct"),
                "bb_upper": market_data.get("bb_upper"),
                "bb_middle": market_data.get("bb_middle"),
                "bb_lower": market_data.get("bb_lower"),
                "bb_width": market_data.get("bb_width"),
            },
            "volume": {
                "volume_ratio": market_data.get("volume_ratio"),
                "obv": market_data.get("obv"),
                "volume_sma": market_data.get("volume_sma"),
            },
        }

        # Remove None values for cleaner output
        indicators = {
            category: {k: v for k, v in signals.items() if v is not None}
            for category, signals in indicators.items()
        }
        indicators = {k: v for k, v in indicators.items() if v}

        # Extract context
        context = {
            "price_change_1d": market_data.get("return_1d")
            or market_data.get("price_change_1d"),
            "price_change_5d": market_data.get("return_5d")
            or market_data.get("price_change_5d"),
            "relative_volume": market_data.get("volume_ratio"),
            "distance_from_high": market_data.get("distance_from_high"),
            "distance_from_low": market_data.get("distance_from_low"),
        }
        context = {k: v for k, v in context.items() if v is not None}

        return cls(
            symbol=symbol,
            timeframe=timeframe,
            timestamp=datetime.now(pytz.UTC).isoformat(),
            price={k: v for k, v in price.items() if v is not None},
            indicators=indicators,
            context=context,
        )


class PromptEngineer:
    """
    Prompt engineering utilities for time series LLM analysis.

    Implements strategies from MachineLearningMastery for effective
    LLM prompting in financial time series contexts.
    """

    def __init__(self):
        self.et_tz = pytz.timezone("US/Eastern")

    def get_temporal_context(
        self,
        regime_state: Any | None = None,
        recent_returns: dict[str, float] | None = None,
        upcoming_events: list[str] | None = None,
    ) -> TemporalContext:
        """
        Generate temporal context for the current moment.

        Args:
            regime_state: RegimeState from regime_detection module
            recent_returns: Dict with '1d', '5d', '20d' returns
            upcoming_events: List of upcoming market events

        Returns:
            TemporalContext with market session info
        """
        now = datetime.now(self.et_tz)
        market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
        market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)

        # Determine market session
        if now.weekday() >= 5:  # Weekend
            session = MarketSession.CLOSED
            day_type = DayType.WEEKEND
        else:
            day_type = DayType(now.strftime("%A").lower())
            hour = now.hour
            minute = now.minute

            if hour < 4:
                session = MarketSession.CLOSED
            elif hour < 9 or (hour == 9 and minute < 30):
                session = MarketSession.PRE_MARKET
            elif hour < 16:
                session = MarketSession.REGULAR
            elif hour < 20:
                session = MarketSession.AFTER_HOURS
            else:
                session = MarketSession.CLOSED

        # Calculate session timing
        minutes_since_open = None
        minutes_until_close = None
        is_first_hour = False
        is_last_hour = False
        is_lunch_lull = False

        if session == MarketSession.REGULAR:
            minutes_since_open = int((now - market_open).total_seconds() / 60)
            minutes_until_close = int((market_close - now).total_seconds() / 60)
            is_first_hour = minutes_since_open < 60
            is_last_hour = minutes_until_close < 60
            is_lunch_lull = 12 <= now.hour < 13

        # Parse trend from returns
        def return_to_trend(ret: float | None) -> str | None:
            if ret is None:
                return None
            if ret > 0.005:
                return "up"
            elif ret < -0.005:
                return "down"
            return "flat"

        recent_returns = recent_returns or {}

        # Extract regime info
        vol_regime = None
        trend_regime = None
        market_regime = None
        if regime_state:
            vol_regime = getattr(regime_state.volatility_regime, "value", None)
            trend_regime = getattr(regime_state.trend_regime, "value", None)
            market_regime = getattr(regime_state.market_regime, "value", None)

        return TemporalContext(
            market_session=session,
            day_type=day_type,
            timestamp=now.isoformat(),
            minutes_since_open=minutes_since_open,
            minutes_until_close=minutes_until_close,
            is_first_hour=is_first_hour,
            is_last_hour=is_last_hour,
            is_lunch_lull=is_lunch_lull,
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            market_regime=market_regime,
            trend_1d=return_to_trend(recent_returns.get("1d")),
            trend_5d=return_to_trend(recent_returns.get("5d")),
            trend_20d=return_to_trend(recent_returns.get("20d")),
            upcoming_events=upcoming_events or [],
        )

    def build_temporal_header(self, context: TemporalContext) -> str:
        """
        Build temporal context header for LLM prompts.

        Args:
            context: TemporalContext with market timing info

        Returns:
            Formatted header string
        """
        lines = ["<temporal_context>"]

        # Market session
        session_desc = {
            MarketSession.PRE_MARKET: "Pre-market session (4:00-9:30 AM ET) - Lower liquidity, wider spreads",
            MarketSession.REGULAR: "Regular trading hours (9:30 AM - 4:00 PM ET)",
            MarketSession.AFTER_HOURS: "After-hours session (4:00-8:00 PM ET) - Lower liquidity",
            MarketSession.CLOSED: "Markets closed",
        }
        lines.append(f"Session: {session_desc[context.market_session]}")

        # Day characteristics
        day_desc = {
            DayType.MONDAY: "Monday - Often sets weekly direction, weekend news digestion",
            DayType.TUESDAY: "Tuesday - Historically lower volatility",
            DayType.WEDNESDAY: "Wednesday - Mid-week, often FOMC announcements",
            DayType.THURSDAY: "Thursday - Pre-Friday positioning, jobless claims",
            DayType.FRIDAY: "Friday - End of week, often profit-taking and position squaring",
            DayType.WEEKEND: "Weekend - Markets closed",
        }
        lines.append(f"Day: {day_desc[context.day_type]}")

        # Session timing
        if context.market_session == MarketSession.REGULAR:
            lines.append(f"Time into session: {context.minutes_since_open} minutes")
            lines.append(f"Time until close: {context.minutes_until_close} minutes")

            if context.is_first_hour:
                lines.append(
                    "⚠️ First hour of trading - Higher volatility, avoid chasing opening moves"
                )
            if context.is_last_hour:
                lines.append(
                    "⚠️ Last hour of trading - End-of-day flows, potential mean reversion"
                )
            if context.is_lunch_lull:
                lines.append("📊 Lunch hour - Typically lower volume and tighter ranges")

        # Market regime
        if context.volatility_regime:
            vol_warnings = {
                "low": "Low volatility - Tighter stops, smaller moves expected",
                "medium": "Normal volatility conditions",
                "high": "High volatility - Wider stops, larger position sizing adjustments",
                "extreme": "⚠️ EXTREME volatility - Crisis conditions, reduce position sizes",
            }
            lines.append(f"Volatility Regime: {vol_warnings.get(context.volatility_regime, context.volatility_regime)}")

        if context.trend_regime:
            lines.append(f"Trend Regime: {context.trend_regime}")

        if context.market_regime:
            lines.append(f"Market Regime: {context.market_regime}")

        # Recent trend context
        if any([context.trend_1d, context.trend_5d, context.trend_20d]):
            trends = []
            if context.trend_1d:
                trends.append(f"1-day: {context.trend_1d}")
            if context.trend_5d:
                trends.append(f"5-day: {context.trend_5d}")
            if context.trend_20d:
                trends.append(f"20-day: {context.trend_20d}")
            lines.append(f"Recent Trends: {', '.join(trends)}")

        # Upcoming events
        if context.upcoming_events:
            lines.append(f"Upcoming Events: {', '.join(context.upcoming_events)}")

        lines.append("</temporal_context>")
        return "\n".join(lines)

    def build_feature_extraction_prompt(
        self,
        market_data: MarketDataSchema,
        temporal_header: str,
    ) -> tuple[str, str]:
        """
        Build Phase 1 prompt: Feature extraction before prediction.

        Args:
            market_data: Structured market data
            temporal_header: Temporal context header

        Returns:
            Tuple of (prompt, system_prompt)
        """
        prompt = f"""You are performing Phase 1 analysis: Feature Extraction.

{temporal_header}

<market_data>
{market_data.to_json()}
</market_data>

Analyze the data and extract key features. Do NOT make predictions yet.

Identify and report:
1. **Trend Analysis**: Current trend direction and strength based on MAs and MACD
2. **Momentum State**: RSI overbought/oversold, momentum divergences
3. **Volatility Assessment**: Current volatility vs recent history, Bollinger Band position
4. **Volume Confirmation**: Is volume confirming or diverging from price action?
5. **Key Levels**: Support/resistance levels visible in the data
6. **Anomalies**: Any unusual patterns or outliers

Format your response as JSON:
{{
    "trend": {{
        "direction": "bullish|bearish|neutral",
        "strength": "strong|moderate|weak",
        "ma_alignment": "bullish|bearish|mixed",
        "macd_signal": "bullish|bearish|neutral"
    }},
    "momentum": {{
        "rsi_state": "overbought|neutral|oversold",
        "rsi_value": <number>,
        "divergence": "bullish|bearish|none"
    }},
    "volatility": {{
        "level": "high|normal|low",
        "bb_position": "upper|middle|lower",
        "expanding": true|false
    }},
    "volume": {{
        "relative": "above_average|average|below_average",
        "confirming_price": true|false
    }},
    "key_levels": {{
        "nearest_support": <price or null>,
        "nearest_resistance": <price or null>
    }},
    "anomalies": ["list of any unusual patterns"],
    "feature_summary": "<1-2 sentence summary of extracted features>"
}}
"""

        system_prompt = """You are a quantitative analyst performing feature extraction on market data.
Your role is to objectively identify patterns and features WITHOUT making predictions.
Focus on technical indicator states, not future forecasts.
Be precise and data-driven in your assessments."""

        return prompt, system_prompt

    def build_prediction_prompt(
        self,
        market_data: MarketDataSchema,
        temporal_header: str,
        extracted_features: dict[str, Any],
    ) -> tuple[str, str]:
        """
        Build Phase 2 prompt: Prediction based on extracted features.

        Args:
            market_data: Structured market data
            temporal_header: Temporal context header
            extracted_features: Features from Phase 1

        Returns:
            Tuple of (prompt, system_prompt)
        """
        prompt = f"""You are performing Phase 2 analysis: Trading Prediction.

{temporal_header}

<market_data>
{market_data.to_json()}
</market_data>

<extracted_features>
{json.dumps(extracted_features, indent=2)}
</extracted_features>

Based on the extracted features and market context, provide your trading analysis.

Consider:
1. How do the temporal factors (session, day, time) affect your prediction?
2. What do the extracted features suggest about near-term direction?
3. What is the risk/reward of potential trades?
4. What would invalidate your thesis?

Format your response as JSON:
{{
    "sentiment": <score from -1.0 (very bearish) to 1.0 (very bullish)>,
    "confidence": <0.0 to 1.0>,
    "direction": "bullish|bearish|neutral",
    "recommendation": "strong_buy|buy|hold|sell|strong_sell",
    "reasoning": "<detailed reasoning based on features>",
    "key_factors": ["top 3 factors driving this assessment"],
    "risks": ["top 2-3 risks to this view"],
    "invalidation": "<what would invalidate this thesis>",
    "time_horizon": "intraday|1-3_days|1_week"
}}
"""

        system_prompt = """You are a senior trading analyst providing actionable recommendations.
Your analysis is based on pre-extracted features - trust the feature extraction and focus on synthesis.
Provide honest confidence levels - if uncertain, say so.
Consider the temporal context carefully in your recommendations.
Risk management is paramount - always note what could go wrong."""

        return prompt, system_prompt

    def build_enhanced_sentiment_prompt(
        self,
        symbol: str,
        market_data: dict[str, Any],
        news: list[dict[str, Any]],
        regime_state: Any | None = None,
        recent_returns: dict[str, float] | None = None,
    ) -> tuple[str, str]:
        """
        Build an enhanced sentiment analysis prompt with temporal context.

        This is the main integration point - use this in place of the
        existing sentiment prompt in multi_llm_analysis.py.

        Args:
            symbol: Trading symbol
            market_data: Raw market data dictionary
            news: List of news articles
            regime_state: Optional RegimeState from regime_detection
            recent_returns: Optional dict with '1d', '5d', '20d' returns

        Returns:
            Tuple of (prompt, system_prompt)
        """
        # Build temporal context
        temporal_ctx = self.get_temporal_context(
            regime_state=regime_state,
            recent_returns=recent_returns,
        )
        temporal_header = self.build_temporal_header(temporal_ctx)

        # Build structured market data
        schema = MarketDataSchema.from_market_data(
            symbol=symbol,
            market_data=market_data,
        )

        # Format news
        news_summary = "\n".join(
            [
                f"- {article.get('title', 'N/A')}: {article.get('content', '')[:200]}..."
                for article in news[:5]
            ]
        )

        prompt = f"""Analyze the market data and news for {symbol} to provide a sentiment assessment.

{temporal_header}

<market_data>
{schema.to_json()}
</market_data>

<recent_news>
{news_summary if news else "No recent news available."}
</recent_news>

Provide your analysis considering:
1. Technical indicator alignment (trend, momentum, volatility)
2. News sentiment and potential impact
3. Current market context (session, regime, timing)
4. Risk factors

Format your response as JSON:
{{
    "sentiment": <score from -1.0 (very bearish) to 1.0 (very bullish)>,
    "confidence": <0.0 to 1.0 - be honest about uncertainty>,
    "reasoning": "<detailed analysis>",
    "technical_view": "bullish|bearish|neutral",
    "news_impact": "positive|negative|neutral|mixed",
    "key_factors": ["top 3 factors"],
    "risks": ["top 2 risks"]
}}
"""

        system_prompt = """You are an expert financial analyst specializing in market sentiment analysis.

Key principles:
1. TEMPORAL AWARENESS: Consider market session, day of week, and time remaining in session
2. REGIME AWARENESS: Adapt analysis based on current volatility and trend regime
3. TECHNICAL-FUNDAMENTAL SYNTHESIS: Combine indicator signals with news sentiment
4. HONEST CONFIDENCE: If signals conflict or data is sparse, lower your confidence score
5. RISK FOCUS: Always highlight what could go wrong

Provide objective, data-driven analysis. When uncertain, say so."""

        return prompt, system_prompt


# Convenience functions for easy integration
def get_temporal_header(
    regime_state: Any | None = None,
    recent_returns: dict[str, float] | None = None,
) -> str:
    """
    Get temporal context header for current moment.

    Quick helper for adding temporal context to existing prompts.
    """
    engineer = PromptEngineer()
    ctx = engineer.get_temporal_context(regime_state, recent_returns)
    return engineer.build_temporal_header(ctx)


def format_market_data_structured(
    symbol: str,
    market_data: dict[str, Any],
    timeframe: str = "1d",
) -> str:
    """
    Convert raw market data to structured JSON schema.

    Quick helper for formatting market data.
    """
    schema = MarketDataSchema.from_market_data(symbol, market_data, timeframe)
    return schema.to_json()

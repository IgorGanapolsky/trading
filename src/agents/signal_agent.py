"""
Signal Agent - Entry/Exit Signals with Introspection

This agent generates buy/sell/hold signals based on technical indicators
with introspection to check indicator consensus and detect extreme conditions.

Key Features:
    - MACD indicator analysis
    - RSI overbought/oversold detection
    - Volume ratio confirmation
    - Momentum scoring
    - Indicator consensus checking
    - Extreme condition detection

Author: Trading System
Created: 2025-11-03
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import pandas as pd
import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Trading signal types."""
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


@dataclass
class SignalIntrospection:
    """Introspection results for signal generation."""
    indicator_consensus: float
    extreme_conditions: bool
    contradictions: List[str]
    warnings: List[str]
    confidence_adjustment: float


@dataclass
class SignalOutput:
    """Output from signal agent."""
    signal: SignalType
    confidence: float
    symbol: str
    indicators: Dict[str, any]
    introspection: SignalIntrospection
    timestamp: datetime
    reason: str


class SignalAgent:
    """
    Signal Agent for generating trading signals with introspection.

    This agent analyzes technical indicators and generates buy/sell/hold signals,
    then performs introspection to check indicator consensus and detect extremes.

    Attributes:
        rsi_period: Period for RSI calculation
        rsi_oversold: RSI oversold threshold
        rsi_overbought: RSI overbought threshold
        macd_fast: MACD fast period
        macd_slow: MACD slow period
        macd_signal: MACD signal period
    """

    RSI_PERIOD = 14
    RSI_OVERSOLD = 30
    RSI_OVERBOUGHT = 70

    MACD_FAST_PERIOD = 12
    MACD_SLOW_PERIOD = 26
    MACD_SIGNAL_PERIOD = 9

    def __init__(
        self,
        rsi_period: int = RSI_PERIOD,
        rsi_oversold: float = RSI_OVERSOLD,
        rsi_overbought: float = RSI_OVERBOUGHT,
    ):
        """
        Initialize the Signal Agent.

        Args:
            rsi_period: Period for RSI calculation
            rsi_oversold: RSI oversold threshold
            rsi_overbought: RSI overbought threshold
        """
        self.rsi_period = rsi_period
        self.rsi_oversold = rsi_oversold
        self.rsi_overbought = rsi_overbought

        logger.info("SignalAgent initialized")
        logger.info(f"  RSI Period: {rsi_period}")
        logger.info(f"  RSI Oversold: {rsi_oversold}")
        logger.info(f"  RSI Overbought: {rsi_overbought}")

    def generate_signal(
        self,
        symbol: str,
        research_output: Optional[any] = None,
    ) -> SignalOutput:
        """
        Generate trading signal with introspection.

        Args:
            symbol: Symbol to analyze
            research_output: Optional research agent output for context

        Returns:
            SignalOutput with signal and introspection results
        """
        logger.info("=" * 80)
        logger.info(f"SIGNAL AGENT: Generating Signal for {symbol}")
        logger.info("=" * 80)

        hist = self._fetch_historical_data(symbol)
        if hist is None or len(hist) < 126:
            logger.error(f"Insufficient data for {symbol}")
            return self._create_hold_signal(symbol, "Insufficient historical data")

        indicators = self._calculate_indicators(hist)

        individual_signals = self._get_individual_signals(indicators)

        introspection = self._perform_introspection(indicators, individual_signals)

        final_signal = self._aggregate_signals(individual_signals, introspection)

        confidence = self._calculate_confidence(introspection, research_output)

        reason = self._generate_reason(final_signal, indicators, introspection)

        output = SignalOutput(
            signal=final_signal,
            confidence=confidence,
            symbol=symbol,
            indicators=indicators,
            introspection=introspection,
            timestamp=datetime.now(),
            reason=reason,
        )

        logger.info(f"Signal: {final_signal.value.upper()}")
        logger.info(f"Confidence: {confidence:.2f}")
        logger.info(f"Indicator Consensus: {introspection.indicator_consensus:.2f}")
        logger.info(f"Reason: {reason}")

        if introspection.warnings:
            for warning in introspection.warnings:
                logger.warning(f"  ⚠️  {warning}")

        return output

    def _fetch_historical_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch historical price data for symbol.

        Args:
            symbol: Symbol to fetch

        Returns:
            DataFrame with historical data or None
        """
        try:
            end_date = datetime.now()
            start_date = end_date - timedelta(days=200)

            ticker = yf.Ticker(symbol)
            hist = ticker.history(start=start_date, end=end_date)

            logger.debug(f"Fetched {len(hist)} bars for {symbol}")
            return hist
        except Exception as e:
            logger.error(f"Failed to fetch data for {symbol}: {e}")
            return None

    def _calculate_indicators(self, hist: pd.DataFrame) -> Dict[str, any]:
        """
        Calculate all technical indicators.

        Args:
            hist: Historical price data

        Returns:
            Dictionary of indicator values
        """
        rsi = self._calculate_rsi(hist["Close"])
        macd_value, macd_signal, macd_histogram = self._calculate_macd(hist["Close"])
        volume_ratio = self._calculate_volume_ratio(hist)

        returns_1m = self._calculate_period_return(hist, 21)
        returns_3m = self._calculate_period_return(hist, 63)

        momentum_score = (returns_1m * 0.5 + returns_3m * 0.5) * 100

        return {
            "rsi": rsi,
            "macd_value": macd_value,
            "macd_signal": macd_signal,
            "macd_histogram": macd_histogram,
            "volume_ratio": volume_ratio,
            "momentum_score": momentum_score,
            "returns_1m": returns_1m,
            "returns_3m": returns_3m,
        }

    def _calculate_rsi(self, prices: pd.Series) -> float:
        """Calculate RSI indicator."""
        delta = prices.diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=self.rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=self.rsi_period).mean()
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        return float(rsi.iloc[-1])

    def _calculate_macd(self, prices: pd.Series) -> Tuple[float, float, float]:
        """Calculate MACD indicator."""
        exp1 = prices.ewm(span=self.MACD_FAST_PERIOD, adjust=False).mean()
        exp2 = prices.ewm(span=self.MACD_SLOW_PERIOD, adjust=False).mean()
        macd = exp1 - exp2
        signal = macd.ewm(span=self.MACD_SIGNAL_PERIOD, adjust=False).mean()
        histogram = macd - signal

        return (
            float(macd.iloc[-1]),
            float(signal.iloc[-1]),
            float(histogram.iloc[-1]),
        )

    def _calculate_volume_ratio(self, hist: pd.DataFrame) -> float:
        """Calculate volume ratio vs 20-day average."""
        avg_volume = hist["Volume"].rolling(window=20).mean()
        current_volume = hist["Volume"].iloc[-1]
        return float(current_volume / avg_volume.iloc[-1])

    def _calculate_period_return(self, hist: pd.DataFrame, periods: int) -> float:
        """Calculate return over specified periods."""
        if len(hist) < periods:
            periods = len(hist) - 1

        if periods <= 0:
            return 0.0

        end_price = hist["Close"].iloc[-1]
        start_price = hist["Close"].iloc[-periods]

        return float((end_price - start_price) / start_price)

    def _get_individual_signals(self, indicators: Dict[str, any]) -> Dict[str, SignalType]:
        """
        Get individual signals from each indicator.

        Args:
            indicators: Dictionary of indicator values

        Returns:
            Dictionary mapping indicator name to signal
        """
        signals = {}

        if indicators["macd_histogram"] > 0:
            signals["macd"] = SignalType.BUY
        elif indicators["macd_histogram"] < 0:
            signals["macd"] = SignalType.SELL
        else:
            signals["macd"] = SignalType.HOLD

        if indicators["rsi"] < self.rsi_oversold:
            signals["rsi"] = SignalType.BUY
        elif indicators["rsi"] > self.rsi_overbought:
            signals["rsi"] = SignalType.SELL
        else:
            signals["rsi"] = SignalType.HOLD

        if indicators["volume_ratio"] > 1.5:
            signals["volume"] = SignalType.BUY
        elif indicators["volume_ratio"] < 0.8:
            signals["volume"] = SignalType.SELL
        else:
            signals["volume"] = SignalType.HOLD

        if indicators["momentum_score"] > 5:
            signals["momentum"] = SignalType.BUY
        elif indicators["momentum_score"] < -5:
            signals["momentum"] = SignalType.SELL
        else:
            signals["momentum"] = SignalType.HOLD

        return signals

    def _perform_introspection(
        self,
        indicators: Dict[str, any],
        individual_signals: Dict[str, SignalType],
    ) -> SignalIntrospection:
        """
        Perform introspection to check indicator consensus and extremes.

        This asks:
        - "Do my indicators agree?"
        - "Are we at an extreme that could reverse?"
        - "Are there any contradictions?"

        Args:
            indicators: Dictionary of indicator values
            individual_signals: Individual signals from each indicator

        Returns:
            SignalIntrospection with consensus and warnings
        """
        logger.info("🔍 INTROSPECTION: Checking indicator consensus...")

        warnings = []
        contradictions = []
        confidence_adjustment = 0.0

        buy_count = sum(1 for s in individual_signals.values() if s == SignalType.BUY)
        sell_count = sum(1 for s in individual_signals.values() if s == SignalType.SELL)
        total_count = len(individual_signals)

        consensus = max(buy_count, sell_count) / total_count

        if consensus < 0.75:
            warnings.append(
                f"Low indicator consensus ({consensus:.0%}) - signals disagree"
            )
            confidence_adjustment -= 0.2

        extreme_conditions = False
        if indicators["rsi"] > 80:
            warnings.append(f"Severely overbought (RSI={indicators['rsi']:.1f})")
            contradictions.append("RSI extremely overbought - avoid BUY signals")
            confidence_adjustment -= 0.3
            extreme_conditions = True
        elif indicators["rsi"] < 20:
            warnings.append(f"Severely oversold (RSI={indicators['rsi']:.1f})")
            contradictions.append("RSI extremely oversold - avoid SELL signals")
            confidence_adjustment -= 0.3
            extreme_conditions = True

        if buy_count > 0 and sell_count > 0:
            contradictions.append(
                f"Mixed signals: {buy_count} BUY, {sell_count} SELL"
            )

        logger.info(f"  Indicator Consensus: {consensus:.2%}")
        logger.info(f"  Extreme Conditions: {extreme_conditions}")
        logger.info(f"  Confidence Adjustment: {confidence_adjustment:+.2f}")

        return SignalIntrospection(
            indicator_consensus=consensus,
            extreme_conditions=extreme_conditions,
            contradictions=contradictions,
            warnings=warnings,
            confidence_adjustment=confidence_adjustment,
        )

    def _aggregate_signals(
        self,
        individual_signals: Dict[str, SignalType],
        introspection: SignalIntrospection,
    ) -> SignalType:
        """
        Aggregate individual signals into final signal.

        Args:
            individual_signals: Individual signals from each indicator
            introspection: Introspection results

        Returns:
            Final aggregated signal
        """
        if introspection.indicator_consensus < 0.75:
            return SignalType.HOLD

        buy_count = sum(1 for s in individual_signals.values() if s == SignalType.BUY)
        sell_count = sum(1 for s in individual_signals.values() if s == SignalType.SELL)

        if buy_count > sell_count:
            return SignalType.BUY
        elif sell_count > buy_count:
            return SignalType.SELL
        else:
            return SignalType.HOLD

    def _calculate_confidence(
        self,
        introspection: SignalIntrospection,
        research_output: Optional[any],
    ) -> float:
        """
        Calculate confidence in the signal.

        Args:
            introspection: Introspection results
            research_output: Optional research output

        Returns:
            Confidence score (0.0 to 1.0)
        """
        base_confidence = 0.8

        confidence = base_confidence + introspection.confidence_adjustment

        if research_output and hasattr(research_output, 'confidence'):
            confidence = (confidence + research_output.confidence) / 2

        return max(0.0, min(1.0, confidence))

    def _generate_reason(
        self,
        signal: SignalType,
        indicators: Dict[str, any],
        introspection: SignalIntrospection,
    ) -> str:
        """Generate human-readable reason for signal."""
        if signal == SignalType.HOLD:
            if introspection.indicator_consensus < 0.75:
                return f"HOLD: Low indicator consensus ({introspection.indicator_consensus:.0%})"
            return "HOLD: No strong signal from indicators"

        reasons = []
        if indicators["macd_histogram"] > 0:
            reasons.append("MACD bullish")
        elif indicators["macd_histogram"] < 0:
            reasons.append("MACD bearish")

        if indicators["rsi"] < self.rsi_oversold:
            reasons.append("RSI oversold")
        elif indicators["rsi"] > self.rsi_overbought:
            reasons.append("RSI overbought")

        if indicators["volume_ratio"] > 1.5:
            reasons.append("high volume")

        return f"{signal.value.upper()}: {', '.join(reasons)}"

    def _create_hold_signal(self, symbol: str, reason: str) -> SignalOutput:
        """Create a HOLD signal with given reason."""
        return SignalOutput(
            signal=SignalType.HOLD,
            confidence=0.0,
            symbol=symbol,
            indicators={},
            introspection=SignalIntrospection(
                indicator_consensus=0.0,
                extreme_conditions=False,
                contradictions=[],
                warnings=[reason],
                confidence_adjustment=0.0,
            ),
            timestamp=datetime.now(),
            reason=reason,
        )

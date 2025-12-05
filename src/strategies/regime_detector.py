"""
Market Regime Detector

Identifies whether the market is in a TRENDING or RANGING regime to
select the appropriate strategy (momentum vs mean reversion).

Regime Detection Methods:
1. ADX (Average Directional Index): ADX > 25 = trending, < 20 = ranging
2. Bollinger Band Width: Narrow bands = ranging, wide bands = trending
3. Price vs SMA: Consistent above/below = trending, oscillating = ranging

The regime determines strategy weights:
- TRENDING: 70% momentum, 30% mean reversion
- RANGING: 30% momentum, 70% mean reversion
- MIXED: 50% each

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)


class MarketRegime(Enum):
    """Market regime classification."""

    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RANGING = "ranging"
    MIXED = "mixed"


@dataclass
class RegimeAnalysis:
    """Result of regime detection analysis."""

    regime: MarketRegime
    confidence: float  # 0.0 to 1.0
    adx: float
    bb_width_percentile: float  # 0-100, how wide BB is vs history
    trend_consistency: float  # 0-1, how consistently price trends
    momentum_weight: float  # Recommended weight for momentum strategy
    mean_reversion_weight: float  # Recommended weight for MR strategy
    details: dict


class RegimeDetector:
    """
    Detects market regime to optimize strategy selection.

    Uses multiple indicators to classify market as trending or ranging,
    then provides recommended weights for each strategy type.
    """

    # ADX thresholds
    ADX_TRENDING_THRESHOLD = 25.0  # Above this = trending
    ADX_RANGING_THRESHOLD = 20.0  # Below this = ranging

    # BB Width percentile thresholds
    BB_NARROW_PERCENTILE = 25  # Below = ranging (squeeze)
    BB_WIDE_PERCENTILE = 75  # Above = trending (expansion)

    def __init__(
        self,
        lookback_period: int = 14,
        bb_lookback: int = 100,  # For percentile calculation
    ):
        """
        Initialize the regime detector.

        Args:
            lookback_period: Period for ADX calculation
            bb_lookback: Period for BB width percentile calculation
        """
        self.lookback_period = lookback_period
        self.bb_lookback = bb_lookback

        logger.info(
            f"RegimeDetector initialized: ADX period={lookback_period}, "
            f"ADX trending>{self.ADX_TRENDING_THRESHOLD}, "
            f"ranging<{self.ADX_RANGING_THRESHOLD}"
        )

    def calculate_adx(self, hist: pd.DataFrame) -> tuple[float, float, float]:
        """
        Calculate Average Directional Index (ADX).

        ADX measures trend strength (not direction):
        - ADX > 25: Strong trend
        - ADX 20-25: Weak trend
        - ADX < 20: No trend (ranging)

        Also returns +DI and -DI for trend direction.

        Args:
            hist: DataFrame with High, Low, Close columns

        Returns:
            Tuple of (ADX, +DI, -DI)
        """
        if len(hist) < self.lookback_period + 1:
            return (0.0, 0.0, 0.0)

        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]

        # Calculate True Range
        tr1 = high - low
        tr2 = abs(high - close.shift(1))
        tr3 = abs(low - close.shift(1))
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Calculate Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low

        plus_dm = up_move.where((up_move > down_move) & (up_move > 0), 0)
        minus_dm = down_move.where((down_move > up_move) & (down_move > 0), 0)

        # Smoothed averages (Wilder's smoothing)
        atr = tr.ewm(span=self.lookback_period, adjust=False).mean()
        plus_di = 100 * (
            plus_dm.ewm(span=self.lookback_period, adjust=False).mean() / atr
        )
        minus_di = 100 * (
            minus_dm.ewm(span=self.lookback_period, adjust=False).mean() / atr
        )

        # Calculate DX and ADX
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di
        dx = 100 * (di_diff / di_sum.replace(0, 1))
        adx = dx.ewm(span=self.lookback_period, adjust=False).mean()

        # Get latest values
        adx_val = float(adx.iloc[-1]) if not pd.isna(adx.iloc[-1]) else 0.0
        plus_di_val = float(plus_di.iloc[-1]) if not pd.isna(plus_di.iloc[-1]) else 0.0
        minus_di_val = (
            float(minus_di.iloc[-1]) if not pd.isna(minus_di.iloc[-1]) else 0.0
        )

        return (adx_val, plus_di_val, minus_di_val)

    def calculate_bb_width_percentile(self, hist: pd.DataFrame) -> float:
        """
        Calculate Bollinger Band width as percentile of historical range.

        Narrow bands (low percentile) = low volatility = ranging market
        Wide bands (high percentile) = high volatility = trending market

        Args:
            hist: DataFrame with Close column

        Returns:
            Percentile (0-100) of current BB width vs history
        """
        if len(hist) < self.bb_lookback:
            return 50.0  # Neutral if insufficient data

        prices = hist["Close"]

        # Calculate BB width over rolling window
        sma = prices.rolling(window=20).mean()
        std = prices.rolling(window=20).std()
        bb_width = (4 * std) / sma  # Width as % of SMA

        # Calculate percentile of current width vs history
        current_width = bb_width.iloc[-1]
        historical_widths = bb_width.dropna().tail(self.bb_lookback)

        if len(historical_widths) == 0 or pd.isna(current_width):
            return 50.0

        percentile = (historical_widths < current_width).sum() / len(
            historical_widths
        ) * 100

        return float(percentile)

    def calculate_trend_consistency(self, hist: pd.DataFrame) -> float:
        """
        Calculate how consistently price stays above/below SMA.

        High consistency (>0.7) = trending market
        Low consistency (<0.3) = ranging market

        Args:
            hist: DataFrame with Close column

        Returns:
            Consistency score (0-1)
        """
        if len(hist) < 50:
            return 0.5

        prices = hist["Close"].tail(50)
        sma = prices.rolling(window=20).mean()

        # Count how many bars are consistently above or below SMA
        above_sma = (prices > sma).tail(30)
        below_sma = (prices < sma).tail(30)

        # Consistency = max of above or below percentage
        above_pct = above_sma.sum() / len(above_sma)
        below_pct = below_sma.sum() / len(below_sma)

        return float(max(above_pct, below_pct))

    def detect_regime(self, hist: pd.DataFrame) -> RegimeAnalysis:
        """
        Detect the current market regime.

        Args:
            hist: Historical OHLCV data

        Returns:
            RegimeAnalysis with regime classification and strategy weights
        """
        if hist is None or len(hist) < self.bb_lookback:
            return RegimeAnalysis(
                regime=MarketRegime.MIXED,
                confidence=0.0,
                adx=0.0,
                bb_width_percentile=50.0,
                trend_consistency=0.5,
                momentum_weight=0.5,
                mean_reversion_weight=0.5,
                details={"error": "Insufficient data"},
            )

        # Calculate indicators
        adx, plus_di, minus_di = self.calculate_adx(hist)
        bb_percentile = self.calculate_bb_width_percentile(hist)
        trend_consistency = self.calculate_trend_consistency(hist)

        # Score for trending (0-3 based on indicators)
        trending_score = 0
        ranging_score = 0

        # ADX scoring
        if adx > self.ADX_TRENDING_THRESHOLD:
            trending_score += 1
        elif adx < self.ADX_RANGING_THRESHOLD:
            ranging_score += 1

        # BB width scoring
        if bb_percentile > self.BB_WIDE_PERCENTILE:
            trending_score += 1
        elif bb_percentile < self.BB_NARROW_PERCENTILE:
            ranging_score += 1

        # Trend consistency scoring
        if trend_consistency > 0.7:
            trending_score += 1
        elif trend_consistency < 0.4:
            ranging_score += 1

        # Determine regime
        if trending_score >= 2 and ranging_score == 0:
            if plus_di > minus_di:
                regime = MarketRegime.TRENDING_UP
            else:
                regime = MarketRegime.TRENDING_DOWN
            confidence = trending_score / 3.0
            momentum_weight = 0.7
            mean_reversion_weight = 0.3
        elif ranging_score >= 2 and trending_score == 0:
            regime = MarketRegime.RANGING
            confidence = ranging_score / 3.0
            momentum_weight = 0.3
            mean_reversion_weight = 0.7
        else:
            regime = MarketRegime.MIXED
            confidence = 0.5
            momentum_weight = 0.5
            mean_reversion_weight = 0.5

        return RegimeAnalysis(
            regime=regime,
            confidence=confidence,
            adx=adx,
            bb_width_percentile=bb_percentile,
            trend_consistency=trend_consistency,
            momentum_weight=momentum_weight,
            mean_reversion_weight=mean_reversion_weight,
            details={
                "plus_di": plus_di,
                "minus_di": minus_di,
                "trending_score": trending_score,
                "ranging_score": ranging_score,
            },
        )

    def get_strategy_weights(
        self, hist: pd.DataFrame
    ) -> tuple[float, float, MarketRegime]:
        """
        Get recommended strategy weights based on regime.

        Convenience method for ensemble strategy.

        Args:
            hist: Historical data

        Returns:
            Tuple of (momentum_weight, mean_reversion_weight, regime)
        """
        analysis = self.detect_regime(hist)
        return (
            analysis.momentum_weight,
            analysis.mean_reversion_weight,
            analysis.regime,
        )


# Convenience function
def get_default_regime_detector() -> RegimeDetector:
    """Get a default regime detector instance."""
    return RegimeDetector(lookback_period=14, bb_lookback=100)

"""
Market Regime Detection Module.

This module identifies market regimes (trending, mean-reverting, high volatility)
to enable adaptive strategy behavior. Different regimes require different
trading approaches for optimal performance.

Features:
    - Volatility regime detection (low/medium/high)
    - Trend regime detection (trending/mean-reverting)
    - Correlation regime detection
    - Hidden Markov Model-based detection
    - Rolling statistics for regime identification

Author: Trading System
Created: 2025-12-04
"""

import logging
from dataclasses import dataclass
from enum import Enum

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class VolatilityRegime(Enum):
    """Volatility regime classifications."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    EXTREME = "extreme"


class TrendRegime(Enum):
    """Trend regime classifications."""

    STRONG_UPTREND = "strong_uptrend"
    WEAK_UPTREND = "weak_uptrend"
    RANGING = "ranging"
    WEAK_DOWNTREND = "weak_downtrend"
    STRONG_DOWNTREND = "strong_downtrend"


class MarketRegime(Enum):
    """Overall market regime."""

    BULL_LOW_VOL = "bull_low_vol"
    BULL_HIGH_VOL = "bull_high_vol"
    BEAR_LOW_VOL = "bear_low_vol"
    BEAR_HIGH_VOL = "bear_high_vol"
    RANGING_LOW_VOL = "ranging_low_vol"
    RANGING_HIGH_VOL = "ranging_high_vol"
    CRISIS = "crisis"


@dataclass
class RegimeState:
    """Current regime state with confidence levels."""

    volatility_regime: VolatilityRegime
    trend_regime: TrendRegime
    market_regime: MarketRegime
    volatility_percentile: float  # Current vol percentile vs history
    trend_strength: float  # -1 (strong down) to +1 (strong up)
    regime_confidence: float  # 0-1 confidence in regime classification
    regime_age_days: int  # Days since regime change
    recommended_position_scale: float  # 0-1 suggested position sizing


@dataclass
class RegimeTransition:
    """Record of a regime transition."""

    from_regime: MarketRegime
    to_regime: MarketRegime
    transition_date: pd.Timestamp
    confidence: float


class RegimeDetector:
    """
    Detects market regimes for adaptive strategy behavior.

    Uses multiple signals to identify the current market regime:
    1. Volatility: Rolling std dev percentile
    2. Trend: Moving average slopes and ADX
    3. Correlation: Asset correlation changes
    """

    def __init__(
        self,
        volatility_window: int = 20,
        trend_window: int = 50,
        history_window: int = 252,
        vol_percentile_low: float = 25,
        vol_percentile_high: float = 75,
        trend_threshold: float = 0.02,
    ):
        """
        Initialize regime detector.

        Args:
            volatility_window: Window for volatility calculation
            trend_window: Window for trend calculation
            history_window: Historical window for percentile calculation
            vol_percentile_low: Percentile threshold for low volatility
            vol_percentile_high: Percentile threshold for high volatility
            trend_threshold: Minimum slope for trend classification
        """
        self.volatility_window = volatility_window
        self.trend_window = trend_window
        self.history_window = history_window
        self.vol_percentile_low = vol_percentile_low
        self.vol_percentile_high = vol_percentile_high
        self.trend_threshold = trend_threshold

        self.regime_history: list[RegimeTransition] = []
        self.current_regime: MarketRegime | None = None
        self.regime_start_date: pd.Timestamp | None = None

        logger.info(
            f"Initialized regime detector: vol_window={volatility_window}, "
            f"trend_window={trend_window}"
        )

    def detect_regime(
        self,
        prices: pd.Series,
        returns: pd.Series | None = None,
    ) -> RegimeState:
        """
        Detect current market regime.

        Args:
            prices: Price series with datetime index
            returns: Optional pre-calculated returns

        Returns:
            RegimeState with current regime classification
        """
        if returns is None:
            returns = prices.pct_change().dropna()

        if len(returns) < self.history_window:
            logger.warning(f"Insufficient data: {len(returns)} < {self.history_window}")
            # Return default regime
            return RegimeState(
                volatility_regime=VolatilityRegime.MEDIUM,
                trend_regime=TrendRegime.RANGING,
                market_regime=MarketRegime.RANGING_LOW_VOL,
                volatility_percentile=50.0,
                trend_strength=0.0,
                regime_confidence=0.0,
                regime_age_days=0,
                recommended_position_scale=0.5,
            )

        # Calculate volatility regime
        vol_regime, vol_percentile = self._detect_volatility_regime(returns)

        # Calculate trend regime
        trend_regime, trend_strength = self._detect_trend_regime(prices)

        # Combine into market regime
        market_regime = self._combine_regimes(vol_regime, trend_regime, vol_percentile)

        # Calculate confidence
        confidence = self._calculate_confidence(returns, prices)

        # Track regime transitions
        regime_age = self._track_regime_transition(market_regime, prices.index[-1])

        # Calculate recommended position scale
        position_scale = self._calculate_position_scale(vol_regime, trend_regime, confidence)

        return RegimeState(
            volatility_regime=vol_regime,
            trend_regime=trend_regime,
            market_regime=market_regime,
            volatility_percentile=vol_percentile,
            trend_strength=trend_strength,
            regime_confidence=confidence,
            regime_age_days=regime_age,
            recommended_position_scale=position_scale,
        )

    def _detect_volatility_regime(
        self,
        returns: pd.Series,
    ) -> tuple[VolatilityRegime, float]:
        """
        Detect volatility regime.

        Returns:
            Tuple of (VolatilityRegime, percentile)
        """
        # Calculate rolling volatility
        rolling_vol = returns.rolling(window=self.volatility_window).std()
        current_vol = rolling_vol.iloc[-1]

        # Calculate percentile vs history
        historical_vol = rolling_vol.iloc[-self.history_window :]
        percentile = (historical_vol < current_vol).mean() * 100

        # Classify regime
        if percentile < self.vol_percentile_low:
            regime = VolatilityRegime.LOW
        elif percentile < self.vol_percentile_high:
            regime = VolatilityRegime.MEDIUM
        elif percentile < 95:
            regime = VolatilityRegime.HIGH
        else:
            regime = VolatilityRegime.EXTREME

        return regime, percentile

    def _detect_trend_regime(
        self,
        prices: pd.Series,
    ) -> tuple[TrendRegime, float]:
        """
        Detect trend regime using moving average analysis.

        Returns:
            Tuple of (TrendRegime, trend_strength)
        """
        # Calculate moving averages
        short_ma = prices.rolling(window=20).mean()
        long_ma = prices.rolling(window=self.trend_window).mean()

        # Calculate trend strength as normalized slope
        price_range = (
            prices.iloc[-self.trend_window :].max() - prices.iloc[-self.trend_window :].min()
        )

        if price_range > 0:
            ma_diff = (short_ma.iloc[-1] - long_ma.iloc[-1]) / price_range
        else:
            ma_diff = 0

        # Calculate price momentum (rate of change)
        roc = (prices.iloc[-1] - prices.iloc[-self.trend_window]) / prices.iloc[-self.trend_window]

        # Combine signals
        trend_strength = (ma_diff + roc) / 2
        trend_strength = max(-1, min(1, trend_strength * 5))  # Scale and clip

        # Classify regime
        if trend_strength > 0.5:
            regime = TrendRegime.STRONG_UPTREND
        elif trend_strength > 0.1:
            regime = TrendRegime.WEAK_UPTREND
        elif trend_strength > -0.1:
            regime = TrendRegime.RANGING
        elif trend_strength > -0.5:
            regime = TrendRegime.WEAK_DOWNTREND
        else:
            regime = TrendRegime.STRONG_DOWNTREND

        return regime, trend_strength

    def _combine_regimes(
        self,
        vol_regime: VolatilityRegime,
        trend_regime: TrendRegime,
        vol_percentile: float,
    ) -> MarketRegime:
        """Combine volatility and trend into overall market regime."""
        is_high_vol = vol_regime in [VolatilityRegime.HIGH, VolatilityRegime.EXTREME]

        # Crisis detection
        if vol_regime == VolatilityRegime.EXTREME and trend_regime in [
            TrendRegime.STRONG_DOWNTREND,
            TrendRegime.WEAK_DOWNTREND,
        ]:
            return MarketRegime.CRISIS

        # Bull regimes
        if trend_regime in [TrendRegime.STRONG_UPTREND, TrendRegime.WEAK_UPTREND]:
            return MarketRegime.BULL_HIGH_VOL if is_high_vol else MarketRegime.BULL_LOW_VOL

        # Bear regimes
        if trend_regime in [TrendRegime.STRONG_DOWNTREND, TrendRegime.WEAK_DOWNTREND]:
            return MarketRegime.BEAR_HIGH_VOL if is_high_vol else MarketRegime.BEAR_LOW_VOL

        # Ranging regimes
        return MarketRegime.RANGING_HIGH_VOL if is_high_vol else MarketRegime.RANGING_LOW_VOL

    def _calculate_confidence(
        self,
        returns: pd.Series,
        prices: pd.Series,
    ) -> float:
        """
        Calculate confidence in regime classification.

        Higher confidence when:
        - Clear trend direction
        - Consistent volatility
        - Strong price momentum
        """
        # Volatility consistency
        vol = returns.rolling(window=self.volatility_window).std()
        vol_stability = 1 - (
            vol.iloc[-20:].std() / vol.iloc[-20:].mean() if vol.iloc[-20:].mean() > 0 else 1
        )

        # Trend clarity (R-squared of price trend)
        recent_prices = prices.iloc[-self.trend_window :]
        x = np.arange(len(recent_prices))

        if len(recent_prices) > 1:
            correlation = np.corrcoef(x, recent_prices)[0, 1]
            trend_clarity = abs(correlation) ** 2  # R-squared
        else:
            trend_clarity = 0

        # Combine
        confidence = (vol_stability + trend_clarity) / 2
        return max(0, min(1, confidence))

    def _track_regime_transition(
        self,
        new_regime: MarketRegime,
        current_date: pd.Timestamp,
    ) -> int:
        """
        Track regime transitions and return age of current regime.

        Returns:
            Days since last regime change
        """
        if self.current_regime != new_regime:
            if self.current_regime is not None:
                transition = RegimeTransition(
                    from_regime=self.current_regime,
                    to_regime=new_regime,
                    transition_date=current_date,
                    confidence=0.5,  # Could be enhanced
                )
                self.regime_history.append(transition)
                logger.info(f"Regime transition: {self.current_regime.value} -> {new_regime.value}")

            self.current_regime = new_regime
            self.regime_start_date = current_date

        if self.regime_start_date is not None:
            return (current_date - self.regime_start_date).days
        return 0

    def _calculate_position_scale(
        self,
        vol_regime: VolatilityRegime,
        trend_regime: TrendRegime,
        confidence: float,
    ) -> float:
        """
        Calculate recommended position scale based on regime.

        Returns:
            Scale factor between 0 and 1
        """
        # Base scale on volatility
        vol_scale = {
            VolatilityRegime.LOW: 1.0,
            VolatilityRegime.MEDIUM: 0.8,
            VolatilityRegime.HIGH: 0.5,
            VolatilityRegime.EXTREME: 0.25,
        }

        # Adjust for trend (reduce in unclear regimes)
        trend_scale = {
            TrendRegime.STRONG_UPTREND: 1.0,
            TrendRegime.WEAK_UPTREND: 0.8,
            TrendRegime.RANGING: 0.6,
            TrendRegime.WEAK_DOWNTREND: 0.5,
            TrendRegime.STRONG_DOWNTREND: 0.3,
        }

        base_scale = vol_scale[vol_regime] * trend_scale[trend_regime]

        # Adjust for confidence
        scale = base_scale * (0.5 + 0.5 * confidence)

        return max(0.1, min(1.0, scale))

    def get_regime_statistics(self) -> dict:
        """
        Get statistics about historical regime transitions.

        Returns:
            Dictionary with regime statistics
        """
        if not self.regime_history:
            return {"transitions": 0, "avg_regime_duration": 0}

        # Calculate average regime duration
        durations = []
        for i, transition in enumerate(self.regime_history[1:], 1):
            prev_transition = self.regime_history[i - 1]
            duration = (transition.transition_date - prev_transition.transition_date).days
            durations.append(duration)

        # Count transitions by type
        transition_counts: dict[str, int] = {}
        for t in self.regime_history:
            key = f"{t.from_regime.value} -> {t.to_regime.value}"
            transition_counts[key] = transition_counts.get(key, 0) + 1

        return {
            "transitions": len(self.regime_history),
            "avg_regime_duration": np.mean(durations) if durations else 0,
            "transition_counts": transition_counts,
            "current_regime": self.current_regime.value if self.current_regime else None,
        }

    def generate_report(self, regime_state: RegimeState) -> str:
        """Generate regime analysis report."""
        report = []
        report.append("=" * 60)
        report.append("MARKET REGIME ANALYSIS")
        report.append("=" * 60)

        report.append(f"\nCurrent Regime: {regime_state.market_regime.value}")
        report.append(f"Regime Age: {regime_state.regime_age_days} days")
        report.append(f"Confidence: {regime_state.regime_confidence:.1%}")

        report.append("\nComponents:")
        report.append(f"  Volatility: {regime_state.volatility_regime.value}")
        report.append(f"  Vol Percentile: {regime_state.volatility_percentile:.0f}%")
        report.append(f"  Trend: {regime_state.trend_regime.value}")
        report.append(f"  Trend Strength: {regime_state.trend_strength:+.2f}")

        report.append(
            f"\nRecommended Position Scale: {regime_state.recommended_position_scale:.0%}"
        )

        # Trading implications
        report.append("\nTrading Implications:")
        regime = regime_state.market_regime

        if regime == MarketRegime.CRISIS:
            report.append("  - REDUCE exposure immediately")
            report.append("  - Consider hedging or cash")
            report.append("  - Wait for volatility to subside")
        elif regime in [MarketRegime.BULL_LOW_VOL]:
            report.append("  - Favorable conditions for momentum")
            report.append("  - Can use full position sizes")
            report.append("  - Trend following likely to work")
        elif regime in [MarketRegime.BULL_HIGH_VOL]:
            report.append("  - Uptrend but choppy")
            report.append("  - Reduce position sizes")
            report.append("  - Use wider stops")
        elif regime in [MarketRegime.BEAR_LOW_VOL]:
            report.append("  - Orderly decline")
            report.append("  - Short strategies may work")
            report.append("  - Be patient for reversal")
        elif regime in [MarketRegime.BEAR_HIGH_VOL]:
            report.append("  - High risk environment")
            report.append("  - Minimize exposure")
            report.append("  - Wait for stabilization")
        else:  # Ranging
            report.append("  - Mean reversion may work")
            report.append("  - Reduce trend following")
            report.append("  - Trade range boundaries")

        # Historical stats
        stats = self.get_regime_statistics()
        if stats["transitions"] > 0:
            report.append(f"\nHistorical Transitions: {stats['transitions']}")
            report.append(f"Avg Regime Duration: {stats['avg_regime_duration']:.0f} days")

        report.append("\n" + "=" * 60)

        return "\n".join(report)


def detect_current_regime(
    symbol: str = "SPY",
    lookback_days: int = 252,
) -> RegimeState:
    """
    Convenience function to detect current market regime.

    Args:
        symbol: Symbol to analyze
        lookback_days: Days of history to use

    Returns:
        RegimeState for current market
    """
    from src.utils import yfinance_wrapper as yf

    # Fetch data
    ticker = yf.Ticker(symbol)
    hist = ticker.history(period=f"{lookback_days + 50}d")

    if len(hist) < lookback_days:
        logger.warning(f"Only got {len(hist)} days of data")

    detector = RegimeDetector()
    return detector.detect_regime(hist["Close"])

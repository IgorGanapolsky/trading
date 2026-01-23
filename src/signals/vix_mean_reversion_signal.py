"""
VIX Mean Reversion Signal - Optimal Iron Condor Entry Timing.

Research backing (Jan 2026):
- LSEG Backtest: VIX mean reversion signals improve iron condor win rates
- 3-day MA smooths false alarms
- 2 std dev threshold adapts to market conditions
- Enter when VIX drops FROM a spike = premium still elevated, fear subsiding

Signal Logic:
1. Track VIX 30-day standard deviation of daily changes
2. Calculate 3-day moving average of VIX (smooths noise)
3. Detect "spike then drop" pattern
4. Signal OPTIMAL_ENTRY when VIX was elevated (>20) and is now falling

Created: January 22, 2026
Author: CTO Claude
Reference: LL-296 (VIX Mean Reversion Research)
"""

import logging
from dataclasses import dataclass
from typing import Optional

import numpy as np
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class VIXSignal:
    """VIX mean reversion signal result."""

    signal: str  # OPTIMAL_ENTRY, GOOD_ENTRY, NEUTRAL, AVOID
    current_vix: float
    vix_3day_ma: float
    recent_high: float
    threshold: float
    reason: str
    confidence: float  # 0.0 to 1.0


class VIXMeanReversionSignal:
    """
    VIX Mean Reversion Signal Generator.

    Identifies optimal iron condor entry windows by detecting
    when VIX drops from elevated levels (premium still rich,
    but fear subsiding = ideal selling opportunity).
    """

    # Configuration
    VIX_SPIKE_THRESHOLD = 20.0  # VIX above this = "elevated"
    VIX_OPTIMAL_MIN = 15.0      # VIX below this = premiums too thin
    VIX_OPTIMAL_MAX = 25.0      # VIX above this = too risky
    VIX_EXTREME = 30.0          # VIX above this = AVOID
    MA_PERIOD = 3               # 3-day moving average
    STD_LOOKBACK = 30           # 30-day std dev lookback
    STD_MULTIPLIER = 2.0        # 2 standard deviations for threshold

    def __init__(self):
        """Initialize the signal generator."""
        logger.info("VIXMeanReversionSignal initialized")
        self._cache: dict = {}

    def get_vix_data(self, lookback_days: int = 60) -> Optional[np.ndarray]:
        """
        Fetch VIX historical data.

        Args:
            lookback_days: Number of days of history to fetch

        Returns:
            numpy array of VIX closing prices, or None if fetch fails
        """
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period=f"{lookback_days}d")

            if hist.empty or len(hist) < self.STD_LOOKBACK:
                logger.warning(f"Insufficient VIX data: {len(hist)} days")
                return None

            return hist["Close"].values

        except Exception as e:
            logger.error(f"Failed to fetch VIX data: {e}")
            return None

    def calculate_signal(self) -> VIXSignal:
        """
        Calculate the VIX mean reversion signal.

        Returns:
            VIXSignal with entry recommendation
        """
        vix_data = self.get_vix_data()

        if vix_data is None:
            return VIXSignal(
                signal="NEUTRAL",
                current_vix=0.0,
                vix_3day_ma=0.0,
                recent_high=0.0,
                threshold=0.0,
                reason="Could not fetch VIX data",
                confidence=0.0
            )

        # Current VIX
        current_vix = float(vix_data[-1])

        # 3-day moving average (smooths noise)
        vix_3day_ma = float(np.mean(vix_data[-self.MA_PERIOD:]))

        # Recent high (last 10 days)
        recent_high = float(np.max(vix_data[-10:]))

        # 30-day standard deviation of daily changes
        daily_changes = np.diff(vix_data[-self.STD_LOOKBACK-1:])
        vix_std = float(np.std(daily_changes))
        threshold = self.STD_MULTIPLIER * vix_std

        # Calculate drop from recent high
        drop_from_high = recent_high - vix_3day_ma

        logger.info(f"VIX Analysis: current={current_vix:.2f}, 3d_ma={vix_3day_ma:.2f}, "
                   f"recent_high={recent_high:.2f}, threshold={threshold:.2f}")

        # Signal logic
        signal, reason, confidence = self._evaluate_signal(
            current_vix, vix_3day_ma, recent_high, drop_from_high, threshold
        )

        return VIXSignal(
            signal=signal,
            current_vix=current_vix,
            vix_3day_ma=vix_3day_ma,
            recent_high=recent_high,
            threshold=threshold,
            reason=reason,
            confidence=confidence
        )

    def _evaluate_signal(
        self,
        current_vix: float,
        vix_3day_ma: float,
        recent_high: float,
        drop_from_high: float,
        threshold: float
    ) -> tuple[str, str, float]:
        """
        Evaluate entry signal based on VIX conditions.

        Returns:
            Tuple of (signal, reason, confidence)
        """
        # AVOID: VIX too extreme
        if current_vix > self.VIX_EXTREME:
            return (
                "AVOID",
                f"VIX {current_vix:.1f} > {self.VIX_EXTREME} (extreme volatility)",
                0.0
            )

        # AVOID: VIX too low (premiums thin)
        if current_vix < self.VIX_OPTIMAL_MIN:
            return (
                "AVOID",
                f"VIX {current_vix:.1f} < {self.VIX_OPTIMAL_MIN} (premiums too thin)",
                0.0
            )

        # OPTIMAL_ENTRY: VIX dropped from spike (the sweet spot!)
        # Recent high was elevated AND VIX has dropped significantly
        if recent_high >= self.VIX_SPIKE_THRESHOLD and drop_from_high >= threshold:
            confidence = min(1.0, drop_from_high / (threshold * 2))
            return (
                "OPTIMAL_ENTRY",
                f"VIX dropped from {recent_high:.1f} to {vix_3day_ma:.1f} "
                f"(drop={drop_from_high:.1f} > threshold={threshold:.1f})",
                0.8 + (confidence * 0.2)
            )

        # GOOD_ENTRY: VIX in optimal range but no clear spike/drop pattern
        if self.VIX_OPTIMAL_MIN <= current_vix <= self.VIX_OPTIMAL_MAX:
            return (
                "GOOD_ENTRY",
                f"VIX {current_vix:.1f} in optimal range ({self.VIX_OPTIMAL_MIN}-{self.VIX_OPTIMAL_MAX})",
                0.6
            )

        # NEUTRAL: VIX elevated but not dropping (wait for better entry)
        if current_vix > self.VIX_OPTIMAL_MAX:
            return (
                "NEUTRAL",
                f"VIX {current_vix:.1f} elevated - wait for mean reversion",
                0.3
            )

        # Default: NEUTRAL
        return (
            "NEUTRAL",
            f"VIX {current_vix:.1f} - no clear signal",
            0.5
        )

    def should_enter_trade(self) -> tuple[bool, str]:
        """
        Simple interface for iron_condor_trader.py integration.

        Returns:
            Tuple of (should_enter: bool, reason: str)
        """
        signal = self.calculate_signal()

        if signal.signal in ("OPTIMAL_ENTRY", "GOOD_ENTRY"):
            return True, signal.reason
        elif signal.signal == "AVOID":
            return False, signal.reason
        else:
            # NEUTRAL: Allow entry but note it's not optimal
            return True, f"Neutral conditions: {signal.reason}"


def get_vix_entry_signal() -> VIXSignal:
    """
    Convenience function to get current VIX entry signal.

    Usage:
        from src.signals.vix_mean_reversion_signal import get_vix_entry_signal
        signal = get_vix_entry_signal()
        if signal.signal == "OPTIMAL_ENTRY":
            print("Perfect time to enter iron condor!")
    """
    generator = VIXMeanReversionSignal()
    return generator.calculate_signal()

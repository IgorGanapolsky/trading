"""
VIX Regime Detection for Options Trading.

Simple, focused VIX regime detector following the trading system's conservative approach.
Implements Phil Town Rule #1: Don't lose money.

Regime Thresholds:
- LOW_VOL: VIX < 15 (can trade, full size)
- NORMAL: VIX 15-20 (can trade, full size)
- HIGH_VOL: VIX 20-30 (trade with 0.5x size)
- EXTREME: VIX > 30 (NO trading - protect capital)

Author: Claude (CTO)
Created: 2026-01-14
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional

logger = logging.getLogger(__name__)


class VIXRegime(Enum):
    """VIX-based market volatility regimes."""

    LOW_VOL = "LOW_VOL"  # VIX < 15
    NORMAL = "NORMAL"  # VIX 15-20
    HIGH_VOL = "HIGH_VOL"  # VIX 20-30
    EXTREME = "EXTREME"  # VIX > 30


class TermStructure(Enum):
    """VIX term structure states."""

    CONTANGO = "CONTANGO"  # VIX < VIX3M (normal, can sell premium)
    BACKWARDATION = "BACKWARDATION"  # VIX > VIX3M (caution, reduce size)
    FLAT = "FLAT"  # VIX ~ VIX3M


@dataclass
class RegimeInfo:
    """Complete regime information."""

    regime: VIXRegime
    vix_value: float
    vix3m_value: Optional[float]
    term_structure: TermStructure
    can_trade: bool
    position_multiplier: float
    message: str
    timestamp: str


class VIXRegimeDetector:
    """
    Detects market regime based on VIX levels.

    Uses simple, well-defined thresholds aligned with the trading system's
    conservative risk management approach.

    Usage:
        detector = VIXRegimeDetector()
        if detector.should_trade():
            multiplier = detector.get_position_multiplier()
            # Execute trade with multiplier applied to position size
    """

    # Regime thresholds
    LOW_VOL_THRESHOLD = 15.0
    NORMAL_THRESHOLD = 20.0
    HIGH_VOL_THRESHOLD = 30.0

    # Position multipliers by regime
    POSITION_MULTIPLIERS = {
        VIXRegime.LOW_VOL: 1.0,  # Full size
        VIXRegime.NORMAL: 1.0,  # Full size
        VIXRegime.HIGH_VOL: 0.5,  # Half size
        VIXRegime.EXTREME: 0.0,  # No trading
    }

    # Default mock values (used when yfinance unavailable)
    MOCK_VIX = 18.5
    MOCK_VIX3M = 20.0

    def __init__(self, use_mock: bool = False):
        """
        Initialize VIX Regime Detector.

        Args:
            use_mock: If True, use mock data instead of live data
        """
        self.use_mock = use_mock
        self._cached_vix: Optional[float] = None
        self._cached_vix3m: Optional[float] = None
        self._cache_time: Optional[datetime] = None
        self._cache_ttl_seconds = 60  # Cache for 1 minute

        logger.info("VIXRegimeDetector initialized (mock=%s)", use_mock)

    def get_current_vix(self) -> float:
        """
        Get current VIX value.

        Returns:
            Current VIX value (float)

        Uses yfinance with fallback to mock data if unavailable.
        """
        if self.use_mock:
            return self.MOCK_VIX

        # Check cache
        if self._is_cache_valid():
            return self._cached_vix

        try:
            # Use the wrapper for graceful fallback
            from src.utils import yfinance_wrapper as yf

            if not yf.is_available():
                logger.warning("yfinance not available, using mock VIX")
                return self.MOCK_VIX

            ticker = yf.Ticker("^VIX")
            hist = ticker.history(period="1d")

            if hist.empty:
                logger.warning("VIX data empty, using mock value")
                return self.MOCK_VIX

            vix_value = float(hist["Close"].iloc[-1])
            self._update_cache(vix_value, None)

            logger.info("Current VIX: %.2f", vix_value)
            return vix_value

        except Exception as e:
            logger.error("Failed to fetch VIX: %s, using mock", e)
            return self.MOCK_VIX

    def _get_vix3m(self) -> Optional[float]:
        """
        Get VIX3M (3-month VIX) value for term structure analysis.

        Returns:
            VIX3M value or None if unavailable
        """
        if self.use_mock:
            return self.MOCK_VIX3M

        # Check cache
        if self._is_cache_valid() and self._cached_vix3m is not None:
            return self._cached_vix3m

        try:
            from src.utils import yfinance_wrapper as yf

            if not yf.is_available():
                return self.MOCK_VIX3M

            # VIX3M is ^VIX3M on Yahoo Finance
            ticker = yf.Ticker("^VIX3M")
            hist = ticker.history(period="1d")

            if hist.empty:
                logger.warning("VIX3M data empty, using mock value")
                return self.MOCK_VIX3M

            vix3m_value = float(hist["Close"].iloc[-1])
            self._cached_vix3m = vix3m_value

            logger.info("Current VIX3M: %.2f", vix3m_value)
            return vix3m_value

        except Exception as e:
            logger.warning("Failed to fetch VIX3M: %s", e)
            return self.MOCK_VIX3M

    def get_regime(self) -> str:
        """
        Get current market regime based on VIX level.

        Returns:
            Regime string: "LOW_VOL", "NORMAL", "HIGH_VOL", or "EXTREME"
        """
        vix = self.get_current_vix()
        regime = self._classify_regime(vix)
        return regime.value

    def _classify_regime(self, vix: float) -> VIXRegime:
        """Classify VIX level into regime."""
        if vix < self.LOW_VOL_THRESHOLD:
            return VIXRegime.LOW_VOL
        elif vix < self.NORMAL_THRESHOLD:
            return VIXRegime.NORMAL
        elif vix < self.HIGH_VOL_THRESHOLD:
            return VIXRegime.HIGH_VOL
        else:
            return VIXRegime.EXTREME

    def should_trade(self) -> bool:
        """
        Check if current regime allows trading.

        Returns:
            True if trading is allowed, False if in EXTREME regime

        Phil Town Rule #1: Don't lose money.
        In EXTREME regime (VIX > 30), we protect capital by not trading.
        """
        vix = self.get_current_vix()
        regime = self._classify_regime(vix)

        can_trade = regime != VIXRegime.EXTREME

        if not can_trade:
            logger.warning(
                "Trading BLOCKED - EXTREME regime (VIX=%.2f > 30). "
                "Protecting capital per Rule #1.",
                vix,
            )
        else:
            logger.info(
                "Trading ALLOWED - %s regime (VIX=%.2f)",
                regime.value,
                vix,
            )

        return can_trade

    def get_position_multiplier(self) -> float:
        """
        Get position size multiplier based on current regime.

        Returns:
            Multiplier between 0.5 and 1.5:
            - LOW_VOL: 1.0 (full size)
            - NORMAL: 1.0 (full size)
            - HIGH_VOL: 0.5 (half size)
            - EXTREME: 0.0 (no trading)

        The multiplier is further adjusted by term structure:
        - Contango: No adjustment (normal conditions)
        - Backwardation: Additional 0.5x reduction (caution)
        """
        vix = self.get_current_vix()
        regime = self._classify_regime(vix)

        base_multiplier = self.POSITION_MULTIPLIERS[regime]

        # Adjust for term structure
        term_structure = self._get_term_structure()
        if term_structure == TermStructure.BACKWARDATION:
            # Reduce size by additional 50% in backwardation
            adjusted_multiplier = base_multiplier * 0.5
            logger.warning(
                "Backwardation detected - reducing multiplier from %.2f to %.2f",
                base_multiplier,
                adjusted_multiplier,
            )
            base_multiplier = adjusted_multiplier

        # Clamp to valid range
        final_multiplier = max(0.0, min(1.5, base_multiplier))

        logger.info(
            "Position multiplier: %.2f (regime=%s, term_structure=%s)",
            final_multiplier,
            regime.value,
            term_structure.value,
        )

        return final_multiplier

    def _get_term_structure(self) -> TermStructure:
        """
        Analyze VIX term structure (VIX vs VIX3M).

        Returns:
            TermStructure enum:
            - CONTANGO: VIX < VIX3M (normal, can sell premium)
            - BACKWARDATION: VIX > VIX3M (caution, reduce size)
            - FLAT: VIX ~ VIX3M (within 1 point)
        """
        vix = self.get_current_vix()
        vix3m = self._get_vix3m()

        if vix3m is None:
            logger.warning("VIX3M unavailable, assuming FLAT term structure")
            return TermStructure.FLAT

        diff = vix - vix3m

        if diff > 1.0:  # VIX significantly above VIX3M
            logger.warning(
                "BACKWARDATION: VIX (%.2f) > VIX3M (%.2f) - market stress signal",
                vix,
                vix3m,
            )
            return TermStructure.BACKWARDATION
        elif diff < -1.0:  # VIX below VIX3M (normal)
            logger.info(
                "CONTANGO: VIX (%.2f) < VIX3M (%.2f) - normal conditions",
                vix,
                vix3m,
            )
            return TermStructure.CONTANGO
        else:
            logger.info(
                "FLAT: VIX (%.2f) ~ VIX3M (%.2f) - neutral conditions",
                vix,
                vix3m,
            )
            return TermStructure.FLAT

    def get_full_regime_info(self) -> RegimeInfo:
        """
        Get complete regime information including all metrics.

        Returns:
            RegimeInfo dataclass with all regime details
        """
        vix = self.get_current_vix()
        vix3m = self._get_vix3m()
        regime = self._classify_regime(vix)
        term_structure = self._get_term_structure()
        can_trade = regime != VIXRegime.EXTREME
        multiplier = self.get_position_multiplier()

        # Build message
        if regime == VIXRegime.EXTREME:
            message = f"DANGER: VIX at {vix:.2f} - NO TRADING allowed (Rule #1)"
        elif regime == VIXRegime.HIGH_VOL:
            message = f"CAUTION: VIX at {vix:.2f} - trade with 50% position size"
        elif term_structure == TermStructure.BACKWARDATION:
            message = "ALERT: Backwardation detected - reduce position size"
        else:
            message = f"NORMAL: VIX at {vix:.2f} - standard trading conditions"

        return RegimeInfo(
            regime=regime,
            vix_value=vix,
            vix3m_value=vix3m,
            term_structure=term_structure,
            can_trade=can_trade,
            position_multiplier=multiplier,
            message=message,
            timestamp=datetime.utcnow().isoformat(),
        )

    def _is_cache_valid(self) -> bool:
        """Check if cached VIX data is still valid."""
        if self._cached_vix is None or self._cache_time is None:
            return False

        age = (datetime.utcnow() - self._cache_time).total_seconds()
        return age < self._cache_ttl_seconds

    def _update_cache(self, vix: float, vix3m: Optional[float]) -> None:
        """Update the VIX cache."""
        self._cached_vix = vix
        if vix3m is not None:
            self._cached_vix3m = vix3m
        self._cache_time = datetime.utcnow()


# Convenience function
def get_vix_regime_detector(use_mock: bool = False) -> VIXRegimeDetector:
    """Get a VIXRegimeDetector instance."""
    return VIXRegimeDetector(use_mock=use_mock)


if __name__ == "__main__":
    """Example usage and testing."""
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("\n" + "=" * 60)
    print("VIX REGIME DETECTOR")
    print("=" * 60)

    # Use mock data for testing if --mock flag provided
    use_mock = "--mock" in sys.argv
    detector = VIXRegimeDetector(use_mock=use_mock)

    print(f"\nUsing {'MOCK' if use_mock else 'LIVE'} data\n")

    # Get current VIX
    vix = detector.get_current_vix()
    print(f"Current VIX: {vix:.2f}")

    # Get regime
    regime = detector.get_regime()
    print(f"Market Regime: {regime}")

    # Check if trading allowed
    can_trade = detector.should_trade()
    print(f"Can Trade: {can_trade}")

    # Get position multiplier
    multiplier = detector.get_position_multiplier()
    print(f"Position Multiplier: {multiplier:.2f}x")

    # Get full info
    print("\n--- Full Regime Info ---")
    info = detector.get_full_regime_info()
    print(f"Regime: {info.regime.value}")
    print(f"VIX: {info.vix_value:.2f}")
    print(f"VIX3M: {info.vix3m_value:.2f}" if info.vix3m_value else "VIX3M: N/A")
    print(f"Term Structure: {info.term_structure.value}")
    print(f"Can Trade: {info.can_trade}")
    print(f"Position Multiplier: {info.position_multiplier:.2f}x")
    print(f"Message: {info.message}")

    print("\n" + "=" * 60)
    print("REGIME THRESHOLDS")
    print("=" * 60)
    print("LOW_VOL:  VIX < 15  -> Full size (1.0x)")
    print("NORMAL:   VIX 15-20 -> Full size (1.0x)")
    print("HIGH_VOL: VIX 20-30 -> Half size (0.5x)")
    print("EXTREME:  VIX > 30  -> NO TRADING (0.0x)")
    print("\nBackwardation (VIX > VIX3M) -> Additional 0.5x reduction")
    print("=" * 60)

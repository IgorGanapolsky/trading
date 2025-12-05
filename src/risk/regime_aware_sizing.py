"""Regime-Aware Position Sizing.

Dec 3, 2025 Enhancement:
Integrates market regime detection with position sizing to automatically
reduce exposure in volatile/bear markets and increase in calm/bull markets.

The Dec 3 analysis identified this as a critical gap:
- System didn't automatically reduce positions in bear/volatile regimes
- This caused unnecessary drawdowns during market stress

This module solves that by:
1. Detecting current market regime (VIX-based + HMM)
2. Applying regime-specific size multipliers
3. Enforcing regime-based allocation limits
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# Regime-based sizing multipliers
# These reduce position sizes in risky regimes and increase in favorable ones
REGIME_SIZE_MULTIPLIERS = {
    # Calm: Low VIX, stable markets - full position sizing
    "calm": 1.0,
    # Trending: Directional market - slightly reduced for reversal risk
    "trending": 0.9,
    "trending_bull": 1.1,  # Lean into uptrends
    "trending_bear": 0.5,  # Reduce in downtrends
    # Volatile: High VIX (20-30) - significant reduction
    "volatile": 0.4,
    # Spike: Crisis (VIX > 30) - minimal or no new positions
    "spike": 0.1,
    # Legacy labels from simple detector
    "BULL": 1.1,
    "BEAR": 0.5,
    "SIDEWAYS": 0.7,
    # Fallback
    "unknown": 0.6,
    "range": 0.8,
    "microstructure_impulse": 0.6,
}

# Regime-based risk_bias actions
RISK_BIAS_ACTIONS = {
    "lean_in": {"size_multiplier": 1.2, "max_position_pct": 0.08},
    "neutral": {"size_multiplier": 1.0, "max_position_pct": 0.05},
    "hedge": {"size_multiplier": 0.7, "max_position_pct": 0.03},
    "de_risk": {"size_multiplier": 0.4, "max_position_pct": 0.02},
    "pause": {"size_multiplier": 0.0, "max_position_pct": 0.0},
}


@dataclass
class RegimeAwareSizeResult:
    """Result of regime-aware position sizing."""

    original_size: float
    adjusted_size: float
    regime_label: str
    regime_multiplier: float
    risk_bias: str
    bias_multiplier: float
    final_multiplier: float
    max_position_pct: float
    regime_confidence: float
    vix_level: float | None
    should_pause_trading: bool
    reason: str


class RegimeAwareSizer:
    """
    Position sizer that automatically adjusts based on market regime.

    Integrates with:
    - src/utils/regime_detector.py (HMM + VIX-based detection)
    - src/ml/market_regime_detector.py (simple BULL/BEAR/SIDEWAYS)
    - src/risk/risk_manager.py (base position sizing)
    """

    def __init__(
        self,
        base_max_position_pct: float = 0.05,
        use_live_regime: bool = True,
        min_size_multiplier: float = 0.1,
        max_size_multiplier: float = 1.5,
    ):
        """
        Initialize regime-aware sizer.

        Args:
            base_max_position_pct: Base maximum position size (default 5%)
            use_live_regime: Whether to fetch live VIX data for regime detection
            min_size_multiplier: Floor for regime multiplier (never below this)
            max_size_multiplier: Ceiling for regime multiplier
        """
        self.base_max_position_pct = base_max_position_pct
        self.use_live_regime = use_live_regime
        self.min_size_multiplier = min_size_multiplier
        self.max_size_multiplier = max_size_multiplier

        # Cache for regime (refresh every 30 minutes)
        self._regime_cache: dict[str, Any] | None = None
        self._regime_cache_time: float | None = None
        self._cache_duration_seconds = 1800  # 30 minutes

    def adjust_position_size(
        self,
        base_size: float,
        account_equity: float,
        symbol: str | None = None,
        market_features: dict[str, Any] | None = None,
    ) -> RegimeAwareSizeResult:
        """
        Adjust position size based on current market regime.

        Args:
            base_size: Position size from base risk manager
            account_equity: Total account equity
            symbol: Optional symbol (for symbol-specific regime analysis)
            market_features: Optional pre-calculated market features

        Returns:
            RegimeAwareSizeResult with adjusted size and reasoning
        """
        # Get current regime
        regime_info = self._get_current_regime(market_features)

        regime_label = regime_info.get("label", "unknown")
        risk_bias = regime_info.get("risk_bias", "neutral")
        confidence = regime_info.get("confidence", 0.5)
        vix_level = regime_info.get("vix_level")

        # Get multipliers
        regime_mult = REGIME_SIZE_MULTIPLIERS.get(regime_label, 0.7)
        bias_action = RISK_BIAS_ACTIONS.get(risk_bias, RISK_BIAS_ACTIONS["neutral"])
        bias_mult = bias_action["size_multiplier"]
        max_position_pct = bias_action["max_position_pct"]

        # Combine multipliers (use geometric mean to prevent extremes)
        final_mult = (regime_mult * bias_mult) ** 0.5  # Sqrt for geometric mean
        final_mult = max(self.min_size_multiplier, min(self.max_size_multiplier, final_mult))

        # Check for trading pause
        should_pause = risk_bias == "pause" or regime_label == "spike"
        if should_pause:
            adjusted_size = 0.0
            reason = f"Trading paused: Regime={regime_label}, RiskBias={risk_bias}"
        else:
            # Apply adjustment
            adjusted_size = base_size * final_mult

            # Enforce regime-specific max position
            max_size = account_equity * max_position_pct
            if adjusted_size > max_size:
                adjusted_size = max_size
                reason = f"Capped at regime max: {max_position_pct:.1%} of equity"
            else:
                reason = f"Regime {regime_label} ({confidence:.0%} conf) applied {final_mult:.2f}x"

        return RegimeAwareSizeResult(
            original_size=base_size,
            adjusted_size=round(adjusted_size, 2),
            regime_label=regime_label,
            regime_multiplier=regime_mult,
            risk_bias=risk_bias,
            bias_multiplier=bias_mult,
            final_multiplier=final_mult,
            max_position_pct=max_position_pct,
            regime_confidence=confidence,
            vix_level=vix_level,
            should_pause_trading=should_pause,
            reason=reason,
        )

    def _get_current_regime(self, market_features: dict[str, Any] | None = None) -> dict[str, Any]:
        """Get current market regime, using cache if fresh."""
        import time

        now = time.time()

        # Check cache
        if (
            self._regime_cache is not None
            and self._regime_cache_time is not None
            and (now - self._regime_cache_time) < self._cache_duration_seconds
        ):
            return self._regime_cache

        # If market features provided, use them for detection
        if market_features:
            regime_info = self._detect_from_features(market_features)
        elif self.use_live_regime:
            regime_info = self._detect_live()
        else:
            regime_info = {"label": "unknown", "risk_bias": "neutral", "confidence": 0.5}

        # Update cache
        self._regime_cache = regime_info
        self._regime_cache_time = now

        return regime_info

    def _detect_from_features(self, features: dict[str, Any]) -> dict[str, Any]:
        """Detect regime from provided market features."""
        try:
            from src.utils.regime_detector import RegimeDetector

            detector = RegimeDetector()
            return detector.detect(features)
        except Exception as e:
            logger.warning(f"Feature-based regime detection failed: {e}")
            return {"label": "unknown", "risk_bias": "neutral", "confidence": 0.5}

    def _detect_live(self) -> dict[str, Any]:
        """Detect regime using live market data (VIX, VVIX)."""
        try:
            from src.utils.regime_detector import RegimeDetector

            detector = RegimeDetector()
            snapshot = detector.detect_live_regime(lookback_days=30)

            return {
                "label": snapshot.label,
                "risk_bias": snapshot.risk_bias,
                "confidence": snapshot.confidence,
                "vix_level": snapshot.vix_level,
                "vvix_level": snapshot.vvix_level,
                "allocation_override": snapshot.allocation_override,
            }
        except Exception as e:
            logger.warning(f"Live regime detection failed: {e}")
            return {"label": "unknown", "risk_bias": "neutral", "confidence": 0.5}

    def should_pause_trading(self) -> tuple[bool, str]:
        """
        Check if trading should be paused based on current regime.

        Returns:
            Tuple of (should_pause, reason)
        """
        regime_info = self._get_current_regime()

        if regime_info.get("risk_bias") == "pause":
            return (
                True,
                f"Regime pause: {regime_info.get('label')} with VIX={regime_info.get('vix_level', 'N/A')}",
            )

        if regime_info.get("label") == "spike":
            return True, "Crisis regime detected (VIX spike)"

        return False, "Trading allowed"


# Singleton instance for easy import
_regime_sizer: RegimeAwareSizer | None = None


def get_regime_aware_sizer() -> RegimeAwareSizer:
    """Get or create the global regime-aware sizer instance."""
    global _regime_sizer
    if _regime_sizer is None:
        _regime_sizer = RegimeAwareSizer()
    return _regime_sizer


def adjust_size_for_regime(
    base_size: float,
    account_equity: float,
    symbol: str | None = None,
    market_features: dict[str, Any] | None = None,
) -> RegimeAwareSizeResult:
    """
    Convenience function to adjust position size for current regime.

    Usage:
        from src.risk.regime_aware_sizing import adjust_size_for_regime

        result = adjust_size_for_regime(
            base_size=1000.0,
            account_equity=100000.0,
            symbol="NVDA"
        )
        if not result.should_pause_trading:
            execute_order(symbol, result.adjusted_size)
    """
    sizer = get_regime_aware_sizer()
    return sizer.adjust_position_size(base_size, account_equity, symbol, market_features)

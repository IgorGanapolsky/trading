"""
Regime-Aware Strategy Selector

Automatically selects the optimal strategy based on market regime:
- MOMENTUM: For trending markets (BULL, BEAR, high ADX)
- MEAN REVERSION: For ranging markets (SIDEWAYS, low ADX, choppy)

This provides diversification and prevents using the wrong strategy in the wrong market.
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.ml.market_regime_detector import MarketRegimeDetector
from src.strategies.legacy_momentum import LegacyMomentumCalculator
from src.strategies.mean_reversion_strategy import MeanReversionStrategy

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """Available strategy types."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    HYBRID = "hybrid"  # Use both with weighted signals


@dataclass
class StrategySelection:
    """Result of strategy selection."""

    selected_strategy: StrategyType
    regime: str
    regime_confidence: float
    reason: str
    momentum_weight: float  # 0.0-1.0
    mean_reversion_weight: float  # 0.0-1.0

    def get_primary_strategy(self) -> StrategyType:
        """Get the primary strategy to use."""
        if self.momentum_weight > self.mean_reversion_weight:
            return StrategyType.MOMENTUM
        elif self.mean_reversion_weight > self.momentum_weight:
            return StrategyType.MEAN_REVERSION
        else:
            return StrategyType.HYBRID


class RegimeAwareStrategySelector:
    """
    Selects optimal trading strategy based on market regime.

    Strategy Selection Rules:
    ========================

    MOMENTUM Strategy (for trending markets):
    - Regime: BULL or BEAR
    - ADX: > 25 (strong trend)
    - Characteristics: Clear directional movement
    - Entry: MACD crossover + RSI confirmation
    - Best for: Capturing trends in SPY, QQQ

    MEAN REVERSION Strategy (for ranging markets):
    - Regime: SIDEWAYS
    - ADX: < 20 (weak trend)
    - Characteristics: Choppy, oscillating price
    - Entry: RSI(2) < 10 (extreme oversold)
    - Best for: Profiting from overreactions

    HYBRID Mode (transitional markets):
    - ADX: 20-25 (moderate trend)
    - Use both strategies with reduced position sizes
    - Diversify across strategy types

    Performance Expectations:
    ========================

    MOMENTUM in trending markets:
    - Win rate: 55-60%
    - Avg hold: 5-15 days
    - Avg gain: 2-5%

    MEAN REVERSION in ranging markets:
    - Win rate: 70-75%
    - Avg hold: 1-5 days
    - Avg gain: 0.5-1.5%

    Using wrong strategy in wrong regime:
    - Momentum in sideways: Whipsaws, false breakouts, losses
    - Mean reversion in trending: Missed trends, early exits
    """

    def __init__(
        self,
        momentum_adx_min: float = 25.0,
        mean_reversion_adx_max: float = 20.0,
        hybrid_adx_range: tuple[float, float] = (20.0, 25.0),
    ):
        """
        Initialize regime-aware selector.

        Args:
            momentum_adx_min: Minimum ADX for momentum strategy (default: 25)
            mean_reversion_adx_max: Maximum ADX for mean reversion (default: 20)
            hybrid_adx_range: ADX range for hybrid mode (default: 20-25)
        """
        self.momentum_adx_min = momentum_adx_min
        self.mean_reversion_adx_max = mean_reversion_adx_max
        self.hybrid_adx_range = hybrid_adx_range

        self.regime_detector = MarketRegimeDetector()
        self.momentum_strategy = LegacyMomentumCalculator()
        self.mean_reversion_strategy = MeanReversionStrategy()

        logger.info(
            f"RegimeAwareStrategySelector initialized: "
            f"momentum_adx>{momentum_adx_min}, "
            f"mean_reversion_adx<{mean_reversion_adx_max}, "
            f"hybrid_adx={hybrid_adx_range}"
        )

    def select_strategy(
        self, symbol: str, market_data: dict[str, Any] = None, adx: float = None
    ) -> StrategySelection:
        """
        Select optimal strategy based on market regime.

        Args:
            symbol: Stock symbol
            market_data: Market data dictionary (prices, returns, etc.)
            adx: ADX value if already calculated

        Returns:
            StrategySelection with recommended strategy and weights
        """
        # Detect regime if market data provided
        regime = "UNKNOWN"
        regime_confidence = 0.0
        trend_strength = 0.0

        if market_data:
            regime_result = self.regime_detector.detect_from_state(market_data)
            regime = regime_result.get("regime", "UNKNOWN")
            regime_confidence = regime_result.get("confidence", 0.0)
            trend_strength = regime_result.get("trend_strength", 0.0)

        # Use ADX if provided (from momentum calculator)
        if adx is None and market_data:
            # Try to get ADX from market data
            adx = market_data.get("adx", 15.0)  # Default to moderate

        # Default ADX if still None
        if adx is None:
            adx = 15.0
            logger.warning(f"{symbol}: ADX not provided, using default {adx}")

        # Strategy selection based on ADX and regime
        momentum_weight = 0.0
        mean_reversion_weight = 0.0
        selected_strategy = StrategyType.MOMENTUM
        reason = ""

        # STRONG TREND -> Momentum
        if adx >= self.momentum_adx_min:
            momentum_weight = 1.0
            mean_reversion_weight = 0.0
            selected_strategy = StrategyType.MOMENTUM
            reason = (
                f"ADX={adx:.1f} >= {self.momentum_adx_min} (strong trend) "
                f"+ regime={regime} -> Use MOMENTUM strategy"
            )

        # WEAK TREND -> Mean Reversion
        elif adx <= self.mean_reversion_adx_max:
            momentum_weight = 0.0
            mean_reversion_weight = 1.0
            selected_strategy = StrategyType.MEAN_REVERSION
            reason = (
                f"ADX={adx:.1f} <= {self.mean_reversion_adx_max} (weak trend) "
                f"+ regime={regime} -> Use MEAN REVERSION strategy"
            )

        # MODERATE TREND -> Hybrid (use both)
        else:
            # Linear interpolation between strategies
            adx_range_size = self.hybrid_adx_range[1] - self.hybrid_adx_range[0]
            if adx_range_size > 0:
                momentum_weight = (adx - self.hybrid_adx_range[0]) / adx_range_size
                mean_reversion_weight = 1.0 - momentum_weight
            else:
                momentum_weight = 0.5
                mean_reversion_weight = 0.5

            selected_strategy = StrategyType.HYBRID
            reason = (
                f"ADX={adx:.1f} in hybrid range {self.hybrid_adx_range} "
                f"-> Use BOTH strategies (momentum={momentum_weight:.1%}, "
                f"mean_reversion={mean_reversion_weight:.1%})"
            )

        # Additional regime confirmation
        if regime in ("BULL", "BEAR") and adx < self.momentum_adx_min:
            # Trending regime but low ADX -> could be early trend formation
            reason += f" | Warning: {regime} regime but ADX only {adx:.1f}"

        if regime == "SIDEWAYS" and adx > self.mean_reversion_adx_max:
            # Sideways regime but high ADX -> conflicting signals
            reason += f" | Warning: SIDEWAYS regime but ADX={adx:.1f} suggests trend"

        logger.info(f"{symbol}: {reason}")

        return StrategySelection(
            selected_strategy=selected_strategy,
            regime=regime,
            regime_confidence=regime_confidence,
            reason=reason,
            momentum_weight=momentum_weight,
            mean_reversion_weight=mean_reversion_weight,
        )

    def should_use_momentum(self, selection: StrategySelection) -> bool:
        """Check if momentum strategy should be used."""
        return selection.momentum_weight > 0.0

    def should_use_mean_reversion(self, selection: StrategySelection) -> bool:
        """Check if mean reversion strategy should be used."""
        return selection.mean_reversion_weight > 0.0

    def get_combined_signal(
        self, symbol: str, selection: StrategySelection
    ) -> dict[str, Any]:
        """
        Get combined signal from both strategies based on weights.

        Args:
            symbol: Stock symbol
            selection: Strategy selection result

        Returns:
            Combined signal with weighted confidence
        """
        signals = {}

        # Get momentum signal if weight > 0
        if selection.momentum_weight > 0.0:
            try:
                momentum_result = self.momentum_strategy.evaluate(symbol)
                signals["momentum"] = {
                    "score": momentum_result.score,
                    "indicators": momentum_result.indicators,
                    "weight": selection.momentum_weight,
                }
            except Exception as e:
                logger.error(f"Momentum strategy error for {symbol}: {e}")
                signals["momentum"] = {"score": 0.0, "error": str(e), "weight": 0.0}

        # Get mean reversion signal if weight > 0
        if selection.mean_reversion_weight > 0.0:
            try:
                mr_signal = self.mean_reversion_strategy.analyze(symbol)
                signals["mean_reversion"] = {
                    "signal_type": mr_signal.signal_type,
                    "confidence": mr_signal.confidence,
                    "rsi_2": mr_signal.rsi_2,
                    "reason": mr_signal.reason,
                    "weight": selection.mean_reversion_weight,
                }
            except Exception as e:
                logger.error(f"Mean reversion strategy error for {symbol}: {e}")
                signals["mean_reversion"] = {
                    "signal_type": "HOLD",
                    "confidence": 0.0,
                    "error": str(e),
                    "weight": 0.0,
                }

        # Calculate combined confidence
        combined_confidence = 0.0

        if "momentum" in signals and signals["momentum"].get("score", 0) > 0:
            combined_confidence += signals["momentum"]["score"] * selection.momentum_weight

        if "mean_reversion" in signals and signals["mean_reversion"].get("confidence", 0) > 0:
            combined_confidence += (
                signals["mean_reversion"]["confidence"] * selection.mean_reversion_weight
            )

        return {
            "symbol": symbol,
            "regime": selection.regime,
            "selected_strategy": selection.selected_strategy.value,
            "signals": signals,
            "combined_confidence": combined_confidence,
            "reason": selection.reason,
        }


# Example usage
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    selector = RegimeAwareStrategySelector()

    # Example 1: Strong trend (ADX=35) -> Momentum
    print("=" * 80)
    print("EXAMPLE 1: STRONG TRENDING MARKET")
    print("=" * 80)

    selection1 = selector.select_strategy(
        "SPY",
        market_data={"adx": 35.0, "regime": "BULL"},
        adx=35.0,
    )

    print(f"Strategy: {selection1.selected_strategy.value}")
    print(f"Regime: {selection1.regime}")
    print(f"Weights: Momentum={selection1.momentum_weight:.1%}, "
          f"MeanReversion={selection1.mean_reversion_weight:.1%}")
    print(f"Reason: {selection1.reason}")
    print()

    # Example 2: Weak trend (ADX=15) -> Mean Reversion
    print("=" * 80)
    print("EXAMPLE 2: SIDEWAYS/RANGING MARKET")
    print("=" * 80)

    selection2 = selector.select_strategy(
        "SPY",
        market_data={"adx": 15.0, "regime": "SIDEWAYS"},
        adx=15.0,
    )

    print(f"Strategy: {selection2.selected_strategy.value}")
    print(f"Regime: {selection2.regime}")
    print(f"Weights: Momentum={selection2.momentum_weight:.1%}, "
          f"MeanReversion={selection2.mean_reversion_weight:.1%}")
    print(f"Reason: {selection2.reason}")
    print()

    # Example 3: Moderate trend (ADX=22) -> Hybrid
    print("=" * 80)
    print("EXAMPLE 3: MODERATE TREND (HYBRID MODE)")
    print("=" * 80)

    selection3 = selector.select_strategy(
        "SPY",
        market_data={"adx": 22.0, "regime": "BULL"},
        adx=22.0,
    )

    print(f"Strategy: {selection3.selected_strategy.value}")
    print(f"Regime: {selection3.regime}")
    print(f"Weights: Momentum={selection3.momentum_weight:.1%}, "
          f"MeanReversion={selection3.mean_reversion_weight:.1%}")
    print(f"Reason: {selection3.reason}")
    print()

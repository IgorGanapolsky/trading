"""
Strategy Ensemble

Combines Momentum and Mean Reversion strategies with dynamic weighting
based on market regime detection. This reduces regime risk by adapting
to different market conditions.

Key Features:
- Regime-aware strategy selection
- Dynamic weight adjustment (trending vs ranging)
- Signal aggregation with confidence weighting
- Diversification across strategy types

Strategy Weights by Regime:
- TRENDING_UP/DOWN: 70% momentum, 30% mean reversion
- RANGING: 30% momentum, 70% mean reversion
- MIXED: 50% each

Author: Trading System
Created: 2025-12-05
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from src.strategies.mean_reversion_strategy import (
    MeanReversionSignal,
    MeanReversionStrategy,
    get_default_mean_reversion_strategy,
)
from src.strategies.regime_detector import (
    MarketRegime,
    RegimeAnalysis,
    RegimeDetector,
    get_default_regime_detector,
)
from src.utils.technical_indicators import calculate_technical_score

logger = logging.getLogger(__name__)


@dataclass
class EnsembleSignal:
    """Combined signal from strategy ensemble."""

    symbol: str
    action: str  # "buy", "sell", "hold"
    combined_strength: float  # Weighted average of strengths
    regime: MarketRegime
    momentum_signal: dict  # Signal from momentum strategy
    mean_reversion_signal: Optional[MeanReversionSignal]  # Signal from MR strategy
    momentum_weight: float
    mean_reversion_weight: float
    entry_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    reason: str = ""


class StrategyEnsemble:
    """
    Ensemble strategy combining momentum and mean reversion.

    This strategy uses regime detection to dynamically adjust weights
    between momentum (trend-following) and mean reversion strategies,
    reducing the risk of strategy-market mismatch.

    Example:
        ensemble = StrategyEnsemble()
        signal = ensemble.generate_ensemble_signal("SPY", historical_data)
        if signal.action == "buy":
            execute_trade(signal)
    """

    def __init__(
        self,
        etf_universe: Optional[list[str]] = None,
        daily_allocation: float = 10.0,
        momentum_min_score: float = 60.0,
        mean_reversion_min_strength: float = 0.3,
        regime_detector: Optional[RegimeDetector] = None,
        mean_reversion_strategy: Optional[MeanReversionStrategy] = None,
    ):
        """
        Initialize the strategy ensemble.

        Args:
            etf_universe: Symbols to trade
            daily_allocation: Dollar amount per trade
            momentum_min_score: Minimum momentum score for signal (0-100)
            mean_reversion_min_strength: Minimum MR strength for signal (0-1)
            regime_detector: Custom regime detector (or use default)
            mean_reversion_strategy: Custom MR strategy (or use default)
        """
        self.etf_universe = etf_universe or ["SPY", "QQQ", "IWM", "DIA", "VOO"]
        self.daily_allocation = daily_allocation
        self.momentum_min_score = momentum_min_score
        self.mean_reversion_min_strength = mean_reversion_min_strength

        # Initialize components
        self.regime_detector = regime_detector or get_default_regime_detector()
        self.mean_reversion = mean_reversion_strategy or get_default_mean_reversion_strategy()
        self.mean_reversion.etf_universe = self.etf_universe

        # Strategy name
        self.name = "StrategyEnsemble"

        # Cache for regime (avoid recalculating)
        self._cached_regime: Optional[RegimeAnalysis] = None
        self._cached_regime_symbol: Optional[str] = None

        logger.info(
            f"StrategyEnsemble initialized: universe={self.etf_universe}, "
            f"momentum_min={momentum_min_score}, mr_min={mean_reversion_min_strength}"
        )

    def _get_momentum_signal(self, symbol: str, hist: pd.DataFrame) -> dict[str, Any]:
        """
        Generate momentum signal using technical indicators.

        Args:
            symbol: Ticker symbol
            hist: Historical OHLCV data

        Returns:
            Dict with momentum signal info
        """
        if hist is None or len(hist) < 35:
            return {
                "symbol": symbol,
                "action": "hold",
                "score": 0.0,
                "strength": 0.0,
                "indicators": {},
                "reason": "Insufficient data",
            }

        # Calculate momentum score using existing utility
        score, indicators = calculate_technical_score(
            hist,
            symbol,
            macd_threshold=0.0,
            rsi_overbought=70.0,
            volume_min=0.8,
        )

        # Determine action based on score
        if score >= self.momentum_min_score:
            action = "buy"
            strength = min(1.0, (score - self.momentum_min_score) / 40.0)  # Scale to 0-1
        else:
            action = "hold"
            strength = 0.0

        return {
            "symbol": symbol,
            "action": action,
            "score": score,
            "strength": strength,
            "indicators": indicators,
            "reason": f"Momentum score={score:.1f}",
        }

    def generate_ensemble_signal(self, symbol: str, hist: pd.DataFrame) -> EnsembleSignal:
        """
        Generate combined signal from both strategies.

        Args:
            symbol: Ticker symbol
            hist: Historical OHLCV data

        Returns:
            EnsembleSignal with combined recommendation
        """
        # Detect regime (use SPY as market proxy if available, else symbol)
        regime_analysis = self.regime_detector.detect_regime(hist)

        # Get signals from both strategies
        momentum_signal = self._get_momentum_signal(symbol, hist)
        mr_signal = self.mean_reversion.generate_signal(symbol, hist)

        # Get weights from regime
        mom_weight = regime_analysis.momentum_weight
        mr_weight = regime_analysis.mean_reversion_weight

        # Combine signals
        combined_action, combined_strength, reason = self._combine_signals(
            momentum_signal=momentum_signal,
            mr_signal=mr_signal,
            mom_weight=mom_weight,
            mr_weight=mr_weight,
            regime=regime_analysis.regime,
        )

        # Determine entry/stop/target from dominant strategy
        entry_price = None
        stop_loss = None
        take_profit = None

        if combined_action != "hold":
            if mom_weight > mr_weight and momentum_signal["action"] != "hold":
                # Use momentum approach (no specific stop in basic momentum)
                entry_price = float(hist["Close"].iloc[-1])
            elif mr_signal.action != "hold":
                # Use mean reversion stops
                entry_price = mr_signal.entry_price
                stop_loss = mr_signal.stop_loss
                take_profit = mr_signal.take_profit

        return EnsembleSignal(
            symbol=symbol,
            action=combined_action,
            combined_strength=combined_strength,
            regime=regime_analysis.regime,
            momentum_signal=momentum_signal,
            mean_reversion_signal=mr_signal,
            momentum_weight=mom_weight,
            mean_reversion_weight=mr_weight,
            entry_price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=reason,
        )

    def _combine_signals(
        self,
        momentum_signal: dict,
        mr_signal: MeanReversionSignal,
        mom_weight: float,
        mr_weight: float,
        regime: MarketRegime,
    ) -> tuple[str, float, str]:
        """
        Combine momentum and mean reversion signals.

        Rules:
        1. If both agree on action, use it with combined strength
        2. If they disagree, use the one with higher weighted strength
        3. If both are "hold", hold

        Args:
            momentum_signal: Signal from momentum strategy
            mr_signal: Signal from mean reversion strategy
            mom_weight: Weight for momentum
            mr_weight: Weight for mean reversion
            regime: Current market regime

        Returns:
            Tuple of (action, combined_strength, reason)
        """
        mom_action = momentum_signal["action"]
        mom_strength = momentum_signal["strength"]
        mr_action = mr_signal.action
        mr_strength = mr_signal.strength

        # Weighted strengths
        weighted_mom = mom_strength * mom_weight
        weighted_mr = mr_strength * mr_weight

        # Case 1: Both hold
        if mom_action == "hold" and mr_action == "hold":
            return ("hold", 0.0, f"Both strategies hold ({regime.value})")

        # Case 2: Both agree (both buy or both sell)
        if mom_action == mr_action and mom_action != "hold":
            combined = weighted_mom + weighted_mr
            return (
                mom_action,
                combined,
                f"Both agree: {mom_action} ({regime.value})",
            )

        # Case 3: Only momentum has signal
        if mom_action != "hold" and mr_action == "hold":
            if weighted_mom >= 0.3:  # Threshold for single-strategy action
                return (
                    mom_action,
                    weighted_mom,
                    f"Momentum only: {mom_action} ({regime.value})",
                )
            return ("hold", 0.0, "Momentum signal too weak")

        # Case 4: Only mean reversion has signal
        if mr_action != "hold" and mom_action == "hold":
            if weighted_mr >= 0.3:
                return (
                    mr_action,
                    weighted_mr,
                    f"Mean reversion only: {mr_action} ({regime.value})",
                )
            return ("hold", 0.0, "Mean reversion signal too weak")

        # Case 5: They disagree (one buy, one sell)
        # Use the strategy with higher weighted strength
        if weighted_mom > weighted_mr:
            return (
                mom_action,
                weighted_mom,
                f"Momentum overrides: {mom_action} ({regime.value})",
            )
        elif weighted_mr > weighted_mom:
            return (
                mr_action,
                weighted_mr,
                f"Mean reversion overrides: {mr_action} ({regime.value})",
            )
        else:
            # Equal weights and disagreement = hold
            return ("hold", 0.0, f"Conflicting signals, holding ({regime.value})")

    def generate_all_signals(self, data: dict[str, pd.DataFrame]) -> list[EnsembleSignal]:
        """
        Generate ensemble signals for all symbols.

        Args:
            data: Dict mapping symbol to historical DataFrame

        Returns:
            List of EnsembleSignal objects
        """
        signals = []
        for symbol in self.etf_universe:
            hist = data.get(symbol)
            if hist is not None:
                signal = self.generate_ensemble_signal(symbol, hist)
                signals.append(signal)
        return signals

    def select_best_signal(self, signals: list[EnsembleSignal]) -> Optional[EnsembleSignal]:
        """
        Select the best signal for trading.

        Args:
            signals: List of generated ensemble signals

        Returns:
            Best signal or None if no actionable signals
        """
        actionable = [s for s in signals if s.action != "hold" and s.combined_strength >= 0.3]

        if not actionable:
            return None

        # Sort by combined strength
        actionable.sort(key=lambda s: s.combined_strength, reverse=True)
        return actionable[0]

    def get_config(self) -> dict[str, Any]:
        """Return strategy configuration."""
        return {
            "name": self.name,
            "etf_universe": self.etf_universe,
            "daily_allocation": self.daily_allocation,
            "momentum_min_score": self.momentum_min_score,
            "mean_reversion_min_strength": self.mean_reversion_min_strength,
            "regime_detector": {
                "adx_trending": self.regime_detector.ADX_TRENDING_THRESHOLD,
                "adx_ranging": self.regime_detector.ADX_RANGING_THRESHOLD,
            },
            "mean_reversion": self.mean_reversion.get_config(),
        }


# Convenience function
def get_default_strategy_ensemble() -> StrategyEnsemble:
    """Get a default strategy ensemble instance."""
    return StrategyEnsemble(
        etf_universe=["SPY", "QQQ", "IWM", "DIA", "VOO"],
        daily_allocation=10.0,
        momentum_min_score=60.0,
        mean_reversion_min_strength=0.3,
    )

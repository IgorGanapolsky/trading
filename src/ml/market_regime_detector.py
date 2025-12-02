"""
Market Regime Detection for RL Trading
Detects bull, bear, and sideways markets for regime-aware training.
"""

import logging
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class MarketRegimeDetector:
    """
    Detects market regimes (bull, bear, sideways) for adaptive RL training.

    Regimes:
    - BULL: Strong uptrend, high momentum
    - BEAR: Strong downtrend, high negative momentum
    - SIDEWAYS: Choppy, low trend strength
    """

    def __init__(
        self,
        trend_window: int = 20,
        momentum_window: int = 10,
        volatility_window: int = 20,
    ):
        self.trend_window = trend_window
        self.momentum_window = momentum_window
        self.volatility_window = volatility_window

    def detect(
        self,
        prices: np.ndarray,
        returns: Optional[np.ndarray] = None,
        volatility: Optional[float] = None,
    ) -> dict[str, Any]:
        """
        Detect current market regime.

        Args:
            prices: Price series
            returns: Returns series (if None, calculated from prices)
            volatility: Volatility (if None, calculated from returns)

        Returns:
            Dictionary with regime, confidence, and metrics
        """
        if len(prices) < self.trend_window:
            return {
                "regime": "UNKNOWN",
                "confidence": 0.0,
                "trend_strength": 0.0,
                "momentum": 0.0,
                "volatility": 0.0,
            }

        # Calculate returns if not provided
        if returns is None:
            returns = np.diff(prices) / prices[:-1]

        # Calculate trend strength (slope of price trend)
        recent_prices = prices[-self.trend_window :]
        trend_slope = np.polyfit(range(len(recent_prices)), recent_prices, 1)[0]
        trend_strength = abs(trend_slope) / np.mean(recent_prices)  # Normalize

        # Calculate momentum (recent returns)
        recent_returns = (
            returns[-self.momentum_window :] if len(returns) >= self.momentum_window else returns
        )
        momentum = np.mean(recent_returns)

        # Calculate volatility
        if volatility is None:
            volatility = (
                np.std(returns[-self.volatility_window :])
                if len(returns) >= self.volatility_window
                else np.std(returns)
            )

        # Determine regime
        if trend_strength > 0.001 and momentum > 0.001:
            regime = "BULL"
            confidence = min(1.0, trend_strength * 100 + abs(momentum) * 100)
        elif trend_strength > 0.001 and momentum < -0.001:
            regime = "BEAR"
            confidence = min(1.0, trend_strength * 100 + abs(momentum) * 100)
        else:
            regime = "SIDEWAYS"
            confidence = min(1.0, volatility * 100)

        return {
            "regime": regime,
            "confidence": float(confidence),
            "trend_strength": float(trend_strength),
            "momentum": float(momentum),
            "volatility": float(volatility),
        }

    def detect_from_state(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Detect regime from market state dictionary.

        Args:
            market_state: Dictionary with market state information

        Returns:
            Regime detection result
        """
        prices = market_state.get("prices")
        returns = market_state.get("returns")
        volatility = market_state.get("volatility")

        if prices is None:
            # Try to reconstruct from other data
            close_prices = market_state.get("close_prices")
            if close_prices is not None:
                prices = np.array(close_prices)
            else:
                return {
                    "regime": "UNKNOWN",
                    "confidence": 0.0,
                    "trend_strength": 0.0,
                    "momentum": 0.0,
                    "volatility": volatility or 0.0,
                }

        return self.detect(prices, returns, volatility)

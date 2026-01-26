"""
RL Filter - Linear Feature Scoring Model

Status: ACTIVE (Jan 26, 2026 - ML-IMP-1)
Uses pre-trained weights from models/ml/rl_filter_weights.json

Implementation:
- Linear scoring: score = bias + sum(weight_i * feature_i)
- Action threshold: if score > threshold -> "enter", else "hold"
- SPY-specific weights for optimized trading

Features used:
- strength: Signal strength (momentum indicator)
- momentum: Short-term momentum
- rsi_gap: RSI deviation from neutral (50)
- volume_premium: Volume vs average
- sma_ratio: Price vs SMA ratio
- atr_normalized: Normalized ATR (volatility)
- adx_normalized: Trend strength (ADX)
- di_difference: Directional indicator difference

The RLHF feedback model (models/ml/feedback_model.json) continues to learn
from user feedback using Thompson Sampling.
"""

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

# Path to pre-trained weights
WEIGHTS_PATH = Path(__file__).parent.parent.parent / "models" / "ml" / "rl_filter_weights.json"


class RLFilter:
    """
    Linear Feature Scoring RL Filter.

    Uses pre-trained weights to score trading signals and determine action.
    Weights are ticker-specific (SPY, QQQ) with a default fallback.
    """

    def __init__(self):
        self.enabled = os.getenv("RL_FILTER_ENABLED", "true").lower() == "true"
        self.weights = self._load_weights()
        self._warned = False

    def _load_weights(self) -> dict:
        """Load pre-trained weights from JSON file."""
        try:
            if WEIGHTS_PATH.exists():
                with open(WEIGHTS_PATH) as f:
                    weights = json.load(f)
                logger.info(f"RLFilter loaded weights for: {list(weights.keys())}")
                return weights
            else:
                logger.warning(f"RLFilter weights not found at {WEIGHTS_PATH}")
                return {}
        except Exception as e:
            logger.error(f"Failed to load RLFilter weights: {e}")
            return {}

    def _get_ticker_weights(self, ticker: str = "SPY") -> dict:
        """Get weights for specific ticker or default."""
        ticker_upper = ticker.upper() if ticker else "SPY"
        if ticker_upper in self.weights:
            return self.weights[ticker_upper]
        return self.weights.get("default", {})

    def _compute_score(self, features: dict, ticker: str = "SPY") -> float:
        """
        Compute linear score from features.

        Score = bias + sum(weight_i * feature_i)
        """
        ticker_weights = self._get_ticker_weights(ticker)
        if not ticker_weights:
            return 0.0

        bias = ticker_weights.get("bias", 0.0)
        weights = ticker_weights.get("weights", {})

        score = bias
        for feature_name, weight in weights.items():
            feature_value = features.get(feature_name, 0.0)
            if feature_value is not None:
                score += weight * float(feature_value)

        return score

    def filter(self, signal: dict, ticker: str = "SPY") -> dict:
        """
        Filter signal using linear scoring model.

        Args:
            signal: Trading signal with features
            ticker: Ticker symbol for weight selection

        Returns:
            dict with action and confidence
        """
        if not self.enabled or not self.weights:
            return {"action": signal.get("action", "hold"), "confidence": 0.5, "is_stub": True}

        # Extract features from signal
        features = signal.get("features", signal)

        # Compute score
        score = self._compute_score(features, ticker)

        # Get threshold for this ticker
        ticker_weights = self._get_ticker_weights(ticker)
        threshold = ticker_weights.get("action_threshold", 0.5)
        multiplier = ticker_weights.get("base_multiplier", 1.0)

        # Determine action based on score vs threshold
        if score > threshold:
            action = "enter"
            # Confidence based on how far above threshold
            confidence = min(0.95, 0.5 + (score - threshold) * multiplier)
        elif score < -threshold:
            action = "exit"
            confidence = min(0.95, 0.5 + abs(score + threshold) * multiplier)
        else:
            action = "hold"
            confidence = 0.5

        logger.debug(f"RLFilter: score={score:.3f}, threshold={threshold}, action={action}")

        return {"action": action, "confidence": round(confidence, 3), "score": round(score, 3)}

    def get_action(self, state: dict, ticker: str = "SPY") -> tuple:
        """
        Get action for given state.

        Args:
            state: State dictionary with features
            ticker: Ticker symbol

        Returns:
            Tuple of (action, confidence)
        """
        result = self.filter(state, ticker)
        return (result["action"], result["confidence"])

    def predict(self, state: dict, ticker: str = "SPY") -> dict:
        """
        Predict action for given state.

        Args:
            state: State dictionary with features
            ticker: Ticker symbol

        Returns:
            dict with action, confidence, and score
        """
        if not self.enabled or not self.weights:
            return {"action": "hold", "confidence": 0.5, "is_stub": True}

        return self.filter(state, ticker)

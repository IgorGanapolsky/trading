from __future__ import annotations

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
import tempfile
from copy import deepcopy
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

    @staticmethod
    def _safe_float(value, default: float = 0.0) -> float:
        """Convert to float safely with fallback."""
        try:
            if value is None:
                return default
            return float(value)
        except (TypeError, ValueError):
            return default

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

    def _extract_features(self, state: dict | None) -> dict:
        """Extract and normalize features from a state payload."""
        if not isinstance(state, dict):
            return {}

        features = state.get("features", state)
        if not isinstance(features, dict):
            return {}

        normalized = {}
        for name, value in features.items():
            if not isinstance(name, str):
                continue
            if value is None:
                continue
            try:
                normalized[name] = float(value)
            except (TypeError, ValueError):
                continue
        return normalized

    def _ensure_ticker_config(self, ticker: str = "SPY") -> tuple[str, dict]:
        """
        Ensure ticker config exists and is well-formed.

        Unknown tickers are initialized from `default` weights.
        """
        ticker_upper = ticker.upper() if ticker else "SPY"
        ticker_config = self.weights.get(ticker_upper)
        if isinstance(ticker_config, dict):
            ticker_config.setdefault("bias", 0.0)
            if not isinstance(ticker_config.get("weights"), dict):
                ticker_config["weights"] = {}
            ticker_config.setdefault("action_threshold", 0.5)
            ticker_config.setdefault("base_multiplier", 1.0)
            self.weights[ticker_upper] = ticker_config
            return ticker_upper, ticker_config

        default_config = self.weights.get("default", {})
        if not isinstance(default_config, dict):
            default_config = {}

        cloned = deepcopy(default_config)
        cloned.setdefault("bias", 0.0)
        if not isinstance(cloned.get("weights"), dict):
            cloned["weights"] = {}
        cloned.setdefault("action_threshold", 0.5)
        cloned.setdefault("base_multiplier", 1.0)

        self.weights[ticker_upper] = cloned
        return ticker_upper, cloned

    def _persist_weights_atomic(self) -> bool:
        """Persist current weights atomically to disk."""
        tmp_path = None
        try:
            WEIGHTS_PATH.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w",
                dir=str(WEIGHTS_PATH.parent),
                prefix=f"{WEIGHTS_PATH.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp_file:
                json.dump(self.weights, tmp_file, indent=2)
                tmp_file.flush()
                os.fsync(tmp_file.fileno())
                tmp_path = Path(tmp_file.name)
            os.replace(tmp_path, WEIGHTS_PATH)
            return True
        except Exception as e:
            logger.error(f"Failed to persist RLFilter weights atomically: {e}")
            return False
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except OSError:
                    pass

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
            return {
                "action": signal.get("action", "hold"),
                "confidence": 0.5,
                "is_stub": True,
            }

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

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "score": round(score, 3),
        }

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

    def record_trade_outcome(
        self,
        entry_state: dict | None,
        action: int | float | None,
        exit_state: dict | None,
        reward: float | None,
        done: bool,
        ticker: str | None = None,
    ) -> dict:
        """
        Online update for linear RL filter weights from a completed trade.

        Uses a one-step temporal-difference update:
          TD target = reward + gamma * Q(exit_state) * (1 - done)
          TD error  = target - Q(entry_state)
        """
        if not self.enabled:
            return {"updated": False, "persisted": False, "reason": "disabled", "is_stub": True}

        # Infer ticker from explicit arg first, then from states, then default.
        resolved_ticker = (ticker or "").upper() if ticker else ""
        if not resolved_ticker:
            for state in (entry_state, exit_state):
                if isinstance(state, dict):
                    symbol = state.get("ticker") or state.get("symbol")
                    if isinstance(symbol, str) and symbol.strip():
                        resolved_ticker = symbol.strip().upper()
                        break
        if not resolved_ticker:
            resolved_ticker = "SPY"

        snapshot = deepcopy(self.weights)
        ticker_key, ticker_config = self._ensure_ticker_config(resolved_ticker)
        weights = ticker_config.get("weights", {})
        if not isinstance(weights, dict):
            weights = {}
            ticker_config["weights"] = weights

        entry_features = self._extract_features(entry_state)
        exit_features = self._extract_features(exit_state)

        learning_rate = self._safe_float(os.getenv("RL_FILTER_LEARNING_RATE", "0.01"), 0.01)
        gamma = self._safe_float(os.getenv("RL_FILTER_GAMMA", "0.95"), 0.95)
        max_abs_weight = self._safe_float(os.getenv("RL_FILTER_MAX_ABS_WEIGHT", "25.0"), 25.0)

        # Clamp hyperparameters to safe ranges.
        learning_rate = min(max(learning_rate, 1e-6), 1.0)
        gamma = min(max(gamma, 0.0), 1.0)
        max_abs_weight = max(max_abs_weight, 1.0)

        bias = self._safe_float(ticker_config.get("bias"), 0.0)

        def _linear_score(features: dict) -> float:
            score = bias
            for name, value in features.items():
                score += self._safe_float(weights.get(name), 0.0) * value
            return score

        q_entry = _linear_score(entry_features)
        q_exit = _linear_score(exit_features)

        reward_value = self._safe_float(reward, 0.0)
        action_value = self._safe_float(action, 1.0)
        done_flag = bool(done)

        target_q = reward_value + (0.0 if done_flag else gamma * q_exit)
        td_error = target_q - q_entry

        # Action scales update direction for long/short compatibility.
        action_sign = 1.0 if action_value >= 0 else -1.0
        updated_weights = 0
        for feature_name, feature_value in entry_features.items():
            current_weight = self._safe_float(weights.get(feature_name), 0.0)
            delta = learning_rate * td_error * feature_value * action_sign
            new_weight = max(min(current_weight + delta, max_abs_weight), -max_abs_weight)
            weights[feature_name] = new_weight
            if abs(new_weight - current_weight) > 0:
                updated_weights += 1

        bias_delta = learning_rate * td_error * action_sign
        new_bias = max(min(bias + bias_delta, max_abs_weight), -max_abs_weight)
        ticker_config["bias"] = new_bias
        ticker_config["weights"] = weights
        self.weights[ticker_key] = ticker_config

        persisted = self._persist_weights_atomic()
        if not persisted:
            self.weights = snapshot
            return {
                "updated": False,
                "persisted": False,
                "ticker": ticker_key,
                "reason": "persist_failed",
            }

        total_loss = 0.5 * (td_error**2)
        return {
            "updated": True,
            "persisted": True,
            "ticker": ticker_key,
            "reward": reward_value,
            "action": action_value,
            "done": done_flag,
            "td_error": round(td_error, 6),
            "target_q": round(target_q, 6),
            "predicted_q": round(q_entry, 6),
            "total_loss": round(total_loss, 6),
            "learning_rate": learning_rate,
            "gamma": gamma,
            "updated_weights": updated_weights,
            "feature_count": len(entry_features),
            "buffer_size": 1,
        }

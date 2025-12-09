"""RL filter used as Gate 2.

Enhanced with DiscoRL-inspired DQN (Dec 2025):
- Categorical value distribution for uncertainty modeling
- EMA normalization for stable learning
- Online learning from trade outcomes
"""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any

import numpy as np

from src.agents.rl_transformer import TransformerRLPolicy, TransformerUnavailableError

# DiscoRL-inspired DQN (Dec 2025)
DISCO_DQN_AVAILABLE = False
try:
    from src.ml.disco_dqn_agent import DiscoDQNAgent
    DISCO_DQN_AVAILABLE = True
except ImportError:
    pass  # PyTorch not available

logger = logging.getLogger(__name__)


class RLFilter:
    """
    Lightweight inference layer that approximates an RL confidence score.

    The weights are exported from our PPO backtests and stored in
    `models/ml/rl_filter_weights.json`. This keeps the inference step fast and
    local while we work on the heavier Torch models.

    Enhanced Dec 2025: DiscoRL-inspired DQN with categorical value distribution.
    """

    # Feature names for state vector (order matters!)
    STATE_FEATURES = [
        "strength", "momentum", "rsi_gap", "volume_premium", "sma_ratio",
        "rsi", "macd_histogram", "volume_ratio", "atr_pct", "price_change_pct"
    ]
    STATE_DIM = len(STATE_FEATURES)

    def __init__(
        self,
        weights_path: str | Path | None = None,
        *,
        enable_transformer: bool | None = None,
        enable_disco_dqn: bool | None = None,
    ) -> None:
        self.weights_path = Path(weights_path or "models/ml/rl_filter_weights.json")
        self.weights = self._load_weights()
        self.default_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.6"))
        self.transformer: TransformerRLPolicy | None = None
        self.disco_dqn: DiscoDQNAgent | None = None

        # Transformer initialization
        flag = (
            enable_transformer
            if enable_transformer is not None
            else os.getenv("RL_USE_TRANSFORMER", "1").lower() in {"1", "true", "yes", "on"}
        )
        if flag:
            try:
                self.transformer = TransformerRLPolicy(
                    context_window=int(os.getenv("RL_TRANSFORMER_WINDOW", "64")),
                    confidence_threshold=float(os.getenv("RL_TRANSFORMER_THRESHOLD", "0.55")),
                )
                logger.info("Transformer RL policy initialised for Gate 2.")
            except TransformerUnavailableError as exc:
                logger.warning("Transformer RL disabled: %s", exc)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Transformer RL initialisation failed: %s", exc)

        # DiscoRL-inspired DQN initialization (Dec 2025)
        disco_flag = (
            enable_disco_dqn
            if enable_disco_dqn is not None
            else os.getenv("RL_USE_DISCO_DQN", "1").lower() in {"1", "true", "yes", "on"}
        )
        if disco_flag and DISCO_DQN_AVAILABLE:
            try:
                model_path = Path(os.getenv("DISCO_DQN_MODEL_PATH", "models/ml/disco_dqn.pt"))
                self.disco_dqn = DiscoDQNAgent(
                    state_dim=self.STATE_DIM,
                    action_dim=3,  # HOLD, BUY, SELL
                    num_bins=int(os.getenv("DISCO_DQN_BINS", "51")),
                    v_min=float(os.getenv("DISCO_DQN_VMIN", "-10.0")),
                    v_max=float(os.getenv("DISCO_DQN_VMAX", "10.0")),
                    gamma=float(os.getenv("DISCO_DQN_GAMMA", "0.997")),
                    learning_rate=float(os.getenv("DISCO_DQN_LR", "0.0003")),
                    use_advantage_normalization=True,
                    use_td_normalization=True,
                )
                # Load pre-trained weights if available
                if model_path.exists():
                    self.disco_dqn.load(str(model_path))
                    logger.info("DiscoRL DQN loaded from %s", model_path)
                else:
                    logger.info("DiscoRL DQN initialized (no pre-trained weights)")
                logger.info(
                    "✅ DiscoRL DQN enabled for Gate 2 (bins=%d, gamma=%.3f)",
                    self.disco_dqn.num_bins,
                    self.disco_dqn.gamma,
                )
            except Exception as exc:
                logger.warning("DiscoRL DQN initialization failed: %s", exc)
        elif disco_flag and not DISCO_DQN_AVAILABLE:
            logger.warning("DiscoRL DQN requested but PyTorch not available")

    def _load_weights(self) -> dict[str, Any]:
        if self.weights_path.exists():
            try:
                data = json.loads(self.weights_path.read_text())
                logger.info(
                    "RLFilter loaded weights for symbols: %s",
                    ", ".join(sorted(data.keys())),
                )
                return data
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Failed to parse RL weights file: %s", exc)
        logger.warning(
            "RL weights file missing (%s). Falling back to default heuristics.",
            self.weights_path,
        )
        return {
            "default": {
                "bias": -0.1,
                "weights": {
                    "strength": 2.0,
                    "momentum": 1.2,
                    "rsi_gap": 0.7,
                    "volume_premium": 0.5,
                    "sma_ratio": 1.3,
                },
                "action_threshold": 0.6,
                "base_multiplier": 0.75,
            }
        }

    def predict(self, market_state: dict[str, Any]) -> dict[str, Any]:
        """
        Args:
            market_state: Dict of indicators from Gate 1.

        Returns:
            Dict with action/confidence/multiplier + explainability payload.
        """
        symbol = (market_state.get("symbol") or "default").upper()
        heuristic = self._predict_with_heuristics(symbol, market_state)
        transformer_decision: dict[str, Any] | None = None
        disco_decision: dict[str, Any] | None = None

        # Transformer prediction
        if self.transformer:
            try:
                transformer_decision = self.transformer.predict(symbol, market_state)
            except Exception as exc:  # pragma: no cover - transformer errors should not halt gate
                logger.warning("Transformer RL inference failed for %s: %s", symbol, exc)

        # DiscoRL DQN prediction (Dec 2025)
        if self.disco_dqn:
            try:
                disco_decision = self._predict_with_disco_dqn(symbol, market_state)
            except Exception as exc:
                logger.warning("DiscoRL DQN inference failed for %s: %s", symbol, exc)

        # Blend all available predictions
        decision = self._blend_all_decisions(
            heuristic=heuristic,
            transformer=transformer_decision,
            disco=disco_decision,
        )

        logger.debug(
            "RLFilter | %s | action=%s | conf=%.3f | sources=%s",
            symbol,
            decision["action"],
            decision["confidence"],
            decision.get("sources"),
        )
        return decision

    def _predict_with_disco_dqn(
        self, symbol: str, market_state: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Get prediction from DiscoRL-inspired DQN.

        Returns:
            Dict with action, confidence, Q-values, and distribution info
        """
        # Extract state vector
        state = self._market_state_to_vector(market_state)

        # Get action and info from DQN
        action_idx, info = self.disco_dqn.select_action(state, training=False)

        # Map action index to action name
        action_map = {0: "neutral", 1: "long", 2: "short"}
        action = action_map.get(action_idx, "neutral")

        # Convert Q-values to confidence
        q_values = info.get("q_values", [0, 0, 0])
        if len(q_values) >= 2:
            # Confidence based on Q-value advantage for BUY action
            q_buy = q_values[1] if len(q_values) > 1 else 0
            q_hold = q_values[0] if len(q_values) > 0 else 0
            advantage = q_buy - q_hold
            # Sigmoid to get confidence in [0, 1]
            confidence = 1 / (1 + math.exp(-advantage))
        else:
            confidence = 0.5

        # If BUY has highest Q-value and confidence > threshold, recommend long
        if action_idx == 1 and confidence >= self.default_threshold:
            action = "long"
        elif action_idx == 2:
            action = "short"
        else:
            action = "neutral"

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "suggested_multiplier": round(0.8 + confidence * 0.4, 3),
            "q_values": [round(q, 4) for q in q_values] if q_values is not None else None,
            "distribution": info.get("distribution"),
            "epsilon": info.get("epsilon", 0),
            "model_stats": self.disco_dqn.get_stats() if self.disco_dqn else {},
        }

    def _market_state_to_vector(self, market_state: dict[str, Any]) -> np.ndarray:
        """
        Convert market state dict to numpy vector for DQN.

        Uses STATE_FEATURES order for consistency.
        """
        features = self._extract_features(market_state)

        # Add additional features for full state
        features["rsi"] = float(market_state.get("rsi", 50.0)) / 100.0  # Normalize
        features["macd_histogram"] = float(market_state.get("macd_histogram", 0.0))
        features["volume_ratio"] = float(market_state.get("volume_ratio", 1.0)) - 1.0  # Center
        features["atr_pct"] = float(market_state.get("atr_pct", 0.02))
        features["price_change_pct"] = float(market_state.get("price_change_pct", 0.0))

        # Build vector in consistent order
        state = np.zeros(self.STATE_DIM, dtype=np.float32)
        for i, feat_name in enumerate(self.STATE_FEATURES):
            state[i] = features.get(feat_name, 0.0)

        return state

    def _blend_all_decisions(
        self,
        heuristic: dict[str, Any],
        transformer: dict[str, Any] | None,
        disco: dict[str, Any] | None,
    ) -> dict[str, Any]:
        """
        Blend predictions from all available models.

        Weights are configurable via environment variables.
        Transformer gets highest weight until DiscoRL is validated with real trades.
        """
        # Get weights from env (default: conservative until DiscoRL validated)
        # Dec 9, 2025: Reduced DiscoRL from 0.45 to 0.15 - needs validation (0 closed trades)
        # Redistributed weight to proven transformer + heuristic models
        heuristic_weight = float(os.getenv("RL_HEURISTIC_WEIGHT", "0.40"))
        transformer_weight = float(os.getenv("RL_TRANSFORMER_WEIGHT", "0.45"))
        disco_weight = float(os.getenv("RL_DISCO_WEIGHT", "0.15"))

        # Accumulate weighted predictions
        total_weight = 0.0
        weighted_confidence = 0.0
        weighted_multiplier = 0.0
        sources = {}

        # Heuristic (always available)
        weighted_confidence += heuristic["confidence"] * heuristic_weight
        weighted_multiplier += heuristic["suggested_multiplier"] * heuristic_weight
        total_weight += heuristic_weight
        sources["heuristic_confidence"] = heuristic["confidence"]

        # Transformer (if available)
        if transformer:
            weighted_confidence += transformer["confidence"] * transformer_weight
            weighted_multiplier += transformer["suggested_multiplier"] * transformer_weight
            total_weight += transformer_weight
            sources["transformer_confidence"] = transformer["confidence"]
            sources["transformer_regime"] = transformer.get("regime")

        # DiscoRL DQN (if available - highest priority)
        if disco:
            weighted_confidence += disco["confidence"] * disco_weight
            weighted_multiplier += disco["suggested_multiplier"] * disco_weight
            total_weight += disco_weight
            sources["disco_confidence"] = disco["confidence"]
            sources["disco_q_values"] = disco.get("q_values")
            sources["disco_epsilon"] = disco.get("epsilon")

        # Normalize
        if total_weight > 0:
            blended_confidence = weighted_confidence / total_weight
            blended_multiplier = weighted_multiplier / total_weight
        else:
            blended_confidence = heuristic["confidence"]
            blended_multiplier = heuristic["suggested_multiplier"]

        # Determine action based on blended confidence
        action = "long" if blended_confidence >= self.default_threshold else "neutral"

        # Determine mode for logging
        if disco:
            mode = "disco_blend" if transformer else "disco_heuristic"
        elif transformer:
            mode = "transformer_heuristic"
        else:
            mode = "heuristic_only"

        sources["mode"] = mode
        sources["threshold"] = self.default_threshold

        return {
            "action": action,
            "confidence": round(blended_confidence, 3),
            "suggested_multiplier": round(blended_multiplier, 3),
            "features": heuristic.get("features", {}),
            "explainability": {
                "heuristic_weights": heuristic.get("explainability", {}).get("heuristic_weights"),
                "disco_q_values": disco.get("q_values") if disco else None,
                "disco_distribution": disco.get("distribution") is not None if disco else False,
            },
            "sources": sources,
        }

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _predict_with_heuristics(self, symbol: str, market_state: dict[str, Any]) -> dict[str, Any]:
        params = self.weights.get(symbol, self.weights.get("default", {}))
        features = self._extract_features(market_state)

        z = params.get("bias", 0.0)
        for key, value in features.items():
            z += params.get("weights", {}).get(key, 0.0) * value

        confidence = self._sigmoid(z)
        threshold = params.get("action_threshold", self.default_threshold)
        action = "long" if confidence >= threshold else "neutral"
        multiplier = self._compute_multiplier(confidence, params)

        return {
            "action": action,
            "confidence": round(confidence, 3),
            "suggested_multiplier": round(multiplier, 3),
            "features": features,
            "explainability": {
                "heuristic_weights": params.get("weights", {}),
                "threshold": threshold,
            },
        }

    def _blend_decisions(
        self,
        heuristic: dict[str, Any],
        transformer_decision: dict[str, Any],
    ) -> dict[str, Any]:
        heuristic_weight = float(os.getenv("RL_HEURISTIC_WEIGHT", "0.45"))
        transformer_weight = float(os.getenv("RL_TRANSFORMER_WEIGHT", "0.55"))
        total_weight = max(1e-6, heuristic_weight + transformer_weight)

        blended_confidence = (
            heuristic["confidence"] * heuristic_weight
            + transformer_decision["confidence"] * transformer_weight
        ) / total_weight

        blended_multiplier = (
            heuristic["suggested_multiplier"] * heuristic_weight
            + transformer_decision["suggested_multiplier"] * transformer_weight
        ) / total_weight

        action = "long" if blended_confidence >= self.default_threshold else "neutral"

        explainability = {
            "transformer": transformer_decision.get("attribution"),
            "transformer_regime": transformer_decision.get("regime"),
            "transformer_model": transformer_decision.get("model_version"),
            "heuristic_weights": heuristic.get("explainability", {}).get("heuristic_weights"),
        }

        return {
            "action": action,
            "confidence": round(blended_confidence, 3),
            "suggested_multiplier": round(blended_multiplier, 3),
            "features": heuristic.get("features", {}),
            "explainability": explainability,
            "sources": {
                "mode": "hybrid",
                "heuristic_confidence": heuristic["confidence"],
                "transformer_confidence": transformer_decision["confidence"],
                "threshold": self.default_threshold,
            },
        }

    @staticmethod
    def _sigmoid(value: float) -> float:
        return 1 / (1 + math.exp(-value))

    @staticmethod
    def _compute_multiplier(confidence: float, params: dict[str, Any]) -> float:
        base = params.get("base_multiplier", 0.8)
        raw = base + confidence * 0.6
        return max(0.4, min(1.6, raw))

    @staticmethod
    def _extract_features(market_state: dict[str, Any]) -> dict[str, float]:
        strength = float(market_state.get("momentum_strength", 0.0))
        momentum = float(market_state.get("macd_histogram", 0.0))
        rsi = float(market_state.get("rsi", 50.0))
        volume_ratio = float(market_state.get("volume_ratio", 1.0))
        sma_ratio = float(market_state.get("sma_50_ratio", 0.0))

        rsi_gap = max(-2.0, min(2.0, (60.0 - rsi) / 25.0))
        volume_premium = max(-1.0, min(1.0, volume_ratio - 1.0))

        return {
            "strength": strength,
            "momentum": momentum,
            "rsi_gap": rsi_gap,
            "volume_premium": volume_premium,
            "sma_ratio": sma_ratio,
        }

    def update_from_telemetry(
        self,
        audit_path: str = "data/audit_trail/hybrid_funnel_runs.jsonl",
        model_path: str = "models/ml/rl_filter_policy.zip",
        dry_run: bool = False,
    ) -> dict[str, Any]:
        """
        Recompute RL weights using telemetry replay and persist them to disk.

        Returns:
            Summary dict describing the update result.
        """
        from src.agents.rl_weight_updater import RLWeightUpdater

        updater = RLWeightUpdater(
            audit_path=audit_path,
            weights_path=self.weights_path,
            model_path=model_path,
            dry_run=dry_run,
        )
        summary = updater.run()
        if summary.get("updated"):
            self.weights = self._load_weights()
        return summary

    # ------------------------------------------------------------------
    # DiscoRL Online Learning (Dec 2025)
    # ------------------------------------------------------------------
    def record_trade_outcome(
        self,
        entry_state: dict[str, Any],
        action: int,
        exit_state: dict[str, Any],
        reward: float,
        done: bool = True,
    ) -> dict[str, Any] | None:
        """
        Record a trade outcome for online learning.

        This enables the DiscoRL DQN to learn from actual trade results,
        improving over time as we collect more data.

        Args:
            entry_state: Market state at trade entry (from momentum agent)
            action: Action taken (0=HOLD, 1=BUY, 2=SELL)
            exit_state: Market state at trade exit
            reward: Trade P/L as reward (positive = profit, negative = loss)
            done: Whether this completes an episode

        Returns:
            Training metrics if training occurred, None otherwise
        """
        if not self.disco_dqn:
            return None

        try:
            # Convert states to vectors
            state_vec = self._market_state_to_vector(entry_state)
            next_state_vec = self._market_state_to_vector(exit_state)

            # Store transition
            self.disco_dqn.store_transition(
                state=state_vec,
                action=action,
                reward=reward,
                next_state=next_state_vec,
                done=done,
            )

            # Train step
            loss_dict = self.disco_dqn.train_step()

            if loss_dict:
                logger.info(
                    "DiscoRL online learning: reward=%.4f, loss=%.4f, buffer=%d",
                    reward,
                    loss_dict.get("total_loss", 0),
                    len(self.disco_dqn.replay_buffer),
                )

            return loss_dict

        except Exception as exc:
            logger.warning("DiscoRL online learning failed: %s", exc)
            return None

    def save_disco_model(self, filepath: str | None = None) -> bool:
        """
        Save the DiscoRL DQN model to disk.

        Args:
            filepath: Path to save model (default: models/ml/disco_dqn.pt)

        Returns:
            True if saved successfully
        """
        if not self.disco_dqn:
            logger.warning("No DiscoRL DQN to save")
            return False

        try:
            path = filepath or os.getenv("DISCO_DQN_MODEL_PATH", "models/ml/disco_dqn.pt")
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.disco_dqn.save(path)
            logger.info("DiscoRL DQN saved to %s", path)
            return True
        except Exception as exc:
            logger.error("Failed to save DiscoRL DQN: %s", exc)
            return False

    def get_disco_stats(self) -> dict[str, Any]:
        """Get DiscoRL DQN training statistics."""
        if not self.disco_dqn:
            return {"enabled": False}

        stats = self.disco_dqn.get_stats()
        stats["enabled"] = True
        return stats

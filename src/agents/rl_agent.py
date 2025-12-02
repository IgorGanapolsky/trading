"""RL filter used as Gate 2."""

from __future__ import annotations

import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Optional

from src.agents.rl_transformer import TransformerRLPolicy, TransformerUnavailableError

logger = logging.getLogger(__name__)


class RLFilter:
    """
    Lightweight inference layer that approximates an RL confidence score.

    The weights are exported from our PPO backtests and stored in
    `models/ml/rl_filter_weights.json`. This keeps the inference step fast and
    local while we work on the heavier Torch models.
    """

    def __init__(
        self,
        weights_path: str | Path | None = None,
        *,
        enable_transformer: bool | None = None,
    ) -> None:
        self.weights_path = Path(weights_path or "models/ml/rl_filter_weights.json")
        self.weights = self._load_weights()
        self.default_threshold = float(os.getenv("RL_CONFIDENCE_THRESHOLD", "0.6"))
        self.transformer: Optional[TransformerRLPolicy] = None

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
        transformer_decision: Optional[dict[str, Any]] = None

        if self.transformer:
            try:
                transformer_decision = self.transformer.predict(symbol, market_state)
            except Exception as exc:  # pragma: no cover - transformer errors should not halt gate
                logger.warning("Transformer RL inference failed for %s: %s", symbol, exc)

        if transformer_decision:
            decision = self._blend_decisions(heuristic, transformer_decision)
        else:
            decision = heuristic
            decision["sources"] = {
                "mode": "heuristic_only",
                "heuristic_confidence": heuristic["confidence"],
            }

        logger.debug(
            "RLFilter | %s | action=%s | conf=%.3f | sources=%s",
            symbol,
            decision["action"],
            decision["confidence"],
            decision.get("sources"),
        )
        return decision

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

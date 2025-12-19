"""Utilities to retrain RL filter weights from telemetry."""

from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

# Optional import - sklearn may not be installed in all environments
try:
    from sklearn.linear_model import LogisticRegression

    SKLEARN_AVAILABLE = True
except ImportError:
    LogisticRegression = None  # type: ignore
    SKLEARN_AVAILABLE = False

from src.ml.reward_functions import RiskAdjustedReward

# Optional imports - defer error to runtime when actually used
try:
    import gymnasium as gym
    from gymnasium import spaces

    GYMNASIUM_AVAILABLE = True
except ImportError:
    gym = None  # type: ignore
    spaces = None  # type: ignore
    GYMNASIUM_AVAILABLE = False

try:
    from stable_baselines3 import PPO

    SB3_AVAILABLE = True
except ImportError:
    PPO = None  # type: ignore
    SB3_AVAILABLE = False

FEATURE_KEYS = ["strength", "momentum", "rsi_gap", "volume_premium", "sma_ratio"]
logger = logging.getLogger(__name__)

# Create base class for when gymnasium is not available
if GYMNASIUM_AVAILABLE:
    _GymEnvBase = gym.Env
else:

    class _GymEnvBase:  # type: ignore
        """Placeholder base class when gymnasium is not installed."""

        metadata: dict = {}

        def reset(self, **kwargs):
            raise NotImplementedError("gymnasium not installed")

        def step(self, action):
            raise NotImplementedError("gymnasium not installed")


@dataclass
class TradeSample:
    features: np.ndarray
    reward: float
    ticker: str
    session: str | None = None


class TradeReplayEnv(_GymEnvBase):
    """Simple finite replay buffer environment for PPO fine-tuning."""

    metadata = {"render_modes": []}

    def __init__(self, samples: list[TradeSample]) -> None:
        if not GYMNASIUM_AVAILABLE:
            raise ImportError("gymnasium is required for TradeReplayEnv. Install gymnasium>=0.29.")
        if not samples:
            raise ValueError("Replay environment requires at least one sample.")
        self.samples = samples
        self.observation_space = spaces.Box(
            low=-10.0,
            high=10.0,
            shape=(len(FEATURE_KEYS),),
            dtype=np.float32,
        )
        self.action_space = spaces.Discrete(2)  # 0 = skip, 1 = enter trade
        self._order: list[int] = list(range(len(samples)))
        self._cursor = 0

    def reset(self, *, seed: int | None = None, options: dict | None = None):
        super().reset(seed=seed)
        random.shuffle(self._order)
        self._cursor = 0
        obs = self._current_obs()
        return obs, {}

    def step(self, action: int):
        sample = self.samples[self._order[self._cursor]]
        reward = self._calculate_reward(sample.reward, action)
        self._cursor += 1

        terminated = self._cursor >= len(self.samples)
        truncated = False
        obs = self._current_obs()
        info: dict[str, Any] = {}
        return obs, reward, terminated, truncated, info

    def _current_obs(self) -> np.ndarray:
        idx = self._order[self._cursor % len(self.samples)]
        return self.samples[idx].features.astype(np.float32)

    @staticmethod
    def _calculate_reward(outcome: float, action: int) -> float:
        """
        Positive outcome (+1) rewards taking the trade. Negative outcome (-1)
        rewards skipping. Neutral samples return 0 regardless of action.
        """
        if outcome == 0:
            return 0.0
        if action == 1:  # take trade
            return outcome
        # skip: reward avoiding bad trades, penalize missing good ones
        return 0.2 if outcome < 0 else -0.2


class RLWeightUpdater:
    """Coordinates replay extraction, PPO training, and JSON export."""

    def __init__(
        self,
        audit_path: str | Path = "data/audit_trail/hybrid_funnel_runs.jsonl",
        weights_path: str | Path = "models/ml/rl_filter_weights.json",
        model_path: str | Path = "models/ml/rl_filter_policy.zip",
        max_samples: int = 200,
        min_symbol_samples: int = 15,
        dry_run: bool = False,
    ) -> None:
        self.audit_path = Path(audit_path)
        self.weights_path = Path(weights_path)
        self.model_path = Path(model_path)
        self.max_samples = max_samples
        self.min_symbol_samples = min_symbol_samples
        self.dry_run = dry_run
        self.risk_reward = RiskAdjustedReward()

    def run(self) -> dict[str, Any]:
        samples = self._collect_samples()
        if not samples:
            return {
                "updated": False,
                "reason": "insufficient_samples",
                "samples_collected": 0,
            }

        logger.info("Collected %s RL replay samples", len(samples))

        env = TradeReplayEnv(samples)
        model = PPO(
            policy="MlpPolicy",
            env=env,
            verbose=0,
            n_steps=min(64, len(samples)),
            learning_rate=2.5e-4,
        )

        if not self.dry_run:
            total_steps = max(500, len(samples) * 25)
            model.learn(total_timesteps=total_steps, progress_bar=False)
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            model.save(self.model_path)

        learned_weights = self._fit_symbol_weights(samples)
        if not learned_weights:
            return {
                "updated": False,
                "reason": "regression_failed",
                "samples_collected": len(samples),
            }

        blended = self._blend_with_existing(learned_weights)
        if not self.dry_run:
            self.weights_path.parent.mkdir(parents=True, exist_ok=True)
            self.weights_path.write_text(json.dumps(blended, indent=2))

        return {
            "updated": True,
            "samples_collected": len(samples),
            "symbols_updated": list(learned_weights.keys()),
            "weights_path": str(self.weights_path),
            "model_path": str(self.model_path),
            "dry_run": self.dry_run,
        }

    def _collect_samples(self) -> list[TradeSample]:
        if not self.audit_path.exists():
            logger.warning("Audit trail %s not found.", self.audit_path)
            return []

        events: list[dict[str, Any]] = []
        with self.audit_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

        replay: list[TradeSample] = []
        for idx, event in enumerate(events):
            if event.get("event") != "gate.rl_filter":
                continue
            features = event.get("payload", {}).get("features", {})
            feature_vec = self._vectorize_features(features)
            if feature_vec is None:
                continue

            reward = self._derive_reward(events, idx, event.get("session"), event.get("ticker"))
            if reward == 0:
                continue

            replay.append(
                TradeSample(
                    features=feature_vec,
                    reward=reward,
                    ticker=(event.get("ticker") or "DEFAULT").upper(),
                    session=event.get("session"),
                )
            )

        if len(replay) > self.max_samples:
            replay = replay[-self.max_samples :]
        return replay

    @staticmethod
    def _vectorize_features(features: dict[str, Any]) -> np.ndarray | None:
        try:
            values = [float(features.get(key, 0.0) or 0.0) for key in FEATURE_KEYS]
        except (TypeError, ValueError):
            return None
        vector = np.array(values, dtype=np.float32)
        return np.nan_to_num(vector, nan=0.0, posinf=0.0, neginf=0.0)

    def _derive_reward(
        self,
        events: list[dict[str, Any]],
        start_index: int,
        session: str | None,
        ticker: str | None,
    ) -> float:
        """
        Look ahead for success/failure signals tied to the RL gate entry.

        Uses RiskAdjustedReward for rich trade data when available,
        falls back to binary reward otherwise.
        """
        trade_result = self._extract_trade_result(events, start_index, session, ticker)

        if trade_result is None:
            return 0.0

        # If we have rich trade data, use RiskAdjustedReward
        if "pl_pct" in trade_result and trade_result["pl_pct"] is not None:
            try:
                reward = self.risk_reward.calculate_from_trade_result(trade_result)
                logger.debug(
                    "Using RiskAdjustedReward for %s: pl_pct=%.4f, reward=%.4f",
                    ticker or "DEFAULT",
                    trade_result["pl_pct"],
                    reward,
                )
                return reward
            except Exception as e:
                logger.warning(
                    "RiskAdjustedReward failed for %s: %s. Falling back to binary.",
                    ticker or "DEFAULT",
                    e,
                )

        # Fallback to binary reward
        if trade_result.get("binary_outcome"):
            return trade_result["binary_outcome"]

        return 0.0

    def _extract_trade_result(
        self,
        events: list[dict[str, Any]],
        start_index: int,
        session: str | None,
        ticker: str | None,
    ) -> dict[str, Any] | None:
        """
        Extract detailed trade information from audit trail events.

        Returns trade_result dict with:
        - pl_pct: Profit/loss percentage
        - holding_period_days: Days trade was held
        - max_drawdown: Maximum drawdown
        - binary_outcome: Fallback binary reward (+1/-1)
        """
        entry_time = events[start_index].get("timestamp")
        exit_time = None
        pl_pct = None
        binary_outcome = None

        for event in events[start_index + 1 : start_index + 25]:
            if session and event.get("session") != session:
                continue
            if ticker and event.get("ticker") != ticker:
                continue

            status = event.get("status")
            event_type = event.get("event", "")
            payload = event.get("payload", {})

            # Extract PnL if available
            pnl = payload.get("pnl") or payload.get("pnl_pct")
            if pnl is not None:
                try:
                    pnl_value = float(pnl)
                    # Assume pnl_pct is already a decimal (0.05 = 5%)
                    # If it's a percentage (5.0 = 5%), convert to decimal
                    if abs(pnl_value) > 1.0:  # Likely a percentage
                        pl_pct = pnl_value / 100.0
                    else:
                        pl_pct = pnl_value

                    exit_time = event.get("timestamp")
                    binary_outcome = 1.0 if pnl_value > 0 else -1.0
                    break
                except (TypeError, ValueError):
                    pass

            # Binary signals for fallback
            if event_type.startswith("execution.") and status == "submitted":
                binary_outcome = 1.0
                exit_time = event.get("timestamp")
                break
            if status == "reject":
                binary_outcome = -1.0
                exit_time = event.get("timestamp")
                break

        if binary_outcome is None:
            return None

        # Calculate holding period
        holding_period_days = 1  # Default
        if entry_time and exit_time:
            try:
                # Simplified: assume timestamps are comparable
                # In practice, would parse and calculate actual duration
                holding_period_days = 1  # Conservative estimate
            except Exception:
                pass

        # Build trade result dict
        result: dict[str, Any] = {
            "binary_outcome": binary_outcome,
            "holding_period_days": holding_period_days,
        }

        if pl_pct is not None:
            result["pl_pct"] = pl_pct
            # Estimate max drawdown (conservative: use pl_pct if negative)
            result["max_drawdown"] = abs(pl_pct) if pl_pct < 0 else 0.0

        return result

    def _fit_symbol_weights(self, samples: list[TradeSample]) -> dict[str, dict[str, Any]]:
        grouped: dict[str, list[TradeSample]] = {}
        for sample in samples:
            grouped.setdefault(sample.ticker, []).append(sample)

        learned: dict[str, dict[str, Any]] = {}
        for symbol, rows in grouped.items():
            if len(rows) < self.min_symbol_samples:
                continue
            X = np.vstack([row.features for row in rows])
            y = np.array([1 if row.reward > 0 else 0 for row in rows])
            if len(np.unique(y)) < 2:
                continue
            clf = LogisticRegression(max_iter=500)
            clf.fit(X, y)
            learned[symbol] = self._serialize_coefficients(clf, X)

        if not learned and samples:
            # Fallback to default weights using full dataset
            X = np.vstack([row.features for row in samples])
            y = np.array([1 if row.reward > 0 else 0 for row in samples])
            if len(np.unique(y)) >= 2:
                clf = LogisticRegression(max_iter=500)
                clf.fit(X, y)
                learned["default"] = self._serialize_coefficients(clf, X)
        return learned

    def _serialize_coefficients(
        self, clf: LogisticRegression, feature_matrix: np.ndarray
    ) -> dict[str, Any]:
        weights = clf.coef_[0]
        intercept = float(clf.intercept_[0])
        probabilities = clf.predict_proba(feature_matrix)[:, 1]
        avg_probability = float(np.clip(np.mean(probabilities), 0.0, 1.0))

        return {
            "bias": round(intercept, 4),
            "weights": {
                key: round(weight, 4) for key, weight in zip(FEATURE_KEYS, weights, strict=False)
            },
            "action_threshold": round(max(0.5, min(0.85, avg_probability)), 3),
            "base_multiplier": round(0.6 + avg_probability * 0.5, 3),
        }

    def _blend_with_existing(self, new_weights: dict[str, dict[str, Any]]) -> dict[str, Any]:
        if not self.weights_path.exists():
            return new_weights
        try:
            existing = json.loads(self.weights_path.read_text())
        except json.JSONDecodeError:
            logger.warning("Existing RL weights file is invalid JSON; replacing.")
            return new_weights

        blended = dict(existing)
        for symbol, payload in new_weights.items():
            prior = existing.get(symbol, existing.get("default", {}))
            blended[symbol] = self._blend_payload(prior, payload)
        return blended

    @staticmethod
    def _blend_payload(
        old: dict[str, Any], new: dict[str, Any], alpha: float = 0.7
    ) -> dict[str, Any]:
        weights = {}
        for key in FEATURE_KEYS:
            old_val = float(old.get("weights", {}).get(key, 0.0))
            new_val = float(new.get("weights", {}).get(key, 0.0))
            weights[key] = round(alpha * old_val + (1 - alpha) * new_val, 4)

        bias = round(
            alpha * float(old.get("bias", 0.0)) + (1 - alpha) * float(new.get("bias", 0.0)), 4
        )
        action_threshold = round(
            alpha * float(old.get("action_threshold", 0.6))
            + (1 - alpha) * float(new.get("action_threshold", 0.6)),
            3,
        )
        base_multiplier = round(
            alpha * float(old.get("base_multiplier", 0.75))
            + (1 - alpha) * float(new.get("base_multiplier", 0.75)),
            3,
        )

        return {
            "bias": bias,
            "weights": weights,
            "action_threshold": action_threshold,
            "base_multiplier": base_multiplier,
        }

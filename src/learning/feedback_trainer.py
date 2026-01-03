"""
Feedback Trainer - Connects thumbs up/down to RL training.

This module bridges the gap between:
1. Feedback capture (.claude/hooks/capture_feedback.sh)
2. RL weight updates (src/agents/rl_agent.py)

Uses contextual bandits for simple, effective learning from binary feedback.
"""

import json
import logging
import math
import random
from datetime import datetime
from glob import glob
from pathlib import Path
from typing import Any

from src.learning.reward_shaper import BinaryRewardShaper

logger = logging.getLogger(__name__)


class FeedbackTrainer:
    """
    Trains RL components from human feedback (thumbs up/down).

    Uses Thompson Sampling contextual bandit for simple, effective learning.
    Research shows this outperforms deep RL for <100 samples.
    """

    def __init__(
        self,
        feedback_dir: str = "data/feedback",
        model_path: str = "models/ml/feedback_model.json",
        min_samples: int = 5,
    ):
        self.feedback_dir = Path(feedback_dir)
        self.model_path = Path(model_path)
        self.min_samples = min_samples
        self.reward_shaper = BinaryRewardShaper()

        # Thompson Sampling parameters (Beta distribution)
        # alpha = successes + 1, beta = failures + 1
        self.alpha = 1.0  # Prior successes
        self.beta = 1.0  # Prior failures

        # Feature weights for decision context
        self.feature_weights: dict[str, float] = {}

        # Load existing model if available
        self._load_model()

    def process_feedback_logs(
        self,
        days_back: int = 7,
    ) -> dict[str, Any]:
        """
        Process feedback logs and update model.

        Args:
            days_back: Number of days of feedback to process

        Returns:
            Training summary with metrics
        """
        feedback_samples = self._load_recent_feedback(days_back)

        if len(feedback_samples) < self.min_samples:
            logger.warning(
                "Only %d feedback samples (need %d). Skipping training.",
                len(feedback_samples),
                self.min_samples,
            )
            return {
                "trained": False,
                "samples": len(feedback_samples),
                "reason": "insufficient_samples",
            }

        # Update Thompson Sampling parameters
        positive_count = sum(1 for s in feedback_samples if s["is_positive"])
        negative_count = len(feedback_samples) - positive_count

        self.alpha += positive_count
        self.beta += negative_count

        # Calculate posterior statistics
        posterior_mean = self.alpha / (self.alpha + self.beta)
        posterior_std = math.sqrt(
            (self.alpha * self.beta)
            / ((self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1))
        )

        # Update feature weights from context
        self._update_feature_weights(feedback_samples)

        # Save updated model
        self._save_model()

        result = {
            "trained": True,
            "samples": len(feedback_samples),
            "positive": positive_count,
            "negative": negative_count,
            "posterior_mean": posterior_mean,
            "posterior_std": posterior_std,
            "confidence_interval": (
                max(0, posterior_mean - 2 * posterior_std),
                min(1, posterior_mean + 2 * posterior_std),
            ),
        }

        logger.info(
            "Feedback training complete: %d samples, %.1f%% positive, posterior=%.3f±%.3f",
            len(feedback_samples),
            100 * positive_count / len(feedback_samples),
            posterior_mean,
            posterior_std,
        )

        return result

    def get_feedback_reward(self, context: dict[str, Any] | None = None) -> float:
        """
        Get predicted reward based on feedback model.

        Uses Thompson Sampling to balance exploration/exploitation.

        Args:
            context: Optional decision context for feature-based prediction

        Returns:
            Reward in range [-1, +1]
        """
        # Sample from posterior Beta distribution using gamma distribution
        # Beta(a,b) = X / (X + Y) where X ~ Gamma(a,1) and Y ~ Gamma(b,1)
        x = random.gammavariate(self.alpha, 1.0)
        y = random.gammavariate(self.beta, 1.0)
        sampled_probability = x / (x + y) if (x + y) > 0 else 0.5

        # Convert to reward [-1, +1]
        base_reward = 2 * sampled_probability - 1

        # Adjust for context features if available
        if context and self.feature_weights:
            context_adjustment = self._compute_context_adjustment(context)
            base_reward = 0.7 * base_reward + 0.3 * context_adjustment

        return float(max(-1, min(1, base_reward)))  # Clip to [-1, +1]

    def record_feedback(
        self,
        is_positive: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Record new feedback and update model immediately.

        Args:
            is_positive: True for thumbs up, False for thumbs down
            context: Optional decision context

        Returns:
            Updated model statistics
        """
        # Update Thompson Sampling parameters
        if is_positive:
            self.alpha += 1
        else:
            self.beta += 1

        # Shape the feedback into training signal
        reward_info = self.reward_shaper.shape_user_feedback(
            thumbs_up=is_positive,
            context=context,
        )

        # Update feature weights from context
        if context:
            self._update_feature_weights_single(context, is_positive)

        # Save immediately
        self._save_model()

        posterior_mean = self.alpha / (self.alpha + self.beta)

        logger.info(
            "Recorded %s feedback. Posterior: %.3f (α=%.1f, β=%.1f)",
            "positive" if is_positive else "negative",
            posterior_mean,
            self.alpha,
            self.beta,
        )

        return {
            "recorded": True,
            "is_positive": is_positive,
            "shaped_reward": reward_info["shaped_reward"],
            "posterior_mean": posterior_mean,
            "alpha": self.alpha,
            "beta": self.beta,
        }

    def get_model_stats(self) -> dict[str, Any]:
        """Get current model statistics."""
        posterior_mean = self.alpha / (self.alpha + self.beta)
        posterior_std = math.sqrt(
            (self.alpha * self.beta)
            / ((self.alpha + self.beta) ** 2 * (self.alpha + self.beta + 1))
        )

        return {
            "alpha": self.alpha,
            "beta": self.beta,
            "total_samples": int(self.alpha + self.beta - 2),  # Subtract priors
            "posterior_mean": posterior_mean,
            "posterior_std": posterior_std,
            "confidence_interval_95": (
                max(0, posterior_mean - 2 * posterior_std),
                min(1, posterior_mean + 2 * posterior_std),
            ),
            "feature_weights": self.feature_weights.copy(),
        }

    def _load_recent_feedback(self, days_back: int) -> list[dict[str, Any]]:
        """Load feedback samples from JSONL files."""
        samples = []

        # Find feedback files
        pattern = str(self.feedback_dir / "feedback_*.jsonl")
        for filepath in glob(pattern):
            try:
                with open(filepath) as f:
                    for line in f:
                        entry = json.loads(line.strip())
                        samples.append(
                            {
                                "timestamp": entry.get("timestamp", ""),
                                "is_positive": entry.get("type") == "positive"
                                or entry.get("score", 0) > 0,
                                "context": entry.get("context", ""),
                            }
                        )
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to read %s: %s", filepath, e)

        return samples

    def _update_feature_weights(self, samples: list[dict[str, Any]]) -> None:
        """Update feature weights based on feedback patterns."""
        # Simple approach: count feature occurrences in positive vs negative
        positive_features: dict[str, int] = {}
        negative_features: dict[str, int] = {}

        for sample in samples:
            context = sample.get("context", "")
            # Extract feature keywords from context
            features = self._extract_features_from_context(context)

            target_dict = positive_features if sample["is_positive"] else negative_features
            for feature in features:
                target_dict[feature] = target_dict.get(feature, 0) + 1

        # Compute weights as log-odds ratio
        all_features = set(positive_features.keys()) | set(negative_features.keys())
        for feature in all_features:
            pos = positive_features.get(feature, 0) + 1  # Laplace smoothing
            neg = negative_features.get(feature, 0) + 1
            self.feature_weights[feature] = math.log(pos / neg)

    def _update_feature_weights_single(self, context: dict[str, Any], is_positive: bool) -> None:
        """Update feature weights from single feedback."""
        features = self._extract_features_from_context(str(context))
        adjustment = 0.1 if is_positive else -0.1

        for feature in features:
            current = self.feature_weights.get(feature, 0.0)
            self.feature_weights[feature] = current + adjustment

    def _extract_features_from_context(self, context: str) -> list[str]:
        """Extract feature keywords from context string."""
        keywords = [
            "ci",
            "test",
            "lint",
            "build",
            "merge",
            "fix",
            "trade",
            "profit",
            "loss",
            "entry",
            "exit",
            "risk",
            "momentum",
            "macd",
            "rsi",
        ]
        context_lower = context.lower()
        return [k for k in keywords if k in context_lower]

    def _compute_context_adjustment(self, context: dict[str, Any]) -> float:
        """Compute reward adjustment based on context features."""
        features = self._extract_features_from_context(str(context))
        if not features:
            return 0.0

        total_weight = sum(self.feature_weights.get(f, 0.0) for f in features)
        return float(math.tanh(total_weight / len(features)))  # Squash to [-1, +1]

    def _save_model(self) -> None:
        """Save model to JSON file."""
        self.model_path.parent.mkdir(parents=True, exist_ok=True)

        model_data = {
            "alpha": self.alpha,
            "beta": self.beta,
            "feature_weights": self.feature_weights,
            "last_updated": datetime.now().isoformat(),
        }

        self.model_path.write_text(json.dumps(model_data, indent=2))
        logger.debug("Saved feedback model to %s", self.model_path)

    def _load_model(self) -> None:
        """Load model from JSON file."""
        if not self.model_path.exists():
            logger.info("No existing feedback model found. Using priors.")
            return

        try:
            model_data = json.loads(self.model_path.read_text())
            self.alpha = model_data.get("alpha", 1.0)
            self.beta = model_data.get("beta", 1.0)
            self.feature_weights = model_data.get("feature_weights", {})
            logger.info(
                "Loaded feedback model: α=%.1f, β=%.1f, %d features",
                self.alpha,
                self.beta,
                len(self.feature_weights),
            )
        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load feedback model: %s", e)

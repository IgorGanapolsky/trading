"""
Microsoft Agent Lightning-style RL Feedback Loop.

Implements reinforcement learning from action sequences and outcomes,
following Microsoft Research patterns for agent learning.

Key features:
- Tracks action sequences and their success/failure outcomes
- Uses Thompson Sampling for exploration/exploitation
- Calculates posterior probabilities for different action types
- Integrates with existing RLHF infrastructure
- Persists feedback state across sessions

Research foundation:
- Thompson Sampling for contextual bandits
- Bayesian updating of success rates
- Action-type specialization

Integration:
- Uses patterns from src/learning/rlhf_storage.py
- Compatible with data/feedback/stats.json
- Works with RAG enforcement system
"""

from __future__ import annotations

import json
import logging
import random
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class FeedbackCategory(Enum):
    """Feedback categories for RL learning."""

    RAG_CONSULTED = "rag_consulted"  # Did agent check RAG?
    ADVICE_FOLLOWED = "advice_followed"  # Did agent follow RAG advice?
    OUTCOME = "outcome"  # Was action successful?
    CEO_FEEDBACK = "ceo_feedback"  # CEO thumbs up/down
    VERIFICATION = "verification"  # Did agent verify before claiming?
    EVIDENCE_PROVIDED = "evidence_provided"  # Did agent show evidence?


class ActionType(Enum):
    """Types of actions the agent can take."""

    RAG_QUERY = "rag_query"  # Querying RAG for lessons
    FOLLOW_RAG_ADVICE = "follow_rag_advice"  # Following RAG recommendations
    VERIFY_CLAIM = "verify_claim"  # Verifying before making claims
    SHOW_EVIDENCE = "show_evidence"  # Providing evidence for claims
    CREATE_PR = "create_pr"  # Creating pull request
    RUN_TESTS = "run_tests"  # Running tests
    COMMIT_CODE = "commit_code"  # Committing changes
    DEPLOY = "deploy"  # Deploying changes
    SKIP_RAG = "skip_rag"  # Skipping RAG consultation
    MAKE_UNVERIFIED_CLAIM = "make_unverified_claim"  # Claiming without verification


@dataclass
class ActionOutcome:
    """Result of an action sequence."""

    action_type: ActionType
    timestamp: str
    success: bool
    feedback_categories: dict[str, bool]  # FeedbackCategory -> passed/failed
    context: dict[str, Any]  # Additional context
    reward: float  # Numerical reward [-1, +1]
    episode_id: str  # Unique episode identifier
    sequence_step: int  # Step in action sequence


@dataclass
class ThompsonSamplingParams:
    """Thompson Sampling parameters for an action type."""

    action_type: ActionType
    alpha: float  # Successes + 1 (prior)
    beta: float  # Failures + 1 (prior)

    @property
    def posterior_mean(self) -> float:
        """Expected success rate."""
        return self.alpha / (self.alpha + self.beta)

    @property
    def posterior_std(self) -> float:
        """Uncertainty in success rate."""
        import math

        n = self.alpha + self.beta
        return math.sqrt((self.alpha * self.beta) / (n * n * (n + 1)))

    def sample_probability(self) -> float:
        """Sample success probability from posterior Beta distribution."""
        # Beta(a,b) = X / (X + Y) where X ~ Gamma(a,1) and Y ~ Gamma(b,1)
        x = random.gammavariate(self.alpha, 1.0)
        y = random.gammavariate(self.beta, 1.0)
        return x / (x + y) if (x + y) > 0 else 0.5

    def update(self, success: bool) -> None:
        """Update parameters based on outcome."""
        if success:
            self.alpha += 1
        else:
            self.beta += 1


class RLFeedbackLoop:
    """
    Microsoft Agent Lightning-style RL Feedback Loop.

    Tracks action sequences, outcomes, and learns which actions lead to success.
    Uses Thompson Sampling to balance exploration vs exploitation.
    """

    def __init__(
        self,
        state_file: str | Path = "data/rl_feedback_state.json",
        stats_file: str | Path = "data/feedback/stats.json",
        alpha_prior: float = 1.0,
        beta_prior: float = 1.0,
    ):
        """
        Initialize RL feedback loop.

        Args:
            state_file: Path to persist Thompson Sampling state
            stats_file: Path to existing feedback stats (for integration)
            alpha_prior: Prior successes (optimistic prior encourages exploration)
            beta_prior: Prior failures
        """
        self.state_file = Path(state_file)
        self.stats_file = Path(stats_file)
        self.alpha_prior = alpha_prior
        self.beta_prior = beta_prior

        # Thompson Sampling parameters for each action type
        self.action_params: dict[ActionType, ThompsonSamplingParams] = {}

        # Action sequence history
        self.episodes: list[list[ActionOutcome]] = []

        # Current episode (active action sequence)
        self.current_episode: list[ActionOutcome] = []
        self.current_episode_id = self._generate_episode_id()

        # Load persisted state
        self._load_state()

        logger.info(
            "RLFeedbackLoop initialized with %d action types tracked",
            len(self.action_params),
        )

    def start_episode(self, episode_id: str | None = None) -> str:
        """
        Start a new action sequence episode.

        Args:
            episode_id: Optional episode ID (auto-generated if not provided)

        Returns:
            Episode ID
        """
        if self.current_episode:
            logger.warning(
                "Starting new episode without finishing previous (episode_id=%s)",
                self.current_episode_id,
            )
            self.end_episode()

        self.current_episode_id = episode_id or self._generate_episode_id()
        self.current_episode = []

        logger.debug("Started episode: %s", self.current_episode_id)
        return self.current_episode_id

    def record_action(
        self,
        action_type: ActionType,
        success: bool,
        feedback_categories: dict[str, bool] | None = None,
        context: dict[str, Any] | None = None,
        reward: float | None = None,
    ) -> ActionOutcome:
        """
        Record an action and its outcome.

        Args:
            action_type: Type of action taken
            success: Whether action succeeded
            feedback_categories: Optional feedback category results
            context: Additional context
            reward: Optional explicit reward (auto-calculated if not provided)

        Returns:
            Recorded ActionOutcome
        """
        # Auto-calculate reward if not provided
        if reward is None:
            reward = self._calculate_reward(success, feedback_categories or {})

        outcome = ActionOutcome(
            action_type=action_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            feedback_categories=feedback_categories or {},
            context=context or {},
            reward=float(reward),
            episode_id=self.current_episode_id,
            sequence_step=len(self.current_episode),
        )

        # Add to current episode
        self.current_episode.append(outcome)

        # Update Thompson Sampling parameters
        self._update_action_params(action_type, success)

        logger.debug(
            "Recorded action: %s (success=%s, reward=%.2f)",
            action_type.value,
            success,
            reward,
        )

        return outcome

    def end_episode(self, success: bool | None = None) -> dict[str, Any]:
        """
        End current episode and calculate statistics.

        Args:
            success: Overall episode success (auto-calculated if not provided)

        Returns:
            Episode statistics
        """
        if not self.current_episode:
            logger.warning("Ending episode with no actions recorded")
            return {"episode_id": self.current_episode_id, "actions": 0}

        # Auto-calculate episode success if not provided
        if success is None:
            success = all(outcome.success for outcome in self.current_episode)

        # Add to episode history
        self.episodes.append(self.current_episode.copy())

        # Calculate statistics
        total_reward = sum(outcome.reward for outcome in self.current_episode)
        avg_reward = total_reward / len(self.current_episode)

        stats = {
            "episode_id": self.current_episode_id,
            "success": success,
            "actions": len(self.current_episode),
            "total_reward": total_reward,
            "avg_reward": avg_reward,
            "action_types": [outcome.action_type.value for outcome in self.current_episode],
        }

        # Persist state
        self._save_state()

        # Integrate with existing feedback stats
        self._update_feedback_stats(success)

        logger.info(
            "Episode ended: %s (success=%s, %d actions, reward=%.2f)",
            self.current_episode_id,
            success,
            len(self.current_episode),
            total_reward,
        )

        # Reset current episode
        self.current_episode = []
        self.current_episode_id = self._generate_episode_id()

        return stats

    def recommend_action(
        self,
        candidate_actions: list[ActionType] | None = None,
    ) -> tuple[ActionType, float]:
        """
        Recommend next action using Thompson Sampling.

        Balances exploration (trying new actions) vs exploitation (using known good actions).

        Args:
            candidate_actions: List of actions to choose from (all if not specified)

        Returns:
            (recommended_action, sampled_probability)
        """
        if candidate_actions is None:
            candidate_actions = list(ActionType)

        # Sample success probabilities for each candidate
        samples: dict[ActionType, float] = {}
        for action_type in candidate_actions:
            params = self._get_or_create_params(action_type)
            samples[action_type] = params.sample_probability()

        # Choose action with highest sampled probability
        best_action = max(samples, key=samples.get)
        best_prob = samples[best_action]

        logger.debug(
            "Recommended action: %s (sampled_prob=%.3f)",
            best_action.value,
            best_prob,
        )

        return best_action, best_prob

    def get_action_stats(self, action_type: ActionType) -> dict[str, Any]:
        """
        Get statistics for a specific action type.

        Args:
            action_type: Action type to query

        Returns:
            Statistics including success rate, confidence interval, samples
        """
        params = self._get_or_create_params(action_type)

        # Count actual outcomes
        outcomes = [
            outcome
            for episode in self.episodes
            for outcome in episode
            if outcome.action_type == action_type
        ]

        successes = sum(1 for o in outcomes if o.success)
        failures = len(outcomes) - successes

        return {
            "action_type": action_type.value,
            "posterior_mean": params.posterior_mean,
            "posterior_std": params.posterior_std,
            "confidence_interval_95": (
                max(0.0, params.posterior_mean - 2 * params.posterior_std),
                min(1.0, params.posterior_mean + 2 * params.posterior_std),
            ),
            "alpha": params.alpha,
            "beta": params.beta,
            "total_samples": len(outcomes),
            "successes": successes,
            "failures": failures,
            "empirical_success_rate": successes / len(outcomes) if outcomes else 0.0,
        }

    def get_all_action_stats(self) -> dict[str, dict[str, Any]]:
        """Get statistics for all tracked action types."""
        return {
            action_type.value: self.get_action_stats(action_type)
            for action_type in self.action_params.keys()
        }

    def analyze_feedback_patterns(self) -> dict[str, Any]:
        """
        Analyze patterns in feedback categories.

        Returns:
            Analysis of which actions lead to positive feedback
        """
        # Track feedback category success by action type
        category_success: dict[str, dict[str, list[bool]]] = {}

        for episode in self.episodes:
            for outcome in episode:
                action = outcome.action_type.value
                if action not in category_success:
                    category_success[action] = {}

                for category, passed in outcome.feedback_categories.items():
                    if category not in category_success[action]:
                        category_success[action][category] = []
                    category_success[action][category].append(passed)

        # Calculate success rates
        analysis: dict[str, dict[str, float]] = {}
        for action, categories in category_success.items():
            analysis[action] = {}
            for category, results in categories.items():
                if results:
                    analysis[action][category] = sum(results) / len(results)

        return {
            "feedback_patterns": analysis,
            "total_episodes": len(self.episodes),
            "total_actions": sum(len(ep) for ep in self.episodes),
        }

    def _get_or_create_params(self, action_type: ActionType) -> ThompsonSamplingParams:
        """Get or create Thompson Sampling parameters for action type."""
        if action_type not in self.action_params:
            self.action_params[action_type] = ThompsonSamplingParams(
                action_type=action_type,
                alpha=self.alpha_prior,
                beta=self.beta_prior,
            )
        return self.action_params[action_type]

    def _update_action_params(self, action_type: ActionType, success: bool) -> None:
        """Update Thompson Sampling parameters based on outcome."""
        params = self._get_or_create_params(action_type)
        params.update(success)

    def _calculate_reward(
        self,
        success: bool,
        feedback_categories: dict[str, bool],
    ) -> float:
        """
        Calculate reward from success and feedback categories.

        Reward structure:
        - Base: +1 for success, -1 for failure
        - Bonus: +0.2 for each positive feedback category
        - Penalty: -0.2 for each negative feedback category
        """
        base_reward = 1.0 if success else -1.0

        # Add feedback category bonuses/penalties
        category_adjustment = 0.0
        for passed in feedback_categories.values():
            category_adjustment += 0.2 if passed else -0.2

        total_reward = base_reward + category_adjustment

        # Clip to [-1, +1]
        return max(-1.0, min(1.0, total_reward))

    def _generate_episode_id(self) -> str:
        """Generate unique episode ID."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
        return f"episode_{timestamp}"

    def _save_state(self) -> None:
        """Persist Thompson Sampling state to file."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)

        state = {
            "version": "1.0.0",
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "action_params": {
                action_type.value: {
                    "alpha": params.alpha,
                    "beta": params.beta,
                }
                for action_type, params in self.action_params.items()
            },
            "episodes_count": len(self.episodes),
            "current_episode_id": self.current_episode_id,
        }

        self.state_file.write_text(json.dumps(state, indent=2))
        logger.debug("Saved RL feedback state to %s", self.state_file)

    def _load_state(self) -> None:
        """Load Thompson Sampling state from file."""
        if not self.state_file.exists():
            logger.info("No existing RL feedback state found. Starting fresh.")
            return

        try:
            state = json.loads(self.state_file.read_text())

            # Restore action parameters
            for action_value, params_dict in state.get("action_params", {}).items():
                try:
                    action_type = ActionType(action_value)
                    self.action_params[action_type] = ThompsonSamplingParams(
                        action_type=action_type,
                        alpha=params_dict["alpha"],
                        beta=params_dict["beta"],
                    )
                except (ValueError, KeyError) as e:
                    logger.warning("Failed to restore action type %s: %s", action_value, e)

            logger.info(
                "Loaded RL feedback state: %d action types, %d episodes",
                len(self.action_params),
                state.get("episodes_count", 0),
            )

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to load RL feedback state: %s. Starting fresh.", e)

    def _update_feedback_stats(self, episode_success: bool) -> None:
        """
        Update data/feedback/stats.json with episode outcome.

        Integrates with existing feedback tracking system.
        """
        if not self.stats_file.exists():
            logger.debug("Feedback stats file not found: %s", self.stats_file)
            return

        try:
            stats = json.loads(self.stats_file.read_text())

            # Update counters
            stats["total"] = stats.get("total", 0) + 1
            if episode_success:
                stats["positive"] = stats.get("positive", 0) + 1
            else:
                stats["negative"] = stats.get("negative", 0) + 1

            # Recalculate satisfaction rate
            total = stats["total"]
            if total > 0:
                stats["satisfaction_rate"] = round(100.0 * stats["positive"] / total, 2)

            stats["last_updated"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

            # Save updated stats
            self.stats_file.write_text(json.dumps(stats, indent=2))
            logger.debug("Updated feedback stats: %s", stats)

        except (json.JSONDecodeError, OSError) as e:
            logger.warning("Failed to update feedback stats: %s", e)


# Singleton instance for easy access
_rl_feedback_loop: RLFeedbackLoop | None = None


def get_rl_feedback_loop() -> RLFeedbackLoop:
    """Get or create singleton RL feedback loop instance."""
    global _rl_feedback_loop
    if _rl_feedback_loop is None:
        _rl_feedback_loop = RLFeedbackLoop()
    return _rl_feedback_loop

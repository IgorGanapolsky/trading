"""
RL Feedback Connector

Connects user feedback (thumbs up/down) to the RL reward signal.
This allows the RL agent to learn from session-level human feedback.

Based on RLHF principles:
- Human preference signals shape the reward function
- Session quality modifies the reward for trades in that session
- Creates a feedback loop: better Claude behavior → more thumbs up → RL learns

Architecture:
1. FeedbackProcessor stores session quality scores
2. RLFeedbackConnector reads and applies to reward shaping
3. RL agent uses shaped reward during training updates
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class RLFeedbackConnector:
    """
    Connects feedback signals to RL reward shaping.

    Usage in RL agent:
        connector = RLFeedbackConnector()
        session_modifier = connector.get_session_reward_modifier()
        shaped_reward = base_reward * session_modifier
    """

    def __init__(
        self,
        signal_file: str = "data/feedback/rl_session_signal.json",
        weight: float = 0.2,  # How much feedback affects reward (0-1)
    ):
        self.signal_file = Path(signal_file)
        self.weight = weight
        self._cached_signal = None
        self._cache_time = None
        self._cache_ttl = 60  # Refresh every 60 seconds

    def get_session_quality(self) -> float:
        """
        Get the current session's quality score from feedback.

        Returns: float in range [-1, 1]
            - Positive: User gave thumbs up (good session)
            - Negative: User gave thumbs down (bad session)
            - Zero: No feedback yet
        """
        # Check cache
        now = datetime.now()
        if (
            self._cached_signal is not None
            and self._cache_time is not None
            and (now - self._cache_time).seconds < self._cache_ttl
        ):
            return self._cached_signal

        # Read signal file
        if not self.signal_file.exists():
            return 0.0

        try:
            data = json.loads(self.signal_file.read_text())
            quality = data.get("quality_score", 0.0)
            self._cached_signal = quality
            self._cache_time = now
            return quality
        except (json.JSONDecodeError, KeyError) as e:
            logger.warning(f"Failed to read RL session signal: {e}")
            return 0.0

    def get_session_reward_modifier(self) -> float:
        """
        Get reward modifier based on session feedback.

        Returns: float multiplier for reward shaping
            - 1.0: Neutral (no feedback effect)
            - > 1.0: Positive feedback (boost rewards)
            - < 1.0: Negative feedback (dampen rewards)

        The weight parameter controls sensitivity:
            modifier = 1.0 + (quality * weight)

        With default weight=0.2:
            - Positive session (+1.0): modifier = 1.2 (20% boost)
            - Negative session (-1.0): modifier = 0.8 (20% reduction)
        """
        quality = self.get_session_quality()
        modifier = 1.0 + (quality * self.weight)

        # Clamp to reasonable range
        return max(0.5, min(1.5, modifier))

    def shape_reward(
        self,
        base_reward: float,
        session_id: Optional[str] = None,
    ) -> float:
        """
        Apply feedback-based reward shaping.

        Args:
            base_reward: The original reward from trade outcome
            session_id: Optional session ID (not used yet, for future multi-session)

        Returns:
            Shaped reward incorporating human feedback
        """
        modifier = self.get_session_reward_modifier()
        shaped = base_reward * modifier

        logger.debug(
            f"Reward shaping: base={base_reward:.4f}, modifier={modifier:.4f}, shaped={shaped:.4f}"
        )

        return shaped

    def record_trade_feedback_association(
        self,
        trade_id: str,
        session_id: str,
        feedback_type: Optional[str] = None,
    ):
        """
        Record which trades were in sessions with specific feedback.
        Allows for retrospective reward updates.
        """
        assoc_file = Path("data/feedback/trade_feedback_assoc.jsonl")
        assoc_file.parent.mkdir(parents=True, exist_ok=True)

        entry = {
            "timestamp": datetime.now().isoformat(),
            "trade_id": trade_id,
            "session_id": session_id,
            "feedback_type": feedback_type,
            "session_quality": self.get_session_quality(),
        }

        with open(assoc_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def get_stats(self) -> dict:
        """Get feedback connector statistics."""
        quality = self.get_session_quality()
        modifier = self.get_session_reward_modifier()

        return {
            "current_session_quality": quality,
            "reward_modifier": modifier,
            "weight": self.weight,
            "signal_file_exists": self.signal_file.exists(),
        }


# Singleton for easy access from RL agent
_connector_instance: Optional[RLFeedbackConnector] = None


def get_rl_feedback_connector() -> RLFeedbackConnector:
    """Get or create the global RL feedback connector."""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = RLFeedbackConnector()
    return _connector_instance


def shape_reward_with_feedback(base_reward: float) -> float:
    """Convenience function for reward shaping."""
    return get_rl_feedback_connector().shape_reward(base_reward)

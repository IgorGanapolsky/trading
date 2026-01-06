#!/usr/bin/env python3
"""
ReasonRAG-style Process-Level Rewards System.

Based on arxiv.org/html/2505.14069v1 - Shortest Path Reward Estimation (SPRE)
Provides fine-grained rewards for query generation, evidence extraction, and answer generation.

The key insight from ReasonRAG: Rather than only rewarding/penalizing final outcomes,
we provide feedback at EACH STEP of the reasoning process. This enables the system
to learn which intermediate steps lead to better outcomes.

Three Core Actions (from paper):
1. Query Generation - Did the query find relevant lessons?
2. Evidence Extraction - Were the right parts extracted?
3. Answer Generation - Was the answer correct?

Reward Scoring System:
  +1.0 = Consulting RAG before action
  +0.5 = Following RAG advice
  -0.5 = Ignoring RAG advice
  -1.0 = Action failure after ignoring RAG

Created: Jan 6, 2026
"""

import json
import logging
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path("data")
PROCESS_REWARDS_FILE = DATA_DIR / "process_rewards.json"


class ActionStage(Enum):
    """Three stages from ReasonRAG paper."""

    QUERY_GENERATION = "query_generation"  # Did query find relevant lessons?
    EVIDENCE_EXTRACTION = "evidence_extraction"  # Were right parts extracted?
    ANSWER_GENERATION = "answer_generation"  # Was answer/action correct?


class RewardScore(Enum):
    """Reward values based on process quality."""

    CONSULTED_RAG = 1.0  # +1.0 for consulting RAG before action
    FOLLOWED_ADVICE = 0.5  # +0.5 for following RAG advice
    IGNORED_ADVICE = -0.5  # -0.5 for ignoring RAG advice
    FAILURE_AFTER_IGNORE = -1.0  # -1.0 for action failure after ignoring RAG


@dataclass
class ProcessReward:
    """A single process reward event."""

    timestamp: str
    action_type: str
    stage: str  # ActionStage value
    reward: float  # RewardScore value
    query_quality: Optional[float] = None  # 0-1: relevance of query results
    evidence_quality: Optional[float] = None  # 0-1: usefulness of extracted evidence
    outcome_quality: Optional[float] = None  # 0-1: correctness of final action
    notes: Optional[str] = None
    context: Optional[dict] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class ProcessRewardTracker:
    """
    Tracks process-level rewards for RAG interactions.

    Implements SPRE (Shortest Path Reward Estimation) concept:
    - Rewards intermediate steps, not just outcomes
    - Tracks quality at each stage
    - Learns from cumulative patterns
    """

    def __init__(self):
        self.rewards: list[ProcessReward] = []
        self.cumulative_scores: dict[str, float] = defaultdict(float)
        self.stage_scores: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
        self._load_rewards()

    def _load_rewards(self):
        """Load existing rewards from disk."""
        if PROCESS_REWARDS_FILE.exists():
            try:
                with open(PROCESS_REWARDS_FILE) as f:
                    data = json.load(f)

                # Reconstruct rewards
                for r in data.get("rewards", []):
                    reward = ProcessReward(
                        timestamp=r["timestamp"],
                        action_type=r["action_type"],
                        stage=r["stage"],
                        reward=r["reward"],
                        query_quality=r.get("query_quality"),
                        evidence_quality=r.get("evidence_quality"),
                        outcome_quality=r.get("outcome_quality"),
                        notes=r.get("notes"),
                        context=r.get("context"),
                    )
                    self.rewards.append(reward)

                # Reconstruct cumulative scores
                self.cumulative_scores = defaultdict(float, data.get("cumulative_scores", {}))
                self.stage_scores = defaultdict(
                    lambda: defaultdict(float),
                    {k: defaultdict(float, v) for k, v in data.get("stage_scores", {}).items()},
                )

                logger.info(f"Loaded {len(self.rewards)} process rewards from disk")
            except (OSError, json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to load process rewards: {e}")
                self._init_empty()
        else:
            self._init_empty()

    def _init_empty(self):
        """Initialize empty reward tracking."""
        self.rewards = []
        self.cumulative_scores = defaultdict(float)
        self.stage_scores = defaultdict(lambda: defaultdict(float))

    def _save_rewards(self):
        """Persist rewards to disk."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        data = {
            "last_updated": datetime.now(timezone.utc).isoformat(),
            "total_rewards": len(self.rewards),
            "rewards": [r.to_dict() for r in self.rewards[-1000:]],  # Keep last 1000
            "cumulative_scores": dict(self.cumulative_scores),
            "stage_scores": {k: dict(v) for k, v in self.stage_scores.items()},
        }

        with open(PROCESS_REWARDS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def record_query_generation(
        self,
        action_type: str,
        lessons_found: int,
        query_relevance: float,  # 0-1 score
        context: Optional[dict] = None,
    ) -> float:
        """
        Record reward for query generation stage.

        Args:
            action_type: Type of action being performed
            lessons_found: Number of lessons retrieved
            query_relevance: How relevant were the results (0-1)
            context: Additional context

        Returns:
            Reward score
        """
        # Base reward for consulting RAG
        reward = RewardScore.CONSULTED_RAG.value

        # Bonus based on query quality
        # High relevance (>0.7) = full reward
        # Medium relevance (0.4-0.7) = partial reward
        # Low relevance (<0.4) = reduced reward
        if query_relevance > 0.7:
            reward += 0.2  # Bonus for excellent query
        elif query_relevance < 0.4:
            reward -= 0.2  # Penalty for poor query

        process_reward = ProcessReward(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type=action_type,
            stage=ActionStage.QUERY_GENERATION.value,
            reward=reward,
            query_quality=query_relevance,
            notes=f"Found {lessons_found} lessons with {query_relevance:.2f} relevance",
            context=context,
        )

        self._record_reward(process_reward)
        return reward

    def record_evidence_extraction(
        self,
        action_type: str,
        evidence_used: bool,
        evidence_quality: float,  # 0-1 score
        context: Optional[dict] = None,
    ) -> float:
        """
        Record reward for evidence extraction stage.

        Args:
            action_type: Type of action being performed
            evidence_used: Whether evidence was actually used
            evidence_quality: How useful was the evidence (0-1)
            context: Additional context

        Returns:
            Reward score
        """
        if not evidence_used:
            reward = 0.0  # Neutral - no evidence extracted
        else:
            # Reward based on evidence quality
            reward = evidence_quality * 0.5  # Scale to 0-0.5 range

        process_reward = ProcessReward(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type=action_type,
            stage=ActionStage.EVIDENCE_EXTRACTION.value,
            reward=reward,
            evidence_quality=evidence_quality,
            notes=f"Evidence {'used' if evidence_used else 'not used'}, quality={evidence_quality:.2f}",
            context=context,
        )

        self._record_reward(process_reward)
        return reward

    def record_answer_generation(
        self,
        action_type: str,
        followed_advice: bool,
        outcome: str,  # "success", "failure", "partial"
        outcome_quality: float = None,  # 0-1 score, calculated if None
        context: Optional[dict] = None,
    ) -> float:
        """
        Record reward for answer/action generation stage.

        Args:
            action_type: Type of action being performed
            followed_advice: Whether RAG advice was followed
            outcome: Outcome of the action
            outcome_quality: Quality score (0-1), auto-calculated if None
            context: Additional context

        Returns:
            Reward score
        """
        # Auto-calculate outcome quality if not provided
        if outcome_quality is None:
            if outcome == "success":
                outcome_quality = 1.0
            elif outcome == "partial":
                outcome_quality = 0.5
            else:  # failure
                outcome_quality = 0.0

        # Assign reward based on adherence and outcome
        if followed_advice:
            if outcome == "success":
                reward = RewardScore.FOLLOWED_ADVICE.value
            elif outcome == "partial":
                reward = RewardScore.FOLLOWED_ADVICE.value * 0.5  # +0.25
            else:  # failure
                reward = 0.0  # Followed advice but failed - neutral
        else:  # Ignored advice
            if outcome == "success":
                reward = RewardScore.IGNORED_ADVICE.value * 0.5  # -0.25 (got lucky)
            else:  # failure or partial
                reward = RewardScore.FAILURE_AFTER_IGNORE.value  # -1.0 (worst case)

        process_reward = ProcessReward(
            timestamp=datetime.now(timezone.utc).isoformat(),
            action_type=action_type,
            stage=ActionStage.ANSWER_GENERATION.value,
            reward=reward,
            outcome_quality=outcome_quality,
            notes=f"{'Followed' if followed_advice else 'Ignored'} advice, {outcome} outcome",
            context=context,
        )

        self._record_reward(process_reward)
        return reward

    def _record_reward(self, reward: ProcessReward):
        """Internal: Record a reward and update cumulative scores."""
        self.rewards.append(reward)

        # Update cumulative score for this action type
        self.cumulative_scores[reward.action_type] += reward.reward

        # Update stage-specific scores
        self.stage_scores[reward.action_type][reward.stage] += reward.reward

        # Persist to disk
        self._save_rewards()

        logger.debug(
            f"Process reward: {reward.action_type} [{reward.stage}] = {reward.reward:+.2f}"
        )

    def get_cumulative_score(self, action_type: Optional[str] = None) -> float:
        """
        Get cumulative score for an action type or overall.

        Args:
            action_type: Specific action type, or None for total

        Returns:
            Cumulative reward score
        """
        if action_type:
            return self.cumulative_scores.get(action_type, 0.0)
        else:
            return sum(self.cumulative_scores.values())

    def get_stage_scores(self, action_type: str) -> dict[str, float]:
        """
        Get scores broken down by stage for an action type.

        Args:
            action_type: Type of action

        Returns:
            Dict mapping stage name to cumulative score
        """
        return dict(self.stage_scores.get(action_type, {}))

    def get_action_summary(self, action_type: str) -> dict[str, Any]:
        """
        Get comprehensive summary for an action type.

        Args:
            action_type: Type of action

        Returns:
            Summary including total score, stage breakdown, quality metrics
        """
        action_rewards = [r for r in self.rewards if r.action_type == action_type]

        if not action_rewards:
            return {
                "action_type": action_type,
                "total_score": 0.0,
                "total_events": 0,
                "stage_scores": {},
                "avg_query_quality": None,
                "avg_evidence_quality": None,
                "avg_outcome_quality": None,
            }

        # Calculate averages
        query_qualities = [r.query_quality for r in action_rewards if r.query_quality]
        evidence_qualities = [r.evidence_quality for r in action_rewards if r.evidence_quality]
        outcome_qualities = [r.outcome_quality for r in action_rewards if r.outcome_quality]

        return {
            "action_type": action_type,
            "total_score": self.cumulative_scores.get(action_type, 0.0),
            "total_events": len(action_rewards),
            "stage_scores": dict(self.stage_scores.get(action_type, {})),
            "avg_query_quality": (
                sum(query_qualities) / len(query_qualities) if query_qualities else None
            ),
            "avg_evidence_quality": (
                sum(evidence_qualities) / len(evidence_qualities) if evidence_qualities else None
            ),
            "avg_outcome_quality": (
                sum(outcome_qualities) / len(outcome_qualities) if outcome_qualities else None
            ),
        }

    def get_overall_stats(self) -> dict[str, Any]:
        """
        Get overall statistics across all actions.

        Returns:
            Comprehensive statistics
        """
        if not self.rewards:
            return {
                "total_rewards": 0,
                "total_score": 0.0,
                "action_types": 0,
                "avg_reward": 0.0,
                "positive_rewards": 0,
                "negative_rewards": 0,
            }

        total_score = sum(r.reward for r in self.rewards)
        positive_rewards = sum(1 for r in self.rewards if r.reward > 0)
        negative_rewards = sum(1 for r in self.rewards if r.reward < 0)

        return {
            "total_rewards": len(self.rewards),
            "total_score": total_score,
            "action_types": len(self.cumulative_scores),
            "avg_reward": total_score / len(self.rewards) if self.rewards else 0.0,
            "positive_rewards": positive_rewards,
            "negative_rewards": negative_rewards,
            "neutral_rewards": len(self.rewards) - positive_rewards - negative_rewards,
        }

    def get_recent_rewards(self, limit: int = 20) -> list[dict[str, Any]]:
        """
        Get recent reward events.

        Args:
            limit: Number of recent events to return

        Returns:
            List of reward dictionaries
        """
        return [r.to_dict() for r in self.rewards[-limit:]]

    def clear_rewards(self, action_type: Optional[str] = None):
        """
        Clear rewards (for testing or reset).

        Args:
            action_type: Specific action to clear, or None for all
        """
        if action_type:
            self.rewards = [r for r in self.rewards if r.action_type != action_type]
            if action_type in self.cumulative_scores:
                del self.cumulative_scores[action_type]
            if action_type in self.stage_scores:
                del self.stage_scores[action_type]
        else:
            self.rewards = []
            self.cumulative_scores = defaultdict(float)
            self.stage_scores = defaultdict(lambda: defaultdict(float))

        self._save_rewards()


# Singleton instance
_tracker: Optional[ProcessRewardTracker] = None


def get_tracker() -> ProcessRewardTracker:
    """Get singleton process reward tracker instance."""
    global _tracker
    if _tracker is None:
        _tracker = ProcessRewardTracker()
    return _tracker


# Convenience functions for integration


def record_query_reward(
    action_type: str,
    lessons_found: int,
    query_relevance: float,
    context: Optional[dict] = None,
) -> float:
    """Convenience function to record query generation reward."""
    return get_tracker().record_query_generation(
        action_type, lessons_found, query_relevance, context
    )


def record_evidence_reward(
    action_type: str,
    evidence_used: bool,
    evidence_quality: float,
    context: Optional[dict] = None,
) -> float:
    """Convenience function to record evidence extraction reward."""
    return get_tracker().record_evidence_extraction(
        action_type, evidence_used, evidence_quality, context
    )


def record_outcome_reward(
    action_type: str,
    followed_advice: bool,
    outcome: str,
    outcome_quality: Optional[float] = None,
    context: Optional[dict] = None,
) -> float:
    """Convenience function to record answer generation reward."""
    return get_tracker().record_answer_generation(
        action_type, followed_advice, outcome, outcome_quality, context
    )


# ============================================================
# USAGE EXAMPLE - Integration with RAG Enforcer
# ============================================================
#
# from src.rag.enforcer import query_before_action, record_outcome
# from src.rag.process_rewards import (
#     record_query_reward,
#     record_evidence_reward,
#     record_outcome_reward,
# )
#
# # 1. QUERY STAGE
# result = query_before_action("EXECUTE_TRADE", "Buy AAPL 100 shares")
# query_relevance = len(result["lessons"]) / 5.0  # Normalize to 0-1
# record_query_reward("EXECUTE_TRADE", len(result["lessons"]), query_relevance)
#
# # 2. EVIDENCE STAGE
# if result["lessons"]:
#     evidence_quality = 1.0 if not result["blocking"] else 0.5
#     record_evidence_reward("EXECUTE_TRADE", True, evidence_quality)
#
# # 3. ANSWER/ACTION STAGE
# followed = result["recommendation"] == "PROCEED"
# # ... execute trade ...
# record_outcome("EXECUTE_TRADE", followed, "success")
# record_outcome_reward("EXECUTE_TRADE", followed, "success")
#

"""
Ensemble Voting System for Trading Signals

Combines signals from multiple models (Momentum, RL, Sentiment) via voting mechanisms.
Supports simple majority, weighted voting, and unanimous requirements.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class SignalType(Enum):
    """Types of trading signals."""

    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


@dataclass
class ModelVote:
    """Individual model's vote."""

    model_name: str
    signal: SignalType
    confidence: float  # 0.0-1.0
    raw_signal: dict[str, Any]  # Original signal data


@dataclass
class EnsembleDecision:
    """Final ensemble decision."""

    action: str  # "buy", "hold", "sell"
    consensus_score: float  # 0.0-1.0 (how much agreement)
    votes: dict[str, int]  # {"for": 2, "against": 1, "abstain": 0}
    weighted_confidence: float  # 0.0-1.0
    individual_votes: dict[str, ModelVote]  # Model name -> vote
    unanimous: bool  # True if all models agree
    metadata: dict[str, Any]  # Additional info


class EnsembleVoter:
    """
    Combines signals from multiple models via voting.

    Supports three voting modes:
    1. Simple majority: Most votes win (default)
    2. Weighted voting: Votes weighted by model confidence and weights
    3. Unanimous: All models must agree

    Example:
        >>> voter = EnsembleVoter(voting_threshold=0.6, weights={"momentum": 0.4, "rl": 0.3, "sentiment": 0.3})
        >>> signals = {
        ...     "momentum": {"signal": "buy", "confidence": 0.8},
        ...     "rl": {"signal": "long", "confidence": 0.7},
        ...     "sentiment": {"signal": "bullish", "score": 0.5}
        ... }
        >>> decision = voter.vote(signals)
        >>> print(decision.action)  # "buy"
    """

    # Signal normalization mapping
    SIGNAL_MAP = {
        # Momentum signals
        "buy": SignalType.BUY,
        "hold": SignalType.HOLD,
        "sell": SignalType.SELL,
        # RL signals
        "long": SignalType.BUY,
        "neutral": SignalType.HOLD,
        "flat": SignalType.HOLD,
        "short": SignalType.SELL,
        # Sentiment signals (based on polarity)
        "bullish": SignalType.BUY,
        "neutral_sentiment": SignalType.HOLD,
        "bearish": SignalType.SELL,
    }

    def __init__(
        self,
        voting_threshold: float = 0.6,
        weights: dict[str, float] | None = None,
        confidence_floor: float = 0.4,
    ):
        """
        Initialize the ensemble voter.

        Args:
            voting_threshold: Fraction of votes needed (0.5 = majority, 0.67 = supermajority)
            weights: Optional weights per model {"momentum": 0.4, "rl": 0.3, "sentiment": 0.3}
                    If None, uses equal weights
            confidence_floor: Minimum confidence to count a vote (filters low-confidence signals)
        """
        self.voting_threshold = voting_threshold
        self.confidence_floor = confidence_floor

        # Set default equal weights if not provided
        if weights is None:
            self.weights = {"momentum": 1.0 / 3, "rl": 1.0 / 3, "sentiment": 1.0 / 3}
        else:
            # Normalize weights to sum to 1.0
            total_weight = sum(weights.values())
            self.weights = {k: v / total_weight for k, v in weights.items()}

        logger.info(
            "EnsembleVoter initialized: threshold=%.2f, weights=%s, confidence_floor=%.2f",
            self.voting_threshold,
            self.weights,
            self.confidence_floor,
        )

    def vote(self, signals: dict[str, dict[str, Any]]) -> EnsembleDecision:
        """
        Combine signals from multiple models via simple majority voting.

        Args:
            signals: Dictionary mapping model names to signal dicts:
                {
                    "momentum": {"signal": "buy"|"hold"|"sell", "confidence": 0.0-1.0},
                    "rl": {"signal": "long"|"flat"|"short", "confidence": 0.0-1.0},
                    "sentiment": {"signal": "bullish"|"neutral"|"bearish", "score": -1.0 to 1.0}
                }

        Returns:
            EnsembleDecision with final action and metadata
        """
        # Parse and normalize signals
        votes = self._parse_signals(signals)

        if not votes:
            logger.warning("No valid votes after parsing signals")
            return self._create_hold_decision("No valid votes", signals)

        # Count votes
        vote_counts = {"buy": 0, "hold": 0, "sell": 0}
        for vote in votes.values():
            if vote.confidence >= self.confidence_floor:
                vote_counts[vote.signal.value] += 1

        # Determine winner
        total_votes = sum(vote_counts.values())
        if total_votes == 0:
            logger.warning("All votes below confidence floor")
            return self._create_hold_decision("All votes below confidence floor", signals)

        max_votes = max(vote_counts.values())
        winning_action = max(vote_counts, key=vote_counts.get)

        # Check if threshold met
        vote_fraction = max_votes / total_votes
        threshold_met = vote_fraction >= self.voting_threshold

        if not threshold_met:
            logger.info(
                "Voting threshold not met (%.2f < %.2f), defaulting to HOLD",
                vote_fraction,
                self.voting_threshold,
            )
            winning_action = "hold"

        # Calculate consensus score (how much agreement)
        consensus_score = vote_fraction

        # Calculate weighted confidence
        weighted_conf = self._calculate_weighted_confidence(votes, winning_action)

        # Check if unanimous
        unanimous = len(set(v.signal for v in votes.values())) == 1

        # Build vote summary
        votes_summary = {
            "for": vote_counts[winning_action],
            "against": sum(v for k, v in vote_counts.items() if k != winning_action),
            "abstain": len(signals) - total_votes,  # Votes filtered by confidence floor
        }

        logger.info(
            "Ensemble vote: action=%s, consensus=%.2f, weighted_conf=%.2f, votes=%s",
            winning_action,
            consensus_score,
            weighted_conf,
            vote_counts,
        )

        return EnsembleDecision(
            action=winning_action,
            consensus_score=consensus_score,
            votes=votes_summary,
            weighted_confidence=weighted_conf,
            individual_votes=votes,
            unanimous=unanimous,
            metadata={
                "vote_counts": vote_counts,
                "total_votes": total_votes,
                "threshold_met": threshold_met,
                "voting_threshold": self.voting_threshold,
            },
        )

    def weighted_vote(self, signals: dict[str, dict[str, Any]]) -> EnsembleDecision:
        """
        Combine signals using weighted voting.

        Each model's vote is weighted by:
        1. Model weight (from self.weights)
        2. Signal confidence

        Args:
            signals: Dictionary mapping model names to signal dicts

        Returns:
            EnsembleDecision with final action
        """
        votes = self._parse_signals(signals)

        if not votes:
            logger.warning("No valid votes after parsing signals")
            return self._create_hold_decision("No valid votes", signals)

        # Accumulate weighted scores for each action
        action_scores = {"buy": 0.0, "hold": 0.0, "sell": 0.0}
        total_weight = 0.0
        votes_used = 0

        for model_name, vote in votes.items():
            if vote.confidence < self.confidence_floor:
                logger.debug(
                    "Skipping %s vote (confidence %.2f < floor)", model_name, vote.confidence
                )
                continue

            # Get model weight (default to equal weight if not specified)
            model_weight = self.weights.get(model_name, 1.0 / len(votes))

            # Weighted score = model_weight * confidence
            weighted_score = model_weight * vote.confidence
            action_scores[vote.signal.value] += weighted_score
            total_weight += model_weight
            votes_used += 1

        if total_weight == 0:
            logger.warning("All votes below confidence floor")
            return self._create_hold_decision("All votes below confidence floor", signals)

        # Normalize scores
        normalized_scores = {k: v / total_weight for k, v in action_scores.items()}

        # Winner is highest score
        winning_action = max(normalized_scores, key=normalized_scores.get)
        winning_score = normalized_scores[winning_action]

        # Consensus = how much winning action dominates
        consensus_score = winning_score / max(sum(normalized_scores.values()), 1e-6)

        # Check threshold
        threshold_met = winning_score >= self.voting_threshold

        if not threshold_met:
            logger.info(
                "Weighted voting threshold not met (%.2f < %.2f), defaulting to HOLD",
                winning_score,
                self.voting_threshold,
            )
            winning_action = "hold"

        # Weighted confidence is the winning action's score
        weighted_conf = winning_score

        # Check unanimity
        unanimous = len(set(v.signal for v in votes.values())) == 1

        votes_summary = {
            "for": sum(
                1
                for v in votes.values()
                if v.signal.value == winning_action and v.confidence >= self.confidence_floor
            ),
            "against": sum(
                1
                for v in votes.values()
                if v.signal.value != winning_action and v.confidence >= self.confidence_floor
            ),
            "abstain": len(signals) - votes_used,
        }

        logger.info(
            "Weighted ensemble vote: action=%s, consensus=%.2f, weighted_conf=%.2f, scores=%s",
            winning_action,
            consensus_score,
            weighted_conf,
            normalized_scores,
        )

        return EnsembleDecision(
            action=winning_action,
            consensus_score=consensus_score,
            votes=votes_summary,
            weighted_confidence=weighted_conf,
            individual_votes=votes,
            unanimous=unanimous,
            metadata={
                "action_scores": normalized_scores,
                "total_weight": total_weight,
                "threshold_met": threshold_met,
                "voting_threshold": self.voting_threshold,
                "mode": "weighted",
            },
        )

    def unanimous_required(self, signals: dict[str, dict[str, Any]]) -> EnsembleDecision:
        """
        Require unanimous agreement from all models.

        If models disagree, returns HOLD with low confidence.

        Args:
            signals: Dictionary mapping model names to signal dicts

        Returns:
            EnsembleDecision with unanimous=True only if all agree
        """
        votes = self._parse_signals(signals)

        if not votes:
            logger.warning("No valid votes after parsing signals")
            return self._create_hold_decision("No valid votes", signals)

        # Filter by confidence floor
        valid_votes = {
            name: vote for name, vote in votes.items() if vote.confidence >= self.confidence_floor
        }

        if not valid_votes:
            logger.warning("All votes below confidence floor")
            return self._create_hold_decision("All votes below confidence floor", signals)

        # Check unanimity
        unique_signals = set(v.signal for v in valid_votes.values())

        if len(unique_signals) == 1:
            # Unanimous!
            unanimous_signal = list(valid_votes.values())[0].signal
            winning_action = unanimous_signal.value

            # Weighted confidence is average of all confidences
            weighted_conf = sum(v.confidence for v in valid_votes.values()) / len(valid_votes)

            logger.info(
                "Unanimous agreement: action=%s, confidence=%.2f, votes=%d",
                winning_action,
                weighted_conf,
                len(valid_votes),
            )

            return EnsembleDecision(
                action=winning_action,
                consensus_score=1.0,  # Perfect consensus
                votes={
                    "for": len(valid_votes),
                    "against": 0,
                    "abstain": len(signals) - len(valid_votes),
                },
                weighted_confidence=weighted_conf,
                individual_votes=votes,
                unanimous=True,
                metadata={
                    "mode": "unanimous",
                    "required_votes": len(valid_votes),
                    "agreement": "full",
                },
            )
        else:
            # Disagreement - default to HOLD
            logger.info(
                "Unanimous requirement not met: %d different signals, defaulting to HOLD",
                len(unique_signals),
            )

            return EnsembleDecision(
                action="hold",
                consensus_score=0.0,  # No consensus
                votes={
                    "for": 0,
                    "against": len(valid_votes),
                    "abstain": len(signals) - len(valid_votes),
                },
                weighted_confidence=0.0,
                individual_votes=votes,
                unanimous=False,
                metadata={
                    "mode": "unanimous",
                    "disagreement": list(unique_signals),
                    "agreement": "none",
                },
            )

    def _parse_signals(self, signals: dict[str, dict[str, Any]]) -> dict[str, ModelVote]:
        """
        Parse and normalize signals from different models.

        Handles different signal formats:
        - Momentum: {"signal": "buy", "confidence": 0.8}
        - RL: {"signal": "long", "confidence": 0.7}
        - Sentiment: {"signal": "bullish", "score": 0.5} or {"score": 0.5}

        Returns:
            Dictionary mapping model names to ModelVote objects
        """
        votes = {}

        for model_name, signal_data in signals.items():
            try:
                # Extract signal and confidence
                if "signal" in signal_data:
                    signal_str = str(signal_data["signal"]).lower()
                elif "score" in signal_data:
                    # Sentiment without explicit signal - infer from score
                    score = float(signal_data["score"])
                    if score > 0.2:
                        signal_str = "bullish"
                    elif score < -0.2:
                        signal_str = "bearish"
                    else:
                        signal_str = "neutral_sentiment"
                else:
                    logger.warning("Model %s missing 'signal' or 'score', skipping", model_name)
                    continue

                # Normalize signal
                signal_type = self.SIGNAL_MAP.get(signal_str)
                if signal_type is None:
                    logger.warning("Unknown signal '%s' from %s, skipping", signal_str, model_name)
                    continue

                # Extract confidence (handle different field names)
                if "confidence" in signal_data:
                    confidence = float(signal_data["confidence"])
                elif "score" in signal_data:
                    # Sentiment score: map -1.0 to 1.0 -> 0.0 to 1.0
                    score = float(signal_data["score"])
                    confidence = abs(score)  # Confidence = strength of opinion
                else:
                    logger.warning(
                        "Model %s missing confidence/score, defaulting to 0.5", model_name
                    )
                    confidence = 0.5

                # Clamp confidence to [0, 1]
                confidence = max(0.0, min(1.0, confidence))

                votes[model_name] = ModelVote(
                    model_name=model_name,
                    signal=signal_type,
                    confidence=confidence,
                    raw_signal=signal_data,
                )

            except Exception as e:
                logger.warning("Error parsing signal from %s: %s", model_name, e)
                continue

        return votes

    def _calculate_weighted_confidence(
        self, votes: dict[str, ModelVote], winning_action: str
    ) -> float:
        """
        Calculate weighted confidence for the winning action.

        Averages confidence of all models that voted for the winning action,
        weighted by model weights.
        """
        total_weight = 0.0
        weighted_sum = 0.0

        for model_name, vote in votes.items():
            if vote.signal.value == winning_action:
                model_weight = self.weights.get(model_name, 1.0 / len(votes))
                weighted_sum += vote.confidence * model_weight
                total_weight += model_weight

        if total_weight == 0:
            return 0.0

        return weighted_sum / total_weight

    def _create_hold_decision(
        self, reason: str, signals: dict[str, dict[str, Any]]
    ) -> EnsembleDecision:
        """Create a default HOLD decision when voting fails."""
        return EnsembleDecision(
            action="hold",
            consensus_score=0.0,
            votes={"for": 0, "against": 0, "abstain": len(signals)},
            weighted_confidence=0.0,
            individual_votes={},
            unanimous=False,
            metadata={"reason": reason, "fallback": True},
        )


# Convenience functions for common use cases


def simple_majority_vote(
    signals: dict[str, dict[str, Any]], threshold: float = 0.5
) -> EnsembleDecision:
    """
    Simple majority voting with configurable threshold.

    Args:
        signals: Model signals dictionary
        threshold: Vote fraction required (default 0.5 = simple majority)

    Returns:
        EnsembleDecision
    """
    voter = EnsembleVoter(voting_threshold=threshold)
    return voter.vote(signals)


def weighted_vote(
    signals: dict[str, dict[str, Any]],
    weights: dict[str, float] | None = None,
    threshold: float = 0.5,
) -> EnsembleDecision:
    """
    Weighted voting with optional model weights.

    Args:
        signals: Model signals dictionary
        weights: Optional model weights (defaults to equal)
        threshold: Vote fraction required

    Returns:
        EnsembleDecision
    """
    voter = EnsembleVoter(voting_threshold=threshold, weights=weights)
    return voter.weighted_vote(signals)


def unanimous_vote(signals: dict[str, dict[str, Any]]) -> EnsembleDecision:
    """
    Require unanimous agreement.

    Args:
        signals: Model signals dictionary

    Returns:
        EnsembleDecision (action='hold' if disagreement)
    """
    voter = EnsembleVoter()
    return voter.unanimous_required(signals)

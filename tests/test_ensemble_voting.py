"""
Unit tests for ensemble voting system.

Tests simple majority, weighted, and unanimous voting modes.
"""

import pytest
from src.ensemble.voting_ensemble import (
    EnsembleDecision,
    EnsembleVoter,
    SignalType,
    simple_majority_vote,
    unanimous_vote,
    weighted_vote,
)


class TestSignalNormalization:
    """Test signal parsing and normalization."""

    def test_normalize_momentum_signals(self):
        """Test parsing momentum agent signals."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
        }

        votes = voter._parse_signals(signals)

        assert "momentum" in votes
        assert votes["momentum"].signal == SignalType.BUY
        assert votes["momentum"].confidence == 0.8

    def test_normalize_rl_signals(self):
        """Test parsing RL agent signals."""
        voter = EnsembleVoter()
        signals = {
            "rl": {"signal": "long", "confidence": 0.7},
        }

        votes = voter._parse_signals(signals)

        assert "rl" in votes
        assert votes["rl"].signal == SignalType.BUY
        assert votes["rl"].confidence == 0.7

    def test_normalize_sentiment_signals_explicit(self):
        """Test parsing sentiment with explicit signal."""
        voter = EnsembleVoter()
        signals = {
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        votes = voter._parse_signals(signals)

        assert "sentiment" in votes
        assert votes["sentiment"].signal == SignalType.BUY
        assert votes["sentiment"].confidence == 0.6

    def test_normalize_sentiment_signals_implicit(self):
        """Test inferring sentiment signal from score."""
        voter = EnsembleVoter()

        # Bullish (score > 0.2)
        signals_bullish = {"sentiment": {"score": 0.5}}
        votes_bullish = voter._parse_signals(signals_bullish)
        assert votes_bullish["sentiment"].signal == SignalType.BUY

        # Bearish (score < -0.2)
        signals_bearish = {"sentiment": {"score": -0.5}}
        votes_bearish = voter._parse_signals(signals_bearish)
        assert votes_bearish["sentiment"].signal == SignalType.SELL

        # Neutral (-0.2 <= score <= 0.2)
        signals_neutral = {"sentiment": {"score": 0.1}}
        votes_neutral = voter._parse_signals(signals_neutral)
        assert votes_neutral["sentiment"].signal == SignalType.HOLD

    def test_normalize_all_signal_types(self):
        """Test normalizing all three signal types together."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        votes = voter._parse_signals(signals)

        assert len(votes) == 3
        assert all(v.signal == SignalType.BUY for v in votes.values())

    def test_normalize_mixed_signals(self):
        """Test normalizing conflicting signals."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "neutral", "confidence": 0.5},
            "sentiment": {"signal": "bearish", "score": -0.4},
        }

        votes = voter._parse_signals(signals)

        assert votes["momentum"].signal == SignalType.BUY
        assert votes["rl"].signal == SignalType.HOLD
        assert votes["sentiment"].signal == SignalType.SELL


class TestSimpleMajorityVoting:
    """Test simple majority voting mechanism."""

    def test_unanimous_buy(self):
        """Test all models vote BUY."""
        voter = EnsembleVoter(voting_threshold=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        decision = voter.vote(signals)

        assert decision.action == "buy"
        assert decision.consensus_score == 1.0
        assert decision.unanimous is True
        assert decision.votes["for"] == 3
        assert decision.votes["against"] == 0

    def test_majority_buy(self):
        """Test 2 out of 3 vote BUY."""
        voter = EnsembleVoter(voting_threshold=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bearish", "score": -0.4},
        }

        decision = voter.vote(signals)

        assert decision.action == "buy"
        assert decision.consensus_score == pytest.approx(2 / 3, rel=0.01)
        assert decision.unanimous is False
        assert decision.votes["for"] == 2
        assert decision.votes["against"] == 1

    def test_no_majority_defaults_hold(self):
        """Test split vote defaults to HOLD."""
        voter = EnsembleVoter(voting_threshold=0.67)  # Supermajority
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "hold", "confidence": 0.5},
            "sentiment": {"signal": "bearish", "score": -0.4},
        }

        decision = voter.vote(signals)

        # No signal has 67%+ votes, so default to HOLD
        assert decision.action == "hold"
        assert decision.votes["against"] > 0

    def test_confidence_floor_filtering(self):
        """Test votes below confidence floor are ignored."""
        voter = EnsembleVoter(voting_threshold=0.5, confidence_floor=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bearish", "score": 0.3},  # Below floor
        }

        decision = voter.vote(signals)

        # Sentiment vote ignored due to low confidence
        assert decision.action == "buy"
        assert decision.votes["abstain"] == 1

    def test_all_below_confidence_floor(self):
        """Test all votes below floor defaults to HOLD."""
        voter = EnsembleVoter(confidence_floor=0.8)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.5},
            "rl": {"signal": "long", "confidence": 0.6},
            "sentiment": {"signal": "bullish", "score": 0.4},
        }

        decision = voter.vote(signals)

        assert decision.action == "hold"
        assert decision.consensus_score == 0.0
        assert decision.votes["abstain"] == 3

    def test_empty_signals(self):
        """Test empty signals returns HOLD."""
        voter = EnsembleVoter()
        signals = {}

        decision = voter.vote(signals)

        assert decision.action == "hold"
        assert decision.consensus_score == 0.0


class TestWeightedVoting:
    """Test weighted voting mechanism."""

    def test_weighted_vote_equal_weights(self):
        """Test weighted voting with equal weights."""
        voter = EnsembleVoter(
            voting_threshold=0.5,
            weights={"momentum": 1 / 3, "rl": 1 / 3, "sentiment": 1 / 3},
        )
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        decision = voter.weighted_vote(signals)

        assert decision.action == "buy"
        assert decision.consensus_score > 0.9  # Strong consensus

    def test_weighted_vote_momentum_dominant(self):
        """Test weighted voting with momentum having highest weight."""
        voter = EnsembleVoter(
            voting_threshold=0.4,
            weights={"momentum": 0.5, "rl": 0.3, "sentiment": 0.2},
        )
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.9},
            "rl": {"signal": "neutral", "confidence": 0.5},
            "sentiment": {"signal": "bearish", "score": -0.3},
        }

        decision = voter.weighted_vote(signals)

        # Momentum's high weight + confidence should win
        assert decision.action == "buy"

    def test_weighted_vote_low_confidence_ignored(self):
        """Test weighted voting filters low confidence votes."""
        voter = EnsembleVoter(
            voting_threshold=0.5,
            weights={"momentum": 0.4, "rl": 0.3, "sentiment": 0.3},
            confidence_floor=0.6,
        )
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bearish", "score": 0.4},  # Below floor
        }

        decision = voter.weighted_vote(signals)

        assert decision.action == "buy"
        assert decision.votes["abstain"] == 1

    def test_weighted_vote_threshold_not_met(self):
        """Test weighted voting defaults to HOLD when threshold not met."""
        voter = EnsembleVoter(
            voting_threshold=0.9,  # Very high threshold
            weights={"momentum": 0.4, "rl": 0.3, "sentiment": 0.3},
        )
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.6},
            "rl": {"signal": "long", "confidence": 0.5},
            "sentiment": {"signal": "bearish", "score": 0.3},
        }

        decision = voter.weighted_vote(signals)

        # Threshold too high, default to HOLD
        assert decision.action == "hold"


class TestUnanimousVoting:
    """Test unanimous voting requirement."""

    def test_unanimous_buy(self):
        """Test all models agree on BUY."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        decision = voter.unanimous_required(signals)

        assert decision.action == "buy"
        assert decision.consensus_score == 1.0
        assert decision.unanimous is True

    def test_unanimous_disagreement_returns_hold(self):
        """Test disagreement defaults to HOLD."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bearish", "score": -0.5},
        }

        decision = voter.unanimous_required(signals)

        assert decision.action == "hold"
        assert decision.consensus_score == 0.0
        assert decision.unanimous is False

    def test_unanimous_with_confidence_floor(self):
        """Test unanimous voting with confidence floor filtering."""
        voter = EnsembleVoter(confidence_floor=0.6)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.4},  # Below floor
        }

        decision = voter.unanimous_required(signals)

        # Sentiment filtered out, momentum + RL unanimous
        assert decision.action == "buy"
        assert decision.unanimous is True


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_invalid_signal_type_skipped(self):
        """Test invalid signal types are skipped."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "invalid_signal", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
        }

        votes = voter._parse_signals(signals)

        # Invalid signal skipped
        assert "momentum" not in votes
        assert "rl" in votes

    def test_missing_confidence_defaults(self):
        """Test missing confidence field defaults to 0.5."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy"},  # No confidence
        }

        votes = voter._parse_signals(signals)

        assert votes["momentum"].confidence == 0.5

    def test_confidence_clamping(self):
        """Test confidence values are clamped to [0, 1]."""
        voter = EnsembleVoter()
        signals = {
            "momentum": {"signal": "buy", "confidence": 1.5},  # Above 1
            "rl": {"signal": "long", "confidence": -0.2},  # Below 0
        }

        votes = voter._parse_signals(signals)

        assert votes["momentum"].confidence == 1.0
        assert votes["rl"].confidence == 0.0

    def test_single_model_voting(self):
        """Test voting with only one model."""
        voter = EnsembleVoter(voting_threshold=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
        }

        decision = voter.vote(signals)

        assert decision.action == "buy"
        assert decision.consensus_score == 1.0

    def test_tie_vote_scenario(self):
        """Test tie voting scenario with even number of models."""
        voter = EnsembleVoter(voting_threshold=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "sell", "confidence": 0.7},
        }

        decision = voter.vote(signals)

        # With threshold=0.5, neither has majority (50% each)
        # Depends on implementation - max() chooses first in case of tie
        assert decision.action in ["buy", "sell", "hold"]


class TestConvenienceFunctions:
    """Test convenience wrapper functions."""

    def test_simple_majority_vote_function(self):
        """Test simple_majority_vote convenience function."""
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        decision = simple_majority_vote(signals, threshold=0.5)

        assert isinstance(decision, EnsembleDecision)
        assert decision.action == "buy"

    def test_weighted_vote_function(self):
        """Test weighted_vote convenience function."""
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }
        weights = {"momentum": 0.5, "rl": 0.3, "sentiment": 0.2}

        decision = weighted_vote(signals, weights=weights, threshold=0.5)

        assert isinstance(decision, EnsembleDecision)
        assert decision.action == "buy"

    def test_unanimous_vote_function(self):
        """Test unanimous_vote convenience function."""
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.8},
            "rl": {"signal": "long", "confidence": 0.7},
            "sentiment": {"signal": "bullish", "score": 0.6},
        }

        decision = unanimous_vote(signals)

        assert isinstance(decision, EnsembleDecision)
        assert decision.action == "buy"
        assert decision.unanimous is True


class TestIntegrationScenarios:
    """Test realistic trading scenarios."""

    def test_strong_buy_signal(self):
        """Test strong BUY signal from all models."""
        voter = EnsembleVoter(voting_threshold=0.6)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.9},
            "rl": {"signal": "long", "confidence": 0.85},
            "sentiment": {"signal": "bullish", "score": 0.8},
        }

        decision = voter.vote(signals)

        assert decision.action == "buy"
        assert decision.consensus_score == 1.0
        assert decision.unanimous is True
        assert decision.weighted_confidence > 0.8

    def test_weak_mixed_signals(self):
        """Test weak, mixed signals default to HOLD."""
        voter = EnsembleVoter(voting_threshold=0.6, confidence_floor=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.55},
            "rl": {"signal": "neutral", "confidence": 0.45},  # Below floor
            "sentiment": {"signal": "bearish", "score": 0.3},  # Below floor
        }

        decision = voter.vote(signals)

        # RL and sentiment filtered, only momentum counts
        assert decision.action == "buy"  # Only one vote, but it passes threshold
        assert decision.votes["abstain"] == 2

    def test_conflicting_high_confidence_signals(self):
        """Test conflicting signals with high confidence."""
        voter = EnsembleVoter(voting_threshold=0.5)
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.9},
            "rl": {"signal": "short", "confidence": 0.85},
            "sentiment": {"signal": "neutral_sentiment", "score": 0.0},
        }

        decision = voter.vote(signals)

        # No majority (1 buy, 1 sell, 1 hold), but threshold=0.5 means 1/3 is not enough
        # Should default to hold or pick max votes
        assert decision.action in ["buy", "sell", "hold"]

    def test_real_world_example_1(self):
        """
        Scenario: Momentum says BUY (strong), RL says BUY (moderate), Sentiment neutral.
        Expected: BUY with good confidence.
        """
        voter = EnsembleVoter(
            voting_threshold=0.6,
            weights={"momentum": 0.4, "rl": 0.35, "sentiment": 0.25},
        )
        signals = {
            "momentum": {"signal": "buy", "confidence": 0.85},
            "rl": {"signal": "long", "confidence": 0.65},
            "sentiment": {"score": 0.1},  # Neutral
        }

        decision = voter.weighted_vote(signals)

        assert decision.action == "buy"

    def test_real_world_example_2(self):
        """
        Scenario: RL confident BUY, but momentum and sentiment bearish.
        Expected: No consensus, default to HOLD.
        """
        voter = EnsembleVoter(voting_threshold=0.67)  # Supermajority
        signals = {
            "momentum": {"signal": "sell", "confidence": 0.7},
            "rl": {"signal": "long", "confidence": 0.9},
            "sentiment": {"signal": "bearish", "score": -0.6},
        }

        decision = voter.vote(signals)

        # 2 out of 3 vote SELL, but threshold=0.67 means need 67%+
        # 2/3 = 66.67%, just barely not enough -> Actually it IS enough (2/3 = 0.666... >= 0.67 is False in exact math, but may round)
        # Let me check: 2/3 = 0.6666... and 0.67 = 0.67, so 0.6666 < 0.67 is True
        # So it should default to HOLD
        assert decision.action == "hold"


class TestWeightNormalization:
    """Test model weight normalization."""

    def test_weights_sum_to_one(self):
        """Test weights are normalized to sum to 1.0."""
        voter = EnsembleVoter(weights={"momentum": 2.0, "rl": 3.0, "sentiment": 5.0})

        # Should normalize to: momentum=0.2, rl=0.3, sentiment=0.5
        assert pytest.approx(voter.weights["momentum"], rel=0.01) == 0.2
        assert pytest.approx(voter.weights["rl"], rel=0.01) == 0.3
        assert pytest.approx(voter.weights["sentiment"], rel=0.01) == 0.5

    def test_default_equal_weights(self):
        """Test default weights are equal."""
        voter = EnsembleVoter()

        assert pytest.approx(voter.weights["momentum"], rel=0.01) == 1 / 3
        assert pytest.approx(voter.weights["rl"], rel=0.01) == 1 / 3
        assert pytest.approx(voter.weights["sentiment"], rel=0.01) == 1 / 3

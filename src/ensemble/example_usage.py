"""
Example usage of the Ensemble Voting System.

Demonstrates different voting modes and signal formats.
"""

from src.ensemble import EnsembleVoter
from src.ensemble.voting_ensemble import simple_majority_vote, unanimous_vote, weighted_vote


def example_1_simple_majority():
    """Example 1: Simple majority voting with unanimous agreement."""
    print("\n" + "=" * 80)
    print("EXAMPLE 1: Simple Majority - Unanimous BUY")
    print("=" * 80)

    signals = {
        "momentum": {"signal": "buy", "confidence": 0.85},
        "rl": {"signal": "long", "confidence": 0.75},
        "sentiment": {"signal": "bullish", "score": 0.7},
    }

    decision = simple_majority_vote(signals, threshold=0.5)

    print(f"Action: {decision.action}")
    print(f"Consensus Score: {decision.consensus_score:.2f}")
    print(f"Weighted Confidence: {decision.weighted_confidence:.2f}")
    print(f"Votes: {decision.votes}")
    print(f"Unanimous: {decision.unanimous}")
    print("\nInterpretation: All models agree on BUY - strong signal!")


def example_2_majority_with_disagreement():
    """Example 2: Majority voting with one dissenting vote."""
    print("\n" + "=" * 80)
    print("EXAMPLE 2: Majority Vote - 2 BUY, 1 SELL")
    print("=" * 80)

    signals = {
        "momentum": {"signal": "buy", "confidence": 0.8},
        "rl": {"signal": "long", "confidence": 0.7},
        "sentiment": {"signal": "bearish", "score": -0.5},  # Dissenting vote
    }

    voter = EnsembleVoter(voting_threshold=0.5)
    decision = voter.vote(signals)

    print(f"Action: {decision.action}")
    print(f"Consensus Score: {decision.consensus_score:.2f}")
    print(f"Unanimous: {decision.unanimous}")
    print(f"Votes: {decision.votes}")
    print("\nInterpretation: 2/3 majority for BUY, but not unanimous.")


def example_3_weighted_voting():
    """Example 3: Weighted voting with custom model weights."""
    print("\n" + "=" * 80)
    print("EXAMPLE 3: Weighted Voting - Momentum Dominant")
    print("=" * 80)

    signals = {
        "momentum": {"signal": "buy", "confidence": 0.9},  # High confidence
        "rl": {"signal": "neutral", "confidence": 0.5},
        "sentiment": {"signal": "bearish", "score": -0.3},
    }

    # Give momentum highest weight
    weights = {"momentum": 0.5, "rl": 0.3, "sentiment": 0.2}

    decision = weighted_vote(signals, weights=weights, threshold=0.45)

    print(f"Model Weights: {weights}")
    print(f"Action: {decision.action}")
    print(f"Weighted Confidence: {decision.weighted_confidence:.2f}")
    print(f"Consensus Score: {decision.consensus_score:.2f}")
    print(
        f"Action Scores: {decision.metadata.get('action_scores', {})}"
    )
    print(
        "\nInterpretation: Despite mixed signals, momentum's high weight + confidence wins."
    )


def example_4_confidence_floor():
    """Example 4: Confidence floor filtering low-confidence votes."""
    print("\n" + "=" * 80)
    print("EXAMPLE 4: Confidence Floor - Filtering Weak Votes")
    print("=" * 80)

    signals = {
        "momentum": {"signal": "buy", "confidence": 0.8},
        "rl": {"signal": "long", "confidence": 0.7},
        "sentiment": {"signal": "bearish", "score": 0.3},  # Low confidence
    }

    voter = EnsembleVoter(voting_threshold=0.5, confidence_floor=0.5)
    decision = voter.vote(signals)

    print(f"Confidence Floor: 0.5")
    print(f"Action: {decision.action}")
    print(f"Votes: {decision.votes}")
    print(
        "\nInterpretation: Sentiment vote filtered out (0.3 < 0.5 floor), "
        "leaving only momentum + RL."
    )


def example_5_unanimous_required():
    """Example 5: Unanimous voting requirement."""
    print("\n" + "=" * 80)
    print("EXAMPLE 5: Unanimous Voting - High Certainty Required")
    print("=" * 80)

    # Scenario A: All agree
    signals_agree = {
        "momentum": {"signal": "buy", "confidence": 0.8},
        "rl": {"signal": "long", "confidence": 0.75},
        "sentiment": {"signal": "bullish", "score": 0.7},
    }

    decision_agree = unanimous_vote(signals_agree)

    print("Scenario A: All models agree")
    print(f"  Action: {decision_agree.action}")
    print(f"  Unanimous: {decision_agree.unanimous}")
    print(f"  Consensus: {decision_agree.consensus_score:.2f}")

    # Scenario B: Disagreement
    signals_disagree = {
        "momentum": {"signal": "buy", "confidence": 0.8},
        "rl": {"signal": "long", "confidence": 0.75},
        "sentiment": {"signal": "bearish", "score": -0.5},  # Dissent
    }

    decision_disagree = unanimous_vote(signals_disagree)

    print("\nScenario B: One model disagrees")
    print(f"  Action: {decision_disagree.action}")
    print(f"  Unanimous: {decision_disagree.unanimous}")
    print(f"  Consensus: {decision_disagree.consensus_score:.2f}")
    print(
        "\nInterpretation: Unanimous mode defaults to HOLD when disagreement exists."
    )


def example_6_threshold_tuning():
    """Example 6: Tuning voting threshold for different requirements."""
    print("\n" + "=" * 80)
    print("EXAMPLE 6: Threshold Tuning - Majority vs Supermajority")
    print("=" * 80)

    signals = {
        "momentum": {"signal": "buy", "confidence": 0.8},
        "rl": {"signal": "long", "confidence": 0.7},
        "sentiment": {"signal": "hold", "confidence": 0.5},
    }

    # Simple majority (50%)
    voter_majority = EnsembleVoter(voting_threshold=0.5)
    decision_majority = voter_majority.vote(signals)

    print("Simple Majority (threshold=0.5):")
    print(f"  Action: {decision_majority.action}")
    print(f"  Consensus: {decision_majority.consensus_score:.2f}")

    # Supermajority (67%)
    voter_supermajority = EnsembleVoter(voting_threshold=0.67)
    decision_supermajority = voter_supermajority.vote(signals)

    print("\nSupermajority (threshold=0.67):")
    print(f"  Action: {decision_supermajority.action}")
    print(f"  Consensus: {decision_supermajority.consensus_score:.2f}")

    print(
        "\nInterpretation: Higher thresholds reduce false positives but may miss trades."
    )


def example_7_sentiment_score_inference():
    """Example 7: Sentiment signal inferred from score."""
    print("\n" + "=" * 80)
    print("EXAMPLE 7: Sentiment Score Inference")
    print("=" * 80)

    # Different sentiment score ranges
    test_scores = [0.6, 0.1, -0.3, -0.7]

    voter = EnsembleVoter()

    for score in test_scores:
        signals = {"sentiment": {"score": score}}

        votes = voter._parse_signals(signals)
        signal_type = votes["sentiment"].signal.value if votes else "unknown"

        print(f"Score: {score:5.1f} -> Signal: {signal_type:10s}", end="")
        if score > 0.2:
            print("(bullish -> BUY)")
        elif score < -0.2:
            print("(bearish -> SELL)")
        else:
            print("(neutral -> HOLD)")

    print(
        "\nInterpretation: Sentiment scores auto-convert to BUY/HOLD/SELL signals."
    )


def example_8_real_world_scenario():
    """Example 8: Real-world trading scenario."""
    print("\n" + "=" * 80)
    print("EXAMPLE 8: Real-World Scenario - Mixed Signals in High Volatility")
    print("=" * 80)

    # Scenario: High volatility market, mixed technical and sentiment signals
    signals = {
        "momentum": {"signal": "buy", "confidence": 0.75},  # Moderate bullish
        "rl": {"signal": "neutral", "confidence": 0.55},  # Uncertain
        "sentiment": {"score": -0.15},  # Slightly bearish
    }

    # Conservative approach in high volatility
    voter_conservative = EnsembleVoter(
        voting_threshold=0.67,  # Require supermajority
        weights={"momentum": 0.3, "rl": 0.4, "sentiment": 0.3},  # Trust RL more
        confidence_floor=0.5,  # Ignore weak signals
    )

    decision = voter_conservative.weighted_vote(signals)

    print("Market Condition: High Volatility")
    print("Voting Config: Conservative (threshold=0.67, confidence_floor=0.5)")
    print(f"\nAction: {decision.action}")
    print(f"Weighted Confidence: {decision.weighted_confidence:.2f}")
    print(f"Votes Used: {decision.votes['for'] + decision.votes['against']}")
    print(f"Votes Abstained: {decision.votes['abstain']}")

    print(
        "\nInterpretation: Conservative settings filter out weak sentiment "
        "and require stronger consensus."
    )


def main():
    """Run all examples."""
    print("\n" + "=" * 80)
    print("ENSEMBLE VOTING SYSTEM - USAGE EXAMPLES")
    print("=" * 80)

    examples = [
        example_1_simple_majority,
        example_2_majority_with_disagreement,
        example_3_weighted_voting,
        example_4_confidence_floor,
        example_5_unanimous_required,
        example_6_threshold_tuning,
        example_7_sentiment_score_inference,
        example_8_real_world_scenario,
    ]

    for example in examples:
        try:
            example()
        except Exception as e:
            print(f"\nERROR in {example.__name__}: {e}")

    print("\n" + "=" * 80)
    print("All examples completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

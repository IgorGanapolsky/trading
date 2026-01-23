#!/usr/bin/env python3
"""
Train feedback model from user thumbs up/down signals.

Uses Thompson Sampling (Beta-Bernoulli conjugate prior) for exploration/exploitation.
Updates alpha (successes) and beta (failures) based on feedback.

Called by: .claude/hooks/capture_feedback.sh
Model file: models/ml/feedback_model.json
"""

import argparse
import json
import logging
import re
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "models" / "ml" / "feedback_model.json"


def load_model() -> dict:
    """Load the feedback model from disk."""
    if MODEL_PATH.exists():
        with open(MODEL_PATH) as f:
            return json.load(f)
    # Initialize with uniform prior (alpha=1, beta=1)
    return {
        "alpha": 1.0,
        "beta": 1.0,
        "feature_weights": {},
        "last_updated": None,
    }


def save_model(model: dict) -> None:
    """Save the feedback model to disk."""
    MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
    model["last_updated"] = datetime.now().isoformat()
    with open(MODEL_PATH, "w") as f:
        json.dump(model, f, indent=2)
    logger.info(f"Model saved: alpha={model['alpha']:.1f}, beta={model['beta']:.1f}")


def extract_features(context: str) -> list[str]:
    """
    Extract features from the context that may correlate with feedback.

    Features are simple tokens that help identify patterns in good/bad outcomes.
    """
    features = []
    context_lower = context.lower()

    # Code-related features
    if re.search(r"test|pytest|unittest", context_lower):
        features.append("test")
    if re.search(r"ci|workflow|action", context_lower):
        features.append("ci")
    if re.search(r"bug|fix|error|issue", context_lower):
        features.append("fix")
    if re.search(r"trade|order|position", context_lower):
        features.append("trade")
    if re.search(r"entry|exit|close", context_lower):
        features.append("entry")
    if re.search(r"rag|lesson|learn", context_lower):
        features.append("rag")
    if re.search(r"pr|merge|branch", context_lower):
        features.append("pr")
    if re.search(r"refactor|clean|improve", context_lower):
        features.append("refactor")

    return features


def update_model(feedback_type: str, context: str) -> None:
    """
    Update the model based on feedback.

    Thompson Sampling approach:
    - Positive feedback: alpha += 1 (more successes)
    - Negative feedback: beta += 1 (more failures)

    Feature weights are updated with small increments to track patterns.
    """
    model = load_model()

    # Update Thompson Sampling parameters
    if feedback_type == "positive":
        model["alpha"] += 1.0
        weight_delta = 0.1  # Positive weight for good patterns
    else:
        model["beta"] += 1.0
        weight_delta = -0.1  # Negative weight for bad patterns

    # Update feature weights
    features = extract_features(context)
    for feature in features:
        current_weight = model["feature_weights"].get(feature, 0.0)
        model["feature_weights"][feature] = round(current_weight + weight_delta, 2)

    save_model(model)

    # Log for observability
    posterior = model["alpha"] / (model["alpha"] + model["beta"])
    logger.info(
        f"Feedback: {feedback_type} | Posterior: {posterior:.3f} | "
        f"Features: {features}"
    )


def main():
    parser = argparse.ArgumentParser(description="Train feedback model from signals")
    parser.add_argument(
        "--feedback", required=True, choices=["positive", "negative"],
        help="Type of feedback received"
    )
    parser.add_argument(
        "--context", default="",
        help="Context around the feedback (for feature extraction)"
    )
    args = parser.parse_args()

    update_model(args.feedback, args.context)


if __name__ == "__main__":
    main()

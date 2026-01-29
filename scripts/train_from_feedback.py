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
from datetime import datetime, timezone
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).parent.parent / "models" / "ml" / "feedback_model.json"
FEEDBACK_DIRS = [
    Path(__file__).parent.parent / "data" / "feedback",
    Path(__file__).parent.parent / ".claude" / "memory" / "feedback",
]

DEFAULT_CATEGORIES = {
    "test": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "ci": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "trade": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "pr": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "refactor": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "analysis": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "log_parsing": {"alpha": 1.0, "beta": 1.0, "count": 0},
    "system_health": {"alpha": 1.0, "beta": 1.0, "count": 0},
}


def load_model() -> dict:
    """Load the feedback model from disk."""
    if MODEL_PATH.exists():
        with open(MODEL_PATH) as f:
            model = json.load(f)
        # Backward compat: add per_category if missing
        if "per_category" not in model:
            model["per_category"] = json.loads(json.dumps(DEFAULT_CATEGORIES))
        return model
    # Initialize with uniform prior (alpha=1, beta=1)
    return {
        "alpha": 1.0,
        "beta": 1.0,
        "feature_weights": {},
        "per_category": json.loads(json.dumps(DEFAULT_CATEGORIES)),
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
    if re.search(r"analys|research|backtest", context_lower):
        features.append("analysis")
    if re.search(r"log|parse|output", context_lower):
        features.append("log_parsing")
    if re.search(r"health|system|check|monitor", context_lower):
        features.append("system_health")

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

    # Update per-category bandits
    per_cat = model.get("per_category", {})
    for feature in features:
        if feature in per_cat:
            if feedback_type == "positive":
                per_cat[feature]["alpha"] += 1.0
            else:
                per_cat[feature]["beta"] += 1.0
            per_cat[feature]["count"] += 1
    model["per_category"] = per_cat

    save_model(model)

    # Log for observability
    posterior = model["alpha"] / (model["alpha"] + model["beta"])
    logger.info(f"Feedback: {feedback_type} | Posterior: {posterior:.3f} | Features: {features}")


def compute_time_weight(timestamp: str) -> float:
    """Compute a decay weight based on age of feedback.

    <7 days: 1.0, 7-30 days: 0.5, >30 days: 0.25
    """
    try:
        if "T" in timestamp:
            ts = datetime.fromisoformat(timestamp)
        else:
            ts = datetime.strptime(timestamp, "%Y-%m-%d %H:%M:%S")
        # Make naive if needed
        if ts.tzinfo is not None:
            now = datetime.now(timezone.utc)
        else:
            now = datetime.now()
        age_days = (now - ts).total_seconds() / 86400
    except (ValueError, TypeError):
        return 0.25  # Unknown timestamp = oldest weight

    if age_days < 7:
        return 1.0
    elif age_days <= 30:
        return 0.5
    else:
        return 0.25


def recompute_from_history() -> None:
    """Rebuild model from all historical feedback with time decay."""
    logger.info("Recomputing model from feedback history with time decay...")

    # Reset model
    model = {
        "alpha": 1.0,
        "beta": 1.0,
        "feature_weights": {},
        "per_category": json.loads(json.dumps(DEFAULT_CATEGORIES)),
        "last_updated": None,
    }

    entries = []
    for fb_dir in FEEDBACK_DIRS:
        if not fb_dir.exists():
            continue
        for f in fb_dir.glob("feedback_*.jsonl"):
            with open(f) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue
        # Also check feedback-log.jsonl
        log_file = fb_dir / "feedback-log.jsonl"
        if log_file.exists():
            with open(log_file) as fh:
                for line in fh:
                    line = line.strip()
                    if line:
                        try:
                            entries.append(json.loads(line))
                        except json.JSONDecodeError:
                            continue

    logger.info(f"Found {len(entries)} historical feedback entries")

    for entry in entries:
        fb_type = entry.get("type", entry.get("feedback", ""))
        if fb_type not in ("positive", "negative"):
            continue

        ts = entry.get("timestamp", "")
        weight = compute_time_weight(ts)

        context = entry.get("summary", entry.get("context", entry.get("user_message", "")))
        features = extract_features(context)

        if fb_type == "positive":
            model["alpha"] += weight
            weight_delta = 0.1 * weight
        else:
            model["beta"] += weight
            weight_delta = -0.1 * weight

        for feature in features:
            current = model["feature_weights"].get(feature, 0.0)
            model["feature_weights"][feature] = round(current + weight_delta, 2)

        per_cat = model["per_category"]
        for feature in features:
            if feature in per_cat:
                if fb_type == "positive":
                    per_cat[feature]["alpha"] += weight
                else:
                    per_cat[feature]["beta"] += weight
                per_cat[feature]["count"] += 1

    save_model(model)
    posterior = model["alpha"] / (model["alpha"] + model["beta"])
    logger.info(
        f"Recompute done: alpha={model['alpha']:.1f}, beta={model['beta']:.1f}, "
        f"posterior={posterior:.3f}, entries={len(entries)}"
    )


def main():
    parser = argparse.ArgumentParser(description="Train feedback model from signals")
    parser.add_argument(
        "--feedback",
        choices=["positive", "negative"],
        help="Type of feedback received",
    )
    parser.add_argument(
        "--context", default="", help="Context around the feedback (for feature extraction)"
    )
    parser.add_argument(
        "--recompute",
        action="store_true",
        help="Rebuild model from all feedback history with time decay",
    )
    args = parser.parse_args()

    if args.recompute:
        recompute_from_history()
    elif args.feedback:
        update_model(args.feedback, args.context)
    else:
        parser.error("Either --feedback or --recompute is required")


if __name__ == "__main__":
    main()

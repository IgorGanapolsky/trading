#!/usr/bin/env python3
"""
Train RL models from human feedback.

This script is called:
1. After thumbs up/down feedback (via capture_feedback.sh hook)
2. End of each session
3. Manually for batch training

Usage:
    python3 scripts/train_from_feedback.py
    python3 scripts/train_from_feedback.py --feedback positive
    python3 scripts/train_from_feedback.py --feedback negative --context "trade failed"
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.learning.feedback_trainer import FeedbackTrainer

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def train_from_logs(days_back: int = 7) -> dict:
    """Train from existing feedback logs."""
    trainer = FeedbackTrainer()
    result = trainer.process_feedback_logs(days_back=days_back)
    return result


def record_immediate_feedback(is_positive: bool, context: str | None = None) -> dict:
    """Record new feedback and update model immediately."""
    trainer = FeedbackTrainer()
    context_dict = {"raw_context": context} if context else None
    result = trainer.record_feedback(is_positive=is_positive, context=context_dict)
    return result


def show_model_stats() -> dict:
    """Display current model statistics."""
    trainer = FeedbackTrainer()
    stats = trainer.get_model_stats()
    return stats


def main():
    parser = argparse.ArgumentParser(description="Train RL from human feedback")
    parser.add_argument(
        "--feedback",
        choices=["positive", "negative"],
        help="Record immediate feedback (positive=thumbs up, negative=thumbs down)",
    )
    parser.add_argument(
        "--context",
        type=str,
        default=None,
        help="Context for the feedback",
    )
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Process all feedback logs (batch training)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        help="Number of days of feedback to process (default: 7)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Show current model statistics",
    )

    args = parser.parse_args()

    if args.stats:
        stats = show_model_stats()
        logger.info("Model Statistics:")
        logger.info("  Alpha (successes): %.1f", stats["alpha"])
        logger.info("  Beta (failures): %.1f", stats["beta"])
        logger.info("  Total samples: %d", stats["total_samples"])
        logger.info("  Posterior mean: %.3f", stats["posterior_mean"])
        logger.info("  95%% CI: [%.3f, %.3f]", *stats["confidence_interval_95"])
        logger.info("  Feature weights: %d features", len(stats["feature_weights"]))
        return

    if args.feedback:
        is_positive = args.feedback == "positive"
        result = record_immediate_feedback(is_positive, args.context)
        logger.info(
            "Recorded %s feedback. Shaped reward: %.2f. Posterior: %.3f",
            args.feedback,
            result["shaped_reward"],
            result["posterior_mean"],
        )
        # Output for hook consumption
        print(json.dumps(result, indent=2))
        return

    if args.batch:
        logger.info("Starting batch training from feedback logs...")
        result = train_from_logs(days_back=args.days)
        if result["trained"]:
            logger.info(
                "Training complete: %d samples (%.1f%% positive). "
                "Posterior: %.3f ± %.3f",
                result["samples"],
                100 * result["positive"] / result["samples"],
                result["posterior_mean"],
                result["posterior_std"],
            )
        else:
            logger.warning("Training skipped: %s", result.get("reason", "unknown"))
        print(json.dumps(result, indent=2))
        return

    # Default: show usage
    parser.print_help()


if __name__ == "__main__":
    main()

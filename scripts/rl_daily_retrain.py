#!/usr/bin/env python3
"""Daily RL weight retraining from telemetry feedback loop.

This script:
1. Reads the audit trail of trade outcomes
2. Retrains RL filter weights based on actual performance
3. Updates the weights file so the system learns from experience

Called after market close to ensure the RL agent learns from the day's trades.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.rl_agent import RLFilter
from src.utils.logging_config import setup_logging


def main() -> int:
    """Execute RL retraining from telemetry."""
    parser = argparse.ArgumentParser(description="Retrain RL weights from telemetry")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate update without writing files",
    )
    parser.add_argument(
        "--audit-path",
        type=str,
        default="data/audit_trail/hybrid_funnel_runs.jsonl",
        help="Path to audit trail file",
    )
    parser.add_argument(
        "--weights-path",
        type=str,
        default="models/ml/rl_filter_weights.json",
        help="Path to RL weights file",
    )
    parser.add_argument(
        "--model-path",
        type=str,
        default="models/ml/rl_filter_policy.zip",
        help="Path to save trained PPO model",
    )
    args = parser.parse_args()

    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("RL DAILY RETRAINING - Closing the feedback loop")
    logger.info("=" * 80)

    # Verify audit trail exists
    audit_path = Path(args.audit_path)
    if not audit_path.exists():
        logger.warning(
            "Audit trail not found at %s - no trades to learn from yet",
            audit_path,
        )
        logger.info("This is normal on first run. Skipping retraining.")
        return 0

    # Check audit trail has content
    try:
        line_count = sum(1 for _ in audit_path.open("r"))
        logger.info("Found %d telemetry events in audit trail", line_count)

        if line_count == 0:
            logger.info("Audit trail is empty - no trades to learn from yet")
            return 0
    except Exception as e:
        logger.error("Failed to read audit trail: %s", e)
        return 1

    # Initialize RL filter and trigger update
    try:
        logger.info("Initializing RL filter for retraining...")
        rl_filter = RLFilter()

        logger.info("Starting telemetry replay and weight update...")
        summary = rl_filter.update_from_telemetry(
            audit_path=str(audit_path),
            model_path=args.model_path,
            dry_run=args.dry_run,
        )

        # Log results
        logger.info("=" * 80)
        logger.info("RETRAINING SUMMARY")
        logger.info("=" * 80)

        if summary.get("updated"):
            logger.info("✅ RL weights successfully updated!")
            logger.info("   Samples collected: %d", summary.get("samples_collected", 0))
            logger.info("   Symbols updated: %s", ", ".join(summary.get("symbols_updated", [])))
            logger.info("   Weights path: %s", summary.get("weights_path"))
            logger.info("   Model path: %s", summary.get("model_path"))

            if args.dry_run:
                logger.info("   (DRY RUN - no files modified)")
            else:
                logger.info("   🎓 System learned from %d trade outcomes", summary.get("samples_collected", 0))

                # Log the updated weights for verification
                weights_path = Path(args.weights_path)
                if weights_path.exists():
                    try:
                        with weights_path.open("r") as f:
                            weights = json.load(f)
                        logger.info("   Updated weights preview:")
                        for symbol, params in list(weights.items())[:3]:
                            logger.info("      %s: threshold=%.3f, bias=%.4f",
                                       symbol,
                                       params.get("action_threshold", 0),
                                       params.get("bias", 0))
                    except Exception as e:
                        logger.warning("Could not preview weights: %s", e)
        else:
            reason = summary.get("reason", "unknown")
            logger.warning("⚠️  RL weights NOT updated: %s", reason)
            logger.info("   Samples collected: %d", summary.get("samples_collected", 0))

            if reason == "insufficient_samples":
                logger.info("   Need more trade history to retrain effectively")
                logger.info("   System will continue using existing weights")

        logger.info("=" * 80)

        return 0 if summary.get("updated") else 1

    except Exception as e:
        logger.error("RL retraining failed: %s", e, exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())

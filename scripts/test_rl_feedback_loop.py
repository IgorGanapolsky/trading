#!/usr/bin/env python3
"""Test script to verify RL feedback loop is working correctly.

This script:
1. Checks if audit trail exists and has data
2. Runs a dry-run retraining to verify the pipeline works
3. Validates weights file structure
4. Provides diagnostic output

Use this to verify the RL feedback loop is properly configured.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure src is on the path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents.rl_agent import RLFilter
from src.utils.logging_config import setup_logging


def main() -> int:
    """Test RL feedback loop components."""
    logger = setup_logging()
    logger.info("=" * 80)
    logger.info("RL FEEDBACK LOOP - Component Test")
    logger.info("=" * 80)

    success = True

    # Test 1: Check audit trail
    logger.info("\n📋 Test 1: Audit Trail Verification")
    audit_path = Path("data/audit_trail/hybrid_funnel_runs.jsonl")

    if not audit_path.exists():
        logger.warning("❌ Audit trail does not exist at %s", audit_path)
        logger.info("   This is normal if no trading has occurred yet.")
        logger.info("   Run a trading session to generate telemetry data.")
        success = False
    else:
        try:
            line_count = sum(1 for _ in audit_path.open("r"))
            logger.info("✅ Audit trail exists with %d events", line_count)

            if line_count == 0:
                logger.warning("   ⚠️  Audit trail is empty - need trades to retrain")
                success = False
            else:
                # Sample a few events
                logger.info("   Sample events:")
                with audit_path.open("r") as f:
                    for i, line in enumerate(f):
                        if i >= 3:  # Show first 3 events
                            break
                        try:
                            event = json.loads(line)
                            logger.info(
                                "      %s | %s | %s | %s",
                                event.get("ts", "")[:19],
                                event.get("event", ""),
                                event.get("ticker", ""),
                                event.get("status", ""),
                            )
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            logger.error("❌ Failed to read audit trail: %s", e)
            success = False

    # Test 2: Check weights file
    logger.info("\n📋 Test 2: Weights File Verification")
    weights_path = Path("models/ml/rl_filter_weights.json")

    if not weights_path.exists():
        logger.warning("⚠️  Weights file does not exist at %s", weights_path)
        logger.info("   Will be created on first retraining.")
        logger.info("   Using default heuristic weights until then.")
    else:
        try:
            with weights_path.open("r") as f:
                weights = json.load(f)

            logger.info("✅ Weights file exists with %d symbol configs", len(weights))

            # Show sample weights
            logger.info("   Sample weights:")
            for symbol, params in list(weights.items())[:3]:
                logger.info(
                    "      %s: threshold=%.3f, bias=%.4f",
                    symbol,
                    params.get("action_threshold", 0),
                    params.get("bias", 0),
                )
        except Exception as e:
            logger.error("❌ Failed to read weights file: %s", e)
            success = False

    # Test 3: RLFilter initialization
    logger.info("\n📋 Test 3: RLFilter Initialization")
    try:
        rl_filter = RLFilter()
        logger.info("✅ RLFilter initialized successfully")
        logger.info("   Weights loaded: %d symbols", len(rl_filter.weights))
        logger.info("   Default threshold: %.3f", rl_filter.default_threshold)

        if rl_filter.transformer:
            logger.info("   ✅ Transformer RL policy loaded")
        else:
            logger.info("   📋 Transformer RL disabled (using heuristics only)")
    except Exception as e:
        logger.error("❌ Failed to initialize RLFilter: %s", e)
        success = False

    # Test 4: Dry-run retraining
    logger.info("\n📋 Test 4: Dry-Run Retraining Test")
    if audit_path.exists():
        try:
            logger.info("Running dry-run retraining...")
            rl_filter = RLFilter()
            summary = rl_filter.update_from_telemetry(
                audit_path=str(audit_path),
                dry_run=True,
            )

            logger.info("✅ Dry-run retraining completed")
            logger.info("   Summary: %s", json.dumps(summary, indent=2))

            if summary.get("updated"):
                logger.info("   ✅ Would update weights with %d samples", summary.get("samples_collected", 0))
            else:
                logger.warning("   ⚠️  Not enough data for retraining: %s", summary.get("reason"))
                if summary.get("reason") == "insufficient_samples":
                    logger.info("      Need more trade history to retrain effectively")
        except Exception as e:
            logger.error("❌ Dry-run retraining failed: %s", e, exc_info=True)
            success = False
    else:
        logger.info("⏭️  Skipped (no audit trail)")

    # Final summary
    logger.info("\n" + "=" * 80)
    if success:
        logger.info("✅ RL FEEDBACK LOOP TEST PASSED")
        logger.info("")
        logger.info("The RL feedback loop is properly configured and ready to use.")
        logger.info("")
        logger.info("Next steps:")
        logger.info("  1. Run trading session to generate telemetry")
        logger.info("  2. Run rl_daily_retrain.py to update weights")
        logger.info("  3. Weights will be automatically used in next session")
    else:
        logger.warning("⚠️  RL FEEDBACK LOOP TEST INCOMPLETE")
        logger.info("")
        logger.info("Some components are not yet ready (this is normal on first setup).")
        logger.info("Run a trading session to generate the necessary data.")
    logger.info("=" * 80)

    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

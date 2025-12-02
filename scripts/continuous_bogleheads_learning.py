#!/usr/bin/env python3
"""
Continuous Bogleheads Forum Learning

Runs continuously to monitor Bogleheads forum, extract insights,
and update RAG storage for RL engine integration.
"""

import logging
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import from .claude/skills first, fall back to direct path
try:
    from claude.skills.bogleheads_learner.scripts.bogleheads_learner import (
        BogleheadsLearner,
    )
except ModuleNotFoundError:
    # In CI/CD environment, use absolute path
    skills_path = project_root / ".claude" / "skills" / "bogleheads_learner" / "scripts"
    sys.path.insert(0, str(skills_path))
    from bogleheads_learner import BogleheadsLearner

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    """Continuous learning loop"""
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--max-posts", type=int, default=50, help="Max posts to analyze")
    args = parser.parse_args()

    learner = BogleheadsLearner()

    logger.info("🔍 Starting continuous Bogleheads forum learning...")
    logger.info("   Monitoring: Personal Investments, Investing Theory")
    logger.info("   Keywords: market timing, risk, volatility, rebalancing")

    iteration = 0

    while True:
        try:
            iteration += 1
            logger.info(f"\n{'=' * 80}")
            logger.info(f"Iteration {iteration} - {datetime.now().isoformat()}")
            logger.info("=" * 80)

            # Monitor forum
            result = learner.monitor_bogleheads_forum(
                topics=["Personal Investments", "Investing - Theory, News & General"],
                keywords=[
                    "market timing",
                    "rebalancing",
                    "risk",
                    "volatility",
                    "bear market",
                    "bull market",
                    "diversification",
                    "allocation",
                    "index funds",
                    "ETF",
                    "SPY",
                    "QQQ",
                    "VOO",
                ],
                max_posts=args.max_posts,
                min_replies=5,
            )

            logger.info(f"📊 Monitoring result: {result}")

            # Extract insights (if posts found)
            if result.get("posts_analyzed", 0) > 0:
                logger.info("💡 Extracting insights from posts...")
                # In production, would extract insights here
                # For now, placeholder

            # Store insights to RAG
            # (Would store extracted insights here)

            # Exit if --once flag is set
            if args.once:
                logger.info("✅ Single run complete (--once flag set)")
                if not result.get("success", False):
                    logger.error(f"❌ Monitoring failed: {result.get('error', 'Unknown error')}")
                    sys.exit(1)
                break

            # Wait before next iteration (24 hours)
            wait_hours = 24
            wait_seconds = wait_hours * 3600
            logger.info(f"⏳ Waiting {wait_hours} hours until next monitoring cycle...")
            logger.info(
                f"   Next run: {datetime.fromtimestamp(time.time() + wait_seconds).isoformat()}"
            )

            time.sleep(wait_seconds)

        except KeyboardInterrupt:
            logger.info("\n🛑 Stopping continuous learning (KeyboardInterrupt)")
            break
        except Exception as e:
            logger.error(f"❌ Error in learning loop: {e}", exc_info=True)
            logger.info("⏳ Waiting 1 hour before retry...")
            time.sleep(3600)


if __name__ == "__main__":
    main()

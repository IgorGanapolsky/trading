import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.orchestration.elite_orchestrator import EliteOrchestrator
from src.safety.chaos_monkey import chaos_monkey
from src.safety.explainability import tracer

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ChaosDrill")


def run_chaos_drill():
    logger.info("🔥 STARTING CHAOS DRILL 🔥")

    # 1. Enable Chaos Monkey
    chaos_monkey.enabled = True
    chaos_monkey.probability = 0.5  # 50% chance of failure/latency
    logger.info("🐒 Chaos Monkey ENABLED (50% probability)")

    # 2. Initialize Orchestrator
    orchestrator = EliteOrchestrator(paper=True)

    # 3. Run Trading Cycle under Chaos
    symbols = ["SPY", "QQQ"]
    try:
        logger.info("🚀 Launching trading cycle under chaos conditions...")
        results = orchestrator.run_trading_cycle(symbols)

        logger.info("\n✅ DRILL COMPLETE: System survived chaos")
        logger.info(f"Final Decision: {results.get('final_decision')}")
        logger.info(f"Errors encountered (and handled): {len(results.get('errors', []))}")
        for err in results.get("errors", []):
            logger.info(f"  - {err}")

    except Exception as e:
        logger.error("\n❌ DRILL FAILED: System crashed under chaos")
        logger.error(f"Reason: {e}")
        sys.exit(1)

    # 4. Verify Audit Trace
    if tracer.current_trace_id:
        logger.info(f"\n🔍 Audit Trace Generated: {tracer.current_trace_id}")
    else:
        logger.warning("\n⚠️ No audit trace found!")


if __name__ == "__main__":
    run_chaos_drill()

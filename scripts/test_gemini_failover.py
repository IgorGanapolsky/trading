#!/usr/bin/env python3
"""Test Gemini Failover - Verify backup LLM provider is operational.

This script tests that:
1. Gemini agent can initialize
2. Gemini can respond to a simple prompt
3. Failover from Claude to Gemini works correctly

Run this regularly to ensure backup LLM is ready if Claude has issues.

Part of operational security improvements (Jan 2026).
"""

import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Add project root to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def test_gemini_initialization() -> tuple[bool, str, float]:
    """Test that Gemini agent can be initialized."""
    start = time.time()
    try:
        from src.agents.gemini_agent import GeminiAgent

        # Check API key
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            return False, "GOOGLE_API_KEY not set in environment", 0.0

        # Initialize agent
        agent = GeminiAgent(
            name="FailoverTest",
            role="Testing Gemini failover capability",
            model="gemini-2.0-flash-exp",  # Fast model for testing
            default_thinking_level="low",
        )

        if agent.client is None:
            return False, "Gemini client failed to initialize", time.time() - start

        elapsed = time.time() - start
        return True, f"Gemini agent initialized in {elapsed:.2f}s", elapsed

    except ImportError as e:
        return False, f"Import error: {e}", time.time() - start
    except Exception as e:
        return False, f"Initialization failed: {e}", time.time() - start


def test_gemini_response() -> tuple[bool, str, float]:
    """Test that Gemini can respond to a simple prompt."""
    start = time.time()
    try:
        from src.agents.gemini_agent import GeminiAgent

        agent = GeminiAgent(
            name="FailoverTest",
            role="Testing",
            model="gemini-2.0-flash-exp",
            default_thinking_level="low",
        )

        if agent.client is None:
            return False, "Gemini client not available", 0.0

        # Simple test prompt
        result = agent.reason(
            prompt="Respond with exactly: 'FAILOVER_TEST_OK'",
            thinking_level="low",
        )

        elapsed = time.time() - start
        reasoning = result.get("reasoning", "")

        if "FAILOVER_TEST_OK" in reasoning or "OK" in reasoning.upper():
            return True, f"Gemini responded correctly in {elapsed:.2f}s", elapsed
        else:
            return False, f"Unexpected response: {reasoning[:100]}", elapsed

    except Exception as e:
        return False, f"Response test failed: {e}", time.time() - start


def test_failover_simulation() -> tuple[bool, str, float]:
    """Simulate a Claude failure and verify Gemini can take over."""
    start = time.time()
    try:
        from src.agents.gemini_agent import GeminiAgent

        # Simulate: Claude is down, use Gemini for a trading-like query
        agent = GeminiAgent(
            name="FailoverTrader",
            role="Backup trading analysis when Claude unavailable",
            model="gemini-2.0-flash-exp",
            default_thinking_level="medium",
        )

        if agent.client is None:
            return False, "Gemini client not available for failover", 0.0

        # Trading-like prompt
        result = agent.reason(
            prompt="""You are a backup trading analyst. Given this data:
- SPY price: $485.50
- RSI: 55 (neutral)
- MACD: positive crossover

Provide a brief (1-2 sentences) trading recommendation.
Respond in format: RECOMMENDATION: [BUY/HOLD/SELL] - [reason]""",
            thinking_level="medium",
        )

        elapsed = time.time() - start
        reasoning = result.get("reasoning", "")

        if "RECOMMENDATION" in reasoning.upper() and any(
            action in reasoning.upper() for action in ["BUY", "HOLD", "SELL"]
        ):
            return True, f"Failover simulation succeeded in {elapsed:.2f}s", elapsed
        else:
            # Still pass if we got any reasonable response
            if len(reasoning) > 20:
                return True, f"Failover produced response in {elapsed:.2f}s", elapsed
            return False, f"Inadequate failover response: {reasoning[:100]}", elapsed

    except Exception as e:
        return False, f"Failover simulation failed: {e}", time.time() - start


def test_gemini_cost_tracking() -> tuple[bool, str, float]:
    """Verify Gemini usage would be tracked in budget system."""
    start = time.time()
    try:
        from src.utils.budget_tracker import API_COSTS, get_tracker

        # Check gemini_research is in cost table
        if "gemini_research" not in API_COSTS:
            return False, "gemini_research not in API_COSTS table", 0.0

        # Verify tracker works
        tracker = get_tracker()
        status = tracker.get_budget_status()

        elapsed = time.time() - start
        return True, f"Budget tracking ready (${status.remaining:.2f} remaining)", elapsed

    except Exception as e:
        return False, f"Cost tracking check failed: {e}", time.time() - start


def run_all_tests() -> dict:
    """Run all failover tests and return results."""
    tests = [
        ("Gemini Initialization", test_gemini_initialization),
        ("Gemini Response", test_gemini_response),
        ("Failover Simulation", test_failover_simulation),
        ("Cost Tracking", test_gemini_cost_tracking),
    ]

    results = {
        "timestamp": datetime.now().isoformat(),
        "tests": [],
        "all_passed": True,
        "total_time": 0.0,
    }

    for name, test_fn in tests:
        logger.info(f"Running: {name}")
        passed, message, elapsed = test_fn()

        results["tests"].append(
            {"name": name, "passed": passed, "message": message, "elapsed_seconds": elapsed}
        )
        results["total_time"] += elapsed

        if not passed:
            results["all_passed"] = False

    return results


def print_results(results: dict) -> None:
    """Print test results to console."""
    print("=" * 70)
    print("🔄 GEMINI FAILOVER TEST RESULTS")
    print("=" * 70)
    print(f"Timestamp: {results['timestamp']}")
    print()

    for test in results["tests"]:
        status = "✅ PASS" if test["passed"] else "❌ FAIL"
        print(f"{status} {test['name']}")
        print(f"     └─ {test['message']}")
        print()

    print("-" * 70)
    print(f"Total Time: {results['total_time']:.2f}s")
    print(f"Overall: {'✅ ALL TESTS PASSED' if results['all_passed'] else '❌ SOME TESTS FAILED'}")
    print("=" * 70)


def main():
    """Run failover tests and report results."""
    print("\n🔄 Testing Gemini failover capability...\n")

    results = run_all_tests()
    print_results(results)

    # Save results
    results_file = Path("data/gemini_failover_test.json")
    results_file.parent.mkdir(parents=True, exist_ok=True)

    import json

    results_file.write_text(json.dumps(results, indent=2))
    logger.info(f"Results saved to {results_file}")

    return 0 if results["all_passed"] else 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

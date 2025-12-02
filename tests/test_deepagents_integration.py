#!/usr/bin/env python3
"""
Test script to verify DeepAgents integration in the main trading loop.

This script:
1. Checks that DeepAgents adapter can be imported and initialized
2. Verifies the environment variable DEEPAGENTS_ENABLED is recognized
3. Tests the integration without executing actual trades
"""

import os
import sys
from pathlib import Path

# Add src directory to path
sys.path.insert(0, str(Path(__file__).parent))

from dotenv import load_dotenv

# Load environment
load_dotenv()


def test_deepagents_import():
    """Test that DeepAgents modules can be imported."""
    print("Testing DeepAgents imports...")
    try:
        from src.deepagents_integration.adapter import (  # noqa: F401
            create_analysis_agent_adapter,
            create_research_agent_adapter,
        )

        print("✅ DeepAgents adapter imports successful")
        return True
    except ImportError as e:
        print(f"❌ Failed to import DeepAgents adapter: {e}")
        return False


def test_environment_variable():
    """Test that DEEPAGENTS_ENABLED environment variable is recognized."""
    print("\nTesting DEEPAGENTS_ENABLED environment variable...")
    deepagents_enabled_env = os.getenv("DEEPAGENTS_ENABLED", "true").lower()
    deepagents_enabled = deepagents_enabled_env not in {"0", "false", "off", "no"}

    print(f"DEEPAGENTS_ENABLED={os.getenv('DEEPAGENTS_ENABLED', 'true')}")
    print(f"Interpreted as: {deepagents_enabled}")

    if deepagents_enabled:
        print("✅ DeepAgents is ENABLED")
    else:
        print("⚠️  DeepAgents is DISABLED")

    return True


def test_adapter_initialization():
    """Test that DeepAgents adapter can be initialized."""
    print("\nTesting DeepAgents adapter initialization...")
    try:
        from src.deepagents_integration.adapter import create_analysis_agent_adapter

        # This will attempt to create the adapter
        # May fail if dependencies are missing, which is OK for this test
        adapter = create_analysis_agent_adapter(agent_name="test-deepagents")
        print("✅ DeepAgents adapter initialized successfully")
        print(f"   Agent name: {adapter.agent_name}")
        return True
    except Exception as e:
        print(
            f"⚠️  DeepAgents adapter initialization failed (this is OK if dependencies are missing): {e}"
        )
        return False


def test_main_orchestrator_import():
    """Test that TradingOrchestrator can be imported with DeepAgents integration."""
    print("\nTesting TradingOrchestrator import...")
    try:
        from src.main import TradingOrchestrator  # noqa: F401

        print("✅ TradingOrchestrator imports successfully with DeepAgents integration")
        return True
    except ImportError as e:
        print(f"❌ Failed to import TradingOrchestrator: {e}")
        return False


def test_orchestrator_initialization():
    """Test that TradingOrchestrator can be initialized with DeepAgents."""
    print("\nTesting TradingOrchestrator initialization...")
    try:
        from src.main import TradingOrchestrator

        # Initialize in paper mode
        orchestrator = TradingOrchestrator(mode="paper")

        # Check if deepagents_adapter was initialized
        if hasattr(orchestrator, "deepagents_adapter"):
            if orchestrator.deepagents_adapter is not None:
                print("✅ TradingOrchestrator initialized with DeepAgents adapter")
                print(f"   Adapter type: {type(orchestrator.deepagents_adapter)}")
            else:
                print(
                    "⚠️  TradingOrchestrator initialized but DeepAgents adapter is None (may be disabled or failed)"
                )
        else:
            print("❌ TradingOrchestrator missing deepagents_adapter attribute")
            return False

        return True
    except Exception as e:
        print(f"❌ Failed to initialize TradingOrchestrator: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 80)
    print("DeepAgents Integration Test Suite")
    print("=" * 80)

    results = []

    # Run tests
    results.append(("Import DeepAgents adapter", test_deepagents_import()))
    results.append(("Environment variable", test_environment_variable()))
    results.append(("Adapter initialization", test_adapter_initialization()))
    results.append(("Import TradingOrchestrator", test_main_orchestrator_import()))
    results.append(("Initialize TradingOrchestrator", test_orchestrator_initialization()))

    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)

    passed = sum(1 for _, result in results if result)
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")

    print(f"\nPassed: {passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed! DeepAgents integration is working.")
        return 0
    else:
        print("\n⚠️  Some tests failed. Review the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())

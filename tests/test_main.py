#!/usr/bin/env python3
"""
Simple test script to verify main.py functionality.

Run this after installing dependencies:
    pip install -r requirements.txt
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))


def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")

    try:
        from main import TradingOrchestrator, setup_logging

        print("✓ Successfully imported TradingOrchestrator and setup_logging")

        from strategies.core_strategy import CoreStrategy

        print("✓ Successfully imported CoreStrategy")

        from strategies.growth_strategy import GrowthStrategy

        print("✓ Successfully imported GrowthStrategy")

        from strategies.ipo_strategy import IPOStrategy

        print("✓ Successfully imported IPOStrategy")

        print("\n✓ All imports successful!")
        return True

    except ImportError as e:
        print(f"\n✗ Import error: {e}")
        return False


def test_logger_setup():
    """Test logger setup."""
    print("\nTesting logger setup...")

    try:
        from main import setup_logging

        logger = setup_logging(log_dir="test_logs", log_level="INFO")
        logger.info("Test log message")
        print("✓ Logger setup successful")
        return True

    except Exception as e:
        print(f"✗ Logger setup error: {e}")
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("MAIN ORCHESTRATOR TEST")
    print("=" * 70)
    print()

    tests = [
        ("Imports", test_imports),
        ("Logger Setup", test_logger_setup),
    ]

    results = []
    for test_name, test_func in tests:
        result = test_func()
        results.append((test_name, result))
        print()

    # Summary
    print("=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {test_name}: {status}")

    all_passed = all(result for _, result in results)
    print()
    if all_passed:
        print("✓ All tests passed!")
        print("\nThe main orchestrator is ready to use.")
        print("\nNext steps:")
        print("  1. Copy .env.example to .env and configure your API keys")
        print("  2. Run: python src/main.py --mode paper --run-once")
        return 0
    else:
        print("✗ Some tests failed")
        print("\nMake sure to install dependencies:")
        print("  pip install -r requirements.txt")
        return 1


if __name__ == "__main__":
    sys.exit(main())

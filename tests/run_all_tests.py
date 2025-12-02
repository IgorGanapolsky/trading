#!/usr/bin/env python3
"""
Run All Tests

Runs complete test suite for trading system.
FREE - No API costs, local testing only.
"""

import os
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def run_test_file(test_file: Path):
    """Run a single test file."""
    print(f"\n{'=' * 70}")
    print(f"Running: {test_file.name}")
    print("=" * 70)

    try:
        # Import and run test module
        import importlib.util

        spec = importlib.util.spec_from_file_location("test_module", test_file)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # If module has a main function, run it
        if hasattr(module, "__main__") or hasattr(module, "main"):
            if hasattr(module, "main"):
                module.main()
            elif "__name__" in dir(module) and module.__name__ == "__main__":
                # Module runs tests on import
                pass

        return True
    except Exception as e:
        print(f"❌ Error running {test_file.name}: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 70)
    print("TRADING SYSTEM TEST SUITE")
    print("=" * 70)
    print()

    tests_dir = Path(__file__).parent
    test_files = list(tests_dir.glob("test_*.py"))

    if not test_files:
        print("⚠️  No test files found")
        return

    passed = 0
    failed = 0

    for test_file in sorted(test_files):
        if test_file.name == "__init__.py" or test_file.name == "run_all_tests.py":
            continue

        success = run_test_file(test_file)
        if success:
            passed += 1
        else:
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Total Tests: {len(test_files) - 2}")  # Exclude __init__ and run_all_tests
    print(f"Passed: {passed} ✅")
    print(f"Failed: {failed} ❌")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print(f"\n⚠️  {failed} test file(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())

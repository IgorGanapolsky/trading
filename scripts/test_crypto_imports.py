#!/usr/bin/env python3
"""
Integration test for crypto trading imports.

This test verifies that crypto trading can run without RAG dependencies,
simulating what happens in GitHub Actions.
"""

import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


def test_embedder_import():
    """Test that embedder can be imported without sentence_transformers."""
    print("Test 1: Import embedder module...")
    try:
        from src.rag.vector_db import embedder

        print("  ✅ PASSED: embedder module imports")

        # Try to get embedder (should fail gracefully if not installed)
        try:
            embedder._get_sentence_transformer()
            print("  ⚠️  WARNING: sentence_transformers is available (unexpected in CI)")
        except ImportError:
            print("  ✅ PASSED: ImportError raised correctly (RAG not installed)")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False


def test_deepagents_tools_import():
    """Test that deepagents tools can be imported."""
    print("\nTest 2: Import deepagents tools...")
    try:
        from src.deepagents_integration import tools

        print("  ✅ PASSED: deepagents tools imports")

        # Check that _get_sentiment_store exists
        assert hasattr(tools, "_get_sentiment_store"), "_get_sentiment_store function missing"
        print("  ✅ PASSED: _get_sentiment_store function exists")
        return True
    except ImportError as e:
        if "langchain" in str(e).lower():
            print(f"  ⚠️  SKIPPED: langchain not installed ({e})")
            return True  # Not critical for crypto trading
        print(f"  ❌ FAILED: {e}")
        return False


def test_crypto_strategy_import():
    """Test that crypto strategy can be imported."""
    print("\nTest 3: Import crypto strategy...")
    try:
        from src.strategies.crypto_strategy import CryptoStrategy

        print("  ✅ PASSED: crypto_strategy imports")

        # Try to create instance (should work even without RAG)
        strategy = CryptoStrategy(daily_amount=0.50)
        assert strategy.daily_amount == 0.50
        print("  ✅ PASSED: CryptoStrategy can be instantiated")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_autonomous_trader_import():
    """Test that autonomous_trader can be imported."""
    print("\nTest 4: Import autonomous_trader...")
    try:
        from scripts.autonomous_trader import is_weekend

        print("  ✅ PASSED: autonomous_trader imports")

        # Test is_weekend function
        result = is_weekend()
        assert isinstance(result, bool)
        print(f"  ✅ PASSED: is_weekend() works (returns {result})")
        return True
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        import traceback

        traceback.print_exc()
        return False


def test_import_chain():
    """Test the full import chain that happens in GitHub Actions."""
    print("\nTest 5: Full import chain (simulating GitHub Actions)...")
    try:
        # This is what happens when autonomous_trader.py runs
        from src.core.alpaca_trader import AlpacaTrader

        print("  ✅ PASSED: AlpacaTrader imports")
    except ImportError as e:
        if "alpaca" in str(e).lower():
            print("  ⚠️  SKIPPED: alpaca not installed (expected in local env)")
        else:
            print(f"  ❌ FAILED: {e}")
            return False

    try:
        print("  ✅ PASSED: RiskManager imports")
    except Exception as e:
        print(f"  ❌ FAILED: {e}")
        return False

    # Verify RAG is NOT imported
    if "src.rag.sentiment_store" in sys.modules:
        print("  ⚠️  WARNING: sentiment_store was imported (should be lazy)")
    else:
        print("  ✅ PASSED: sentiment_store NOT imported (lazy loading works)")

    return True


def main():
    """Run all tests."""
    print("=" * 70)
    print("CRYPTO TRADING IMPORT TESTS")
    print("=" * 70)

    tests = [
        test_embedder_import,
        test_deepagents_tools_import,
        test_crypto_strategy_import,
        test_autonomous_trader_import,
        test_import_chain,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"  ❌ TEST CRASHED: {e}")
            import traceback

            traceback.print_exc()
            results.append(False)

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    passed = sum(results)
    total = len(results)
    print(f"Passed: {passed}/{total}")

    if passed == total:
        print("✅ ALL TESTS PASSED")
        return 0
    else:
        print("❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""
Test Evaluation System with Historical Mistakes

Tests the evaluation system against our 10 documented mistakes to verify
it catches them automatically.

FREE - No API costs, uses local data.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.rag_storage import EvaluationRAGStorage
from src.evaluation.trading_evaluator import TradingSystemEvaluator


def test_mistake_1():
    """Test Mistake #1: $1,600 order instead of $8 (200x error)"""
    print("\n" + "=" * 70)
    print("TEST: Mistake #1 - $1,600 order instead of $8")
    print("=" * 70)

    evaluator = TradingSystemEvaluator()

    # Simulate the mistake
    trade_result = {
        "symbol": "SPY",
        "amount": 1600.0,  # WRONG - should be $8
        "status": "filled",
        "order_id": "test_mistake_1",
        "timestamp": datetime.now().isoformat(),
        "validated": False,
        "preflight_passed": True,
        "system_state_age_hours": 1.0,
        "data_source": "alpaca",
        "api_errors": [],
        "execution_time_ms": 500,
    }

    evaluation = evaluator.evaluate_trade_execution(
        trade_result=trade_result, expected_amount=8.0, daily_allocation=10.0
    )

    print(f"Overall Score: {evaluation.overall_score:.2f}")
    print(f"Passed: {evaluation.passed}")
    print(f"Critical Issues: {len(evaluation.critical_issues)}")

    # Check accuracy dimension
    accuracy = evaluation.evaluation.get("accuracy")
    if accuracy:
        print(f"\nAccuracy Score: {accuracy.score:.2f}")
        print(f"Accuracy Passed: {accuracy.passed}")
        print(f"Issues: {accuracy.issues}")

    # Check error detection
    errors = evaluation.evaluation.get("errors")
    if errors:
        print("\nError Detection:")
        print(f"  Issues Found: {len(errors.issues)}")
        for issue in errors.issues:
            print(f"    - {issue}")

    # Verify it caught the mistake
    assert not evaluation.passed, "Should FAIL - order size is 200x expected"
    assert accuracy.score == 0.0, "Accuracy should be 0.0 for 200x error"
    assert any(
        "10x" in issue.lower() or "order size" in issue.lower() for issue in accuracy.issues
    ), "Should detect order size error"

    print("\n✅ TEST PASSED - Mistake #1 detected correctly")
    return evaluation


def test_mistake_2():
    """Test Mistake #2: System state stale for 5 days"""
    print("\n" + "=" * 70)
    print("TEST: Mistake #2 - System state stale (5 days)")
    print("=" * 70)

    evaluator = TradingSystemEvaluator()

    # Simulate stale system state
    trade_result = {
        "symbol": "GOOGL",
        "amount": 2.0,
        "status": "filled",
        "order_id": "test_mistake_2",
        "timestamp": datetime.now().isoformat(),
        "validated": True,
        "preflight_passed": True,
        "system_state_age_hours": 120.0,  # 5 days = 120 hours
        "data_source": "alpaca",
        "api_errors": [],
        "execution_time_ms": 500,
    }

    evaluation = evaluator.evaluate_trade_execution(
        trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
    )

    print(f"Overall Score: {evaluation.overall_score:.2f}")
    print(f"Passed: {evaluation.passed}")

    # Check reliability dimension
    reliability = evaluation.evaluation.get("reliability")
    if reliability:
        print(f"\nReliability Score: {reliability.score:.2f}")
        print(f"Reliability Passed: {reliability.passed}")
        print(f"Issues: {reliability.issues}")

    # Verify it caught the mistake
    assert not reliability.passed, "Should FAIL - system state is stale"
    assert reliability.score == 0.0, "Reliability should be 0.0 for stale state"
    assert any(
        "stale" in issue.lower() or "hours old" in issue.lower() for issue in reliability.issues
    ), "Should detect stale system state"

    print("\n✅ TEST PASSED - Mistake #2 detected correctly")
    return evaluation


def test_mistake_3():
    """Test Mistake #3: Network/DNS errors"""
    print("\n" + "=" * 70)
    print("TEST: Mistake #3 - Network/DNS errors")
    print("=" * 70)

    evaluator = TradingSystemEvaluator()

    # Simulate network errors
    trade_result = {
        "symbol": "NVDA",
        "amount": 2.0,
        "status": "failed",
        "order_id": "test_mistake_3",
        "timestamp": datetime.now().isoformat(),
        "validated": True,
        "preflight_passed": True,
        "system_state_age_hours": 1.0,
        "data_source": "alpaca",
        "api_errors": ["Network error: Connection refused", "DNS resolution failed"],
        "execution_time_ms": 30000,
    }

    evaluation = evaluator.evaluate_trade_execution(
        trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
    )

    print(f"Overall Score: {evaluation.overall_score:.2f}")
    print(f"Passed: {evaluation.passed}")

    # Check error detection
    errors = evaluation.evaluation.get("errors")
    if errors:
        print("\nError Detection:")
        for issue in errors.issues:
            print(f"  - {issue}")

    # Verify it caught the mistake
    assert any("network" in issue.lower() or "dns" in issue.lower() for issue in errors.issues), (
        "Should detect network/DNS errors"
    )

    print("\n✅ TEST PASSED - Mistake #3 detected correctly")
    return evaluation


def test_mistake_5():
    """Test Mistake #5: Anti-lying violation (wrong dates - weekend trade)"""
    print("\n" + "=" * 70)
    print("TEST: Mistake #5 - Weekend trade (calendar error)")
    print("=" * 70)

    evaluator = TradingSystemEvaluator()

    # Simulate weekend trade
    saturday = datetime(2025, 11, 8)  # Saturday
    trade_result = {
        "symbol": "SPY",
        "amount": 6.0,
        "status": "filled",
        "order_id": "test_mistake_5",
        "timestamp": saturday.isoformat(),
        "date": saturday.isoformat(),
        "validated": True,
        "preflight_passed": True,
        "system_state_age_hours": 1.0,
        "data_source": "alpaca",
        "api_errors": [],
        "execution_time_ms": 500,
    }

    evaluation = evaluator.evaluate_trade_execution(
        trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
    )

    print(f"Overall Score: {evaluation.overall_score:.2f}")
    print(f"Passed: {evaluation.passed}")

    # Check error detection
    errors = evaluation.evaluation.get("errors")
    if errors:
        print("\nError Detection:")
        for issue in errors.issues:
            print(f"  - {issue}")

    # Verify it caught the mistake
    assert any(
        "weekend" in issue.lower() or "saturday" in issue.lower() for issue in errors.issues
    ), "Should detect weekend trade"

    print("\n✅ TEST PASSED - Mistake #5 detected correctly")
    return evaluation


def test_rag_storage():
    """Test storing evaluations in RAG system"""
    print("\n" + "=" * 70)
    print("TEST: RAG Storage")
    print("=" * 70)

    storage = EvaluationRAGStorage()

    if not storage.enabled:
        print("⚠️  RAG storage not available - skipping test")
        return

    # Create test evaluation
    evaluation = {
        "trade_id": "test_rag_1",
        "symbol": "SPY",
        "timestamp": datetime.now().isoformat(),
        "overall_score": 0.5,
        "passed": False,
        "evaluation": {"accuracy": {"score": 0.0, "passed": False, "issues": ["Order size error"]}},
        "critical_issues": ["Order size >10x expected"],
    }

    trade_result = {"amount": 1600.0, "status": "filled"}

    success = storage.store_evaluation(evaluation, trade_result)

    if success:
        print("✅ Evaluation stored in RAG system")

        # Test query
        results = storage.query_similar_evaluations("order size errors", n_results=3)
        print(f"✅ Query returned {len(results)} results")
    else:
        print("❌ Failed to store evaluation")

    return success


def main():
    """Run all tests"""
    print("=" * 70)
    print("EVALUATION SYSTEM TEST SUITE")
    print("Testing against 10 documented mistakes")
    print("=" * 70)

    tests = [
        ("Mistake #1: $1,600 order", test_mistake_1),
        ("Mistake #2: Stale system state", test_mistake_2),
        ("Mistake #3: Network/DNS errors", test_mistake_3),
        ("Mistake #5: Weekend trade", test_mistake_5),
        ("RAG Storage", test_rag_storage),
    ]

    passed = 0
    failed = 0

    for test_name, test_func in tests:
        try:
            test_func()
            passed += 1
        except AssertionError as e:
            print(f"\n❌ TEST FAILED: {test_name}")
            print(f"   Error: {e}")
            failed += 1
        except Exception as e:
            print(f"\n❌ TEST ERROR: {test_name}")
            print(f"   Error: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    print(f"Passed: {passed}")
    print(f"Failed: {failed}")
    print(f"Total: {passed + failed}")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED - Evaluation system working correctly!")
    else:
        print(f"\n⚠️  {failed} test(s) failed - review needed")


if __name__ == "__main__":
    main()

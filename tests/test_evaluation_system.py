"""
Test Suite for Trading System Evaluator

Tests evaluation system against documented mistakes to ensure
they are caught automatically.

FREE - No API costs, local testing only.
"""

import os
import sys
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.trading_evaluator import TradingSystemEvaluator


class TestEvaluationSystem:
    """Test suite for evaluation system."""

    def setup_method(self):
        """Set up test fixtures."""
        self.evaluator = TradingSystemEvaluator()

    def test_mistake_1_order_size_error(self):
        """Test Mistake #1: $1,600 order instead of $8 (200x error)"""
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

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=8.0, daily_allocation=10.0
        )

        assert not evaluation.passed, "Should FAIL - order size is 200x expected"
        accuracy = evaluation.evaluation.get("accuracy")
        assert accuracy.score == 0.0, "Accuracy should be 0.0 for 200x error"
        assert any(
            "10x" in issue.lower() or "order size" in issue.lower() for issue in accuracy.issues
        ), "Should detect order size error"

    def test_mistake_2_stale_system_state(self):
        """Test Mistake #2: System state stale for 5 days"""
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

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
        )

        reliability = evaluation.evaluation.get("reliability")
        assert not reliability.passed, "Should FAIL - system state is stale"
        assert reliability.score == 0.0, "Reliability should be 0.0 for stale state"
        assert any(
            "stale" in issue.lower() or "hours old" in issue.lower() for issue in reliability.issues
        ), "Should detect stale system state"

    def test_mistake_3_network_errors(self):
        """Test Mistake #3: Network/DNS errors"""
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
            "api_errors": [
                "Network error: Connection refused",
                "DNS resolution failed",
            ],
            "execution_time_ms": 30000,
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
        )

        errors = evaluation.evaluation.get("errors")
        assert any(
            "network" in issue.lower() or "dns" in issue.lower() for issue in errors.issues
        ), "Should detect network/DNS errors"

    def test_mistake_5_weekend_trade(self):
        """Test Mistake #5: Anti-lying violation (wrong dates - weekend trade)"""
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

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        errors = evaluation.evaluation.get("errors")
        assert any(
            "weekend" in issue.lower() or "saturday" in issue.lower() for issue in errors.issues
        ), "Should detect weekend trade"

    def test_valid_trade_passes(self):
        """Test that valid trades pass evaluation"""
        trade_result = {
            "symbol": "SPY",
            "amount": 6.0,
            "status": "filled",
            "order_id": "test_valid",
            "timestamp": datetime.now().isoformat(),
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
            "api_errors": [],
            "execution_time_ms": 500,
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        assert evaluation.passed, "Valid trade should pass"
        assert evaluation.overall_score >= 0.7, "Valid trade should score >= 0.7"
        assert len(evaluation.critical_issues) == 0, "Valid trade should have no critical issues"

    def test_evaluation_save_and_load(self):
        """Test that evaluations can be saved and loaded"""
        trade_result = {
            "symbol": "QQQ",
            "amount": 6.0,
            "status": "filled",
            "order_id": "test_save",
            "timestamp": datetime.now().isoformat(),
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
            "api_errors": [],
            "execution_time_ms": 500,
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        # Save evaluation
        eval_file = self.evaluator.save_evaluation(evaluation)
        assert eval_file.exists(), "Evaluation file should be created"

        # Verify file contains evaluation
        import json

        with open(eval_file) as f:
            evaluations = json.load(f)
        assert len(evaluations) > 0, "Evaluation file should contain data"
        assert evaluations[-1]["trade_id"] == evaluation.trade_id, "Saved evaluation should match"


def run_tests():
    """Run all tests."""
    import pytest

    # Run tests
    pytest.main([__file__, "-v"])


if __name__ == "__main__":
    # Simple test runner (no pytest required)
    test_suite = TestEvaluationSystem()
    test_suite.setup_method()

    tests = [
        ("Mistake #1: Order Size Error", test_suite.test_mistake_1_order_size_error),
        (
            "Mistake #2: Stale System State",
            test_suite.test_mistake_2_stale_system_state,
        ),
        ("Mistake #3: Network Errors", test_suite.test_mistake_3_network_errors),
        ("Mistake #5: Weekend Trade", test_suite.test_mistake_5_weekend_trade),
        ("Valid Trade Passes", test_suite.test_valid_trade_passes),
        ("Evaluation Save/Load", test_suite.test_evaluation_save_and_load),
    ]

    passed = 0
    failed = 0

    print("=" * 70)
    print("RUNNING TEST SUITE")
    print("=" * 70)
    print()

    for test_name, test_func in tests:
        try:
            test_func()
            print(f"✅ {test_name}")
            passed += 1
        except AssertionError as e:
            print(f"❌ {test_name}: {e}")
            failed += 1
        except Exception as e:
            print(f"❌ {test_name}: {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print()
    print("=" * 70)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 70)

    if failed == 0:
        print("\n✅ ALL TESTS PASSED!")
    else:
        print(f"\n⚠️  {failed} test(s) failed")

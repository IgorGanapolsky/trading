"""
Critical Trading System Tests

Tests for the most critical functions that prevent mistakes.
FREE - No API costs, local testing only.
"""

import os
import sys
import unittest
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.evaluation.trading_evaluator import TradingSystemEvaluator


class TestOrderValidation(unittest.TestCase):
    """Test order size validation (prevents Mistake #1: $1,600 order)"""

    def setUp(self):
        self.evaluator = TradingSystemEvaluator()

    def test_order_size_10x_error_detected(self):
        """Test that orders >10x expected are detected."""
        trade_result = {
            "symbol": "SPY",
            "amount": 1600.0,  # 200x expected
            "status": "filled",
            "order_id": "test_1",
            "timestamp": datetime.now().isoformat(),
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=8.0, daily_allocation=10.0
        )

        # Should fail
        self.assertFalse(evaluation.passed)
        self.assertEqual(evaluation.overall_score, 0.45)  # Low score

        # Accuracy should be 0.0
        accuracy = evaluation.evaluation.get("accuracy")
        self.assertIsNotNone(accuracy)
        self.assertEqual(accuracy.score, 0.0)
        self.assertFalse(accuracy.passed)

        # Should detect error pattern
        errors = evaluation.evaluation.get("errors")
        self.assertIsNotNone(errors)
        self.assertTrue(any("ERROR PATTERN #1" in issue for issue in errors.issues))

    def test_normal_order_passes(self):
        """Test that normal orders pass validation."""
        trade_result = {
            "symbol": "SPY",
            "amount": 6.0,  # Normal amount
            "status": "filled",
            "order_id": "test_2",
            "timestamp": datetime.now().isoformat(),
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        # Should pass
        self.assertTrue(evaluation.passed)
        self.assertGreater(evaluation.overall_score, 0.8)


class TestStalenessDetection(unittest.TestCase):
    """Test system state staleness detection (prevents Mistake #2)"""

    def setUp(self):
        self.evaluator = TradingSystemEvaluator()

    def test_stale_system_state_detected(self):
        """Test that stale system state (>24h) is detected."""
        trade_result = {
            "symbol": "GOOGL",
            "amount": 2.0,
            "status": "filled",
            "order_id": "test_3",
            "timestamp": datetime.now().isoformat(),
            "system_state_age_hours": 120.0,  # 5 days old
            "validated": True,
            "preflight_passed": True,
            "data_source": "alpaca",
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
        )

        # Should fail reliability check
        reliability = evaluation.evaluation.get("reliability")
        self.assertIsNotNone(reliability)
        self.assertEqual(reliability.score, 0.0)
        self.assertFalse(reliability.passed)

        # Should detect error pattern
        errors = evaluation.evaluation.get("errors")
        self.assertTrue(any("ERROR PATTERN #2" in issue for issue in errors.issues))


class TestErrorPatternDetection(unittest.TestCase):
    """Test error pattern detection (all 5 patterns)"""

    def setUp(self):
        self.evaluator = TradingSystemEvaluator()

    def test_network_error_detected(self):
        """Test that network/DNS errors are detected."""
        trade_result = {
            "symbol": "NVDA",
            "amount": 2.0,
            "status": "failed",
            "order_id": "test_4",
            "timestamp": datetime.now().isoformat(),
            "api_errors": [
                "Network error: Connection refused",
                "DNS resolution failed",
            ],
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=2.0, daily_allocation=10.0
        )

        errors = evaluation.evaluation.get("errors")
        self.assertTrue(any("ERROR PATTERN #3" in issue for issue in errors.issues))

    def test_weekend_trade_detected(self):
        """Test that weekend trades are detected."""
        saturday = datetime(2025, 11, 8)  # Saturday
        trade_result = {
            "symbol": "SPY",
            "amount": 6.0,
            "status": "filled",
            "order_id": "test_5",
            "timestamp": saturday.isoformat(),
            "date": saturday.isoformat(),
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        errors = evaluation.evaluation.get("errors")
        self.assertTrue(any("ERROR PATTERN #5" in issue for issue in errors.issues))


class TestEvaluationStorage(unittest.TestCase):
    """Test evaluation storage and retrieval"""

    def setUp(self):
        self.evaluator = TradingSystemEvaluator()
        # Use temporary directory for tests
        import tempfile

        self.temp_dir = Path(tempfile.mkdtemp())
        self.evaluator.data_dir = self.temp_dir
        self.evaluator.eval_dir = self.temp_dir / "evaluations"
        self.evaluator.eval_dir.mkdir(exist_ok=True)

    def test_evaluation_saved(self):
        """Test that evaluations are saved correctly."""
        trade_result = {
            "symbol": "SPY",
            "amount": 6.0,
            "status": "filled",
            "order_id": "test_save",
            "timestamp": datetime.now().isoformat(),
            "validated": True,
            "preflight_passed": True,
            "system_state_age_hours": 1.0,
            "data_source": "alpaca",
        }

        evaluation = self.evaluator.evaluate_trade_execution(
            trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
        )

        # Save evaluation
        eval_file = self.evaluator.save_evaluation(evaluation)

        # Verify file exists
        self.assertTrue(eval_file.exists())

        # Verify content
        import json

        with open(eval_file) as f:
            saved_evaluations = json.load(f)

        self.assertEqual(len(saved_evaluations), 1)
        self.assertEqual(saved_evaluations[0]["trade_id"], evaluation.trade_id)
        self.assertEqual(saved_evaluations[0]["symbol"], "SPY")

    def test_evaluation_summary(self):
        """Test evaluation summary generation."""
        # Create test evaluations
        for i in range(3):
            trade_result = {
                "symbol": "SPY",
                "amount": 6.0,
                "status": "filled",
                "order_id": f"test_summary_{i}",
                "timestamp": datetime.now().isoformat(),
                "validated": True,
                "preflight_passed": True,
                "system_state_age_hours": 1.0,
                "data_source": "alpaca",
            }

            evaluation = self.evaluator.evaluate_trade_execution(
                trade_result=trade_result, expected_amount=6.0, daily_allocation=10.0
            )

            self.evaluator.save_evaluation(evaluation)

        # Get summary
        summary = self.evaluator.get_evaluation_summary(days=7)

        self.assertEqual(summary["total_evaluations"], 3)
        self.assertEqual(summary["passed"], 3)
        self.assertEqual(summary["failed"], 0)
        self.assertGreater(summary["avg_score"], 0.8)


if __name__ == "__main__":
    unittest.main()

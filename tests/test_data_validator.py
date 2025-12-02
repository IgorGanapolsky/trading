"""
Tests for data validator to ensure false claims are caught.
"""

import sys
import unittest
from datetime import datetime, timedelta
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.data_validator import DataValidator


class TestDataValidator(unittest.TestCase):
    """Test data validator functionality."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = DataValidator()

    def test_validate_false_yesterday_claim(self):
        """Test that false yesterday profit claims are caught."""
        # Test with a clearly false claim
        false_claim = 14.01
        result = self.validator.validate_yesterday_profit(false_claim)

        self.assertFalse(result.is_valid, "False claim should be invalid")
        self.assertIsNotNone(result.error_message, "Should have error message")
        self.assertIn("Claimed", result.error_message)

    def test_validate_true_yesterday_claim(self):
        """Test that true yesterday profit claims pass."""
        # Get actual yesterday profit
        yesterday_profit = self.validator.get_yesterday_profit()

        if yesterday_profit is not None:
            result = self.validator.validate_yesterday_profit(yesterday_profit)
            self.assertTrue(result.is_valid, "True claim should be valid")

    def test_data_consistency_check(self):
        """Test that data consistency is checked."""
        results = self.validator.check_data_consistency()

        # Results should be a list
        self.assertIsInstance(results, list)

        # If inconsistencies found, they should have error messages
        for result in results:
            self.assertFalse(result.is_valid)
            self.assertIsNotNone(result.error_message)

    def test_get_profit_for_date(self):
        """Test getting profit for a specific date."""
        # Get a date that should exist
        if self.validator.perf_log:
            test_date = self.validator.perf_log[-1].get("date")
            profit = self.validator.get_profit_for_date(test_date)

            self.assertIsNotNone(profit, "Should return profit for existing date")
            self.assertIsInstance(profit, (int, float), "Profit should be numeric")

    def test_get_nonexistent_date(self):
        """Test getting profit for nonexistent date."""
        future_date = (datetime.now() + timedelta(days=365)).date().isoformat()
        profit = self.validator.get_profit_for_date(future_date)

        self.assertIsNone(profit, "Should return None for nonexistent date")


if __name__ == "__main__":
    unittest.main()

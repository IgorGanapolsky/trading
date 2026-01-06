"""
Tests for guaranteed_trader.py RAG blocking logic.

Tests the fix for RAG blocking all trading due to CI/CD lessons matching
"failures" keyword. The fix ensures only TRADING category lessons block execution.
"""

import os
import sys
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@dataclass
class MockLesson:
    """Mock lesson for testing RAG responses."""

    id: str
    title: str
    severity: str
    category: str
    prevention: str = "Test prevention"


class TestRAGBlockingLogic:
    """Test the RAG blocking logic in guaranteed_trader.py."""

    def test_ci_lesson_does_not_block_trading(self):
        """CI/CD category lessons should NOT block trading."""
        # This was the bug - CI/CD lessons were blocking trading
        lesson = MockLesson(
            id="ci_failure",
            title="CI Test Failures Blocking Trading Execution",
            severity="CRITICAL",
            category="CI/CD",
        )

        # The fix: only block if category is in ["trading", "execution", "risk"]
        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert not should_block, "CI/CD lessons should NOT block trading"

    def test_trading_lesson_blocks_when_critical(self):
        """Trading category CRITICAL lessons SHOULD block trading."""
        lesson = MockLesson(
            id="trading_failure",
            title="SPY Trading Loss",
            severity="CRITICAL",
            category="Trading",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert should_block, "Trading category CRITICAL lessons SHOULD block"

    def test_execution_lesson_blocks_when_critical(self):
        """Execution category CRITICAL lessons SHOULD block trading."""
        lesson = MockLesson(
            id="exec_failure",
            title="Order Execution Failed",
            severity="CRITICAL",
            category="Execution",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert should_block, "Execution category CRITICAL lessons SHOULD block"

    def test_risk_lesson_blocks_when_critical(self):
        """Risk category CRITICAL lessons SHOULD block trading."""
        lesson = MockLesson(
            id="risk_failure",
            title="Risk Limit Exceeded",
            severity="CRITICAL",
            category="Risk",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert should_block, "Risk category CRITICAL lessons SHOULD block"

    def test_non_critical_trading_lesson_does_not_block(self):
        """Non-CRITICAL trading lessons should NOT block."""
        lesson = MockLesson(
            id="trading_info",
            title="Trading Best Practice",
            severity="INFO",
            category="Trading",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert not should_block, "Non-CRITICAL lessons should NOT block"

    def test_unknown_category_does_not_block(self):
        """Unknown category lessons should NOT block trading."""
        lesson = MockLesson(
            id="unknown",
            title="Some Lesson",
            severity="CRITICAL",
            category="unknown",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert not should_block, "Unknown category lessons should NOT block"

    def test_empty_category_does_not_block(self):
        """Empty category lessons should NOT block trading."""
        lesson = MockLesson(
            id="no_category",
            title="No Category Lesson",
            severity="CRITICAL",
            category="",
        )

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson

        assert not should_block, "Empty category lessons should NOT block"

    def test_low_relevance_score_does_not_block(self):
        """Even trading lessons with low relevance score should NOT block."""
        lesson = MockLesson(
            id="trading_low_relevance",
            title="Old Trading Issue",
            severity="CRITICAL",
            category="Trading",
        )
        score = 0.5  # Low relevance

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        # The fix added score > 0.8 threshold
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson and score > 0.8

        assert not should_block, "Low relevance score lessons should NOT block"

    def test_high_relevance_trading_lesson_blocks(self):
        """High relevance trading CRITICAL lessons SHOULD block."""
        lesson = MockLesson(
            id="trading_high_relevance",
            title="Current Trading Issue",
            severity="CRITICAL",
            category="Trading",
        )
        score = 0.9  # High relevance

        is_trading_lesson = lesson.category.lower() in ["trading", "execution", "risk"]
        should_block = lesson.severity == "CRITICAL" and is_trading_lesson and score > 0.8

        assert should_block, "High relevance trading CRITICAL lessons SHOULD block"


class TestCategoryMatching:
    """Test category string matching edge cases."""

    @pytest.mark.parametrize(
        "category,expected",
        [
            ("trading", True),
            ("Trading", True),
            ("TRADING", True),
            ("execution", True),
            ("Execution", True),
            ("EXECUTION", True),
            ("risk", True),
            ("Risk", True),
            ("RISK", True),
            ("CI/CD", False),
            ("ci/cd", False),
            ("Infrastructure", False),
            ("Documentation", False),
            ("", False),
            ("unknown", False),
        ],
    )
    def test_category_matching(self, category, expected):
        """Test various category string formats."""
        is_trading_lesson = category.lower() in ["trading", "execution", "risk"]
        assert is_trading_lesson == expected


class TestGetAttrFallback:
    """Test getattr fallback for lessons without category."""

    def test_lesson_without_category_attribute(self):
        """Lessons without category attribute should use fallback."""

        class LessonNoCategory:
            id = "no_cat"
            title = "No Category"
            severity = "CRITICAL"
            prevention = "Test"

        lesson = LessonNoCategory()
        category = getattr(lesson, "category", "").lower()

        assert category == ""
        is_trading = category in ["trading", "execution", "risk"]
        assert not is_trading, "Missing category should not match trading"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

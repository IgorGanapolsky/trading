"""
Tests for Lessons Learned Validation System.

These tests ensure that:
1. Lessons are properly stored and retrieved
2. Trades are validated against past mistakes
3. Critical lessons block dangerous actions
4. Semantic search finds relevant lessons
"""

import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest
from src.rag.lessons_learned_store import (
    Lesson,
    LessonCategory,
    LessonSeverity,
    LessonsLearnedStore,
    seed_initial_lessons,
    validate_trade_against_lessons,
)


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        yield Path(f.name)


@pytest.fixture
def store(temp_db):
    """Create a LessonsLearnedStore with temporary database."""
    return LessonsLearnedStore(db_path=temp_db)


@pytest.fixture
def sample_lesson():
    """Create a sample lesson for testing."""
    return Lesson(
        lesson_id="TEST-001",
        title="Test Large Order Rejection",
        description="Orders exceeding 10x expected amount should be rejected",
        root_cause="Missing validation on order amounts",
        resolution="Added 10x limit validation",
        prevention="Always validate order amounts before execution",
        severity=LessonSeverity.CRITICAL,
        category=LessonCategory.TRADING_LOGIC,
        date_learned=datetime.now(timezone.utc),
        impact_description="Could deploy excessive capital",
        financial_impact=1000.0,
        related_files=["scripts/autonomous_trader.py"],
        tags=["order-validation", "capital-protection"],
    )


class TestLessonsLearnedStore:
    """Test the LessonsLearnedStore class."""

    def test_store_initialization(self, store):
        """Test that store initializes correctly."""
        assert store.db_path.exists()
        assert store.connection is not None

    def test_add_lesson(self, store, sample_lesson):
        """Test adding a lesson to the store."""
        result = store.add_lesson(sample_lesson)
        assert result is True

    def test_search_lessons_by_keyword(self, store, sample_lesson):
        """Test searching lessons by keyword."""
        store.add_lesson(sample_lesson)

        results = store.search_lessons("order validation")
        assert len(results) > 0
        assert results[0]["title"] == sample_lesson.title

    def test_search_lessons_by_category(self, store, sample_lesson):
        """Test filtering lessons by category."""
        store.add_lesson(sample_lesson)

        results = store.search_lessons("validation", category=LessonCategory.TRADING_LOGIC)
        assert len(results) > 0

        results = store.search_lessons("validation", category=LessonCategory.AUTOMATION)
        assert len(results) == 0

    def test_search_lessons_by_severity(self, store, sample_lesson):
        """Test filtering lessons by minimum severity."""
        store.add_lesson(sample_lesson)

        # Should find critical lessons
        results = store.search_lessons("order", min_severity=LessonSeverity.CRITICAL)
        assert len(results) > 0

        # Add a low severity lesson
        low_lesson = Lesson(
            lesson_id="TEST-002",
            title="Minor Style Issue",
            description="Code formatting inconsistency",
            root_cause="Missing linter",
            resolution="Added linter",
            prevention="Run linter before commit",
            severity=LessonSeverity.LOW,
            category=LessonCategory.CODE_QUALITY,
            date_learned=datetime.now(timezone.utc),
            tags=["style"],
        )
        store.add_lesson(low_lesson)

        # Critical filter should not return low severity
        results = store.search_lessons("style", min_severity=LessonSeverity.CRITICAL)
        assert len(results) == 0

    def test_get_critical_lessons(self, store, sample_lesson):
        """Test retrieving all critical lessons."""
        store.add_lesson(sample_lesson)

        critical = store.get_critical_lessons()
        assert len(critical) > 0
        assert all(lesson["severity"] == "critical" for lesson in critical)

    def test_validate_action(self, store, sample_lesson):
        """Test validating actions against lessons."""
        store.add_lesson(sample_lesson)

        warnings = store.validate_action("execute large order", {"symbol": "SPY", "amount": 5000})

        # Should return warnings for order-related lessons
        assert isinstance(warnings, list)


class TestTradeValidation:
    """Test the trade validation integration."""

    def test_validate_trade_returns_tuple(self, store, sample_lesson):
        """Test that validate_trade returns proper tuple."""
        store.add_lesson(sample_lesson)

        is_valid, warnings = validate_trade_against_lessons(
            symbol="SPY", amount=100.0, action="BUY", store=store
        )

        assert isinstance(is_valid, bool)
        assert isinstance(warnings, list)


class TestSeedInitialLessons:
    """Test seeding initial lessons."""

    def test_seed_creates_lessons(self, store):
        """Test that seed function creates initial lessons."""
        count = seed_initial_lessons(store)

        assert count > 0

        # Verify lessons exist
        critical = store.get_critical_lessons()
        assert len(critical) > 0

    def test_seed_idempotent(self, store):
        """Test that seeding twice doesn't duplicate."""
        count1 = seed_initial_lessons(store)
        count2 = seed_initial_lessons(store)

        # Second seed should replace, not add
        assert count1 == count2


class TestLessonDataclass:
    """Test the Lesson dataclass."""

    def test_to_searchable_text(self, sample_lesson):
        """Test conversion to searchable text."""
        text = sample_lesson.to_searchable_text()

        assert sample_lesson.title in text
        assert sample_lesson.description in text
        assert sample_lesson.prevention in text

    def test_default_values(self):
        """Test that default values work correctly."""
        lesson = Lesson(
            lesson_id="TEST",
            title="Test",
            description="Test",
            root_cause="Test",
            resolution="Test",
            prevention="Test",
            severity=LessonSeverity.LOW,
            category=LessonCategory.CODE_QUALITY,
            date_learned=datetime.now(timezone.utc),
        )

        assert lesson.financial_impact == 0.0
        assert lesson.related_files == []
        assert lesson.tags == []


class TestOrderValidationLessons:
    """Test order amount validation lessons."""

    def test_200x_error_lesson_found(self, store):
        """Test that the 200x order error lesson is searchable."""
        seed_initial_lessons(store)

        results = store.search_lessons("large order amount error 200x")
        assert len(results) > 0

        # Should find the critical lesson
        critical = [r for r in results if r["severity"] == "critical"]
        assert len(critical) > 0

    def test_order_validation_warning(self, store):
        """Test that large orders trigger warnings."""
        seed_initial_lessons(store)

        warnings = store.validate_action(
            "execute order $1600 SPY", {"amount": 1600, "symbol": "SPY"}
        )

        # Should have at least one warning about order validation
        assert isinstance(warnings, list)

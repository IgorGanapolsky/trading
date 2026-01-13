#!/usr/bin/env python3
"""
Smoke tests for LessonsLearnedRAG module.

These tests verify:
1. Module imports successfully
2. Key classes/functions exist
3. Basic instantiation and method signatures

Created: Jan 13, 2026
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


class TestLessonsLearnedRAGImports:
    """Test that lessons_learned_rag module imports correctly."""

    def test_module_imports(self):
        """Should import lessons_learned_rag module without errors."""
        from src.rag import lessons_learned_rag

        assert lessons_learned_rag is not None

    def test_lessonslearnedrag_class_exists(self):
        """Should have LessonsLearnedRAG class."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        assert LessonsLearnedRAG is not None
        assert callable(LessonsLearnedRAG)

    def test_lessons_search_available_constant(self):
        """Should have LESSONS_SEARCH_AVAILABLE constant."""
        from src.rag.lessons_learned_rag import LESSONS_SEARCH_AVAILABLE

        assert isinstance(LESSONS_SEARCH_AVAILABLE, bool)


class TestLessonsLearnedRAGInstantiation:
    """Test LessonsLearnedRAG class instantiation."""

    def test_init_with_default_dir(self):
        """Should initialize with default knowledge directory."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()

            assert rag.knowledge_dir == Path("rag_knowledge/lessons_learned")
            assert isinstance(rag.lessons, list)

    def test_init_with_custom_dir(self):
        """Should initialize with custom knowledge directory."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            custom_dir = Path(tempfile.gettempdir()) / "test_lessons"
            rag = LessonsLearnedRAG(knowledge_dir=str(custom_dir))

            assert rag.knowledge_dir == custom_dir

    def test_class_has_expected_methods(self):
        """Should have expected public methods."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        assert hasattr(LessonsLearnedRAG, "query")
        assert hasattr(LessonsLearnedRAG, "search")
        assert hasattr(LessonsLearnedRAG, "get_critical_lessons")
        assert hasattr(LessonsLearnedRAG, "add_lesson")

    def test_class_has_private_methods(self):
        """Should have expected private methods."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        assert hasattr(LessonsLearnedRAG, "_load_lessons")
        assert hasattr(LessonsLearnedRAG, "_extract_severity")
        assert hasattr(LessonsLearnedRAG, "_extract_tags")
        assert hasattr(LessonsLearnedRAG, "_extract_prevention")


class TestLessonsLearnedRAGMethods:
    """Test LessonsLearnedRAG methods."""

    def test_query_returns_list(self):
        """Should return list from query method."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            result = rag.query("test query")

            assert isinstance(result, list)

    def test_query_with_severity_filter(self):
        """Should accept severity_filter parameter."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            result = rag.query("test query", top_k=3, severity_filter="CRITICAL")

            assert isinstance(result, list)

    def test_search_returns_tuples(self):
        """Should return list of (LessonResult, score) tuples."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            result = rag.search("test query", top_k=5)

            assert isinstance(result, list)
            # If there are results, they should be tuples
            for item in result:
                assert isinstance(item, tuple)
                assert len(item) == 2

    def test_get_critical_lessons(self):
        """Should return list of critical lessons."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            result = rag.get_critical_lessons()

            assert isinstance(result, list)

    def test_extract_severity_critical(self):
        """Should extract CRITICAL severity."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            content = "**Severity**: CRITICAL\nSome lesson content"
            severity = rag._extract_severity(content)

            assert severity == "CRITICAL"

    def test_extract_severity_high(self):
        """Should extract HIGH severity."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            content = "**Severity**: HIGH\nSome lesson content"
            severity = rag._extract_severity(content)

            assert severity == "HIGH"

    def test_extract_severity_default_low(self):
        """Should default to LOW severity when not found."""
        with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            rag = LessonsLearnedRAG()
            content = "Some lesson without severity marker"
            severity = rag._extract_severity(content)

            assert severity == "LOW"


class TestLessonsLearnedRAGWithTestData:
    """Test with actual test data in a temp directory."""

    def test_loads_lessons_from_directory(self):
        """Should load lessons from markdown files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test lesson file
            lesson_path = Path(tmpdir) / "test_lesson.md"
            lesson_path.write_text("""# Test Lesson

**Severity**: HIGH

## Description
This is a test lesson for smoke testing.

## Prevention
Always run tests before committing.

## Tags
`testing`, `smoke`
""")

            with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

                assert len(rag.lessons) == 1
                assert rag.lessons[0]["id"] == "test_lesson"
                assert rag.lessons[0]["severity"] == "HIGH"

    def test_query_finds_matching_lessons(self):
        """Should find lessons matching query terms."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create test lesson files
            lesson1 = Path(tmpdir) / "trading_error.md"
            lesson1.write_text("""# Trading Error

**Severity**: CRITICAL

Stop loss was not set correctly. Always verify stop loss orders.
""")

            lesson2 = Path(tmpdir) / "deployment_fix.md"
            lesson2.write_text("""# Deployment Fix

**Severity**: MEDIUM

CI pipeline needs proper configuration.
""")

            with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

                # Query for trading-related lessons
                results = rag.query("trading stop loss", top_k=2)

                assert len(results) >= 1
                # Trading error should be found
                found_trading = any(r["id"] == "trading_error" for r in results)
                assert found_trading


class TestLessonsLearnedRAGAddLesson:
    """Test adding new lessons."""

    def test_add_lesson_creates_file(self):
        """Should create lesson file when adding."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.rag.lessons_learned_rag.LESSONS_SEARCH_AVAILABLE", False):
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

                content = """# New Lesson

**Severity**: HIGH

This is a new lesson.
"""
                rag.add_lesson("new_lesson", content)

                # File should exist
                lesson_file = Path(tmpdir) / "new_lesson.md"
                assert lesson_file.exists()

                # Lessons should be reloaded
                assert len(rag.lessons) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

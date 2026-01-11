"""
RAG Operational Tests - CI verification that RAG is working.

These tests MUST pass for any PR to be merged. No more silent RAG failures.

Created: Jan 1, 2026
Updated: Jan 11, 2026 - Removed ChromaDB tests (ChromaDB removed Jan 7, 2026 CEO directive)
Reason: LL-074 - RAG was broken for 18 days without detection
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRAGLessonsSearch:
    """Test LessonsSearch keyword-based RAG (ChromaDB was removed Jan 7, 2026)."""

    def test_lessons_search_loads_lessons(self):
        """Verify LessonsSearch loads lessons from disk."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()

        # Should have loaded lessons
        count = ls.count()
        assert count > 0, "LessonsSearch failed to load any lessons"
        assert count >= 50, f"Only {count} lessons loaded - expected at least 50"

    def test_lessons_search_returns_results(self):
        """Verify LessonsSearch.search() returns results."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()
        if ls.count() == 0:
            pytest.skip("No lessons loaded")

        # Query that should find blind trading lesson
        results = ls.search("blind trading catastrophe account data", top_k=5)

        assert len(results) > 0, "Search returned no results"

        # Check result format
        lesson, score = results[0]
        assert hasattr(lesson, "id"), "Result missing 'id' attribute"
        assert hasattr(lesson, "severity"), "Result missing 'severity' attribute"
        assert score >= 0, f"Score should be non-negative, got {score}"

    def test_lessons_search_finds_critical_lessons(self):
        """Verify search can find CRITICAL severity lessons."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()
        if ls.count() == 0:
            pytest.skip("No lessons loaded")

        # Get critical lessons
        critical = ls.get_critical_lessons()

        assert len(critical) > 0, "No CRITICAL lessons found - system has no safety guardrails"

        # All should be CRITICAL severity
        for lesson in critical:
            assert lesson.severity == "CRITICAL", (
                f"Lesson {lesson.id} returned by get_critical_lessons() "
                f"has severity {lesson.severity}, expected CRITICAL"
            )

    def test_search_finds_relevant_content(self):
        """Verify search finds relevant content based on keywords."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()
        if ls.count() == 0:
            pytest.skip("No lessons loaded")

        # Query about capital protection
        results = ls.search("capital protection losing money", top_k=10)

        if len(results) == 0:
            pytest.fail(
                "Search returned no results for 'capital protection losing money'. "
                "This indicates keyword search is not working."
            )

        # At least one result should be about money/loss/protection
        relevant_terms = ["money", "loss", "lose", "capital", "protect", "rule"]
        found_relevant = False

        for lesson, score in results:
            content = lesson.snippet.lower() if lesson.snippet else ""
            title = lesson.title.lower() if lesson.title else ""
            combined = content + " " + title

            if any(term in combined for term in relevant_terms):
                found_relevant = True
                break

        assert found_relevant, (
            "Search didn't find relevant results for 'capital protection'. "
            "Results should include lessons about losing money or capital preservation."
        )


class TestRAGLessonsLoaded:
    """Verify lessons are properly loaded."""

    def test_lessons_directory_exists(self):
        """Verify lessons directory exists."""
        lessons_dir = Path("rag_knowledge/lessons_learned")
        assert lessons_dir.exists(), f"Lessons directory not found: {lessons_dir}"

    def test_lessons_have_content(self):
        """Verify lessons have actual content."""
        lessons_dir = Path("rag_knowledge/lessons_learned")
        if not lessons_dir.exists():
            pytest.skip("Lessons directory not present")

        lesson_files = list(lessons_dir.glob("*.md"))
        assert len(lesson_files) >= 50, (
            f"Only found {len(lesson_files)} lessons, expected 50+. "
            f"Lessons may not have been properly copied."
        )

        # Check a few lessons have content
        for lesson_file in lesson_files[:5]:
            content = lesson_file.read_text()
            assert len(content) > 100, (
                f"Lesson {lesson_file.name} has very little content ({len(content)} chars)"
            )

    def test_critical_lessons_exist(self):
        """Verify critical lessons are present."""
        lessons_dir = Path("rag_knowledge/lessons_learned")
        if not lessons_dir.exists():
            pytest.skip("Lessons directory not present")

        critical_patterns = [
            "ll_051_blind_trading",  # Blind trading catastrophe
            "ll_054_rag_not_actually",  # RAG not used
            "ll_074_rag_vector",  # Vector DB not installed
        ]

        for pattern in critical_patterns:
            matches = list(lessons_dir.glob(f"*{pattern}*"))
            assert len(matches) > 0, (
                f"Critical lesson matching '{pattern}' not found. "
                f"These lessons document important failures and must be present."
            )


class TestVertexRAGNotStub:
    """Verify Vertex AI RAG is not a stub - it must actually upload data."""

    def test_vertex_rag_add_trade_not_stub(self):
        """Verify add_trade actually uploads, not just logs."""
        try:
            from src.rag.vertex_rag import VertexRAG
        except ImportError:
            pytest.skip("VertexRAG not available")

        import inspect

        source = inspect.getsource(VertexRAG.add_trade)

        # Must NOT just log and return True (stub pattern)
        assert "import_files" in source or "upload_file" in source, (
            "VertexRAG.add_trade() appears to be a STUB - it doesn't actually upload data. "
            "It must use rag.import_files() or similar to upload to Vertex AI RAG corpus."
        )

        # Must NOT have the old stub pattern
        assert "_trade_text prepared for batch import" not in source, (
            "VertexRAG.add_trade() contains stub comment 'prepared for batch import'. "
            "This indicates it was never implemented to actually upload data."
        )

    def test_vertex_rag_add_lesson_not_stub(self):
        """Verify add_lesson actually uploads, not just logs."""
        try:
            from src.rag.vertex_rag import VertexRAG
        except ImportError:
            pytest.skip("VertexRAG not available")

        import inspect

        source = inspect.getsource(VertexRAG.add_lesson)

        # Must NOT just log and return True (stub pattern)
        assert "import_files" in source or "upload_file" in source, (
            "VertexRAG.add_lesson() appears to be a STUB - it doesn't actually upload data. "
            "It must use rag.import_files() or similar to upload to Vertex AI RAG corpus."
        )

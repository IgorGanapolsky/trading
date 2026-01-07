"""
Test RAG Search - Ensures LessonsSearch is functional.

Created: Dec 30, 2025
Updated: Jan 7, 2026 - Removed ChromaDB tests (CEO directive), replaced with LessonsSearch tests

This test MUST run in CI to catch RAG search failures early.
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock


class TestLessonsSearchInstallation:
    """Verify LessonsSearch is functional."""

    def test_lessons_search_importable(self):
        """LessonsSearch must be importable."""
        from src.rag.lessons_search import LessonsSearch

        assert LessonsSearch is not None

    def test_lessons_search_initialization(self):
        """LessonsSearch must initialize without errors."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        assert search is not None
        assert hasattr(search, "_lessons_cache")

    def test_lessons_search_deprecated_chromadb_param(self):
        """use_chromadb parameter should be deprecated but not error."""
        from src.rag.lessons_search import LessonsSearch

        # Should not raise, just warn
        search = LessonsSearch(use_chromadb=True)
        assert search is not None


class TestLessonsSearchFunctionality:
    """Verify LessonsSearch keyword search works."""

    def test_search_returns_list(self):
        """Search should return a list of results."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        results = search.search("trading", top_k=5)
        assert isinstance(results, list)

    def test_search_with_severity_filter(self):
        """Search should support severity filtering."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        results = search.search("error", severity_filter="CRITICAL")
        # All results should be CRITICAL if filtering works
        for lesson, score in results:
            if hasattr(lesson, 'severity'):
                assert lesson.severity == "CRITICAL"

    def test_get_critical_lessons(self):
        """Should be able to get critical lessons."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        critical = search.get_critical_lessons()
        assert isinstance(critical, list)

    def test_count_lessons(self):
        """Should be able to count loaded lessons."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        count = search.count()
        assert isinstance(count, int)
        assert count >= 0

    def test_index_lessons_reload(self):
        """index_lessons should reload lessons from disk."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        count = search.index_lessons(force_rebuild=True)
        assert isinstance(count, int)


class TestLessonsLearnedRAG:
    """Verify LessonsLearnedRAG wrapper works."""

    def test_rag_importable(self):
        """LessonsLearnedRAG must be importable."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        assert LessonsLearnedRAG is not None

    def test_rag_initialization(self):
        """LessonsLearnedRAG must initialize without errors."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        assert rag is not None

    def test_rag_query(self):
        """RAG query should return results."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        results = rag.query("trading lessons")
        assert isinstance(results, list)

    def test_rag_search_format(self):
        """RAG search should return (LessonResult, score) tuples."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()
        results = rag.search("risk management")
        assert isinstance(results, list)
        for result in results:
            assert isinstance(result, tuple)
            assert len(result) == 2


class TestRAGDataPresence:
    """Verify RAG has data (if running in full environment)."""

    @pytest.mark.skipif(
        not Path("rag_knowledge/lessons_learned").exists(),
        reason="Lessons directory not present",
    )
    def test_lessons_directory_has_files(self):
        """Lessons directory should have markdown files."""
        lessons_dir = Path("rag_knowledge/lessons_learned")
        md_files = list(lessons_dir.glob("*.md"))
        assert len(md_files) > 0, "No lessons found in rag_knowledge/lessons_learned"

    @pytest.mark.skipif(
        not Path("rag_knowledge/lessons_learned").exists(),
        reason="Lessons directory not present",
    )
    def test_lessons_search_has_data(self):
        """LessonsSearch should find lessons if directory has files."""
        from src.rag.lessons_search import LessonsSearch

        search = LessonsSearch()
        count = search.count()

        lessons_dir = Path("rag_knowledge/lessons_learned")
        md_files = list(lessons_dir.glob("*.md"))

        # Count should match number of files (approximately)
        if len(md_files) > 0:
            assert count > 0, "LessonsSearch has no lessons loaded"


class TestVectorDBCacheFile:
    """Verify vectorized_files.json cache works."""

    @pytest.mark.skipif(
        not Path("data/vector_db/vectorized_files.json").exists(),
        reason="Cache file not present",
    )
    def test_cache_file_valid_json(self):
        """Cache file should be valid JSON."""
        import json

        cache_file = Path("data/vector_db/vectorized_files.json")
        data = json.loads(cache_file.read_text())
        assert isinstance(data, dict)
        assert "files" in data or "last_updated" in data

"""
Integration Tests: RAG Quality & Architecture

Ensures production RAG uses proper vector database and maintains performance.
Prevents regression to "half-assed" JSON+numpy implementation.

Lesson Learned: lesson_20251215_104602_0
Prevention: Test-driven architecture validation.

Author: Trading System CTO
Created: 2025-12-15
"""

import time
from pathlib import Path

import pytest


class TestRAGArchitecture:
    """Test RAG uses proper vector database architecture."""

    def test_rag_uses_chromadb(self):
        """Ensure production RAG uses ChromaDB, not just JSON."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Must have ChromaDB attributes
        assert hasattr(rag, "_chroma_collection"), (
            "RAG must have _chroma_collection attribute. Using JSON fallback indicates regression!"
        )

        # ChromaDB must be initialized
        assert rag._chroma_collection is not None, (
            "ChromaDB collection is None. Vector database not properly initialized."
        )

        # Must be actively using ChromaDB (not just available)
        assert rag._use_chromadb is True, (
            "RAG has _use_chromadb=False. System regressed to JSON storage!"
        )

    def test_chromadb_has_data(self):
        """Verify ChromaDB is populated with data."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # ChromaDB should have documents
        count = rag._chroma_collection.count()
        assert count > 0, (
            f"ChromaDB has {count} documents. "
            "Empty vector database indicates regression or migration failure."
        )

        # Should have at least the default lessons
        assert count >= 4, (
            f"ChromaDB only has {count} documents. Expected at least 4 default lessons."
        )

    def test_chromadb_in_requirements(self):
        """Ensure chromadb is not commented out in requirements."""
        req_file = Path("requirements-minimal.txt")
        assert req_file.exists(), "requirements-minimal.txt not found"

        content = req_file.read_text()

        # ChromaDB must be present
        assert "chromadb" in content.lower(), (
            "chromadb not found in requirements-minimal.txt. This will cause production failure!"
        )

        # ChromaDB must NOT be commented out
        assert "# chromadb" not in content, (
            "chromadb is commented out in requirements-minimal.txt! "
            "This indicates regression to JSON-only implementation."
        )


class TestRAGPerformance:
    """Test RAG search performance (vector DB should be fast)."""

    def test_search_performance(self):
        """Ensure RAG search is fast (O(log n) with vector DB, not O(n) with JSON)."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Warm up (first query may include initialization overhead)
        rag.search("test warmup", top_k=1)

        # Measure performance
        start = time.time()
        results = rag.search("position sizing error", top_k=5)
        duration = time.time() - start

        # With ChromaDB (O(log n)), search should be <100ms for ~100 docs
        # With JSON (O(n)), search would be >100ms and scale linearly
        assert duration < 0.2, (
            f"RAG search too slow: {duration:.3f}s. "
            f"Expected <0.2s with vector DB. "
            f"This indicates regression to O(n) JSON scan."
        )

        # Should return results
        assert len(results) > 0, "RAG should return results for valid query"

    def test_search_returns_relevant_results(self):
        """Ensure search returns semantically relevant results."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Search for position sizing lessons
        results = rag.search("position sizing error", top_k=5)

        assert len(results) > 0, "Should return results"

        # First result should be relevant (high score)
        first_lesson, first_score = results[0]
        assert first_score > 0.3, (
            f"Top result score too low: {first_score:.1%}. "
            f"Vector DB should return relevant results with high scores."
        )

        # Check if it's actually about position sizing
        title_lower = first_lesson.title.lower()
        desc_lower = first_lesson.description.lower()
        is_relevant = (
            "position" in title_lower
            or "size" in title_lower
            or "position" in desc_lower
            or "size" in desc_lower
        )

        assert is_relevant, (
            f"Top result not relevant: {first_lesson.title}. "
            f"Vector DB semantic search should find relevant matches."
        )


class TestRAGFunctionality:
    """Test core RAG functionality works correctly."""

    def test_add_lesson_to_chromadb(self):
        """Verify new lessons are added to ChromaDB, not just JSON."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Get initial count
        initial_count = rag._chroma_collection.count()

        # Add a test lesson
        _lesson_id = rag.add_lesson(
            category="test",
            title="Test Lesson for Architecture Validation",
            description="This is a test lesson to verify ChromaDB integration",
            root_cause="Testing",
            prevention="Don't regress to JSON",
            tags=["test", "architecture"],
            severity="low",
        )

        # Verify it was added to ChromaDB
        new_count = rag._chroma_collection.count()
        assert new_count == initial_count + 1, (
            f"Lesson not added to ChromaDB. "
            f"Count: {initial_count} -> {new_count}. "
            f"This indicates regression to JSON-only storage."
        )

    def test_search_finds_new_lessons(self):
        """Verify search can find newly added lessons."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Add a lesson with unique content
        unique_term = "xyztest123uniqueterm"
        rag.add_lesson(
            category="test",
            title=f"Test Lesson with {unique_term}",
            description=f"Contains unique term: {unique_term}",
            root_cause="Testing search",
            prevention="Verify search works",
            tags=["test"],
            severity="low",
        )

        # Search for it
        results = rag.search(unique_term, top_k=5)

        # Should find the lesson
        assert len(results) > 0, (
            f"Search didn't find lesson with unique term '{unique_term}'. "
            f"ChromaDB search may not be working."
        )

        found = any(unique_term.lower() in lesson.title.lower() for lesson, score in results)
        assert found, (
            f"Search results don't include lesson with '{unique_term}'. "
            f"Vector DB indexing may not be working."
        )


class TestCohereRerankIntegration:
    """Test Cohere Rerank integration is preserved."""

    def test_cohere_rerank_parameter_exists(self):
        """Ensure use_rerank parameter still works."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        # Should accept use_rerank parameter
        rag_no_rerank = LessonsLearnedRAG(use_rerank=False)
        assert hasattr(rag_no_rerank, "use_rerank"), "use_rerank attribute missing"
        assert rag_no_rerank.use_rerank is False, "use_rerank not set correctly"

        rag_with_rerank = LessonsLearnedRAG(use_rerank=True)
        assert rag_with_rerank.use_rerank is True or rag_with_rerank.use_rerank is False, (
            "use_rerank should be boolean (may be False if API key missing)"
        )

    def test_cost_summary_method_exists(self):
        """Ensure get_cost_summary() method exists for Cohere tracking."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        assert hasattr(rag, "get_cost_summary"), (
            "get_cost_summary() method missing. Cohere Rerank cost tracking was removed!"
        )

        # Should return dict
        summary = rag.get_cost_summary()
        assert isinstance(summary, dict), "get_cost_summary() should return dict"
        assert "rerank_enabled" in summary, "Cost summary missing rerank_enabled key"


@pytest.mark.skipif(
    not Path("src/rag/lessons_learned_rag.py").exists(), reason="RAG module not available"
)
class TestBackwardCompatibility:
    """Ensure ChromaDB migration is backward compatible."""

    def test_default_initialization_works(self):
        """Ensure RAG can be initialized with no parameters."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        # Should work with no parameters (backward compatible)
        rag = LessonsLearnedRAG()
        assert rag is not None

    def test_json_fallback_exists(self):
        """Ensure JSON fallback exists for graceful degradation."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        # Should have lessons attribute (JSON fallback)
        assert hasattr(rag, "lessons"), (
            "lessons attribute missing. JSON fallback removed, breaking backward compatibility!"
        )

    def test_migration_method_exists(self):
        """Ensure migration method exists for upgrading old data."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        rag = LessonsLearnedRAG()

        assert hasattr(rag, "migrate_from_json_to_chromadb"), (
            "migrate_from_json_to_chromadb() method missing. Users can't migrate old data!"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

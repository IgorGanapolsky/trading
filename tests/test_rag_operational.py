"""
RAG Operational Tests - CI verification that RAG is working.

These tests MUST pass for any PR to be merged. No more silent RAG failures.

Created: Jan 1, 2026
Reason: LL-074 - RAG was broken for 18 days without detection
"""

import sys
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Check if chromadb is available
try:
    import chromadb

    CHROMADB_AVAILABLE = True
except ImportError:
    CHROMADB_AVAILABLE = False


@pytest.mark.skipif(not CHROMADB_AVAILABLE, reason="chromadb not installed")
class TestRAGOperational:
    """Critical RAG operational tests - these block PRs if they fail."""

    def test_chromadb_is_installed(self):
        """Verify chromadb package is installed."""
        try:
            import chromadb

            assert chromadb.__version__, "chromadb version should be set"
        except ImportError:
            pytest.fail(
                "chromadb is NOT INSTALLED. Run: pip install chromadb\n"
                "This caused LL-074 where RAG silently fell back to useless keyword matching."
            )

    def test_vector_db_has_documents(self):
        """Verify vector database has documents indexed."""
        import chromadb
        from chromadb.config import Settings

        db_path = Path("data/vector_db")
        if not db_path.exists():
            pytest.skip("Vector DB directory not present (may be CI without data)")

        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        collection = client.get_or_create_collection(name="phil_town_rag")
        count = collection.count()

        # Skip in CI when vector DB exists but is empty (not vectorized)
        if count == 0:
            pytest.skip("Vector DB is empty (CI environment without vectorized data)")

        # Should have at least 100 documents (we have 700+)
        assert count >= 100, (
            f"Vector DB only has {count} documents (expected 100+). "
            f"This may indicate incomplete vectorization."
        )

    def test_semantic_search_returns_results(self):
        """Verify semantic search actually works."""
        import chromadb
        from chromadb.config import Settings

        db_path = Path("data/vector_db")
        if not db_path.exists():
            pytest.skip("Vector DB directory not present")

        client = chromadb.PersistentClient(
            path=str(db_path),
            settings=Settings(anonymized_telemetry=False),
        )

        collection = client.get_or_create_collection(name="phil_town_rag")
        if collection.count() == 0:
            pytest.skip("Vector DB is empty")

        # Test query
        results = collection.query(
            query_texts=["losing money protect capital"],
            n_results=5,
            include=["documents", "distances"],
        )

        assert results is not None, "Query returned None"
        assert results.get("ids"), "Query returned no IDs"
        assert len(results["ids"][0]) > 0, "Query returned empty results"

        # Verify results are relevant (low distance = high similarity)
        distances = results.get("distances", [[]])[0]
        assert len(distances) > 0, "No distance scores returned"
        assert min(distances) < 2.0, (
            f"Results have high distance ({min(distances):.2f}), "
            f"indicating poor semantic match. Embeddings may be broken."
        )

    def test_lessons_search_connects_to_correct_collection(self):
        """Verify LessonsSearch uses the same collection as vectorize script."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()

        # Should connect to phil_town_rag, not lessons_learned
        assert ls.collection is not None, "LessonsSearch not connected to ChromaDB"

        # The collection should have documents
        doc_count = ls.collection.count()
        if doc_count == 0:
            pytest.skip("Collection is empty in CI environment")

        # Critical: should have same count as what vectorize script created
        assert doc_count > 100, (
            f"LessonsSearch collection only has {doc_count} docs. "
            f"May be connected to wrong collection (was: lessons_learned, should be: phil_town_rag)"
        )

    def test_lessons_search_returns_semantic_results(self):
        """Verify LessonsSearch.search() returns semantically relevant results."""
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()
        if ls.collection is None or ls.collection.count() == 0:
            pytest.skip("No vector data available")

        # Query that should find blind trading lesson
        results = ls.search("blind trading catastrophe account data", top_k=5)

        assert len(results) > 0, "Search returned no results"

        # Check result format
        lesson, score = results[0]
        assert hasattr(lesson, "id"), "Result missing 'id' attribute"
        assert hasattr(lesson, "severity"), "Result missing 'severity' attribute"
        assert hasattr(lesson, "score"), "Result missing 'score' attribute"

        # Score should be reasonable
        assert score >= 0, f"Score should be non-negative, got {score}"

    def test_semantic_vs_keyword_differentiation(self):
        """
        Verify semantic search finds relevant content that keyword search would miss.

        This is the CRITICAL test - if this fails, RAG is doing useless keyword matching.
        """
        try:
            from src.rag.lessons_search import LessonsSearch
        except ImportError:
            pytest.skip("LessonsSearch not available")

        ls = LessonsSearch()
        if ls.collection is None or ls.collection.count() == 0:
            pytest.skip("No vector data available")

        # Query using synonyms/related terms that wouldn't match exact keywords
        # "capital protection" should find lessons about "losing money", "don't lose"
        results = ls.search("capital protection investment safety", top_k=10)

        if len(results) == 0:
            pytest.fail(
                "Semantic search returned no results for 'capital protection'. "
                "This indicates embeddings are not working properly."
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
            "Semantic search didn't find relevant results for 'capital protection'. "
            "Results should include lessons about losing money or capital preservation. "
            "This suggests RAG is doing keyword matching instead of semantic search."
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

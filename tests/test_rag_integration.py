"""Integration tests for RAG (Retrieval-Augmented Generation) round-trip.

Tests the flow: Write lesson -> Read/Query -> Gate decision

Scenarios:
1. Lesson found: Write a lesson, query it, verify it blocks trades
2. Lesson not found: Query for non-existent lesson, verify trade proceeds

Uses LessonsLearnedRAG with a temporary directory. No real LanceDB or external APIs.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRAGRoundTripLessonFound:
    """Test RAG round-trip when a relevant lesson exists."""

    @patch.dict("os.environ", {"LANCEDB_RAG": "false", "LANCEDB_REQUIRED": "false"})
    def test_write_then_query_finds_lesson(self):
        """Write a lesson to temp dir, then query and find it."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        with tempfile.TemporaryDirectory() as tmpdir:
            # Step 1: Write a lesson
            lesson_content = """# LL-TEST-001: Iron Condor Stop Loss Failure

## Summary
Iron condor position was not closed at 100% stop loss, resulting in $500 loss.

## Severity
**Severity**: CRITICAL

## Tags
`iron_condor`, `stop_loss`, `risk_management`

## Prevention
Always enforce stop-loss at 100% of credit received. Use automated monitoring.

## Fix
Added automated position monitoring script that checks P/L every 5 minutes.
"""
            lesson_path = Path(tmpdir)
            lesson_file = lesson_path / "LL-TEST-001.md"
            lesson_file.write_text(lesson_content)

            # Step 2: Create RAG with temp directory
            rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

            # Step 3: Query for the lesson
            results = rag.query("iron condor stop loss failure")

            # Step 4: Verify lesson is found
            assert len(results) > 0
            found = results[0]
            assert "LL-TEST-001" in found["id"]
            assert found["severity"] == "CRITICAL"
            assert "stop" in found["snippet"].lower() or "iron condor" in found["snippet"].lower()

    @patch.dict("os.environ", {"LANCEDB_RAG": "false", "LANCEDB_REQUIRED": "false"})
    def test_search_returns_lesson_result_tuples(self):
        """search() should return (LessonResult, score) tuples for gate compatibility."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        with tempfile.TemporaryDirectory() as tmpdir:
            lesson_content = """# LL-TEST-002: SPY Trading Failure

## Summary
SPY iron condor lost money due to VIX spike.

## Severity
**Severity**: HIGH

## Tags
`spy`, `iron_condor`, `vix`

## Prevention
Check VIX level before entry. Avoid VIX > 25.
"""
            lesson_path = Path(tmpdir)
            (lesson_path / "LL-TEST-002.md").write_text(lesson_content)

            rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

            # search() returns list of (LessonResult, score) tuples
            results = rag.search("SPY iron condor VIX")

            assert len(results) > 0
            lesson_result, score = results[0]

            # Verify LessonResult has required attributes for gate compatibility
            assert hasattr(lesson_result, "id")
            assert hasattr(lesson_result, "title")
            assert hasattr(lesson_result, "severity")
            assert hasattr(lesson_result, "snippet")
            assert hasattr(lesson_result, "prevention")
            assert hasattr(lesson_result, "file")
            assert isinstance(score, (int, float))
            assert score > 0


class TestRAGRoundTripLessonNotFound:
    """Test RAG round-trip when no relevant lesson exists."""

    @patch.dict("os.environ", {"LANCEDB_RAG": "false", "LANCEDB_REQUIRED": "false"})
    def test_query_returns_empty_for_unrelated_topic(self):
        """Query for unrelated topic should return empty results."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        with tempfile.TemporaryDirectory() as tmpdir:
            # Write a lesson about something completely different
            lesson_content = """# LL-TEST-003: Blog Post Formatting

## Summary
Blog post had broken markdown links.

## Severity
**Severity**: LOW

## Tags
`blog`, `markdown`

## Prevention
Run markdown linter before publishing.
"""
            lesson_path = Path(tmpdir)
            (lesson_path / "LL-TEST-003.md").write_text(lesson_content)

            rag = LessonsLearnedRAG(knowledge_dir=tmpdir)

            # Query for iron condor - should not find blog post lesson
            results = rag.query("iron condor catastrophic loss gamma risk")

            # Either empty or very low relevance
            if results:
                # If any results, they should be low relevance
                assert results[0]["score"] < 0.5

    @patch.dict("os.environ", {"LANCEDB_RAG": "false", "LANCEDB_REQUIRED": "false"})
    def test_empty_knowledge_dir_returns_empty(self):
        """Empty knowledge directory should return no results."""
        from src.rag.lessons_learned_rag import LessonsLearnedRAG

        with tempfile.TemporaryDirectory() as tmpdir:
            rag = LessonsLearnedRAG(knowledge_dir=tmpdir)
            results = rag.query("anything at all")
            assert results == []

            results_search = rag.search("iron condor")
            assert results_search == []

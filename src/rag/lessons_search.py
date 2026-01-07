"""
LessonsSearch - Simple keyword search for lessons learned.

Uses straightforward keyword matching on markdown files.
Fast and dependency-free - no external vector database required.

Created: Dec 31, 2025 (Fix for ll_054 - RAG not actually used)
Updated: Jan 7, 2026 - Simplified to keyword search only (CEO directive)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths
LESSONS_DIR = Path("rag_knowledge/lessons_learned")


@dataclass
class LessonResult:
    """A lesson search result with all relevant fields."""

    id: str
    title: str
    severity: str
    snippet: str
    prevention: str
    file: str
    score: float = 0.0


class LessonsSearch:
    """
    Simple keyword search over lessons learned.

    Scans markdown files for matching terms. Fast and dependency-free.
    For cloud-based semantic search, use Vertex AI RAG via CI workflows.
    """

    def __init__(self, use_chromadb: bool = False):
        """
        Initialize LessonsSearch.

        Args:
            use_chromadb: Deprecated parameter, kept for backward compatibility.
                         Always uses keyword search now.
        """
        self._lessons_cache: list[dict] = []

        if use_chromadb:
            logger.warning("ChromaDB is deprecated - using keyword search instead")

        # Load lessons for keyword search
        self._load_lessons()

    def _load_lessons(self) -> None:
        """Load all lessons from markdown files."""
        self._lessons_cache = []

        if not LESSONS_DIR.exists():
            logger.warning(f"Lessons directory not found: {LESSONS_DIR}")
            return

        for lesson_file in LESSONS_DIR.glob("*.md"):
            try:
                content = lesson_file.read_text()
                lesson = {
                    "id": lesson_file.stem,
                    "file": str(lesson_file),
                    "content": content,
                    "severity": self._extract_severity(content),
                    "title": self._extract_title(content, lesson_file.stem),
                    "prevention": self._extract_prevention(content),
                }
                self._lessons_cache.append(lesson)
            except Exception as e:
                logger.warning(f"Failed to load lesson {lesson_file}: {e}")

        logger.info(f"LessonsSearch: Loaded {len(self._lessons_cache)} lessons")

    def _extract_severity(self, content: str) -> str:
        """Extract severity from lesson content."""
        content_lower = content.lower()
        if "severity**: critical" in content_lower or "**severity:** critical" in content_lower:
            return "CRITICAL"
        elif "severity**: high" in content_lower or "**severity:** high" in content_lower:
            return "HIGH"
        elif "severity**: medium" in content_lower or "**severity:** medium" in content_lower:
            return "MEDIUM"
        return "LOW"

    def _extract_title(self, content: str, fallback: str) -> str:
        """Extract title from lesson content."""
        lines = content.strip().split("\n")
        for line in lines[:5]:
            line = line.strip()
            if line.startswith("# "):
                return line[2:].strip()
            if line.startswith("## "):
                return line[3:].strip()
        return fallback

    def _extract_prevention(self, content: str) -> str:
        """Extract prevention/action section from lesson content."""
        import re

        patterns = [
            r"## Prevention\s*\n(.*?)(?=\n##|\Z)",
            r"## Action\s*\n(.*?)(?=\n##|\Z)",
            r"## Solution\s*\n(.*?)(?=\n##|\Z)",
            r"## What to Do\s*\n(.*?)(?=\n##|\Z)",
            r"## Fix\s*\n(.*?)(?=\n##|\Z)",
            r"## Corrective Action\s*\n(.*?)(?=\n##|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()[:500]

        return content[:300].strip()

    def search(
        self, query: str, top_k: int = 5, severity_filter: Optional[str] = None
    ) -> list[tuple[LessonResult, float]]:
        """
        Search lessons using keyword matching.

        Args:
            query: Search query (e.g., "position sizing error", "API failure")
            top_k: Number of results to return
            severity_filter: Optional filter for severity level (CRITICAL, HIGH, MEDIUM, LOW)

        Returns:
            List of (LessonResult, score) tuples, sorted by relevance
        """
        return self._search_keywords(query, top_k, severity_filter)

    def _search_keywords(
        self, query: str, top_k: int, severity_filter: Optional[str]
    ) -> list[tuple[LessonResult, float]]:
        """Keyword-based search over loaded lessons."""
        query_terms = query.lower().split()
        results = []

        for lesson in self._lessons_cache:
            # Filter by severity if specified
            if severity_filter and lesson["severity"] != severity_filter:
                continue

            content_lower = lesson["content"].lower()

            # Score based on term matches
            score = 0
            for term in query_terms:
                if term in content_lower:
                    score += content_lower.count(term)

            # Boost CRITICAL lessons
            if lesson["severity"] == "CRITICAL":
                score *= 2
            elif lesson["severity"] == "HIGH":
                score *= 1.5

            if score > 0:
                # Normalize score to 0-1 range
                normalized_score = min(score / 50.0, 1.0)

                lesson_result = LessonResult(
                    id=lesson["id"],
                    title=lesson["title"],
                    severity=lesson["severity"],
                    snippet=lesson["content"][:500],
                    prevention=lesson["prevention"],
                    file=lesson["file"],
                    score=normalized_score,
                )
                results.append((lesson_result, normalized_score))

        # Sort by score descending
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def index_lessons(self, force_rebuild: bool = False) -> int:
        """
        Reload lessons from disk.

        Args:
            force_rebuild: If True, reload all lessons from disk

        Returns:
            Number of lessons loaded
        """
        if force_rebuild:
            self._lessons_cache = []

        self._load_lessons()
        logger.info(f"Loaded {len(self._lessons_cache)} lessons")
        return len(self._lessons_cache)

    def get_critical_lessons(self) -> list[LessonResult]:
        """Get all CRITICAL severity lessons."""
        return [
            LessonResult(
                id=lesson["id"],
                title=lesson["title"],
                severity=lesson["severity"],
                snippet=lesson["content"][:500],
                prevention=lesson["prevention"],
                file=lesson["file"],
            )
            for lesson in self._lessons_cache
            if lesson["severity"] == "CRITICAL"
        ]

    def count(self) -> int:
        """Return total number of lessons loaded."""
        return len(self._lessons_cache)


# Singleton instance
_search_instance: Optional[LessonsSearch] = None


def get_lessons_search() -> LessonsSearch:
    """Get or create singleton LessonsSearch instance."""
    global _search_instance
    if _search_instance is None:
        _search_instance = LessonsSearch()
    return _search_instance


if __name__ == "__main__":
    # Test the implementation
    logging.basicConfig(level=logging.INFO)

    search = get_lessons_search()
    print(f"Loaded {search.count()} lessons")

    # Test search
    test_queries = [
        "position sizing error",
        "API failure",
        "blind trading catastrophe",
        "wash sale tax",
        "margin of safety",
    ]

    for query in test_queries:
        print(f"\n--- Searching: '{query}' ---")
        results = search.search(query, top_k=3)
        for lesson, score in results:
            print(f"  [{lesson.severity}] {lesson.id}: {lesson.title[:50]}... (score: {score:.2f})")

    # Test critical lessons
    critical = search.get_critical_lessons()
    print(f"\n--- CRITICAL Lessons ({len(critical)}) ---")
    for lesson in critical[:5]:
        print(f"  {lesson.id}: {lesson.title[:60]}...")

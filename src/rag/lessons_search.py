"""
LessonsSearch - Simple keyword search for lessons learned.

Uses straightforward keyword matching on markdown files.
ChromaDB was REMOVED on Jan 7, 2026 (CEO directive - unnecessary complexity).

Created: Dec 31, 2025 (Fix for ll_054 - RAG not actually used)
Updated: Jan 8, 2026 - ACTUALLY removed ChromaDB code (was still present despite docstring)
Updated: Jan 11, 2026 - Added recency boost to prioritize recent lessons
"""

import logging
import re
from dataclasses import dataclass
from datetime import datetime
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


def _extract_date_from_filename(filename: str) -> datetime | None:
    """
    Extract date from lesson filename like 'll_130_investment_strategy_review_jan11.md'.

    Returns datetime if found, None otherwise.
    """
    # Pattern: month + day (e.g., jan11, dec25, nov03)
    month_map = {
        "jan": 1,
        "feb": 2,
        "mar": 3,
        "apr": 4,
        "may": 5,
        "jun": 6,
        "jul": 7,
        "aug": 8,
        "sep": 9,
        "oct": 10,
        "nov": 11,
        "dec": 12,
    }

    match = re.search(
        r"(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)(\d{1,2})", filename.lower()
    )
    if match:
        month_str, day_str = match.groups()
        month = month_map[month_str]
        day = int(day_str)
        # Assume current year (2026) for recent, previous year for older
        year = datetime.now().year
        try:
            date = datetime(year, month, day)
            # If date is in future, assume previous year
            if date > datetime.now():
                date = datetime(year - 1, month, day)
            return date
        except ValueError:
            return None

    # Pattern: YYYYMMDD (e.g., 20260106)
    match = re.search(r"(\d{8})", filename)
    if match:
        try:
            return datetime.strptime(match.group(1), "%Y%m%d")
        except ValueError:
            return None

    return None


class LessonsSearch:
    """
    Simple keyword search over lessons learned.

    Scans markdown files for matching terms. Fast and dependency-free.
    No external vector DB required - simple TF-IDF style matching.
    Includes recency boost: recent lessons score higher (Jan 11, 2026 fix).
    """

    def __init__(self):
        """Initialize LessonsSearch with keyword-only search."""
        self._lessons_cache: list[dict] = []
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
                    "date": _extract_date_from_filename(lesson_file.stem),
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

            # Recency boost: newer lessons score higher
            # Lessons from last 7 days get 2x boost, 30 days get 1.5x boost
            if lesson.get("date"):
                days_old = (datetime.now() - lesson["date"]).days
                if days_old <= 7:
                    score *= 2.0  # Strong boost for very recent
                elif days_old <= 30:
                    score *= 1.5  # Moderate boost for recent
                elif days_old <= 90:
                    score *= 1.2  # Small boost for somewhat recent
                # Older lessons get no boost (but no penalty either)

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

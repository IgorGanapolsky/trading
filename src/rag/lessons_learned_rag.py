"""Lessons learned RAG with LanceDB-first retrieval and keyword fallback.

Updated Feb 9, 2026: LanceDB-first semantic retrieval with keyword fallback.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Optional LanceDB semantic search
try:
    from src.memory.document_aware_rag import get_document_aware_rag

    LANCEDB_RAG_AVAILABLE = True
except ImportError:
    LANCEDB_RAG_AVAILABLE = False
    logger.warning("DocumentAwareRAG not available")

# Use the simplified LessonsSearch
try:
    from src.rag.lessons_search import get_lessons_search

    LESSONS_SEARCH_AVAILABLE = True
except ImportError:
    LESSONS_SEARCH_AVAILABLE = False
    logger.warning("LessonsSearch not available")


class LessonsLearnedRAG:
    """RAG for lessons learned with LanceDB-first retrieval."""

    def __init__(self, knowledge_dir: Optional[str] = None):
        self.knowledge_dir = Path(knowledge_dir or "rag_knowledge/lessons_learned")
        self.lessons = []
        self.last_source = "none"

        # LanceDB-first retrieval (semantic)
        self.lancedb_rag = None
        self.lancedb_enabled = os.getenv("LANCEDB_RAG", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        self.lancedb_auto_index = os.getenv("LANCEDB_AUTO_INDEX", "true").lower() in {
            "1",
            "true",
            "yes",
        }
        if self.lancedb_enabled and LANCEDB_RAG_AVAILABLE:
            try:
                self.lancedb_rag = get_document_aware_rag()
                if self.lancedb_auto_index:
                    self.lancedb_rag.ensure_index()
                logger.info("✅ LanceDB RAG initialized (primary)")
            except Exception as e:
                logger.warning(f"LanceDB RAG init failed: {e}")
                self.lancedb_rag = None

        # Use LessonsSearch for keyword-based search
        if LESSONS_SEARCH_AVAILABLE:
            try:
                self.search_engine = get_lessons_search()
                logger.info(
                    f"✅ LessonsSearch initialized with {self.search_engine.count()} lessons"
                )
                # Still load lessons for compatibility
                self._load_lessons()
                return
            except Exception as e:
                logger.warning(
                    f"LessonsSearch initialization failed: {e} - using direct file search"
                )

        # Fallback to direct file-based search
        self.search_engine = None
        self._load_lessons()

    def _load_lessons(self) -> None:
        """Load all lessons from markdown files."""
        if not self.knowledge_dir.exists():
            logger.warning(f"Lessons directory not found: {self.knowledge_dir}")
            return

        for lesson_file in self.knowledge_dir.glob("*.md"):
            try:
                content = lesson_file.read_text()
                # Parse basic metadata
                lesson = {
                    "id": lesson_file.stem,
                    "file": str(lesson_file),
                    "content": content,
                    "severity": self._extract_severity(content),
                    "tags": self._extract_tags(content),
                }
                self.lessons.append(lesson)
            except Exception as e:
                logger.warning(f"Failed to load lesson {lesson_file}: {e}")

        logger.info(f"Loaded {len(self.lessons)} lessons from {self.knowledge_dir}")

    def _extract_severity(self, content: str) -> str:
        """Extract severity from lesson content."""
        content_lower = content.lower()
        if "severity**: critical" in content_lower:
            return "CRITICAL"
        elif "severity**: high" in content_lower:
            return "HIGH"
        elif "severity**: medium" in content_lower:
            return "MEDIUM"
        return "LOW"

    def _extract_tags(self, content: str) -> list:
        """Extract tags from lesson content."""
        import re

        match = re.search(r"`([^`]+)`(?:,\s*`([^`]+)`)*\s*$", content, re.MULTILINE)
        if match:
            tags_line = content.split("## Tags")[-1] if "## Tags" in content else ""
            return re.findall(r"`([^`]+)`", tags_line)
        return []

    def _query_lancedb(self, query: str, top_k: int = 5) -> list[dict]:
        if self.lancedb_rag is None:
            return []

        results = self.lancedb_rag.search(query, limit=max(top_k * 2, 5))
        formatted = []
        for r in results:
            source = r.metadata.get("source", "") if r.metadata else ""
            if "rag_knowledge/lessons_learned" not in source:
                continue

            lesson_id = r.metadata.get("lesson_id") or r.document_id
            severity = (r.metadata.get("severity") or "LOW").upper()
            content = r.content or ""
            snippet = content[:500]

            formatted.append(
                {
                    "id": lesson_id,
                    "severity": severity,
                    "score": r.score,
                    "snippet": snippet,
                    "content": content,
                    "file": source,
                    "title": r.title,
                    "prevention": "",
                }
            )

            if len(formatted) >= top_k:
                break

        return formatted

    def query(self, query: str, top_k: int = 5, severity_filter: Optional[str] = None) -> list:
        """Search lessons using LanceDB first, then keyword matching."""
        if self.lancedb_rag is not None:
            try:
                results = self._query_lancedb(query, top_k=top_k)
                if results:
                    if severity_filter:
                        results = [r for r in results if r.get("severity") == severity_filter][
                            :top_k
                        ]
                    self.last_source = "lancedb"
                    return results
            except Exception as e:
                logger.warning(f"LanceDB query failed: {e} - using keyword fallback")

        # Use LessonsSearch if available
        if self.search_engine is not None:
            try:
                results = self.search_engine.search(
                    query, top_k=top_k, severity_filter=severity_filter
                )
                # Convert results to expected format
                self.last_source = "keyword"
                return [
                    {
                        "id": lesson.id,
                        "severity": lesson.severity,
                        "score": score,
                        "snippet": lesson.snippet,
                        "content": lesson.snippet,  # Use snippet as content
                        "file": lesson.file,
                        "title": lesson.title,
                        "prevention": lesson.prevention,
                    }
                    for lesson, score in results
                ]
            except Exception as e:
                logger.warning(f"LessonsSearch failed: {e} - using direct file search")

        # Fallback: keyword-based search
        if not self.lessons:
            return []

        query_terms = query.lower().split()
        results = []

        for lesson in self.lessons:
            # Filter by severity if specified
            if severity_filter and lesson["severity"] != severity_filter:
                continue

            content_lower = lesson["content"].lower()
            lesson_id = lesson["id"].lower()

            # Score based on term matches
            score = 0
            for term in query_terms:
                if term in content_lower:
                    score += content_lower.count(term)
                # Boost for matches in tags
                if any(term in tag.lower() for tag in lesson["tags"]):
                    score += 5

            # Boost CRITICAL lessons
            if lesson["severity"] == "CRITICAL":
                score *= 2

            # RECENCY BOOST: Prioritize recent content (but don't PENALIZE old lessons)
            # CRITICAL lessons from any date should still be findable
            if "jan11" in lesson_id or "jan10" in lesson_id or "jan09" in lesson_id:
                score *= 2.0  # Boost recent lessons
            elif "jan" in lesson_id:
                score *= 1.5  # Moderate boost for January
            elif "trading_rules" in lesson_id or "2026" in lesson_id:
                score *= 2.0  # Boost actionable rules
            # Note: Old lessons are NOT penalized - we need to find CRITICAL lessons from any date

            if score > 0:
                # Normalize score to 0-1 range for consistency with ChromaDB
                normalized_score = min(score / 50.0, 1.0)
                results.append(
                    {
                        "id": lesson["id"],
                        "severity": lesson["severity"],
                        "score": normalized_score,
                        "snippet": lesson["content"][:500],
                        "content": lesson["content"],
                        "file": lesson["file"],
                    }
                )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        self.last_source = "keyword"
        return results[:top_k]

    def search(self, query: str, top_k: int = 5) -> list:
        """
        Search lessons - returns format expected by gates.py and main.py.

        Returns list of (LessonResult, score) tuples for compatibility.
        """
        from dataclasses import dataclass

        @dataclass
        class LessonResult:
            id: str
            title: str
            severity: str
            snippet: str
            prevention: str  # Required by gates.py and main.py
            file: str

        raw_results = self.query(query, top_k=top_k)
        results = []
        for r in raw_results:
            # Extract prevention section from content or use snippet as fallback
            prevention = r.get("prevention") or self._extract_prevention(
                r.get("content", r["snippet"])
            )
            lesson = LessonResult(
                id=r["id"],
                title=r.get("title", r["id"]),
                severity=r["severity"],
                snippet=r["snippet"],
                prevention=prevention,
                file=r["file"],
            )
            # Score is already normalized to 0-1 range by query()
            results.append((lesson, r["score"]))
        return results

    def _extract_prevention(self, content: str) -> str:
        """Extract prevention/action section from lesson content."""
        import re

        # Try to find Prevention, Action, or Solution section
        patterns = [
            r"## Prevention\s*\n(.*?)(?=\n##|\Z)",
            r"## Action\s*\n(.*?)(?=\n##|\Z)",
            r"## Solution\s*\n(.*?)(?=\n##|\Z)",
            r"## What to Do\s*\n(.*?)(?=\n##|\Z)",
            r"## Fix\s*\n(.*?)(?=\n##|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, content, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1).strip()[:500]

        # Fallback: use first 300 chars of content
        return content[:300].strip()

    def get_critical_lessons(self) -> list:
        """Get all CRITICAL severity lessons."""
        return [lesson for lesson in self.lessons if lesson["severity"] == "CRITICAL"]

    def add_lesson(self, lesson_id: str, content: str) -> None:
        """Add a new lesson (writes to file)."""
        lesson_file = self.knowledge_dir / f"{lesson_id}.md"
        lesson_file.write_text(content)
        self._load_lessons()  # Reload

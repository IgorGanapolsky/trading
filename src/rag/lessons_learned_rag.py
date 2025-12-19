"""Lightweight RAG for lessons learned - no heavy dependencies."""

import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class LessonsLearnedRAG:
    """Lightweight RAG that loads and searches lessons from files."""

    def __init__(self, knowledge_dir: Optional[str] = None):
        self.knowledge_dir = Path(knowledge_dir or "rag_knowledge/lessons_learned")
        self.lessons = []
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

    def query(self, query: str, top_k: int = 5, severity_filter: Optional[str] = None) -> list:
        """Search lessons using simple relevance scoring."""
        if not self.lessons:
            return []

        query_terms = query.lower().split()
        results = []

        for lesson in self.lessons:
            # Filter by severity if specified
            if severity_filter and lesson["severity"] != severity_filter:
                continue

            content_lower = lesson["content"].lower()

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

            if score > 0:
                results.append(
                    {
                        "id": lesson["id"],
                        "severity": lesson["severity"],
                        "score": score,
                        "snippet": lesson["content"][:500],
                        "file": lesson["file"],
                    }
                )

        # Sort by score descending
        results.sort(key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    def get_critical_lessons(self) -> list:
        """Get all CRITICAL severity lessons."""
        return [l for l in self.lessons if l["severity"] == "CRITICAL"]

    def add_lesson(self, lesson_id: str, content: str) -> None:
        """Add a new lesson (writes to file)."""
        lesson_file = self.knowledge_dir / f"{lesson_id}.md"
        lesson_file.write_text(content)
        self._load_lessons()  # Reload

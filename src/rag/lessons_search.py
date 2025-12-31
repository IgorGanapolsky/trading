"""
LessonsSearch - Semantic search for lessons learned using ChromaDB.

This module provides proper vector-based semantic search on lessons learned,
replacing the simple keyword matching with true embeddings-based retrieval.

Created: Dec 31, 2025 (Fix for ll_054 - RAG not actually used)
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Paths
LESSONS_DIR = Path("rag_knowledge/lessons_learned")
VECTOR_DB_PATH = Path("data/vector_db")


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
    Semantic search over lessons learned using ChromaDB embeddings.

    Provides true semantic similarity search, not just keyword matching.
    Falls back to keyword search if ChromaDB is unavailable.
    """

    def __init__(self, use_chromadb: bool = True):
        """
        Initialize LessonsSearch.

        Args:
            use_chromadb: Whether to use ChromaDB for semantic search.
                         Falls back to keyword search if unavailable.
        """
        self.collection = None
        self.use_chromadb = use_chromadb
        self._lessons_cache: list[dict] = []

        if use_chromadb:
            self._init_chromadb()

        # Always load lessons for fallback
        self._load_lessons()

    def _init_chromadb(self) -> None:
        """Initialize ChromaDB collection for lessons."""
        try:
            import chromadb
            from chromadb.config import Settings

            VECTOR_DB_PATH.mkdir(parents=True, exist_ok=True)

            client = chromadb.PersistentClient(
                path=str(VECTOR_DB_PATH),
                settings=Settings(anonymized_telemetry=False),
            )

            self.collection = client.get_or_create_collection(
                name="lessons_learned",
                metadata={
                    "description": "Trading lessons learned knowledge base",
                    "hnsw:space": "cosine",
                },
            )

            logger.info(
                f"LessonsSearch: ChromaDB initialized with {self.collection.count()} documents"
            )

        except ImportError:
            logger.warning("ChromaDB not available - falling back to keyword search")
            self.collection = None
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e} - falling back to keyword search")
            self.collection = None

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
        Search lessons using semantic similarity.

        Args:
            query: Search query (e.g., "position sizing error", "API failure")
            top_k: Number of results to return
            severity_filter: Optional filter for severity level (CRITICAL, HIGH, MEDIUM, LOW)

        Returns:
            List of (LessonResult, score) tuples, sorted by relevance
        """
        # Try ChromaDB semantic search first
        if self.collection is not None and self.collection.count() > 0:
            try:
                return self._search_chromadb(query, top_k, severity_filter)
            except Exception as e:
                logger.warning(f"ChromaDB search failed: {e} - falling back to keyword")

        # Fallback to keyword search
        return self._search_keywords(query, top_k, severity_filter)

    def _search_chromadb(
        self, query: str, top_k: int, severity_filter: Optional[str]
    ) -> list[tuple[LessonResult, float]]:
        """Search using ChromaDB semantic similarity."""
        where_filter = None
        if severity_filter:
            where_filter = {"severity": severity_filter}

        results = self.collection.query(
            query_texts=[query],
            n_results=min(top_k * 2, 20),  # Get more, then filter
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )

        output = []
        if results and results.get("ids") and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                metadata = results["metadatas"][0][i] if results.get("metadatas") else {}
                document = results["documents"][0][i] if results.get("documents") else ""
                distance = results["distances"][0][i] if results.get("distances") else 1.0

                # Convert distance to similarity score (0-1)
                score = max(0, 1 - distance)

                lesson = LessonResult(
                    id=doc_id,
                    title=metadata.get("title", doc_id),
                    severity=metadata.get("severity", "MEDIUM"),
                    snippet=document[:500] if document else "",
                    prevention=metadata.get("prevention", ""),
                    file=metadata.get("file", ""),
                    score=score,
                )
                output.append((lesson, score))

        return output[:top_k]

    def _search_keywords(
        self, query: str, top_k: int, severity_filter: Optional[str]
    ) -> list[tuple[LessonResult, float]]:
        """Fallback keyword-based search."""
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
        Index all lessons into ChromaDB for semantic search.

        Args:
            force_rebuild: If True, delete existing index and rebuild

        Returns:
            Number of lessons indexed
        """
        if self.collection is None:
            logger.error("ChromaDB not available - cannot index lessons")
            return 0

        if force_rebuild:
            # Clear existing documents
            try:
                existing_ids = self.collection.get()["ids"]
                if existing_ids:
                    self.collection.delete(ids=existing_ids)
                    logger.info(f"Cleared {len(existing_ids)} existing documents")
            except Exception as e:
                logger.warning(f"Failed to clear collection: {e}")

        indexed = 0
        for lesson in self._lessons_cache:
            try:
                self.collection.upsert(
                    ids=[lesson["id"]],
                    documents=[lesson["content"]],
                    metadatas=[
                        {
                            "title": lesson["title"],
                            "severity": lesson["severity"],
                            "prevention": lesson["prevention"][:500],
                            "file": lesson["file"],
                        }
                    ],
                )
                indexed += 1
            except Exception as e:
                logger.warning(f"Failed to index lesson {lesson['id']}: {e}")

        logger.info(f"Indexed {indexed} lessons into ChromaDB")
        return indexed

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

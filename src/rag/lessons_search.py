"""
Lessons Learned Semantic Search

Provides semantic search over indexed lessons learned documents.
Returns top-K most relevant lesson excerpts with metadata.

Architecture:
- Uses FastEmbed for query embeddings (with TF-IDF fallback)
- Searches LanceDB vector store (with JSON fallback)
- Returns ranked results with relevance scores
- Supports metadata filtering

Usage:
    from src.rag.lessons_search import LessonsSearch

    search = LessonsSearch()
    results = search.query("How to prevent CI failures?", top_k=3)

    for result in results:
        print(f"{result['lesson_file']}: {result['section_title']}")
        print(f"Score: {result['score']:.3f}")
        print(f"Content: {result['content'][:200]}...")
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Import numpy only if needed
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    logger.warning("numpy not installed - limited fallback capabilities")

# Lazy imports for optional dependencies
FASTEMBED_AVAILABLE = False
LANCEDB_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
except ImportError:
    logger.warning("fastembed not installed - will use TF-IDF fallback")

try:
    import lancedb
    LANCEDB_AVAILABLE = True
except ImportError:
    logger.warning("lancedb not installed - will use JSON fallback")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    SKLEARN_AVAILABLE = True
except ImportError:
    logger.warning("scikit-learn not installed - limited search capabilities")


@dataclass
class SearchResult:
    """Represents a search result."""

    lesson_file: str
    section_title: str
    content: str
    score: float
    metadata: dict[str, Any]
    chunk_index: int

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "lesson_file": self.lesson_file,
            "section_title": self.section_title,
            "content": self.content,
            "score": float(self.score),
            "metadata": self.metadata,
            "chunk_index": self.chunk_index,
        }


class LessonsSearch:
    """
    Semantic search over lessons learned documents.

    Features:
    - Fast vector similarity search
    - FastEmbed or TF-IDF embeddings
    - Configurable top-K results
    - Metadata filtering (severity, category, date)
    - Relevance scoring

    Storage:
    - Vector DB: data/rag/lessons_learned_db/
    - Fallback JSON: data/rag/lessons_learned_index.json
    """

    def __init__(
        self,
        db_path: str = "data/rag/lessons_learned_db",
    ):
        """
        Initialize the lessons search engine.

        Args:
            db_path: Path to vector database storage
        """
        self.db_path = Path(db_path)
        self.table_name = "lessons"

        # Initialize fallback storage first (needed by _init_tfidf)
        self.fallback_index_path = Path("data/rag/lessons_learned_index.json")
        self.fallback_data = []

        # Initialize database
        self.db = None
        self.table = None

        if LANCEDB_AVAILABLE and self.db_path.exists():
            try:
                self.db = lancedb.connect(str(self.db_path))
                if self.table_name in self.db.table_names():
                    self.table = self.db.open_table(self.table_name)
                    logger.info(f"Connected to LanceDB table: {self.table_name}")
                else:
                    logger.warning(f"Table {self.table_name} not found in LanceDB")
            except Exception as e:
                logger.warning(f"LanceDB connection failed: {e}, using JSON fallback")

        # Load fallback data if not using LanceDB
        if not self.table and self.fallback_index_path.exists():
            try:
                self.fallback_data = json.loads(self.fallback_index_path.read_text())
                logger.info(f"Loaded {len(self.fallback_data)} chunks from JSON fallback")
            except Exception as e:
                logger.error(f"Failed to load JSON fallback: {e}")

        # Initialize embedding model
        self.embedding_model = None
        self.use_tfidf = False
        self.tfidf_vectorizer = None

        if FASTEMBED_AVAILABLE:
            try:
                self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                logger.info("Using FastEmbed for query embeddings")
            except Exception as e:
                logger.warning(f"FastEmbed initialization failed: {e}")
                self._init_tfidf()
        else:
            self._init_tfidf()

    def _init_tfidf(self):
        """Initialize TF-IDF vectorizer for search."""
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available, cannot use TF-IDF fallback")
            return

        self.use_tfidf = True

        # Try to load pre-fitted vectorizer from indexing
        vectorizer_path = Path("data/rag/tfidf_vectorizer.pkl")
        if vectorizer_path.exists():
            try:
                import pickle
                with open(vectorizer_path, 'rb') as f:
                    self.tfidf_vectorizer = pickle.load(f)  # noqa: S301 - trusted local vectorizer file
                logger.info("Loaded pre-fitted TF-IDF vectorizer from indexing")
                return
            except Exception as e:
                logger.warning(f"Failed to load pre-fitted vectorizer: {e}")

        # Fallback: create and fit on existing corpus
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=384,
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
        )
        logger.info("Initialized TF-IDF vectorizer for search")

        # Fit on existing corpus if using fallback
        if self.fallback_data:
            corpus = [item["content"] for item in self.fallback_data]
            try:
                self.tfidf_vectorizer.fit(corpus)
                logger.info("TF-IDF vectorizer fitted on corpus")
            except Exception as e:
                logger.error(f"Failed to fit TF-IDF: {e}")

    def _generate_query_embedding(self, query: str) -> list[float]:
        """
        Generate embedding for search query.

        Args:
            query: Search query text

        Returns:
            Embedding vector
        """
        if self.embedding_model and not self.use_tfidf:
            # Use FastEmbed
            try:
                embeddings = list(self.embedding_model.embed([query]))
                return embeddings[0].tolist()
            except Exception as e:
                logger.error(f"FastEmbed query embedding failed: {e}")
                return [0.0] * 384

        elif self.use_tfidf and self.tfidf_vectorizer:
            # Use TF-IDF
            try:
                tfidf_vector = self.tfidf_vectorizer.transform([query])
                return tfidf_vector.toarray()[0].tolist()
            except Exception as e:
                logger.error(f"TF-IDF query embedding failed: {e}")
                return [0.0] * 384

        else:
            logger.warning("No embedding model available for query")
            return [0.0] * 384

    def query(
        self,
        query_text: str,
        top_k: int = 3,
        filters: dict[str, Any] | None = None,
    ) -> list[SearchResult]:
        """
        Search for relevant lessons.

        Args:
            query_text: Natural language search query
            top_k: Number of results to return (default: 3)
            filters: Optional metadata filters (e.g., {"severity": "HIGH"})

        Returns:
            List of SearchResult objects, ranked by relevance
        """
        logger.info(f"Searching for: '{query_text}' (top_k={top_k})")

        # Generate query embedding
        query_vector = self._generate_query_embedding(query_text)

        # Search using LanceDB or fallback
        if self.table:
            return self._search_lancedb(query_vector, top_k, filters)
        else:
            return self._search_fallback(query_vector, query_text, top_k, filters)

    def _search_lancedb(
        self,
        query_vector: list[float],
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Search using LanceDB."""
        try:
            # Perform vector search
            results = self.table.search(query_vector).limit(top_k).to_list()

            # Convert to SearchResult objects
            search_results = []
            for result in results:
                # Parse metadata JSON
                metadata = {}
                if "metadata" in result:
                    try:
                        metadata = json.loads(result["metadata"])
                    except Exception:
                        pass

                # Apply filters if specified
                if filters and not self._matches_filters(metadata, filters):
                    continue

                search_results.append(SearchResult(
                    lesson_file=result.get("lesson_file", "unknown"),
                    section_title=result.get("section_title", ""),
                    content=result.get("content", ""),
                    score=1.0 - result.get("_distance", 0.0),  # Convert distance to similarity
                    metadata=metadata,
                    chunk_index=result.get("chunk_index", 0),
                ))

            logger.info(f"Found {len(search_results)} results from LanceDB")
            return search_results

        except Exception as e:
            logger.error(f"LanceDB search failed: {e}")
            return []

    def _search_fallback(
        self,
        query_vector: list[float],
        query_text: str,
        top_k: int,
        filters: dict[str, Any] | None,
    ) -> list[SearchResult]:
        """Search using JSON fallback with cosine similarity."""
        if not self.fallback_data:
            logger.warning("No fallback data available for search")
            return []

        try:
            # Calculate similarities
            results_with_scores = []

            for item in self.fallback_data:
                # Parse metadata
                metadata = {}
                if "metadata" in item:
                    try:
                        metadata = json.loads(item["metadata"])
                    except Exception:
                        pass

                # Apply filters
                if filters and not self._matches_filters(metadata, filters):
                    continue

                # Calculate similarity
                item_vector = item.get("vector", [0.0] * 384)
                if SKLEARN_AVAILABLE:
                    similarity = cosine_similarity([query_vector], [item_vector])[0][0]
                elif NUMPY_AVAILABLE:
                    # Simple dot product fallback
                    similarity = np.dot(query_vector, item_vector) / (
                        np.linalg.norm(query_vector) * np.linalg.norm(item_vector) + 1e-8
                    )
                else:
                    # Pure Python fallback
                    dot_product = sum(a * b for a, b in zip(query_vector, item_vector))
                    norm_query = sum(a ** 2 for a in query_vector) ** 0.5
                    norm_item = sum(b ** 2 for b in item_vector) ** 0.5
                    similarity = dot_product / (norm_query * norm_item + 1e-8)

                results_with_scores.append((similarity, item, metadata))

            # Sort by similarity and take top_k
            results_with_scores.sort(key=lambda x: x[0], reverse=True)
            top_results = results_with_scores[:top_k]

            # Convert to SearchResult objects
            search_results = []
            for score, item, metadata in top_results:
                search_results.append(SearchResult(
                    lesson_file=item.get("lesson_file", "unknown"),
                    section_title=item.get("section_title", ""),
                    content=item.get("content", ""),
                    score=float(score),
                    metadata=metadata,
                    chunk_index=item.get("chunk_index", 0),
                ))

            logger.info(f"Found {len(search_results)} results from JSON fallback")
            return search_results

        except Exception as e:
            logger.error(f"Fallback search failed: {e}")
            return []

    def _matches_filters(self, metadata: dict[str, Any], filters: dict[str, Any]) -> bool:
        """Check if metadata matches filter criteria."""
        for key, value in filters.items():
            if key not in metadata or metadata[key] != value:
                return False
        return True

    def get_all_lessons(self) -> list[str]:
        """Get list of all indexed lesson files."""
        lessons = set()

        if self.table:
            try:
                results = self.table.to_pandas()
                lessons = set(results["lesson_file"].unique())
            except Exception as e:
                logger.error(f"Failed to get lessons from LanceDB: {e}")

        elif self.fallback_data:
            lessons = set(item["lesson_file"] for item in self.fallback_data)

        return sorted(lessons)

    def get_stats(self) -> dict[str, Any]:
        """Get search engine statistics."""
        total_chunks = 0
        total_files = 0

        if self.table:
            try:
                total_chunks = self.table.count_rows()
                total_files = len(self.get_all_lessons())
            except Exception:
                pass
        elif self.fallback_data:
            total_chunks = len(self.fallback_data)
            total_files = len(self.get_all_lessons())

        return {
            "total_chunks": total_chunks,
            "total_files": total_files,
            "using_fastembed": FASTEMBED_AVAILABLE and self.embedding_model is not None,
            "using_lancedb": self.table is not None,
            "using_tfidf": self.use_tfidf,
        }


if __name__ == "__main__":
    # Simple CLI for testing
    logging.basicConfig(level=logging.INFO)

    search = LessonsSearch()

    # Print stats
    stats = search.get_stats()
    print("\n=== Search Engine Stats ===")
    print(f"Total chunks: {stats['total_chunks']}")
    print(f"Total files: {stats['total_files']}")
    print(f"Using FastEmbed: {stats['using_fastembed']}")
    print(f"Using LanceDB: {stats['using_lancedb']}")
    print(f"Using TF-IDF: {stats['using_tfidf']}")

    # Example search
    query = "How to prevent CI failures?"
    print(f"\n=== Searching: '{query}' ===")
    results = search.query(query, top_k=3)

    for i, result in enumerate(results, 1):
        print(f"\n[{i}] {result.lesson_file} - {result.section_title}")
        print(f"Score: {result.score:.3f}")
        print(f"Content: {result.content[:200]}...")

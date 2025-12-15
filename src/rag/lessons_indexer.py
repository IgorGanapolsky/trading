"""
Lessons Learned Vector Store Indexer

Indexes markdown files from rag_knowledge/lessons_learned/ into a vector store
for semantic search. Uses FastEmbed for embeddings with TF-IDF fallback.

Architecture:
- Chunks documents by ## headers (sections)
- Generates embeddings using FastEmbed (BAAI/bge-small-en-v1.5)
- Stores in LanceDB at data/rag/lessons_learned_db/
- Falls back to TF-IDF if FastEmbed unavailable

Usage:
    from src.rag.lessons_indexer import LessonsIndexer

    indexer = LessonsIndexer()
    indexer.index_all_lessons()
    print(f"Indexed {indexer.get_stats()} lessons")
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Lazy imports for optional dependencies
FASTEMBED_AVAILABLE = False
LANCEDB_AVAILABLE = False
SKLEARN_AVAILABLE = False

try:
    from fastembed import TextEmbedding
    FASTEMBED_AVAILABLE = True
    logger.info("FastEmbed available for lessons indexing")
except ImportError:
    logger.warning("fastembed not installed - will use TF-IDF fallback")

try:
    import lancedb
    LANCEDB_AVAILABLE = True
    logger.info("LanceDB available for lessons storage")
except ImportError:
    logger.warning("lancedb not installed - will use JSON fallback")

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    SKLEARN_AVAILABLE = True
    logger.info("scikit-learn available for TF-IDF fallback")
except ImportError:
    logger.warning("scikit-learn not installed - limited fallback capabilities")


@dataclass
class LessonChunk:
    """Represents a chunk of a lesson learned document."""

    lesson_file: str
    section_title: str
    content: str
    chunk_index: int
    metadata: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            "lesson_file": self.lesson_file,
            "section_title": self.section_title,
            "content": self.content,
            "chunk_index": self.chunk_index,
            "metadata": json.dumps(self.metadata),
            "indexed_at": datetime.now().isoformat(),
        }


class LessonsIndexer:
    """
    Indexes lessons learned markdown files into a vector store.

    Features:
    - Chunks by ## headers (sections)
    - Extracts metadata from frontmatter
    - Generates embeddings (FastEmbed or TF-IDF)
    - Stores in LanceDB or JSON fallback
    - Tracks indexing statistics

    Storage:
    - Vector DB: data/rag/lessons_learned_db/
    - Fallback JSON: data/rag/lessons_learned_index.json
    - TF-IDF Model: data/rag/lessons_tfidf_model.json
    """

    def __init__(
        self,
        lessons_dir: str = "rag_knowledge/lessons_learned",
        db_path: str = "data/rag/lessons_learned_db",
    ):
        """
        Initialize the lessons indexer.

        Args:
            lessons_dir: Directory containing lesson markdown files
            db_path: Path to vector database storage
        """
        self.lessons_dir = Path(lessons_dir)
        self.db_path = Path(db_path)
        self.table_name = "lessons"

        # Create directories
        self.db_path.mkdir(parents=True, exist_ok=True)

        # Initialize embedding model
        self.embedding_model = None
        self.use_tfidf = False
        self.tfidf_vectorizer = None

        if FASTEMBED_AVAILABLE:
            try:
                self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
                logger.info("Using FastEmbed for lesson embeddings")
            except Exception as e:
                logger.warning(f"FastEmbed initialization failed: {e}, falling back to TF-IDF")
                self._init_tfidf()
        else:
            self._init_tfidf()

        # Initialize database
        self.db = None
        self.table = None

        if LANCEDB_AVAILABLE:
            try:
                self.db = lancedb.connect(str(self.db_path))
                logger.info(f"Connected to LanceDB at {self.db_path}")
            except Exception as e:
                logger.warning(f"LanceDB initialization failed: {e}, using JSON fallback")

        # Fallback storage
        self.fallback_index_path = Path("data/rag/lessons_learned_index.json")
        self.fallback_index_path.parent.mkdir(parents=True, exist_ok=True)

        # Stats
        self.stats = {
            "total_files": 0,
            "total_chunks": 0,
            "indexed_at": None,
            "using_fastembed": FASTEMBED_AVAILABLE and self.embedding_model is not None,
            "using_lancedb": LANCEDB_AVAILABLE and self.db is not None,
            "using_tfidf": self.use_tfidf,
        }

    def _init_tfidf(self):
        """Initialize TF-IDF vectorizer as fallback."""
        if not SKLEARN_AVAILABLE:
            logger.error("scikit-learn not available, cannot use TF-IDF fallback")
            return

        self.use_tfidf = True
        self.tfidf_vectorizer = TfidfVectorizer(
            max_features=384,  # Match FastEmbed dimension
            stop_words='english',
            ngram_range=(1, 2),
            min_df=1,
            max_df=0.95,
        )
        logger.info("Initialized TF-IDF vectorizer as fallback")

    def _extract_metadata(self, content: str) -> dict[str, Any]:
        """
        Extract metadata from lesson frontmatter.

        Args:
            content: Full markdown content

        Returns:
            Dictionary of metadata (date, severity, category, etc.)
        """
        metadata = {}

        # Extract frontmatter-style metadata
        lines = content.split('\n')
        for line in lines[:20]:  # Check first 20 lines
            if match := re.match(r'\*\*(\w+)\*\*:\s*(.+)', line):
                key, value = match.groups()
                metadata[key.lower()] = value.strip()

        return metadata

    def _chunk_by_sections(self, content: str, filename: str) -> list[LessonChunk]:
        """
        Chunk markdown content by ## headers.

        Args:
            content: Full markdown content
            filename: Name of the source file

        Returns:
            List of LessonChunk objects
        """
        chunks = []

        # Extract metadata
        metadata = self._extract_metadata(content)

        # Split by ## headers
        sections = re.split(r'\n## ', content)

        for idx, section in enumerate(sections):
            section = section.strip()
            if not section:
                continue

            # Extract section title
            lines = section.split('\n', 1)
            if len(lines) == 1:
                title = "Introduction"
                section_content = lines[0]
            else:
                title = lines[0].replace('#', '').strip()
                section_content = lines[1] if len(lines) > 1 else ""

            # Skip empty sections
            if not section_content.strip():
                continue

            chunk = LessonChunk(
                lesson_file=filename,
                section_title=title,
                content=section_content.strip(),
                chunk_index=idx,
                metadata=metadata,
            )
            chunks.append(chunk)

        return chunks

    def _generate_embeddings(self, texts: list[str]) -> list[list[float]]:
        """
        Generate embeddings for texts.

        Args:
            texts: List of text strings

        Returns:
            List of embedding vectors
        """
        if self.embedding_model and not self.use_tfidf:
            # Use FastEmbed
            try:
                embeddings = list(self.embedding_model.embed(texts))
                return [emb.tolist() for emb in embeddings]
            except Exception as e:
                logger.error(f"FastEmbed embedding failed: {e}")
                return [[0.0] * 384 for _ in texts]

        elif self.use_tfidf and self.tfidf_vectorizer:
            # Use TF-IDF - fit or transform depending on whether already fitted
            try:
                # For TF-IDF, we fit on ALL texts at once, not per file
                # This is handled in index_all_lessons
                if hasattr(self, '_all_texts'):
                    # Transform using fitted model
                    tfidf_matrix = self.tfidf_vectorizer.transform(texts)
                else:
                    # Fit and transform (single file mode)
                    tfidf_matrix = self.tfidf_vectorizer.fit_transform(texts)
                return tfidf_matrix.toarray().tolist()
            except Exception as e:
                logger.error(f"TF-IDF embedding failed: {e}")
                return [[0.0] * 384 for _ in texts]

        else:
            # No embedding capability
            logger.warning("No embedding model available")
            return [[0.0] * 384 for _ in texts]

    def index_file(self, filepath: Path) -> int:
        """
        Index a single lesson file.

        Args:
            filepath: Path to markdown file

        Returns:
            Number of chunks indexed
        """
        logger.info(f"Indexing {filepath.name}...")

        try:
            content = filepath.read_text(encoding='utf-8')
        except Exception as e:
            logger.error(f"Failed to read {filepath}: {e}")
            return 0

        # Chunk the document
        chunks = self._chunk_by_sections(content, filepath.name)

        if not chunks:
            logger.warning(f"No chunks extracted from {filepath.name}")
            return 0

        # Generate embeddings
        texts = [chunk.content for chunk in chunks]
        embeddings = self._generate_embeddings(texts)

        # Prepare data for storage
        records = []
        for chunk, embedding in zip(chunks, embeddings):
            record = chunk.to_dict()
            record["vector"] = embedding
            records.append(record)

        # Store in database
        if self.db:
            try:
                # Create or append to table
                if self.table_name in self.db.table_names():
                    table = self.db.open_table(self.table_name)
                    table.add(records)
                else:
                    self.table = self.db.create_table(self.table_name, records)

                logger.info(f"Stored {len(records)} chunks in LanceDB")
            except Exception as e:
                logger.error(f"LanceDB storage failed: {e}, using JSON fallback")
                self._store_fallback(records)
        else:
            self._store_fallback(records)

        return len(chunks)

    def _store_fallback(self, records: list[dict[str, Any]]):
        """Store records in JSON fallback."""
        existing = []
        if self.fallback_index_path.exists():
            try:
                existing = json.loads(self.fallback_index_path.read_text())
            except Exception as e:
                logger.warning(f"Failed to read existing fallback index: {e}")

        existing.extend(records)

        try:
            self.fallback_index_path.write_text(
                json.dumps(existing, indent=2),
                encoding='utf-8'
            )
            logger.info(f"Stored {len(records)} chunks in JSON fallback")
        except Exception as e:
            logger.error(f"JSON fallback storage failed: {e}")

    def index_all_lessons(self) -> dict[str, Any]:
        """
        Index all lesson files in the lessons directory.

        Returns:
            Statistics dictionary
        """
        logger.info(f"Starting indexing of all lessons in {self.lessons_dir}...")

        # Get all markdown files
        lesson_files = sorted(self.lessons_dir.glob("*.md"))

        if not lesson_files:
            logger.warning(f"No lesson files found in {self.lessons_dir}")
            return self.stats

        # For TF-IDF, we need to fit on ALL text at once
        if self.use_tfidf and self.tfidf_vectorizer:
            logger.info("Collecting all texts for TF-IDF fitting...")
            all_chunks = []
            for filepath in lesson_files:
                content = filepath.read_text(encoding='utf-8')
                chunks = self._chunk_by_sections(content, filepath.name)
                all_chunks.extend(chunks)

            # Fit TF-IDF on entire corpus
            all_texts = [chunk.content for chunk in all_chunks]
            logger.info(f"Fitting TF-IDF on {len(all_texts)} chunks...")
            try:
                self.tfidf_vectorizer.fit(all_texts)
                self._all_texts = all_texts  # Mark as fitted
                logger.info("TF-IDF vectorizer fitted successfully")

                # Save the vectorizer for later use
                import pickle
                vectorizer_path = Path("data/rag/tfidf_vectorizer.pkl")
                vectorizer_path.parent.mkdir(parents=True, exist_ok=True)
                with open(vectorizer_path, 'wb') as f:
                    pickle.dump(self.tfidf_vectorizer, f)
                logger.info(f"Saved TF-IDF vectorizer to {vectorizer_path}")
            except Exception as e:
                logger.error(f"Failed to fit TF-IDF: {e}")
                return self.stats

        total_chunks = 0

        for filepath in lesson_files:
            chunks = self.index_file(filepath)
            total_chunks += chunks

        # Update stats
        self.stats["total_files"] = len(lesson_files)
        self.stats["total_chunks"] = total_chunks
        self.stats["indexed_at"] = datetime.now().isoformat()

        # Save stats
        stats_path = Path("data/rag/lessons_indexing_stats.json")
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps(self.stats, indent=2))

        logger.info(f"Indexing complete: {len(lesson_files)} files, {total_chunks} chunks")

        return self.stats

    def get_stats(self) -> dict[str, Any]:
        """Get indexing statistics."""
        return self.stats

    def clear_index(self):
        """Clear the entire index (use with caution)."""
        if self.db and self.table_name in self.db.table_names():
            try:
                self.db.drop_table(self.table_name)
                logger.info(f"Dropped table {self.table_name}")
            except Exception as e:
                logger.error(f"Failed to drop table: {e}")

        if self.fallback_index_path.exists():
            self.fallback_index_path.unlink()
            logger.info("Cleared JSON fallback index")


if __name__ == "__main__":
    # Simple CLI for testing
    logging.basicConfig(level=logging.INFO)

    indexer = LessonsIndexer()
    stats = indexer.index_all_lessons()

    print("\n=== Indexing Complete ===")
    print(f"Files indexed: {stats['total_files']}")
    print(f"Chunks created: {stats['total_chunks']}")
    print(f"Using FastEmbed: {stats['using_fastembed']}")
    print(f"Using LanceDB: {stats['using_lancedb']}")
    print(f"Using TF-IDF: {stats['using_tfidf']}")
    print(f"Indexed at: {stats['indexed_at']}")

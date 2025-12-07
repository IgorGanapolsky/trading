"""
Semantic Query Cache for RAG System

Provides intelligent caching for RAG queries to reduce latency and
avoid redundant embedding computations.

Features:
- Semantic similarity-based cache lookup (not just exact match)
- TTL-based expiration for fresh results
- LRU eviction for memory management
- Cache hit/miss analytics
- Configurable similarity threshold

Author: Trading System
Created: 2025-12-01
"""

import hashlib
import json
import logging
import sqlite3
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class CacheEntry:
    """A cached query result."""

    query: str
    query_hash: str
    results: list[dict[str, Any]]
    embedding: list[float] | None = None
    created_at: float = field(default_factory=time.time)
    hits: int = 0
    ticker: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self, ttl_seconds: float) -> bool:
        """Check if entry is expired."""
        return time.time() - self.created_at > ttl_seconds

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "query": self.query,
            "query_hash": self.query_hash,
            "results": self.results,
            "embedding": self.embedding,
            "created_at": self.created_at,
            "hits": self.hits,
            "ticker": self.ticker,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CacheEntry":
        """Create from dictionary."""
        return cls(**data)


@dataclass
class CacheStats:
    """Cache statistics."""

    hits: int = 0
    misses: int = 0
    semantic_hits: int = 0  # Hits via semantic similarity
    exact_hits: int = 0  # Hits via exact query match
    evictions: int = 0
    expirations: int = 0

    @property
    def hit_rate(self) -> float:
        """Calculate cache hit rate."""
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "semantic_hits": self.semantic_hits,
            "exact_hits": self.exact_hits,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": f"{self.hit_rate:.1%}",
        }


class SemanticQueryCache:
    """
    Semantic query cache for RAG system.

    Caches query results and uses embedding similarity for cache lookups,
    so similar queries can return cached results even if not exactly matching.

    Args:
        capacity: Maximum number of entries to cache
        ttl_seconds: Time-to-live for cached entries (default: 1 hour)
        similarity_threshold: Minimum similarity for semantic cache hit (0-1)
        db_path: Path to SQLite persistence (optional)
        embedder: Embedding function (optional, for semantic matching)
    """

    def __init__(
        self,
        capacity: int = 1000,
        ttl_seconds: float = 3600,
        similarity_threshold: float = 0.9,
        db_path: str | None = None,
        embedder=None,
    ):
        self.capacity = capacity
        self.ttl_seconds = ttl_seconds
        self.similarity_threshold = similarity_threshold
        self.embedder = embedder

        # In-memory cache (LRU)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()

        # Embedding index for semantic lookup
        self._embeddings: dict[str, np.ndarray] = {}

        # Statistics
        self.stats = CacheStats()

        # Persistence
        self.db_path = Path(db_path) if db_path else None
        if self.db_path:
            self._init_database()
            self._load_from_db()

        logger.info(
            f"SemanticQueryCache initialized: capacity={capacity}, "
            f"ttl={ttl_seconds}s, threshold={similarity_threshold}"
        )

    def _init_database(self) -> None:
        """Initialize SQLite database for persistence."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_cache (
                    query_hash TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    results TEXT NOT NULL,
                    embedding TEXT,
                    created_at REAL NOT NULL,
                    hits INTEGER DEFAULT 0,
                    ticker TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON query_cache(created_at DESC)
            """)
            conn.commit()

    def _load_from_db(self) -> None:
        """Load cache entries from database."""
        if not self.db_path or not self.db_path.exists():
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    SELECT query_hash, query, results, embedding, created_at,
                           hits, ticker, metadata
                    FROM query_cache
                    ORDER BY created_at DESC
                    LIMIT ?
                """,
                    (self.capacity,),
                )

                for row in cursor.fetchall():
                    entry = CacheEntry(
                        query_hash=row[0],
                        query=row[1],
                        results=json.loads(row[2]),
                        embedding=json.loads(row[3]) if row[3] else None,
                        created_at=row[4],
                        hits=row[5],
                        ticker=row[6],
                        metadata=json.loads(row[7]) if row[7] else {},
                    )

                    # Skip expired entries
                    if not entry.is_expired(self.ttl_seconds):
                        self._cache[entry.query_hash] = entry
                        if entry.embedding:
                            self._embeddings[entry.query_hash] = np.array(entry.embedding)

            logger.info(f"Loaded {len(self._cache)} entries from cache database")

        except Exception as e:
            logger.warning(f"Failed to load cache from database: {e}")

    def _save_to_db(self, entry: CacheEntry) -> None:
        """Save entry to database."""
        if not self.db_path:
            return

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO query_cache
                    (query_hash, query, results, embedding, created_at, hits, ticker, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                    (
                        entry.query_hash,
                        entry.query,
                        json.dumps(entry.results),
                        json.dumps(entry.embedding) if entry.embedding else None,
                        entry.created_at,
                        entry.hits,
                        entry.ticker,
                        json.dumps(entry.metadata),
                    ),
                )
                conn.commit()
        except Exception as e:
            logger.warning(f"Failed to save cache entry: {e}")

    def get(
        self,
        query: str,
        ticker: str | None = None,
        use_semantic: bool = True,
    ) -> list[dict[str, Any]] | None:
        """
        Get cached results for a query.

        Args:
            query: Query string
            ticker: Optional ticker filter
            use_semantic: Whether to use semantic matching

        Returns:
            Cached results or None if not found
        """
        query_hash = self._hash_query(query, ticker)

        # Check exact match first
        entry = self._cache.get(query_hash)
        if entry and not entry.is_expired(self.ttl_seconds):
            entry.hits += 1
            self._cache.move_to_end(query_hash)
            self.stats.hits += 1
            self.stats.exact_hits += 1
            logger.debug(f"Cache exact hit for query: {query[:50]}...")
            return entry.results

        # Check semantic match if embedder available
        if use_semantic and self.embedder and len(self._embeddings) > 0:
            similar_entry = self._find_semantic_match(query, ticker)
            if similar_entry:
                similar_entry.hits += 1
                self.stats.hits += 1
                self.stats.semantic_hits += 1
                logger.debug(f"Cache semantic hit for query: {query[:50]}...")
                return similar_entry.results

        # Expired entry cleanup
        if entry and entry.is_expired(self.ttl_seconds):
            self._evict(query_hash)
            self.stats.expirations += 1

        self.stats.misses += 1
        return None

    def put(
        self,
        query: str,
        results: list[dict[str, Any]],
        ticker: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """
        Cache query results.

        Args:
            query: Query string
            results: Query results to cache
            ticker: Optional ticker filter
            metadata: Optional metadata
        """
        query_hash = self._hash_query(query, ticker)

        # Compute embedding if embedder available
        embedding = None
        if self.embedder:
            try:
                embedding = self.embedder(query)
                if isinstance(embedding, np.ndarray):
                    embedding = embedding.tolist()
            except Exception as e:
                logger.debug(f"Failed to compute embedding: {e}")

        entry = CacheEntry(
            query=query,
            query_hash=query_hash,
            results=results,
            embedding=embedding,
            ticker=ticker,
            metadata=metadata or {},
        )

        # Evict if at capacity
        while len(self._cache) >= self.capacity:
            oldest_key = next(iter(self._cache))
            self._evict(oldest_key)
            self.stats.evictions += 1

        # Store
        self._cache[query_hash] = entry
        if embedding:
            self._embeddings[query_hash] = np.array(embedding)

        # Persist
        self._save_to_db(entry)

        logger.debug(f"Cached query: {query[:50]}... ({len(results)} results)")

    def _find_semantic_match(self, query: str, ticker: str | None) -> CacheEntry | None:
        """Find semantically similar cached query."""
        if not self.embedder or len(self._embeddings) == 0:
            return None

        try:
            query_embedding = self.embedder(query)
            if isinstance(query_embedding, list):
                query_embedding = np.array(query_embedding)

            best_match = None
            best_similarity = 0.0

            for hash_key, cached_embedding in self._embeddings.items():
                entry = self._cache.get(hash_key)
                if not entry or entry.is_expired(self.ttl_seconds):
                    continue

                # Filter by ticker if specified
                if ticker and entry.ticker and entry.ticker != ticker:
                    continue

                # Compute cosine similarity
                similarity = self._cosine_similarity(query_embedding, cached_embedding)

                if similarity > best_similarity and similarity >= self.similarity_threshold:
                    best_similarity = similarity
                    best_match = entry

            if best_match:
                logger.debug(f"Semantic match found with similarity {best_similarity:.3f}")

            return best_match

        except Exception as e:
            logger.debug(f"Semantic matching failed: {e}")
            return None

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Compute cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _hash_query(self, query: str, ticker: str | None) -> str:
        """Generate hash for query."""
        content = f"{query}|{ticker or ''}"
        return hashlib.md5(content.encode()).hexdigest()

    def _evict(self, key: str) -> None:
        """Evict entry from cache."""
        self._cache.pop(key, None)
        self._embeddings.pop(key, None)

    def invalidate(self, ticker: str | None = None) -> int:
        """
        Invalidate cache entries.

        Args:
            ticker: If specified, only invalidate entries for this ticker

        Returns:
            Number of entries invalidated
        """
        if ticker is None:
            count = len(self._cache)
            self._cache.clear()
            self._embeddings.clear()
            return count

        keys_to_remove = [k for k, v in self._cache.items() if v.ticker == ticker]

        for key in keys_to_remove:
            self._evict(key)

        return len(keys_to_remove)

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        stats = self.stats.to_dict()
        stats["entries"] = len(self._cache)
        stats["capacity"] = self.capacity
        stats["memory_usage_mb"] = self._estimate_memory_usage() / (1024 * 1024)
        return stats

    def _estimate_memory_usage(self) -> int:
        """Estimate memory usage in bytes."""
        # Rough estimate
        total = 0
        for entry in self._cache.values():
            total += len(entry.query.encode())
            total += len(json.dumps(entry.results).encode())
            if entry.embedding:
                total += len(entry.embedding) * 4  # float32
        return total

    def cleanup_expired(self) -> int:
        """Remove expired entries."""
        expired_keys = [k for k, v in self._cache.items() if v.is_expired(self.ttl_seconds)]

        for key in expired_keys:
            self._evict(key)
            self.stats.expirations += 1

        if expired_keys:
            logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")

        return len(expired_keys)


# Global cache instance
_query_cache: SemanticQueryCache | None = None


def get_query_cache(
    embedder=None,
    db_path: str = "data/rag/query_cache.db",
) -> SemanticQueryCache:
    """Get or create global query cache instance."""
    global _query_cache

    if _query_cache is None:
        _query_cache = SemanticQueryCache(
            capacity=1000,
            ttl_seconds=3600,  # 1 hour
            similarity_threshold=0.9,
            db_path=db_path,
            embedder=embedder,
        )

    return _query_cache


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("SEMANTIC QUERY CACHE DEMO")
    print("=" * 80)

    cache = SemanticQueryCache(capacity=100, ttl_seconds=3600)

    # Store some queries
    print("\nStoring queries...")
    cache.put(
        query="What is the latest news for NVDA?",
        results=[{"title": "NVDA hits new high", "sentiment": 0.8}],
        ticker="NVDA",
    )

    cache.put(
        query="AAPL earnings report analysis",
        results=[{"title": "Apple beats expectations", "sentiment": 0.7}],
        ticker="AAPL",
    )

    # Test exact match
    print("\nTesting exact match...")
    results = cache.get("What is the latest news for NVDA?", ticker="NVDA")
    print(f"  Results: {results}")

    # Test miss
    print("\nTesting cache miss...")
    results = cache.get("Random query that doesn't exist")
    print(f"  Results: {results}")

    # Print stats
    print("\nCache Statistics:")
    stats = cache.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

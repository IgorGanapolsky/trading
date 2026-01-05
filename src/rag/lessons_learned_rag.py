"""
Lessons Learned RAG System

Stores and retrieves trading mistakes, bugs, and lessons learned using
vector similarity search. Integrates with pre-trade verification to
prevent repeating past mistakes.

Key Features:
1. ChromaDB vector storage with persistent embeddings (Dec 15, 2025)
2. Semantic search for similar past issues
3. Automatic ingestion of post-trade anomalies
4. Category-based filtering (size_error, execution, strategy, etc.)
5. Integration with verification pipeline
6. Cohere Rerank for improved retrieval quality

Storage Strategy (Dec 15, 2025):
1. ChromaDB with sentence-transformers embeddings (primary - production)
2. JSON + numpy fallback (backward compatibility)

Embedding Strategy (Dec 2025):
1. OpenAI API via OpenRouter (primary - fast, cheap, high quality)
2. sentence-transformers local (fallback - no API needed)
3. Keyword search (final fallback - no ML needed)

Author: Trading System
Created: 2025-12-11
Updated: 2025-12-15 (ChromaDB integration)
"""

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)

# ChromaDB availability
CHROMA_AVAILABLE = False
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions

    CHROMA_AVAILABLE = True
    logger.info("ChromaDB available for vector storage")
except ImportError:
    logger.warning("ChromaDB not available. Install with: pip install chromadb")

# Embedding availability flags
OPENAI_EMBEDDINGS_AVAILABLE = False
LOCAL_EMBEDDINGS_AVAILABLE = False

# Try OpenAI/OpenRouter API first (preferred for 2025)
try:
    # Check if API keys are available (httpx imported lazily when needed)
    OPENAI_EMBEDDINGS_AVAILABLE = bool(
        os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
    )
    if OPENAI_EMBEDDINGS_AVAILABLE:
        logger.info("OpenAI/OpenRouter embeddings available (API)")
except ImportError:
    pass

# Try sentence-transformers as fallback
try:
    from sentence_transformers import SentenceTransformer

    LOCAL_EMBEDDINGS_AVAILABLE = True
    logger.info("sentence-transformers available (local)")
except ImportError:
    pass

# Combined availability
EMBEDDINGS_AVAILABLE = OPENAI_EMBEDDINGS_AVAILABLE or LOCAL_EMBEDDINGS_AVAILABLE
if not EMBEDDINGS_AVAILABLE:
    logger.warning("No embeddings available. Using keyword search fallback.")


@dataclass
class Lesson:
    """A single lesson learned entry."""

    id: str
    timestamp: str
    category: str
    title: str
    description: str
    root_cause: str
    prevention: str
    tags: list[str]
    severity: str  # "low", "medium", "high", "critical"
    financial_impact: Optional[float] = None
    symbol: Optional[str] = None
    embedding: Optional[list[float]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "root_cause": self.root_cause,
            "prevention": self.prevention,
            "tags": self.tags,
            "severity": self.severity,
            "financial_impact": self.financial_impact,
            "symbol": self.symbol,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Lesson":
        return cls(
            id=data["id"],
            timestamp=data["timestamp"],
            category=data["category"],
            title=data["title"],
            description=data["description"],
            root_cause=data["root_cause"],
            prevention=data["prevention"],
            tags=data.get("tags", []),
            severity=data.get("severity", "medium"),
            financial_impact=data.get("financial_impact"),
            symbol=data.get("symbol"),
            embedding=data.get("embedding"),
        )


class LessonsLearnedRAG:
    """
    RAG system for storing and retrieving lessons learned.

    Uses semantic search to find relevant past mistakes based on:
    - Trade context (symbol, side, amount)
    - Error type
    - Similar descriptions

    Backend Strategy (Dec 15, 2025):
    1. ChromaDB with persistent vector storage (primary - O(log n) search)
    2. JSON + numpy in-memory vectors (fallback - O(n) search)

    Embedding Strategy (Dec 2025):
    1. OpenAI text-embedding-3-small via OpenRouter (primary)
    2. sentence-transformers all-MiniLM-L6-v2 (fallback)
    3. Keyword search (final fallback)

    Reranking Strategy (Dec 15, 2025):
    1. Cohere Rerank for improved retrieval quality (optional)
    2. Retrieves k*multiplier candidates, reranks to top k
    """

    def __init__(
        self,
        db_path: str = "data/rag/lessons_learned.json",
        model_name: str = "all-MiniLM-L6-v2",
        use_rerank: Optional[bool] = None,
        rerank_multiplier: int = 4,
    ):
        self.db_path = Path(db_path)
        self.model_name = model_name
        self.encoder = None
        self.lessons: list[Lesson] = []
        self.embeddings: Optional[np.ndarray] = None
        self._embedding_method = "keyword"  # Default fallback

        # ChromaDB setup (Dec 15, 2025 - production vector DB)
        self._use_chromadb = CHROMA_AVAILABLE
        self._chroma_client = None
        self._chroma_collection = None

        if self._use_chromadb:
            try:
                # Initialize ChromaDB client
                chroma_dir = Path("data/rag/chroma_db")
                chroma_dir.mkdir(parents=True, exist_ok=True)

                self._chroma_client = chromadb.PersistentClient(
                    path=str(chroma_dir), settings=Settings(anonymized_telemetry=False)
                )

                # Create embedding function
                self._chroma_embedding_fn = (
                    embedding_functions.SentenceTransformerEmbeddingFunction(
                        model_name=self.model_name
                    )
                )

                # Get or create collection
                self._chroma_collection = self._chroma_client.get_or_create_collection(
                    name="lessons_learned",
                    embedding_function=self._chroma_embedding_fn,
                    metadata={"description": "Trading lessons learned and mistakes"},
                )

                logger.info(
                    f"ChromaDB initialized: {self._chroma_collection.count()} lessons in collection"
                )
            except Exception as e:
                logger.error(f"Failed to initialize ChromaDB: {e}")
                self._use_chromadb = False

        # Cohere Rerank integration (added Dec 15, 2025)
        if use_rerank is None:
            use_rerank = os.getenv("ENABLE_COHERE_RERANK", "true").lower() in {
                "1",
                "true",
                "yes",
                "on",
            }
        self.use_rerank = use_rerank
        self.rerank_multiplier = rerank_multiplier
        self._reranker = None

        # Load existing lessons (from ChromaDB if available, else JSON)
        self._load_db()

        # Initialize embedding method (API > Local > Keyword)
        self._init_embeddings()

        # Initialize reranker if enabled
        if self.use_rerank:
            self._init_reranker()

    def _init_embeddings(self) -> None:
        """Initialize embedding method based on available resources."""
        # Priority 1: OpenAI/OpenRouter API (best quality, no local install)
        if OPENAI_EMBEDDINGS_AVAILABLE:
            self._embedding_method = "api"
            logger.info("Using OpenAI API embeddings (text-embedding-3-small)")
            return

        # Priority 2: Local sentence-transformers
        if LOCAL_EMBEDDINGS_AVAILABLE:
            try:
                self.encoder = SentenceTransformer(self.model_name)
                self._embedding_method = "local"
                logger.info(f"Using local embeddings ({self.model_name})")
                self._compute_embeddings()
                return
            except Exception as e:
                logger.warning(f"Could not load local model: {e}")

        # Priority 3: Keyword search fallback
        self._embedding_method = "keyword"
        logger.warning("Using keyword search (no embeddings available)")

    def _init_reranker(self) -> None:
        """Initialize Cohere Reranker if available."""
        try:
            from src.rag.cohere_reranker import COHERE_AVAILABLE, CohereReranker

            if not COHERE_AVAILABLE:
                logger.warning("Cohere SDK not available. Reranking disabled.")
                self.use_rerank = False
                return

            self._reranker = CohereReranker(enable_cost_tracking=True)
            logger.info(f"Cohere Rerank enabled (multiplier={self.rerank_multiplier}x)")
        except Exception as e:
            logger.warning(f"Could not initialize Cohere Reranker: {e}")
            self.use_rerank = False

    def _get_api_embedding(self, text: str) -> Optional[list[float]]:
        """Get embedding via OpenAI/OpenRouter API."""
        api_key = os.getenv("OPENROUTER_API_KEY") or os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None

        try:
            import httpx

            # Use OpenRouter if available, else OpenAI
            if os.getenv("OPENROUTER_API_KEY"):
                url = "https://openrouter.ai/api/v1/embeddings"
                headers = {
                    "Authorization": f"Bearer {api_key}",
                    "HTTP-Referer": "https://github.com/IgorGanapolsky/trading",
                }
                model = "openai/text-embedding-3-small"
            else:
                url = "https://api.openai.com/v1/embeddings"
                headers = {"Authorization": f"Bearer {api_key}"}
                model = "text-embedding-3-small"

            response = httpx.post(
                url,
                headers=headers,
                json={"input": text[:8000], "model": model},  # Truncate to avoid token limit
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()
            return data["data"][0]["embedding"]

        except Exception as e:
            logger.warning(f"API embedding failed: {e}")
            return None

    def _encode(self, text: str) -> Optional[list[float]]:
        """Get embedding using current method."""
        if self._embedding_method == "api":
            return self._get_api_embedding(text)
        elif self._embedding_method == "local" and self.encoder:
            return self.encoder.encode(text).tolist()
        return None

    def add_lesson(
        self,
        category: str,
        title: str,
        description: str,
        root_cause: str,
        prevention: str,
        tags: Optional[list[str]] = None,
        severity: str = "medium",
        financial_impact: Optional[float] = None,
        symbol: Optional[str] = None,
    ) -> str:
        """
        Add a new lesson to the database.

        Args:
            category: Category (size_error, execution, strategy, data, etc.)
            title: Short title for the lesson
            description: Detailed description of what happened
            root_cause: What caused the issue
            prevention: How to prevent it in the future
            tags: Optional tags for filtering
            severity: Severity level
            financial_impact: Dollar impact if known
            symbol: Related symbol if applicable

        Returns:
            ID of the new lesson
        """
        lesson_id = f"lesson_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{len(self.lessons)}"

        lesson = Lesson(
            id=lesson_id,
            timestamp=datetime.now().isoformat(),
            category=category,
            title=title,
            description=description,
            root_cause=root_cause,
            prevention=prevention,
            tags=tags or [],
            severity=severity,
            financial_impact=financial_impact,
            symbol=symbol,
        )

        # Compute embedding using current method (for backward compat)
        if self._embedding_method != "keyword":
            text = f"{title} {description} {root_cause} {prevention}"
            lesson.embedding = self._encode(text)

        self.lessons.append(lesson)

        # Add to ChromaDB if available
        if self._use_chromadb and self._chroma_collection:
            try:
                # Prepare document text
                doc_text = f"{title}\n\n{description}\n\nRoot Cause: {root_cause}\n\nPrevention: {prevention}"

                # Prepare metadata (ChromaDB requires scalar values)
                metadata = {
                    "category": category,
                    "title": title,
                    "severity": severity,
                    "timestamp": lesson.timestamp,
                }

                # Add optional scalar metadata
                if tags:
                    metadata["tags"] = ", ".join(tags)
                if symbol:
                    metadata["symbol"] = symbol
                if financial_impact is not None:
                    metadata["financial_impact"] = float(financial_impact)

                # Upsert to ChromaDB (handles duplicates)
                self._chroma_collection.upsert(
                    ids=[lesson_id], documents=[doc_text], metadatas=[metadata]
                )

                logger.info(f"Added lesson to ChromaDB: {lesson_id} - {title}")
            except Exception as e:
                logger.error(f"Failed to add lesson to ChromaDB: {e}")

        # Also save to JSON for backward compatibility
        self._save_db()

        logger.info(f"Added lesson: {lesson_id} - {title}")
        return lesson_id

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        symbol: Optional[str] = None,
        top_k: int = 5,
    ) -> list[tuple[Lesson, float]]:
        """
        Search for relevant lessons.

        Args:
            query: Search query (natural language)
            category: Optional category filter
            symbol: Optional symbol filter
            top_k: Number of results to return

        Returns:
            List of (Lesson, relevance_score) tuples
        """
        # Use ChromaDB if available
        if self._use_chromadb and self._chroma_collection:
            try:
                # Build metadata filter
                where_filter = {}
                if category:
                    where_filter["category"] = category
                if symbol:
                    where_filter["symbol"] = symbol

                # Retrieve more candidates for reranking if enabled
                retrieve_k = top_k * self.rerank_multiplier if self.use_rerank else top_k

                # Query ChromaDB
                results = self._chroma_collection.query(
                    query_texts=[query],
                    n_results=retrieve_k,
                    where=where_filter if where_filter else None,
                )

                if not results["documents"][0]:
                    return []

                # Convert ChromaDB results to Lesson objects
                lessons_with_scores = []
                for i, doc in enumerate(results["documents"][0]):
                    metadata = results["metadatas"][0][i]
                    distance = results["distances"][0][i] if "distances" in results else 0.0

                    # Convert distance to similarity score (1 - normalized_distance)
                    # ChromaDB returns L2 distance, convert to similarity [0, 1]
                    similarity = max(0.0, 1.0 - (distance / 2.0))

                    # Parse tags back from comma-separated string
                    tags_str = metadata.get("tags", "")
                    tags = [t.strip() for t in tags_str.split(",")] if tags_str else []

                    # Create Lesson object from metadata
                    lesson = Lesson(
                        id=results["ids"][0][i],
                        timestamp=metadata.get("timestamp", ""),
                        category=metadata.get("category", "unknown"),
                        title=metadata.get("title", ""),
                        description=doc,  # Full doc text
                        root_cause="",  # Not stored separately in ChromaDB
                        prevention="",  # Not stored separately in ChromaDB
                        tags=tags,
                        severity=metadata.get("severity", "medium"),
                        financial_impact=metadata.get("financial_impact"),
                        symbol=metadata.get("symbol"),
                    )

                    lessons_with_scores.append((lesson, similarity))

                # Apply Cohere Rerank if enabled
                if self.use_rerank and self._reranker and len(lessons_with_scores) > 0:
                    try:
                        reranked = self._reranker.rerank(
                            query=query,
                            documents=lessons_with_scores,
                            top_k=top_k,
                        )
                        logger.info(
                            f"Reranked {len(lessons_with_scores)} ChromaDB results to top {len(reranked)}"
                        )
                        return reranked
                    except Exception as e:
                        logger.warning(f"Reranking failed, using ChromaDB ranking: {e}")
                        return lessons_with_scores[:top_k]

                return lessons_with_scores[:top_k]

            except Exception as e:
                logger.error(f"ChromaDB search failed: {e}")
                # Fall through to legacy search

        # Legacy fallback (JSON-based search)
        if not self.lessons:
            return []

        # Filter by category/symbol first
        candidates = self.lessons
        if category:
            candidates = [lesson for lesson in candidates if lesson.category == category]
        if symbol:
            candidates = [
                lesson for lesson in candidates if lesson.symbol == symbol or lesson.symbol is None
            ]

        if not candidates:
            return []

        # Semantic search if embeddings available (API or local)
        if self._embedding_method != "keyword":
            # Get query embedding
            query_embedding = self._encode(query)

            if query_embedding:
                scores = []
                for lesson in candidates:
                    if lesson.embedding:
                        similarity = self._cosine_similarity(
                            np.array(query_embedding), lesson.embedding
                        )
                        scores.append((lesson, similarity))
                    else:
                        # No embedding for lesson - compute on the fly if API available
                        if self._embedding_method == "api":
                            text = f"{lesson.title} {lesson.description} {lesson.root_cause}"
                            lesson_embedding = self._encode(text)
                            if lesson_embedding:
                                lesson.embedding = lesson_embedding
                                similarity = self._cosine_similarity(
                                    np.array(query_embedding), lesson_embedding
                                )
                                scores.append((lesson, similarity))
                                continue
                        # Fallback to keyword match for this lesson
                        scores.append((lesson, 0.1))

                # Sort by similarity
                scores.sort(key=lambda x: x[1], reverse=True)

                # Apply reranking if enabled (Dec 15, 2025)
                if self.use_rerank and self._reranker:
                    # Retrieve more candidates for reranking
                    retrieve_k = min(len(scores), top_k * self.rerank_multiplier)
                    initial_results = scores[:retrieve_k]

                    if len(initial_results) > 0:
                        try:
                            reranked = self._reranker.rerank(
                                query=query,
                                documents=initial_results,
                                top_k=top_k,
                            )
                            logger.info(
                                f"Reranked {len(initial_results)} candidates to top {len(reranked)}"
                            )
                            return reranked
                        except Exception as e:
                            logger.warning(f"Reranking failed, using original ranking: {e}")
                            return initial_results[:top_k]

                return scores[:top_k]

        # Fallback to keyword search
        query_words = set(query.lower().split())

        scores = []
        for lesson in candidates:
            text = f"{lesson.title} {lesson.description} {lesson.root_cause}".lower()
            text_words = set(text.split())
            overlap = len(query_words & text_words)
            score = overlap / len(query_words) if query_words else 0
            scores.append((lesson, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def get_prevention_checklist(
        self,
        category: Optional[str] = None,
    ) -> list[str]:
        """
        Get prevention checklist from lessons.

        Args:
            category: Optional category filter

        Returns:
            List of prevention steps
        """
        lessons = self.lessons
        if category:
            lessons = [lesson for lesson in lessons if lesson.category == category]

        # Extract unique prevention steps, prioritize by severity
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_lessons = sorted(lessons, key=lambda lesson: severity_order.get(lesson.severity, 4))

        checklist = []
        seen = set()
        for lesson in sorted_lessons:
            if lesson.prevention not in seen:
                checklist.append(lesson.prevention)
                seen.add(lesson.prevention)

        return checklist

    def get_context_for_trade(
        self,
        symbol: str,
        side: str,
        amount: float,
    ) -> dict[str, Any]:
        """
        Get relevant context for a trade decision.

        Args:
            symbol: Trading symbol
            side: "buy" or "sell"
            amount: Trade amount

        Returns:
            Dict with relevant lessons and warnings
        """
        # Build query from trade context
        query = f"{symbol} {side} trade amount {amount} dollars position size"

        # Search for relevant lessons
        results = self.search(query, top_k=3)

        # Also search for symbol-specific lessons
        symbol_results = self.search(symbol, symbol=symbol, top_k=2)

        # Combine and deduplicate
        all_results = {}
        for lesson, score in results + symbol_results:
            if lesson.id not in all_results:
                all_results[lesson.id] = (lesson, score)

        # Sort by score
        sorted_results = sorted(all_results.values(), key=lambda x: x[1], reverse=True)[:5]

        # Build context
        warnings = []
        prevention_steps = []

        for lesson, score in sorted_results:
            if score > 0.3:  # Relevance threshold
                warnings.append(
                    {
                        "title": lesson.title,
                        "severity": lesson.severity,
                        "prevention": lesson.prevention,
                        "relevance": score,
                    }
                )
                prevention_steps.append(lesson.prevention)

        return {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "relevant_lessons": len(warnings),
            "warnings": warnings,
            "prevention_checklist": list(set(prevention_steps)),
        }

    def _cosine_similarity(self, a: np.ndarray, b: list) -> float:
        """Calculate cosine similarity between two vectors."""
        b_arr = np.array(b)
        return float(np.dot(a, b_arr) / (np.linalg.norm(a) * np.linalg.norm(b_arr)))

    def _compute_embeddings(self) -> None:
        """Compute embeddings for lessons without them."""
        if self._embedding_method == "keyword":
            return

        updated = False
        for lesson in self.lessons:
            if not lesson.embedding:
                text = (
                    f"{lesson.title} {lesson.description} {lesson.root_cause} {lesson.prevention}"
                )
                embedding = self._encode(text)
                if embedding:
                    lesson.embedding = embedding
                    updated = True

        if updated:
            self._save_db()
            logger.info(
                f"Computed embeddings for {sum(1 for lesson in self.lessons if lesson.embedding)} lessons"
            )

    def _load_db(self) -> None:
        """Load lessons from database (ChromaDB or JSON fallback)."""
        # If using ChromaDB and it has data, load from there
        if self._use_chromadb and self._chroma_collection:
            try:
                count = self._chroma_collection.count()
                if count > 0:
                    logger.info(f"Loaded {count} lessons from ChromaDB")
                    # Don't load to self.lessons - ChromaDB is source of truth
                    return
            except Exception as e:
                logger.warning(f"Failed to check ChromaDB: {e}")

        # Fallback to JSON
        if not self.db_path.exists():
            self._initialize_default_lessons()
            return

        try:
            with open(self.db_path) as f:
                data = json.load(f)
            self.lessons = [Lesson.from_dict(lesson_data) for lesson_data in data]
            logger.info(f"Loaded {len(self.lessons)} lessons from {self.db_path}")

            # If ChromaDB available but empty, suggest migration
            if self._use_chromadb and self._chroma_collection:
                chroma_count = self._chroma_collection.count()
                if chroma_count == 0 and len(self.lessons) > 0:
                    logger.warning(
                        f"ChromaDB empty but JSON has {len(self.lessons)} lessons. "
                        f"Consider running migrate_from_json_to_chromadb()"
                    )
        except Exception as e:
            logger.error(f"Error loading lessons DB: {e}")
            self._initialize_default_lessons()

    def _save_db(self) -> None:
        """Save lessons to database file."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        data = []
        for lesson in self.lessons:
            d = lesson.to_dict()
            if lesson.embedding:
                d["embedding"] = lesson.embedding
            data.append(d)

        with open(self.db_path, "w") as f:
            json.dump(data, f, indent=2)

    def _initialize_default_lessons(self) -> None:
        """Initialize with default lessons from known issues."""
        default_lessons = [
            {
                "category": "size_error",
                "title": "200x Position Size Bug (Nov 3, 2025)",
                "description": "Trade executed at $1,600 instead of expected $8 due to unit confusion between shares and dollars",
                "root_cause": "Code calculated position in shares but passed to API expecting dollars",
                "prevention": "Always verify order size matches expected daily budget before submit. Add pre-trade size sanity check.",
                "tags": ["bug", "critical", "position_size", "unit_conversion"],
                "severity": "critical",
                "financial_impact": 1592.0,
            },
            {
                "category": "execution",
                "title": "Market Order Slippage Warning",
                "description": "Large market orders can experience significant slippage during volatile periods",
                "root_cause": "Market orders execute at best available price, which can vary widely",
                "prevention": "Use limit orders for large positions. Add slippage tolerance checks.",
                "tags": ["execution", "slippage", "market_order"],
                "severity": "medium",
            },
            {
                "category": "strategy",
                "title": "Momentum Signal False Positive",
                "description": "MACD crossover signals can be unreliable in low-volume conditions",
                "root_cause": "Technical indicators assume sufficient volume for price discovery",
                "prevention": "Add volume filter: only trade when volume > 80% of 20-day average",
                "tags": ["strategy", "momentum", "volume", "macd"],
                "severity": "low",
            },
            {
                "category": "data",
                "title": "Stale Data Detection",
                "description": "System used 24-hour old market data for trading decision",
                "root_cause": "Data freshness check was not enforced before trading",
                "prevention": "Verify data timestamp < 5 minutes before any trade. Block trading on stale data.",
                "tags": ["data", "freshness", "validation"],
                "severity": "high",
            },
        ]

        for lesson_data in default_lessons:
            self.add_lesson(**lesson_data)

        logger.info(f"Initialized {len(default_lessons)} default lessons")

    def migrate_from_json_to_chromadb(self) -> dict[str, Any]:
        """
        Migrate lessons from JSON file to ChromaDB.

        Returns:
            Dict with migration results:
            - success: bool
            - migrated: int (number of lessons migrated)
            - skipped: int (already existed)
            - failed: int (errors)
            - message: str
        """
        if not self._use_chromadb or not self._chroma_collection:
            return {
                "success": False,
                "migrated": 0,
                "skipped": 0,
                "failed": 0,
                "message": "ChromaDB not available",
            }

        if not self.db_path.exists():
            return {
                "success": False,
                "migrated": 0,
                "skipped": 0,
                "failed": 0,
                "message": f"JSON file not found: {self.db_path}",
            }

        try:
            # Load JSON data
            with open(self.db_path) as f:
                data = json.load(f)

            migrated = 0
            skipped = 0
            failed = 0

            # Get existing IDs in ChromaDB
            existing_results = self._chroma_collection.get()
            existing_ids = set(existing_results["ids"]) if existing_results else set()

            for lesson_data in data:
                try:
                    lesson = Lesson.from_dict(lesson_data)

                    # Skip if already exists
                    if lesson.id in existing_ids:
                        skipped += 1
                        continue

                    # Prepare document text
                    doc_text = f"{lesson.title}\n\n{lesson.description}\n\nRoot Cause: {lesson.root_cause}\n\nPrevention: {lesson.prevention}"

                    # Prepare metadata
                    metadata = {
                        "category": lesson.category,
                        "title": lesson.title,
                        "severity": lesson.severity,
                        "timestamp": lesson.timestamp,
                    }

                    if lesson.tags:
                        metadata["tags"] = ", ".join(lesson.tags)
                    if lesson.symbol:
                        metadata["symbol"] = lesson.symbol
                    if lesson.financial_impact is not None:
                        metadata["financial_impact"] = float(lesson.financial_impact)

                    # Upsert to ChromaDB
                    self._chroma_collection.upsert(
                        ids=[lesson.id], documents=[doc_text], metadatas=[metadata]
                    )

                    migrated += 1

                except Exception as e:
                    logger.error(
                        f"Failed to migrate lesson {lesson_data.get('id', 'unknown')}: {e}"
                    )
                    failed += 1

            message = f"Migration complete: {migrated} migrated, {skipped} skipped, {failed} failed"
            logger.info(message)

            return {
                "success": True,
                "migrated": migrated,
                "skipped": skipped,
                "failed": failed,
                "message": message,
            }

        except Exception as e:
            error_msg = f"Migration failed: {e}"
            logger.error(error_msg)
            return {
                "success": False,
                "migrated": 0,
                "skipped": 0,
                "failed": 0,
                "message": error_msg,
            }

    def get_cost_summary(self) -> dict[str, Any]:
        """
        Get cost tracking summary for reranking operations.

        Returns:
            Dict with cost summary including:
            - rerank_enabled: bool
            - total_calls: int (if enabled)
            - estimated_cost_usd: float (if enabled)
        """
        if not self.use_rerank or not self._reranker:
            return {"rerank_enabled": False, "message": "Reranking is disabled or unavailable"}

        try:
            cost_summary = self._reranker.get_cost_summary()
            cost_summary["rerank_enabled"] = True
            cost_summary["rerank_multiplier"] = self.rerank_multiplier
            return cost_summary
        except Exception as e:
            logger.warning(f"Failed to get cost summary: {e}")
            return {"rerank_enabled": True, "error": str(e)}


def ingest_trade_anomaly(
    rag: LessonsLearnedRAG,
    anomaly_type: str,
    description: str,
    root_cause: str,
    symbol: Optional[str] = None,
    financial_impact: Optional[float] = None,
) -> str:
    """
    Convenience function to ingest a trade anomaly as a lesson.

    Args:
        rag: LessonsLearnedRAG instance
        anomaly_type: Type of anomaly
        description: What happened
        root_cause: Why it happened
        symbol: Related symbol
        financial_impact: Dollar impact

    Returns:
        Lesson ID
    """
    prevention = f"Add validation to prevent: {anomaly_type}"

    return rag.add_lesson(
        category=anomaly_type,
        title=f"Trade Anomaly: {anomaly_type}",
        description=description,
        root_cause=root_cause,
        prevention=prevention,
        severity="high" if financial_impact and financial_impact > 100 else "medium",
        financial_impact=financial_impact,
        symbol=symbol,
    )


if __name__ == "__main__":
    """Demo the lessons learned RAG system."""
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("LESSONS LEARNED RAG DEMO")
    print("=" * 80)

    # Initialize
    rag = LessonsLearnedRAG()

    print(f"\nLoaded {len(rag.lessons)} lessons")

    # Search demo
    print("\n" + "=" * 80)
    print("SEARCH: 'position size too large'")
    print("=" * 80)

    results = rag.search("position size too large", top_k=3)
    for lesson, score in results:
        print(f"\n[{score:.2f}] {lesson.title}")
        print(f"  Category: {lesson.category}")
        print(f"  Prevention: {lesson.prevention}")

    # Context for trade
    print("\n" + "=" * 80)
    print("CONTEXT FOR TRADE: SPY $1500 buy")
    print("=" * 80)

    context = rag.get_context_for_trade("SPY", "buy", 1500.0)
    print(f"\nRelevant lessons: {context['relevant_lessons']}")

    if context["warnings"]:
        print("\nWarnings:")
        for w in context["warnings"]:
            print(f"  [{w['severity'].upper()}] {w['title']}")
            print(f"    Prevention: {w['prevention']}")

    # Prevention checklist
    print("\n" + "=" * 80)
    print("PREVENTION CHECKLIST (size_error)")
    print("=" * 80)

    checklist = rag.get_prevention_checklist("size_error")
    for i, step in enumerate(checklist, 1):
        print(f"  {i}. {step}")

"""
Lightweight RAG Module using FastEmbed + LanceDB

This module provides a drop-in replacement for the heavy ChromaDB + sentence-transformers stack.
Uses FastEmbed (94MB) instead of sentence-transformers (~750MB) for embeddings,
and LanceDB for efficient vector storage.

Architecture:
- FastEmbed: BAAI/bge-small-en-v1.5 model (384 dimensions)
- LanceDB: Arrow-based vector database
- Storage: data/rag/lance_db/
- Graceful fallback: Returns dummy results if dependencies not installed

Example:
    db = LightweightRAG()
    db.add_documents(
        documents=["NVDA beats earnings..."],
        metadatas=[{"ticker": "NVDA", "date": "2025-12-12", "source": "yahoo"}]
    )
    results = db.query("NVIDIA earnings", n_results=5)
"""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Environment variable to disable RAG features
RAG_ENABLED = os.getenv("ENABLE_RAG_FEATURES", "true").lower() in {"1", "true", "yes", "on"}

# Lazy imports for optional dependencies
FASTEMBED_AVAILABLE = False
LANCEDB_AVAILABLE = False

if RAG_ENABLED:
    try:
        from fastembed import TextEmbedding

        FASTEMBED_AVAILABLE = True
        logger.info("FastEmbed available")
    except ImportError:
        logger.warning("fastembed not installed - lightweight RAG disabled")

    try:
        import lancedb

        LANCEDB_AVAILABLE = True
        logger.info("LanceDB available")
    except ImportError:
        logger.warning("lancedb not installed - lightweight RAG disabled")
else:
    logger.info("RAG features disabled via ENABLE_RAG_FEATURES=false")


class LightweightRAG:
    """
    Lightweight RAG system using FastEmbed + LanceDB.

    Provides same interface as TradingRAGDatabase but with significantly reduced
    dependencies (~94MB vs ~750MB).

    Features:
    - Fast embeddings via FastEmbed (BAAI/bge-small-en-v1.5)
    - Efficient vector storage via LanceDB
    - Metadata filtering (ticker, date, source)
    - Similarity search with configurable top-k
    - Graceful fallback if dependencies not installed

    Storage:
    - DB Path: data/rag/lance_db/
    - Table: market_news
    - Embeddings: 384 dimensions
    """

    def __init__(self, persist_directory: str = "data/rag/lance_db"):
        """
        Initialize lightweight RAG system.

        Args:
            persist_directory: Path to LanceDB storage (default: data/rag/lance_db)

        Raises:
            ImportError: If required dependencies not installed (but falls back gracefully)
        """
        self.persist_directory = persist_directory
        self.table_name = "market_news"
        self.embedding_model = None
        self.db = None
        self.table = None
        self._fallback_mode = False

        # Ensure directory exists
        Path(persist_directory).mkdir(parents=True, exist_ok=True)

        # Check if dependencies are available
        if not FASTEMBED_AVAILABLE or not LANCEDB_AVAILABLE:
            logger.warning(
                "FastEmbed or LanceDB not available - running in fallback mode. "
                "Install with: pip install fastembed lancedb"
            )
            self._fallback_mode = True
            self._fallback_store = {"documents": [], "metadatas": [], "ids": []}
            return

        try:
            # Initialize FastEmbed model
            logger.info("Loading FastEmbed model: BAAI/bge-small-en-v1.5")
            self.embedding_model = TextEmbedding(model_name="BAAI/bge-small-en-v1.5")
            logger.info("FastEmbed model loaded successfully")

            # Initialize LanceDB
            self.db = lancedb.connect(persist_directory)

            # Try to open existing table or create new one
            try:
                self.table = self.db.open_table(self.table_name)
                doc_count = len(self.table)
                logger.info(
                    f"LanceDB initialized at {persist_directory} with {doc_count} documents"
                )
            except Exception:
                # Table doesn't exist yet - will be created on first add
                logger.info(f"LanceDB initialized at {persist_directory} (new database)")

        except Exception as e:
            logger.error(f"Failed to initialize lightweight RAG: {e}")
            logger.warning("Falling back to in-memory store")
            self._fallback_mode = True
            self._fallback_store = {"documents": [], "metadatas": [], "ids": []}

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Add documents to the vector database.

        Args:
            documents: List of text content to embed
            metadatas: List of metadata dicts (ticker, date, source, etc.)
            ids: Optional list of unique IDs (auto-generated if None)

        Returns:
            Dict with status and count

        Example:
            db.add_documents(
                documents=["NVDA beats earnings...", "GOOGL announces..."],
                metadatas=[
                    {"ticker": "NVDA", "date": "2025-12-12", "source": "yahoo"},
                    {"ticker": "GOOGL", "date": "2025-12-12", "source": "bloomberg"}
                ]
            )
        """
        if not documents:
            return {"status": "error", "message": "No documents provided"}

        if len(documents) != len(metadatas):
            return {
                "status": "error",
                "message": "Documents and metadatas length mismatch",
            }

        # Auto-generate IDs if not provided
        if ids is None:
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            ids = [f"doc_{timestamp}_{i}" for i in range(len(documents))]

        # Fallback mode - store in memory
        if self._fallback_mode:
            self._fallback_store["documents"].extend(documents)
            self._fallback_store["metadatas"].extend(metadatas)
            self._fallback_store["ids"].extend(ids)
            logger.info(f"Added {len(documents)} documents to fallback store")
            return {"status": "success", "count": len(documents), "ids": ids}

        try:
            # Generate embeddings using FastEmbed
            embeddings = list(self.embedding_model.embed(documents))

            # Prepare data for LanceDB
            data = []
            for i, (doc, meta, doc_id, emb) in enumerate(
                zip(documents, metadatas, ids, embeddings, strict=False)
            ):
                # LanceDB requires flat structure
                row = {
                    "id": doc_id,
                    "document": doc,
                    "vector": emb.tolist() if hasattr(emb, "tolist") else list(emb),
                    "ticker": meta.get("ticker", ""),
                    "date": meta.get("date", ""),
                    "source": meta.get("source", ""),
                    "metadata_json": json.dumps(meta),  # Store full metadata as JSON
                    "timestamp": datetime.now().isoformat(),
                }
                data.append(row)

            # Create table if it doesn't exist, otherwise add to existing
            if self.table is None:
                self.table = self.db.create_table(self.table_name, data=data)
                logger.info(f"Created new table '{self.table_name}' with {len(data)} documents")
            else:
                self.table.add(data)
                logger.info(f"Added {len(documents)} documents to existing table")

            return {"status": "success", "count": len(documents), "ids": ids}

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return {"status": "error", "message": str(e)}

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Query the vector database with semantic search.

        Args:
            query_text: Natural language query
            n_results: Number of results to return (default 5)
            where: Metadata filters (e.g., {"ticker": "NVDA"})

        Returns:
            Dict with documents, metadatas, distances, ids

        Example:
            results = db.query(
                query_text="NVIDIA earnings and revenue growth",
                n_results=10,
                where={"ticker": "NVDA"}
            )
        """
        # Fallback mode - return dummy results
        if self._fallback_mode:
            filtered_docs = []
            filtered_metas = []
            filtered_ids = []

            for doc, meta, doc_id in zip(
                self._fallback_store["documents"],
                self._fallback_store["metadatas"],
                self._fallback_store["ids"],
                strict=False,
            ):
                # Apply filters if provided
                if where:
                    match = all(meta.get(k) == v for k, v in where.items())
                    if not match:
                        continue

                filtered_docs.append(doc)
                filtered_metas.append(meta)
                filtered_ids.append(doc_id)

            # Return first n_results
            results = filtered_docs[:n_results]
            return {
                "status": "success",
                "documents": results,
                "metadatas": filtered_metas[:n_results],
                "distances": [0.0] * len(results),
                "ids": filtered_ids[:n_results],
            }

        if self.table is None:
            return {
                "status": "success",
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": [],
            }

        try:
            # Generate query embedding
            query_embedding = next(self.embedding_model.embed([query_text]))
            query_vector = (
                query_embedding.tolist()
                if hasattr(query_embedding, "tolist")
                else list(query_embedding)
            )

            # Build filter string for LanceDB
            filter_str = None
            if where:
                conditions = []
                for key, value in where.items():
                    if isinstance(value, str):
                        conditions.append(f"{key} = '{value}'")
                    else:
                        conditions.append(f"{key} = {value}")
                filter_str = " AND ".join(conditions)

            # Query LanceDB
            query_builder = self.table.search(query_vector).limit(n_results)
            if filter_str:
                query_builder = query_builder.where(filter_str)

            results = query_builder.to_list()

            # Format results to match ChromaDB interface
            documents = []
            metadatas = []
            distances = []
            ids = []

            for result in results:
                documents.append(result.get("document", ""))
                # Parse metadata from JSON
                metadata_json = result.get("metadata_json", "{}")
                try:
                    metadata = json.loads(metadata_json)
                except json.JSONDecodeError:
                    metadata = {
                        "ticker": result.get("ticker", ""),
                        "date": result.get("date", ""),
                        "source": result.get("source", ""),
                    }
                metadatas.append(metadata)
                distances.append(result.get("_distance", 0.0))
                ids.append(result.get("id", ""))

            return {
                "status": "success",
                "documents": documents,
                "metadatas": metadatas,
                "distances": distances,
                "ids": ids,
            }

        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return {"status": "error", "message": str(e)}

    def get_stats(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with total documents, unique tickers, date range, etc.

        Example:
            stats = db.get_stats()
            # Returns: {
            #     "total_documents": 150,
            #     "unique_tickers": 10,
            #     "tickers": ["NVDA", "GOOGL", ...],
            #     "sources": ["yahoo", "bloomberg"],
            #     "date_range": {"start": "2025-12-01", "end": "2025-12-12"}
            # }
        """
        # Fallback mode
        if self._fallback_mode:
            metadatas = self._fallback_store["metadatas"]
            tickers = set(m.get("ticker") for m in metadatas if m.get("ticker"))
            sources = set(m.get("source") for m in metadatas if m.get("source"))
            dates = [m.get("date") for m in metadatas if m.get("date")]

            date_range = None
            if dates:
                dates.sort()
                date_range = {"start": dates[0], "end": dates[-1]}

            return {
                "total_documents": len(self._fallback_store["documents"]),
                "unique_tickers": len(tickers),
                "tickers": sorted(list(tickers)),
                "sources": sorted(list(sources)),
                "date_range": date_range,
                "mode": "fallback",
            }

        if self.table is None:
            return {
                "total_documents": 0,
                "unique_tickers": 0,
                "tickers": [],
                "sources": [],
                "date_range": None,
                "mode": "lancedb",
            }

        try:
            total_docs = len(self.table)

            if total_docs == 0:
                return {
                    "total_documents": 0,
                    "unique_tickers": 0,
                    "tickers": [],
                    "sources": [],
                    "date_range": None,
                    "mode": "lancedb",
                }

            # Sample documents for stats (limit to 1000 for performance)
            sample_size = min(total_docs, 1000)
            sample = self.table.to_pandas().head(sample_size)

            # Extract unique tickers and sources
            tickers = set(sample["ticker"].dropna().unique())
            sources = set(sample["source"].dropna().unique())
            dates = sorted(sample["date"].dropna().unique())

            date_range = None
            if dates:
                date_range = {"start": dates[0], "end": dates[-1]}

            return {
                "total_documents": total_docs,
                "unique_tickers": len(tickers),
                "tickers": sorted(list(tickers)),
                "sources": sorted(list(sources)),
                "date_range": date_range,
                "sample_size": sample_size,
                "mode": "lancedb",
            }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e), "mode": "lancedb"}

    def get_latest_insights(self, ticker: str | None = None, n: int = 5) -> list[dict[str, Any]]:
        """
        Get latest insights from RAG knowledge used for trading.

        This method returns the most recent documents that were likely used
        for trading decisions, sorted by timestamp.

        Args:
            ticker: Optional ticker filter (e.g., "NVDA")
            n: Number of insights to return (default 5)

        Returns:
            List of insight dicts with content, metadata, and timestamp

        Example:
            # Get latest insights for NVDA
            insights = db.get_latest_insights(ticker="NVDA", n=10)

            # Get latest insights across all tickers
            insights = db.get_latest_insights(n=20)
        """
        # Fallback mode
        if self._fallback_mode:
            filtered = []
            for doc, meta, doc_id in zip(
                self._fallback_store["documents"],
                self._fallback_store["metadatas"],
                self._fallback_store["ids"],
                strict=False,
            ):
                if ticker and meta.get("ticker") != ticker:
                    continue
                filtered.append(
                    {
                        "content": doc,
                        "metadata": meta,
                        "id": doc_id,
                        "timestamp": meta.get("timestamp", ""),
                    }
                )

            # Sort by timestamp descending (newest first)
            filtered.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
            return filtered[:n]

        if self.table is None:
            return []

        try:
            # Build filter for ticker if provided

            # Query with timestamp sorting
            query = self.table.to_pandas()

            # Apply ticker filter if provided
            if ticker:
                query = query[query["ticker"] == ticker]

            # Sort by timestamp descending
            query = query.sort_values(by="timestamp", ascending=False)

            # Take top n
            results = query.head(n)

            # Format results
            insights = []
            for _, row in results.iterrows():
                metadata_json = row.get("metadata_json", "{}")
                try:
                    metadata = json.loads(metadata_json)
                except json.JSONDecodeError:
                    metadata = {
                        "ticker": row.get("ticker", ""),
                        "date": row.get("date", ""),
                        "source": row.get("source", ""),
                    }

                insights.append(
                    {
                        "content": row.get("document", ""),
                        "metadata": metadata,
                        "id": row.get("id", ""),
                        "timestamp": row.get("timestamp", ""),
                    }
                )

            logger.info(
                f"Retrieved {len(insights)} latest insights" + (f" for {ticker}" if ticker else "")
            )
            return insights

        except Exception as e:
            logger.error(f"Error getting latest insights: {e}")
            return []

    def count(self) -> int:
        """
        Get total number of documents in database.

        Returns:
            Document count
        """
        if self._fallback_mode:
            return len(self._fallback_store["documents"])

        if self.table is None:
            return 0

        try:
            return len(self.table)
        except Exception as e:
            logger.error(f"Error counting documents: {e}")
            return 0


# Convenience function for quick access
def get_lightweight_rag(persist_directory: str = "data/rag/lance_db") -> LightweightRAG:
    """
    Get or create a lightweight RAG instance.

    Args:
        persist_directory: Path to LanceDB storage

    Returns:
        LightweightRAG instance

    Example:
        db = get_lightweight_rag()
        db.add_documents([...])
    """
    return LightweightRAG(persist_directory=persist_directory)


# Singleton instance (optional)
_lightweight_rag_instance = None


def get_singleton_rag(persist_directory: str = "data/rag/lance_db") -> LightweightRAG:
    """
    Get or create singleton lightweight RAG instance.

    This ensures only one instance is created and reused across the application.

    Args:
        persist_directory: Path to LanceDB storage

    Returns:
        LightweightRAG instance (singleton)
    """
    global _lightweight_rag_instance

    if _lightweight_rag_instance is None:
        _lightweight_rag_instance = LightweightRAG(persist_directory=persist_directory)

    return _lightweight_rag_instance

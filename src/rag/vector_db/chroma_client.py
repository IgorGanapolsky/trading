from __future__ import annotations
"""
ChromaDB Vector Database Client for Trading RAG System

Provides persistent vector storage for market news, sentiment, and research.
"""

import logging
from datetime import datetime
from typing import Any, Optional

from src.utils.pydantic_compat import ensure_pydantic_base_settings

logger = logging.getLogger(__name__)

ensure_pydantic_base_settings()

try:
    from sentence_transformers import CrossEncoder, SentenceTransformer, util

    SENTENCE_TRANSFORMERS_AVAILABLE = True
except ImportError:
    SENTENCE_TRANSFORMERS_AVAILABLE = False
    logger.warning("sentence-transformers not found. InMemoryCollection will use dummy similarity.")

try:
    from rank_bm25 import BM25Okapi

    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False
    logger.warning("rank_bm25 not found. Hybrid search disabled.")


# Simple in‑memory collection fallback used when ChromaDB cannot be imported.
class InMemoryCollection:
    """A minimal in‑memory stand‑in for ChromaDB collection.

    Stores documents, metadatas and ids in Python lists and provides a very
    lightweight ``add`` and ``query`` interface sufficient for the existing
    ``TradingRAGDatabase`` methods.
    """

    def __init__(self):
        self.documents: list[str] = []
        self.metadatas: list[dict] = []
        self.ids: list[str] = []
        self.embeddings = None
        self.model = None
        self.cross_encoder = None
        self.bm25 = None
        self.persist_path = "data/rag/in_memory_store.json"

        # Ensure directory exists
        import os

        os.makedirs(os.path.dirname(self.persist_path), exist_ok=True)

        if SENTENCE_TRANSFORMERS_AVAILABLE:
            try:
                # Load Bi-Encoder for fast retrieval
                self.model = SentenceTransformer("all-MiniLM-L6-v2")
                # Load Cross-Encoder for high-precision re-ranking
                self.cross_encoder = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")
                self.embeddings = []
            except Exception as e:
                logger.warning(f"Failed to load embedding models: {e}")
                self.model = None
                self.cross_encoder = None

        # Load existing data
        self.load_from_disk()

    def save_to_disk(self):
        """Save collection to disk."""
        import json

        try:
            data = {
                "documents": self.documents,
                "metadatas": self.metadatas,
                "ids": self.ids,
                # We don't save embeddings/models, we re-compute or re-load them
                # Re-computing embeddings on load might be slow for large datasets,
                # but for "in-memory" scale it's acceptable for now.
                # Ideally we'd save embeddings as numpy arrays, but JSON is simple.
            }
            with open(self.persist_path, "w") as f:
                json.dump(data, f)
            logger.info(f"Saved in-memory RAG store to {self.persist_path}")
        except Exception as e:
            logger.error(f"Failed to save in-memory store: {e}")

    def load_from_disk(self):
        """Load collection from disk."""
        import json
        import os

        if not os.path.exists(self.persist_path):
            return

        try:
            with open(self.persist_path) as f:
                data = json.load(f)

            self.documents = data.get("documents", [])
            self.metadatas = data.get("metadatas", [])
            self.ids = data.get("ids", [])

            logger.info(f"Loaded {len(self.documents)} documents from {self.persist_path}")

            # Re-generate embeddings if model is loaded
            if self.model and self.documents:
                logger.info("Regenerating embeddings for loaded documents...")
                new_embeddings = self.model.encode(self.documents)
                self.embeddings = new_embeddings.tolist()

            # Re-build BM25
            if BM25_AVAILABLE and self.documents:
                tokenized_corpus = [doc.lower().split() for doc in self.documents]
                self.bm25 = BM25Okapi(tokenized_corpus)

        except Exception as e:
            logger.error(f"Failed to load in-memory store: {e}")

    def add(self, documents: list[str], metadatas: list[dict], ids: list[str] | None = None):
        if ids is None:
            ids = [f"doc_{len(self.documents) + i}" for i in range(len(documents))]

        self.documents.extend(documents)
        self.metadatas.extend(metadatas)
        self.ids.extend(ids)

        # Generate embeddings if model is available
        if self.model:
            new_embeddings = self.model.encode(documents)
            if self.embeddings is None or len(self.embeddings) == 0:
                self.embeddings = new_embeddings.tolist()
            else:
                self.embeddings.extend(new_embeddings.tolist())

        # Update BM25 index
        if BM25_AVAILABLE:
            tokenized_corpus = [doc.lower().split() for doc in self.documents]
            self.bm25 = BM25Okapi(tokenized_corpus)

        # Auto-save
        self.save_to_disk()

        return {"ids": ids}

    def query(self, query_texts: list[str], n_results: int = 5, where: dict | None = None):
        # Filter first
        indices = []
        for i, (meta, _doc_id) in enumerate(zip(self.metadatas, self.ids)):
            if where:
                match = all(meta.get(k) == v for k, v in where.items())
                if not match:
                    continue
            indices.append(i)

        if not indices:
            return {
                "documents": [],
                "metadatas": [],
                "distances": [],
                "ids": [],
            }

        # If we have embeddings and a model, do semantic search
        if self.model and self.embeddings:
            # 1. Semantic Search
            query_embedding = self.model.encode(query_texts[0])
            filtered_embeddings = [self.embeddings[i] for i in indices]
            semantic_scores = util.cos_sim(query_embedding, filtered_embeddings)[0]

            # 2. BM25 Search (if available)
            bm25_scores = []
            if BM25_AVAILABLE and self.bm25:
                # We need to score ONLY the filtered documents.
                # BM25Okapi doesn't easily support subset scoring without re-indexing or manual calculation.
                # For this simple fallback, we'll score ALL and then filter.
                tokenized_query = query_texts[0].lower().split()
                all_bm25_scores = self.bm25.get_scores(tokenized_query)
                bm25_scores = [all_bm25_scores[i] for i in indices]
            else:
                bm25_scores = [0.0] * len(indices)

            # 3. Hybrid Fusion (Reciprocal Rank Fusion - RRF)
            # or simple weighted sum. Let's do weighted sum for simplicity in this fallback.
            # Normalize BM25 scores to 0-1 range roughly
            if bm25_scores and max(bm25_scores) > 0:
                max_bm25 = max(bm25_scores)
                bm25_scores = [s / max_bm25 for s in bm25_scores]

            # Combine: 0.7 Semantic + 0.3 Keyword
            candidates = []
            for idx, (sem_score, bm_score) in enumerate(zip(semantic_scores, bm25_scores)):
                original_idx = indices[idx]
                hybrid_score = (0.7 * float(sem_score)) + (0.3 * float(bm_score))

                candidates.append(
                    {
                        "document": self.documents[original_idx],
                        "metadata": self.metadatas[original_idx],
                        "id": self.ids[original_idx],
                        "score": hybrid_score,
                        "distance": 1.0 - hybrid_score,
                    }
                )

            # Sort by hybrid score descending
            candidates.sort(key=lambda x: x["score"], reverse=True)

            # --- RE-RANKING STEP ---
            # --- RE-RANKING STEP ---
            # Take top N candidates (e.g., 20) and re-rank with Cross-Encoder
            top_n_candidates = candidates[:20]

            if self.cross_encoder and top_n_candidates:
                # Prepare pairs: (Query, Document)
                pairs = [[query_texts[0], c["document"]] for c in top_n_candidates]
                cross_scores = self.cross_encoder.predict(pairs)

                # Update scores with Cross-Encoder scores (which are logits, unbounded)
                # We can just replace the score or blend it. Replacing is usually better for final ranking.
                for i, score in enumerate(cross_scores):
                    top_n_candidates[i]["score"] = float(score)
                # Distance is tricky with logits, but we can just invert rank or sigmoid it.
                # For compatibility, we'll just use 1/(1+exp(-score)) to map to 0-1 roughly if needed,
                # but for now let's just sort by score.
                top_n_candidates[i]["distance"] = -float(score)  # Higher score = lower distance

                # Re-sort based on Cross-Encoder score
                top_n_candidates.sort(key=lambda x: x["score"], reverse=True)

                # Use re-ranked results
                results = top_n_candidates[:n_results]
            else:
                # Fallback if no cross-encoder
                results = candidates[:n_results]

            return {
                "documents": [[r["document"] for r in results]],
                "metadatas": [[r["metadata"] for r in results]],
                "distances": [[r["distance"] for r in results]],
                "ids": [[r["id"] for r in results]],
            }

        else:
            # Fallback to naive "first N" if no embeddings
            filtered = []
            for i in indices:
                filtered.append(
                    {
                        "document": self.documents[i],
                        "metadata": self.metadatas[i],
                        "id": self.ids[i],
                    }
                )

            results = filtered[:n_results]
            return {
                "documents": [[r["document"] for r in results]],
                "metadatas": [[r["metadata"] for r in results]],
                "distances": [[0.0 for _ in results]],
                "ids": [[r["id"] for r in results]],
            }

    def get(self, ids: list[str] = None, limit: int = None):
        if ids:
            docs = []
            metas = []
            for doc_id in ids:
                if doc_id in self.ids:
                    idx = self.ids.index(doc_id)
                    docs.append(self.documents[idx])
                    metas.append(self.metadatas[idx])
            return {"documents": docs, "metadatas": metas, "ids": ids}

        if limit:
            return {
                "documents": self.documents[:limit],
                "metadatas": self.metadatas[:limit],
                "ids": self.ids[:limit],
            }

        return {"documents": self.documents, "metadatas": self.metadatas, "ids": self.ids}

    def delete(self, ids: list[str]):
        for doc_id in ids:
            if doc_id in self.ids:
                idx = self.ids.index(doc_id)
                del self.documents[idx]
                del self.metadatas[idx]
                del self.ids[idx]
        return True

    def count(self) -> int:
        return len(self.documents)


try:
    import chromadb  # type: ignore
    from chromadb.config import Settings  # type: ignore
except Exception as exc:  # noqa: BLE001
    chromadb = None  # type: ignore
    Settings = None  # type: ignore
    logger.warning("ChromaDB import failed - RAG persistence disabled: %s", exc)


class TradingRAGDatabase:
    """
    Persistent vector database for trading system using ChromaDB.

    Features:
    - Persistent storage (survives restarts)
    - Metadata filtering (ticker, date, source)
    - Similarity search with configurable top-k
    - Document management (add, query, delete)
    """

    def __init__(self, persist_directory: str = "data/rag/chroma_db"):
        """
        Initialize ChromaDB client with persistent storage.

        Args:
            persist_directory: Path to store ChromaDB data
        """
        self.persist_directory = persist_directory

        if chromadb is None:
            # Fallback to an in‑memory store when ChromaDB is unavailable.
            logger.warning("ChromaDB not installed – using in‑memory RAG store fallback.")
            self.client = None
            self.collection = InMemoryCollection()
            return

        # Initialize persistent client
        self.client = chromadb.PersistentClient(path=persist_directory)

        # Get or create collection for market news
        self.collection = self.client.get_or_create_collection(
            name="market_news",
            metadata={"hnsw:space": "cosine"},  # Cosine similarity
        )

        logger.info(f"ChromaDB initialized at {persist_directory}")
        logger.info(f"Collection 'market_news' has {self.collection.count()} documents")

    def add_documents(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        ids: Optional[list[str]] = None,
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
                    {"ticker": "NVDA", "date": "2025-11-10", "source": "yahoo"},
                    {"ticker": "GOOGL", "date": "2025-11-10", "source": "bloomberg"}
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

        try:
            # Add to ChromaDB (will automatically generate embeddings)
            self.collection.add(documents=documents, metadatas=metadatas, ids=ids)

            logger.info(f"Added {len(documents)} documents to RAG database")
            return {"status": "success", "count": len(documents), "ids": ids}

        except Exception as e:
            logger.error(f"Error adding documents: {e}")
            return {"status": "error", "message": str(e)}

    def query(
        self,
        query_text: str,
        n_results: int = 5,
        where: Optional[dict[str, Any]] = None,
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
            # Get recent NVDA news
            results = db.query(
                query_text="NVIDIA earnings and revenue growth",
                n_results=10,
                where={"ticker": "NVDA"}
            )
        """
        try:
            results = self.collection.query(
                query_texts=[query_text], n_results=n_results, where=where
            )

            return {
                "status": "success",
                "documents": results["documents"][0] if results["documents"] else [],
                "metadatas": results["metadatas"][0] if results["metadatas"] else [],
                "distances": results["distances"][0] if results["distances"] else [],
                "ids": results["ids"][0] if results["ids"] else [],
            }

        except Exception as e:
            logger.error(f"Error querying database: {e}")
            return {"status": "error", "message": str(e)}

    def get_ticker_news(
        self, ticker: str, n_results: int = 20, date_filter: Optional[str] = None
    ) -> list[dict[str, Any]]:
        """
        Get all news for a specific ticker.

        Args:
            ticker: Stock ticker (e.g., "NVDA")
            n_results: Max results to return
            date_filter: Optional date filter (YYYY-MM-DD)

        Returns:
            List of news articles with content and metadata
        """
        where = {"ticker": ticker}
        if date_filter:
            where["date"] = date_filter

        # Query with ticker-specific prompt
        results = self.query(
            query_text=f"Latest news and analysis for {ticker}",
            n_results=n_results,
            where=where,
        )

        if results["status"] != "success":
            return []

        # Combine into article objects
        articles = []
        for i in range(len(results["documents"])):
            articles.append(
                {
                    "content": results["documents"][i],
                    "metadata": results["metadatas"][i],
                    "relevance_score": 1
                    - results["distances"][i],  # Convert distance to similarity
                    "id": results["ids"][i],
                }
            )

        return articles

    def get_by_id(self, doc_id: str) -> Optional[dict[str, Any]]:
        """
        Retrieve a document by its ID.

        Args:
            doc_id: Document ID

        Returns:
            Document dict or None if not found
        """
        try:
            result = self.collection.get(ids=[doc_id])

            if not result["documents"]:
                return None

            return {
                "content": result["documents"][0],
                "metadata": result["metadatas"][0],
                "id": result["ids"][0],
            }

        except Exception as e:
            logger.error(f"Error getting document {doc_id}: {e}")
            return None

    def delete_by_id(self, doc_id: str) -> bool:
        """
        Delete a document by ID.

        Args:
            doc_id: Document ID to delete

        Returns:
            True if successful, False otherwise
        """
        try:
            self.collection.delete(ids=[doc_id])
            logger.info(f"Deleted document {doc_id}")
            return True

        except Exception as e:
            logger.error(f"Error deleting document {doc_id}: {e}")
            return False

    def count(self) -> int:
        """Get total number of documents in database."""
        return self.collection.count()

    def reset(self) -> bool:
        """
        Delete all documents from the collection.

        WARNING: This is irreversible!

        Returns:
            True if successful
        """
        try:
            # Delete and recreate collection
            self.client.delete_collection("market_news")
            self.collection = self.client.get_or_create_collection(
                name="market_news", metadata={"hnsw:space": "cosine"}
            )
            logger.warning("RAG database reset - all documents deleted")
            return True

        except Exception as e:
            logger.error(f"Error resetting database: {e}")
            return False

    def get_stats(self) -> dict[str, Any]:
        """
        Get database statistics.

        Returns:
            Dict with total documents, unique tickers, date range, etc.
        """
        try:
            total_docs = self.collection.count()

            # Get all metadata to compute stats
            if total_docs == 0:
                return {
                    "total_documents": 0,
                    "unique_tickers": 0,
                    "sources": [],
                    "date_range": None,
                }

            # Sample up to 1000 documents for stats
            sample_size = min(total_docs, 1000)
            results = self.collection.get(limit=sample_size)

            metadatas = results["metadatas"]

            # Extract unique tickers and sources
            tickers = set(m.get("ticker") for m in metadatas if m.get("ticker"))
            sources = set(m.get("source") for m in metadatas if m.get("source"))
            dates = [m.get("date") for m in metadatas if m.get("date")]

            date_range = None
            if dates:
                dates.sort()
                date_range = {"start": dates[0], "end": dates[-1]}

            return {
                "total_documents": total_docs,
                "unique_tickers": len(tickers),
                "tickers": sorted(list(tickers)),
                "sources": sorted(list(sources)),
                "date_range": date_range,
                "sample_size": sample_size,
            }

        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}


# Convenience function for quick access
def get_rag_db(persist_directory: str = "data/rag/chroma_db") -> TradingRAGDatabase:
    """
    Get or create a RAG database instance.

    Args:
        persist_directory: Path to ChromaDB storage

    Returns:
        TradingRAGDatabase instance
    """
    return TradingRAGDatabase(persist_directory=persist_directory)

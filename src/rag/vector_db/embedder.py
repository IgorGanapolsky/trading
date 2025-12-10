"""
Embedding Pipeline for Trading RAG System

Uses sentence-transformers for local, FREE text embeddings.
"""

import logging
import os
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# Environment variable to disable RAG features (useful for CI or minimal environments)
RAG_ENABLED = os.getenv("ENABLE_RAG_FEATURES", "true").lower() in {"1", "true", "yes", "on"}

# Lazy import to avoid breaking crypto trading when RAG dependencies aren't installed
_SentenceTransformer: type | None = None


def _get_sentence_transformer():
    """Lazy import of SentenceTransformer."""
    global _SentenceTransformer
    if _SentenceTransformer is None:
        try:
            from sentence_transformers import SentenceTransformer

            _SentenceTransformer = SentenceTransformer
        except ImportError:
            logger.warning("sentence-transformers not installed - RAG features disabled")
            raise ImportError(
                "sentence-transformers is required for RAG features. "
                "Install with: pip install -r requirements-rag.txt"
            )
    return _SentenceTransformer


class NewsEmbedder:
    """
    Generate embeddings for market news using sentence-transformers.

    Model: all-MiniLM-L6-v2
    - 384 dimensions
    - Optimized for semantic search
    - Runs locally (no API costs)
    - Fast inference (~20ms per document)
    """

    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        """
        Initialize sentence-transformers model.

        Args:
            model_name: HuggingFace model ID (default: all-MiniLM-L6-v2)
        """
        self.model_name = model_name
        logger.info(f"Loading embedding model: {model_name}")

        try:
            SentenceTransformer = _get_sentence_transformer()
            self.model = SentenceTransformer(model_name)
            logger.info(
                f"Embedding model loaded successfully (dimensions: {self.model.get_sentence_embedding_dimension()})"
            )

        except ImportError as e:
            logger.error(f"Failed to import sentence-transformers: {e}")
            raise
        except Exception as e:
            logger.error(f"Failed to load embedding model: {e}")
            raise

    def embed_text(self, text: str) -> np.ndarray:
        """
        Generate embedding for a single text.

        Args:
            text: Text content to embed

        Returns:
            384-dimensional embedding vector
        """
        try:
            embedding = self.model.encode(text, convert_to_numpy=True)
            return embedding

        except Exception as e:
            logger.error(f"Error embedding text: {e}")
            raise

    # Alias for compatibility
    embed_single = embed_text

    def embed_batch(self, texts: list[str], batch_size: int = 32) -> list[np.ndarray]:
        """
        Generate embeddings for multiple texts (batch processing).

        Args:
            texts: List of text content
            batch_size: Batch size for processing (default 32)

        Returns:
            List of embedding vectors

        Example:
            embedder = NewsEmbedder()
            texts = ["NVDA beats earnings...", "GOOGL announces..."]
            embeddings = embedder.embed_batch(texts)
        """
        try:
            embeddings = self.model.encode(
                texts,
                batch_size=batch_size,
                show_progress_bar=len(texts) > 100,
                convert_to_numpy=True,
            )
            return [emb for emb in embeddings]

        except Exception as e:
            logger.error(f"Error embedding batch: {e}")
            raise

    def embed_articles(self, articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """
        Embed news articles with metadata.

        Args:
            articles: List of article dicts with 'content' and 'metadata'

        Returns:
            Articles with added 'embedding' field

        Example:
            articles = [
                {
                    "content": "NVDA reports record revenue...",
                    "metadata": {"ticker": "NVDA", "date": "2025-11-10", "source": "yahoo"}
                }
            ]
            embedded = embedder.embed_articles(articles)
        """
        if not articles:
            return []

        # Extract text content
        texts = [article.get("content", "") for article in articles]

        # Generate embeddings in batch
        embeddings = self.embed_batch(texts)

        # Add embeddings to articles
        for i, article in enumerate(articles):
            article["embedding"] = embeddings[i]

        logger.info(f"Embedded {len(articles)} articles")
        return articles

    def get_dimensions(self) -> int:
        """Get embedding dimensions (384 for all-MiniLM-L6-v2)."""
        return self.model.get_sentence_embedding_dimension()


# Singleton instance for reuse
_embedder_instance = None


def get_embedder(model_name: str = "all-MiniLM-L6-v2") -> NewsEmbedder | None:
    """
    Get or create a NewsEmbedder instance (singleton pattern).

    Args:
        model_name: HuggingFace model ID

    Returns:
        NewsEmbedder instance, or None if RAG is disabled or unavailable
    """
    global _embedder_instance

    # Check if RAG is disabled via environment variable
    if not RAG_ENABLED:
        logger.info("RAG features disabled via ENABLE_RAG_FEATURES=false")
        return None

    if _embedder_instance is None:
        try:
            _embedder_instance = NewsEmbedder(model_name=model_name)
        except Exception as e:
            logger.warning(f"Failed to create embedder (RAG will be disabled): {e}")
            return None

    return _embedder_instance

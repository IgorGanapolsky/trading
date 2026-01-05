"""
Cohere Rerank Integration for RAG System

Enhances RAG retrieval quality using Cohere's Rerank 4 API to intelligently
reorder retrieved documents by relevance to the query.

Key Features:
1. Rerank RAG retrieval results for better precision
2. Cost tracking for API usage monitoring
3. Fallback to original ranking if API fails
4. Configurable reranking parameters (top_n, model)

Architecture:
- Initial retrieval: Get top_k * rerank_multiplier candidates
- Reranking: Use Cohere Rerank 4 to score and reorder
- Return: Top_k best results after reranking

Cost Estimates (as of Dec 2025):
- Rerank 4: ~$1/1000 requests
- Expected usage: 1-2 reranks/day = $0.03-0.06/mo

Integration:
- Works with LessonsLearnedRAG.search()
- Can be applied to any retrieval system

Author: Trading System
Created: 2025-12-13
Phase: R&D Day 9/90 - Phase 1 Pilot
"""

import logging
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Check Cohere availability
COHERE_AVAILABLE = False
try:
    import cohere

    COHERE_AVAILABLE = True
    logger.info("Cohere SDK available")
except ImportError:
    logger.warning("Cohere SDK not installed. Run: pip install cohere>=5.11.4")


@dataclass
class RerankResult:
    """Result from Cohere Rerank API."""

    index: int  # Original index in candidate list
    relevance_score: float  # Cohere relevance score (0-1)
    document: Any  # Original document/lesson


@dataclass
class RerankCostTracker:
    """Track costs for Cohere Rerank API usage."""

    total_requests: int = 0
    total_documents: int = 0
    total_cost: float = 0.0
    last_request_time: Optional[float] = None

    # Pricing (update based on Cohere's current pricing)
    COST_PER_1000_SEARCHES = 1.0  # $1 per 1000 searches

    def record_request(self, num_documents: int):
        """Record a rerank request."""
        self.total_requests += 1
        self.total_documents += num_documents
        self.last_request_time = time.time()
        # Cost per search
        self.total_cost += self.COST_PER_1000_SEARCHES / 1000

    def get_summary(self) -> dict[str, Any]:
        """Get cost tracking summary."""
        return {
            "total_requests": self.total_requests,
            "total_documents": self.total_documents,
            "total_cost_usd": round(self.total_cost, 4),
            "avg_documents_per_request": (
                round(self.total_documents / self.total_requests, 1)
                if self.total_requests > 0
                else 0
            ),
            "last_request_time": self.last_request_time,
        }


class CohereReranker:
    """
    Cohere Rerank integration for RAG systems.

    Enhances retrieval quality by reranking candidates using Cohere's
    state-of-the-art reranking model (Rerank 4).

    Example:
        >>> reranker = CohereReranker()
        >>> # Get initial candidates from RAG
        >>> candidates = rag.search(query, top_k=20)
        >>> # Rerank to get best 5
        >>> best_results = reranker.rerank(
        ...     query=query,
        ...     documents=candidates,
        ...     top_k=5
        ... )
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "rerank-v3.5",  # Latest stable model
        max_retries: int = 2,
        timeout: int = 10,
        enable_cost_tracking: bool = True,
    ):
        """
        Initialize Cohere Reranker.

        Args:
            api_key: Cohere API key (defaults to COHERE_API_KEY env var)
            model: Rerank model to use (rerank-v3.5 recommended)
            max_retries: Max retry attempts on failure
            timeout: Request timeout in seconds
            enable_cost_tracking: Whether to track API costs
        """
        if not COHERE_AVAILABLE:
            raise ImportError("Cohere SDK not installed. Install with: pip install cohere>=5.11.4")

        self.api_key = api_key or os.getenv("COHERE_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Cohere API key required. Set COHERE_API_KEY env var or pass api_key parameter."
            )

        self.model = model
        self.max_retries = max_retries
        self.timeout = timeout
        self.enable_cost_tracking = enable_cost_tracking

        # Initialize Cohere client
        self.client = cohere.Client(api_key=self.api_key, timeout=timeout)

        # Cost tracking
        self.cost_tracker = RerankCostTracker() if enable_cost_tracking else None

        logger.info(f"Initialized CohereReranker with model={model}")

    def rerank(
        self,
        query: str,
        documents: list[tuple[Any, float]],
        top_k: int = 5,
        return_documents: bool = True,
    ) -> list[tuple[Any, float]]:
        """
        Rerank documents using Cohere Rerank API.

        Args:
            query: Search query (natural language)
            documents: List of (document, score) tuples from initial retrieval
            top_k: Number of top results to return after reranking
            return_documents: Whether to return full documents or just indices

        Returns:
            List of (document, relevance_score) tuples, reranked by Cohere

        Example:
            >>> # Initial retrieval from RAG
            >>> candidates = rag.search("position size error", top_k=20)
            >>> # Rerank to get best 5
            >>> best = reranker.rerank(query="position size error", documents=candidates, top_k=5)
        """
        if not documents:
            logger.warning("No documents to rerank")
            return []

        # Extract document objects and prepare texts for Cohere
        doc_objects = [doc for doc, _ in documents]
        doc_texts = self._prepare_documents(doc_objects)

        # Call Cohere Rerank API with retry logic
        for attempt in range(self.max_retries + 1):
            try:
                start_time = time.time()

                response = self.client.rerank(
                    query=query,
                    documents=doc_texts,
                    top_n=top_k,
                    model=self.model,
                    return_documents=return_documents,
                )

                latency = time.time() - start_time

                # Track costs
                if self.cost_tracker:
                    self.cost_tracker.record_request(len(documents))

                # Process results
                results = []
                for result in response.results:
                    original_doc = doc_objects[result.index]
                    relevance_score = result.relevance_score
                    results.append((original_doc, relevance_score))

                logger.info(
                    f"Reranked {len(documents)} documents to top {len(results)} "
                    f"in {latency:.2f}s (model={self.model})"
                )

                return results

            except Exception as e:
                error_type = type(e).__name__
                logger.warning(
                    f"Rerank attempt {attempt + 1}/{self.max_retries + 1} failed: "
                    f"{error_type}: {str(e)}"
                )

                if attempt == self.max_retries:
                    logger.error(
                        f"Rerank failed after {self.max_retries + 1} attempts. "
                        "Falling back to original ranking."
                    )
                    # Return original ranking as fallback
                    return documents[:top_k]

                # Exponential backoff
                time.sleep(2**attempt)

        # Fallback (should not reach here)
        return documents[:top_k]

    def _prepare_documents(self, documents: list[Any]) -> list[str]:
        """
        Prepare documents for Cohere Rerank API.

        Converts document objects (Lessons, etc.) to text strings
        that Cohere can process.

        Args:
            documents: List of document objects

        Returns:
            List of text strings ready for reranking
        """
        texts = []
        for doc in documents:
            # Handle different document types
            if hasattr(doc, "to_dict"):
                # Lesson object or similar
                data = doc.to_dict()
                # Combine key fields for reranking
                text = f"{data.get('title', '')} {data.get('description', '')} {data.get('root_cause', '')} {data.get('prevention', '')}"
                texts.append(text.strip())
            elif isinstance(doc, dict):
                # Dict object
                text = (
                    f"{doc.get('title', '')} {doc.get('description', '')} {doc.get('content', '')}"
                )
                texts.append(text.strip())
            elif isinstance(doc, str):
                # Raw text
                texts.append(doc)
            else:
                # Fallback: convert to string
                texts.append(str(doc))

        return texts

    def get_cost_summary(self) -> dict[str, Any]:
        """
        Get cost tracking summary.

        Returns:
            Dict with cost metrics (total requests, cost, etc.)
        """
        if not self.cost_tracker:
            return {"error": "Cost tracking disabled"}

        return self.cost_tracker.get_summary()

    def reset_cost_tracker(self):
        """Reset cost tracking metrics."""
        if self.cost_tracker:
            self.cost_tracker = RerankCostTracker()
            logger.info("Cost tracker reset")


# Convenience function for quick reranking
def rerank_rag_results(
    query: str,
    results: list[tuple[Any, float]],
    top_k: int = 5,
    api_key: Optional[str] = None,
) -> list[tuple[Any, float]]:
    """
    Convenience function to rerank RAG results.

    Args:
        query: Search query
        results: List of (document, score) tuples from RAG
        top_k: Number of top results to return
        api_key: Optional Cohere API key

    Returns:
        Reranked list of (document, score) tuples

    Example:
        >>> rag_results = rag.search("position size error", top_k=20)
        >>> best = rerank_rag_results("position size error", rag_results, top_k=5)
    """
    try:
        reranker = CohereReranker(api_key=api_key)
        return reranker.rerank(query, results, top_k)
    except Exception as e:
        logger.error(f"Reranking failed: {e}. Returning original results.")
        return results[:top_k]


# Example usage
if __name__ == "__main__":
    import sys

    # Mock lesson objects for testing
    @dataclass
    class MockLesson:
        title: str
        description: str
        root_cause: str
        prevention: str

        def to_dict(self):
            return {
                "title": self.title,
                "description": self.description,
                "root_cause": self.root_cause,
                "prevention": self.prevention,
            }

    # Sample lessons
    lessons = [
        (
            MockLesson(
                "Position size too large",
                "Attempted to buy $5000 of SPY but account only had $3000",
                "Insufficient buying power check",
                "Always verify available cash before placing orders",
            ),
            0.85,
        ),
        (
            MockLesson(
                "Wrong symbol format",
                "Used 'SPY' instead of options contract format",
                "Symbol validation missing",
                "Validate symbol format before execution",
            ),
            0.80,
        ),
        (
            MockLesson(
                "Market closed execution",
                "Attempted to place order on Saturday",
                "Missing market hours check",
                "Check if market is open before orders",
            ),
            0.75,
        ),
    ]

    # Test reranking
    try:
        reranker = CohereReranker()
        query = "position sizing error with insufficient funds"

        print(f"Query: {query}")
        print("\nOriginal ranking (top 3):")
        for i, (lesson, score) in enumerate(lessons, 1):
            print(f"  {i}. {lesson.title} (score: {score:.2f})")

        print("\nReranking with Cohere...")
        reranked = reranker.rerank(query, lessons, top_k=3)

        print("\nReranked results:")
        for i, (lesson, score) in enumerate(reranked, 1):
            print(f"  {i}. {lesson.title} (relevance: {score:.3f})")

        print("\nCost summary:")
        cost = reranker.get_cost_summary()
        print(f"  Total requests: {cost['total_requests']}")
        print(f"  Total cost: ${cost['total_cost_usd']:.4f}")

    except Exception as e:
        print(f"Error: {e}")
        print("Make sure COHERE_API_KEY is set in your environment")
        sys.exit(1)

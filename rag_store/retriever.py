"""
HyDE (Hypothetical Document Embeddings) Retriever for Financial RAG

This module implements the HyDE retrieval strategy:
1. Agent hallucinates a "perfect" hypothetical financial document based on the query.
2. The hypothetical document is embedded.
3. We search the vector store for real documents closest to that embedding.
"""

import logging
from typing import Any

from src.agents.gemini_agent import GeminiAgent
from src.rag.vector_db.chroma_client import get_rag_db

logger = logging.getLogger(__name__)


class HyDERetriever:
    """
    Retrieves documents using Hypothetical Document Embeddings (HyDE).
    """

    def __init__(self, model_name: str = "gemini-3-pro-preview"):
        """
        Initialize HyDE retriever.

        Args:
            model_name: Gemini model to use for generation
        """
        self.agent = GeminiAgent(
            name="HyDE_Generator",
            role="Financial Research Expert",
            model=model_name,
            default_thinking_level="low",  # Fast, focused generation
        )
        self.db = get_rag_db()
        logger.info(f"Initialized HyDE Retriever with model {model_name}")

    def generate_hypothetical_document(self, query: str) -> str:
        """
        Generate a hypothetical document that would answer the query.
        """
        prompt = (
            f"You are an expert financial analyst. Write a snippet from a professional financial report, "
            f"API documentation, or research paper that definitively answers the following question. "
            f"Do not include conversational filler. Just write the hypothetical content.\n\n"
            f"Question: {query}\n\n"
            f"Hypothetical Document Snippet:"
        )

        result = self.agent.reason(prompt)
        hypothetical_text = result.get("reasoning", "").strip()

        if not hypothetical_text:
            logger.warning("HyDE generation failed, falling back to original query")
            return query

        logger.info(f"Generated HyDE document ({len(hypothetical_text)} chars)")
        return hypothetical_text

    def retrieve(
        self, query: str, n_results: int = 5, use_hyde: bool = True, where: dict[str, Any] = None
    ) -> dict[str, Any]:
        """
        Retrieve documents relevant to the query.

        Args:
            query: User's question
            n_results: Number of docs to retrieve
            use_hyde: Whether to use HyDE or standard retrieval
            where: Metadata filters

        Returns:
            Dict containing documents, metadatas, distances, ids
        """
        search_query = query

        if use_hyde:
            try:
                hypothetical_doc = self.generate_hypothetical_document(query)
                # We use the hypothetical doc as the search query.
                # The vector DB will embed this text, effectively creating the "Hypothetical Document Embedding".
                search_query = hypothetical_doc
            except Exception as e:
                logger.error(f"HyDE generation error: {e}")
                # Fallback to standard query
                search_query = query

        return self.db.query(query_text=search_query, n_results=n_results, where=where)


# Singleton instance
_retriever = None


def get_retriever() -> HyDERetriever:
    """Get or create global retriever instance."""
    global _retriever
    if _retriever is None:
        _retriever = HyDERetriever()
    return _retriever

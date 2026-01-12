"""
RAG (Retrieval-Augmented Generation) module for the trading system.

This module provides:
- Vertex AI RAG integration for lessons learned
- Local JSON backup for trade recording
- Semantic search across trading knowledge

Note: ChromaDB was deprecated Jan 7, 2026 in favor of Vertex AI RAG.
"""

from src.rag.lessons_learned_rag import LessonsLearnedRAG

__all__ = ["LessonsLearnedRAG"]

"""
RAG (Retrieval-Augmented Generation) module for the trading system.

This module provides:
- LanceDB RAG integration for lessons learned
- Local JSON backup for trade recording
- Semantic search across trading knowledge
- RAG evaluation metrics (Precision@k, Recall@k, MRR)

Note: ChromaDB was deprecated Jan 7, 2026 in favor of LanceDB.
"""

from src.rag.evaluation import (
    EvaluationQuery,
    EvaluationReport,
    RAGEvaluator,
    get_evaluator,
)
from src.rag.lessons_learned_rag import LessonsLearnedRAG

__all__ = [
    "LessonsLearnedRAG",
    "RAGEvaluator",
    "EvaluationQuery",
    "EvaluationReport",
    "get_evaluator",
]

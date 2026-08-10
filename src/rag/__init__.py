"""
RAG (Retrieval-Augmented Generation) module for the trading system.

This module provides:
- LanceDB RAG integration for lessons learned
- Local JSON backup for trade recording
- Semantic search across trading knowledge
- RAG evaluation metrics (Precision@k, Recall@k, MRR)
- Financial Graph RAG (temporal property graph + TokenGuard)

Note: ChromaDB was deprecated Jan 7, 2026 in favor of LanceDB.
Graph RAG lives under ``src.rag.graph`` — import from there to avoid
shadowing submodule paths (same rule as retrieve_for_trade).
"""

from src.rag.answer_metrics import (
    AnswerScore,
    RAGAnswerMetrics,
    measure_answer_metrics,
)
from src.rag.evaluation import (
    EvaluationQuery,
    EvaluationReport,
    RAGEvaluator,
    get_evaluator,
)
from src.rag.lessons_learned_rag import LessonsLearnedRAG
from src.rag.unified_search import UnifiedSearch, get_unified_search

# NOTE: Do not re-export retrieve_for_trade or graph pipeline symbols here —
# that shadows submodule package names. Import from ``src.rag.graph`` directly.

__all__ = [
    "LessonsLearnedRAG",
    "UnifiedSearch",
    "get_unified_search",
    "RAGEvaluator",
    "EvaluationQuery",
    "EvaluationReport",
    "get_evaluator",
    "AnswerScore",
    "RAGAnswerMetrics",
    "measure_answer_metrics",
]

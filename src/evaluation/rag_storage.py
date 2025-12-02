"""
RAG Storage for Evaluation Results

Stores evaluation results in ChromaDB for semantic search and pattern detection.
FREE - Uses existing ChromaDB infrastructure.
"""

import logging
import os
import sys
from datetime import datetime
from typing import Any

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from src.rag.vector_db.chroma_client import TradingRAGDatabase
    from src.rag.vector_db.embedder import NewsEmbedder

    RAG_AVAILABLE = True
except Exception as e:
    RAG_AVAILABLE = False
    logger = logging.getLogger(__name__)
    logger.warning(f"RAG not available: {e}")

logger = logging.getLogger(__name__)


class EvaluationRAGStorage:
    """
    Store evaluation results in RAG system for semantic search.

    FREE - Uses existing ChromaDB, no additional costs.
    """

    def __init__(self):
        """Initialize RAG storage."""
        if not RAG_AVAILABLE:
            logger.warning("RAG not available - evaluation storage disabled")
            self.enabled = False
            return

        try:
            self.db = TradingRAGDatabase()
            self.embedder = NewsEmbedder()
            self.enabled = True
            logger.info("EvaluationRAGStorage initialized")
        except Exception as e:
            logger.error(f"Failed to initialize RAG storage: {e}")
            self.enabled = False

    def store_evaluation(self, evaluation: dict[str, Any], trade_result: dict[str, Any]) -> bool:
        """
        Store evaluation result in RAG system.

        Args:
            evaluation: TradeEvaluation as dict
            trade_result: Original trade result

        Returns:
            True if stored successfully
        """
        if not self.enabled:
            return False

        try:
            # Create document text from evaluation
            doc_text = self._create_document_text(evaluation, trade_result)

            # Create metadata
            metadata = {
                "type": "evaluation",
                "trade_id": evaluation.get("trade_id", "unknown"),
                "symbol": evaluation.get("symbol", "unknown"),
                "timestamp": evaluation.get("timestamp", datetime.now().isoformat()),
                "overall_score": evaluation.get("overall_score", 0.0),
                "passed": evaluation.get("passed", False),
                "dimensions": list(evaluation.get("evaluation", {}).keys()),
            }

            # Create unique ID
            doc_id = f"eval_{evaluation.get('trade_id', 'unknown')}_{datetime.now().strftime('%Y%m%d%H%M%S')}"

            # Store in ChromaDB
            result = self.db.add_documents(documents=[doc_text], metadatas=[metadata], ids=[doc_id])

            logger.info(f"Stored evaluation {doc_id} in RAG system")
            return result.get("status") == "success"

        except Exception as e:
            logger.error(f"Error storing evaluation in RAG: {e}")
            return False

    def _create_document_text(
        self, evaluation: dict[str, Any], trade_result: dict[str, Any]
    ) -> str:
        """Create searchable text from evaluation."""
        lines = []

        # Trade info
        lines.append(f"Trade: {evaluation.get('symbol', 'UNKNOWN')}")
        lines.append(f"Trade ID: {evaluation.get('trade_id', 'unknown')}")
        lines.append(f"Timestamp: {evaluation.get('timestamp', 'unknown')}")
        lines.append(f"Overall Score: {evaluation.get('overall_score', 0.0):.2f}")
        lines.append(f"Passed: {evaluation.get('passed', False)}")

        # Evaluation dimensions
        eval_data = evaluation.get("evaluation", {})
        for dimension, result in eval_data.items():
            lines.append(f"\n{dimension.upper()}:")
            lines.append(f"  Score: {result.get('score', 0.0):.2f}")
            lines.append(f"  Passed: {result.get('passed', False)}")
            issues = result.get("issues", [])
            if issues:
                lines.append(f"  Issues: {', '.join(issues)}")

        # Critical issues
        critical_issues = evaluation.get("critical_issues", [])
        if critical_issues:
            lines.append("CRITICAL ISSUES:")
            for issue in critical_issues:
                lines.append(f"  - {issue}")

        # Trade result context
        lines.append("Trade Result:")
        lines.append(f"  Amount: ${trade_result.get('amount', 0.0):.2f}")
        lines.append(f"  Status: {trade_result.get('status', 'unknown')}")

        return "\n".join(lines)

    def query_similar_evaluations(self, query: str, n_results: int = 5) -> list[dict[str, Any]]:
        """
        Query similar evaluations using semantic search.

        Args:
            query: Natural language query (e.g., "order size errors")
            n_results: Number of results to return

        Returns:
            List of similar evaluations
        """
        if not self.enabled:
            return []

        try:
            results = self.db.query_documents(
                query_text=query,
                n_results=n_results,
                filter_metadata={"type": "evaluation"},
            )
            return results
        except Exception as e:
            logger.error(f"Error querying evaluations: {e}")
            return []

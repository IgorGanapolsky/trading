"""
RAG-Backed Safety Guard - Step 6 of Strategy Upgrade.
Uses historical lessons to provide a 'soft' veto or warning on current trade parameters.
"""

import logging
from typing import Any

from src.rag.rag_pipeline import get_trading_rag_pipeline

logger = logging.getLogger(__name__)


class RAGSafetyGuard:
    """Consults the RAG database for similar past incidents before entry.

    Uses TradingRAGPipeline with SQLite FTS5 + bigram-Jaccard hybrid + cross-encoder
    reranking for robust lesson retrieval.
    """

    def __init__(self):
        self.pipeline = get_trading_rag_pipeline()

    def check_safety(self, symbol: str, vix: float, iv: float) -> dict[str, Any]:
        """
        Query RAG for similar volatility regimes and return risk assessment.
        """
        query = f"SPY iron condor risk at VIX {vix:.1f} and IV {iv:.1%}."
        try:
            results = self.pipeline.query(query=query, top_k=3, rerank=True)

            if not results:
                return {"veto": False, "reason": "No similar historical data found."}

            # Simple logic: if any retrieved lesson has 'CRITICAL' or 'FAILURE' in content
            # and matches the regime, we flag a warning.
            warnings = []
            for doc in results:
                content = (doc.get("content_snippet", "") or doc.get("content", "") or "").upper()
                # Check severity from the lesson record
                severity = str(doc.get("severity", "")).upper()
                if "FAILURE" in content or "LOSS" in content or "CRITICAL" in content or severity in ("CRITICAL", "HIGH"):
                    warnings.append(doc.get("id", "Unknown Lesson"))

            if warnings:
                return {
                    "veto": False,  # Soft veto (warning)
                    "warning": True,
                    "reason": f"Historical parallels found in lessons: {', '.join(warnings)}",
                    "lessons": warnings,
                }

            return {"veto": False, "warning": False, "reason": "No immediate historical red flags."}

        except Exception as e:
            logger.error(f"RAG safety check failed: {e}")
            return {"veto": False, "reason": f"Safety check error: {e}"}

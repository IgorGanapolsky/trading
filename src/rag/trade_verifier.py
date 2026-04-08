"""
Trade Verifier: The RAG-based Mistake Preventer.
[WORLD-CLASS RAG PHASE 1]
Performs semantic lookup of past trading disasters before every entry.
If a high-similarity failure is found, the trade is blocked.
"""

import logging

logger = logging.getLogger(__name__)


class TradeVerifier:
    def __init__(self, threshold: float = 0.75):
        """
        Initialize the verifier with a similarity threshold.
        If a past failure similarity score > threshold, trade is blocked.
        """
        self.threshold = threshold
        self.rag_available = False
        self.rag_engine = None

        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG

            self.rag_engine = LessonsLearnedRAG()
            self.rag_available = True
            logger.info("TradeVerifier: RAG Engine initialized successfully.")
        except Exception as e:
            logger.warning(
                f"TradeVerifier: RAG Engine failed to initialize: {e}. Defaulting to Pass-Through."
            )

    def verify_entry(self, symbol: str, strategy: str, setup_context: str) -> tuple[bool, str]:
        """
        Verify a trade entry against past lessons learned.

        Returns:
            (is_approved, reason)
        """
        if not self.rag_available or not self.rag_engine:
            return True, "RAG unavailable; verifier in pass-through mode."

        query = f"Trading disaster or mistake involving {symbol} {strategy} {setup_context}"
        logger.info(f"RAG Verifier: Checking past disasters for: {query}")

        try:
            # Search top 3 most similar lessons
            matches = self.rag_engine.search(query, top_k=3)

            if not matches:
                return True, "No similar past disasters found."

            for lesson, score in matches:
                # LanceDB scores are often distance (0.0 = exact match)
                # LessonsLearnedRAG normalizes them to 0-1 (1.0 = best match)
                if score >= self.threshold:
                    if lesson.severity in ["CRITICAL", "HIGH"]:
                        block_msg = f"BLOCKING TRADE: High similarity ({score:.2f}) to past disaster {lesson.id}: {lesson.title}"
                        logger.warning(f"🚨 {block_msg}")
                        logger.warning(f"Lesson Prevention: {lesson.prevention}")
                        return False, block_msg

            best_match = matches[0][0]
            best_score = matches[0][1]
            return (
                True,
                f"Verified against RAG. Closest match: {best_match.id} (Score: {best_score:.2f})",
            )

        except Exception as e:
            logger.error(f"TradeVerifier: RAG search failed: {e}")
            return True, f"Error during RAG verification: {e}. Failing open."


def get_trade_verifier(threshold: float = 0.75) -> TradeVerifier:
    return TradeVerifier(threshold)

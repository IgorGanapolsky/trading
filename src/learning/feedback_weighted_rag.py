"""
Feedback-Weighted RAG

Wraps LessonsLearnedRAG to apply feedback-based weights to search results.
Lessons that led to positive feedback get boosted.
Lessons that led to negative feedback get demoted.

This closes the loop: feedback → learning → better recommendations.
"""

from typing import Optional

from src.learning.feedback_processor import FeedbackProcessor
from src.rag.lessons_learned_rag import LessonsLearnedRAG


class FeedbackWeightedRAG:
    """
    RAG with feedback-based reranking.

    Usage:
        rag = FeedbackWeightedRAG()
        results = rag.search("trading risk management")
        # Results are reranked based on historical feedback
    """

    def __init__(
        self,
        knowledge_dir: Optional[str] = None,
        feedback_db: str = "data/feedback_memory.db",
    ):
        self.base_rag = LessonsLearnedRAG(knowledge_dir)
        self.feedback = FeedbackProcessor(db_path=feedback_db)

    def search(self, query: str, top_k: int = 5) -> list:
        """
        Search with feedback-weighted reranking.

        Returns list of (LessonResult, adjusted_score) tuples.
        """
        # Get base results
        base_results = self.base_rag.search(query, top_k=top_k * 2)  # Get more for reranking

        # Apply feedback weights
        weighted_results = []
        for lesson, base_score in base_results:
            weight = self.feedback.get_lesson_weight(lesson.id)
            adjusted_score = base_score * weight
            weighted_results.append((lesson, adjusted_score, weight))

        # Rerank by adjusted score
        weighted_results.sort(key=lambda x: x[1], reverse=True)

        # Return top_k with original format
        return [(lesson, score) for lesson, score, _ in weighted_results[:top_k]]

    def query(self, query: str, top_k: int = 5, severity_filter: Optional[str] = None) -> list:
        """Query with feedback weighting applied."""
        base_results = self.base_rag.query(query, top_k=top_k * 2, severity_filter=severity_filter)

        weighted_results = []
        for result in base_results:
            weight = self.feedback.get_lesson_weight(result["id"])
            result["feedback_weight"] = weight
            result["adjusted_score"] = result["score"] * weight
            weighted_results.append(result)

        weighted_results.sort(key=lambda x: x["adjusted_score"], reverse=True)
        return weighted_results[:top_k]

    def record_lesson_used(self, lesson_id: str, in_context: bool = True):
        """
        Record that a lesson was used in current context.
        Call this when citing a lesson so feedback can be attributed.
        """
        # This is tracked in the feedback processor when feedback arrives
        pass

    def get_critical_lessons(self) -> list:
        """Get critical lessons, weighted by feedback."""
        lessons = self.base_rag.get_critical_lessons()

        # Apply weights
        weighted = []
        for lesson in lessons:
            weight = self.feedback.get_lesson_weight(lesson["id"])
            lesson["feedback_weight"] = weight
            weighted.append(lesson)

        # Sort by weight (most reliable critical lessons first)
        weighted.sort(key=lambda x: x["feedback_weight"], reverse=True)
        return weighted

    def get_stats(self) -> dict:
        """Get combined RAG and feedback stats."""
        return {
            "total_lessons": len(self.base_rag.lessons),
            "feedback_stats": self.feedback.get_stats(),
        }

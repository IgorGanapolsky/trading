"""RAG Evaluation Metrics for Trading System.

This module provides evaluation metrics to measure RAG retrieval quality:
- Precision@k: Proportion of relevant docs in top-k results
- Recall@k: Proportion of all relevant docs found in top-k
- Mean Reciprocal Rank (MRR): Average of 1/rank of first relevant result

The ground truth is based on known lesson IDs that should be returned
for specific queries (e.g., "iron condor exit" should return LL-268).

Created: January 28, 2026
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default output directory for evaluation results
EVAL_OUTPUT_DIR = Path("data/evaluations/rag")


@dataclass
class EvaluationQuery:
    """A single evaluation query with expected results."""

    query: str
    expected_lesson_ids: list[str]  # Lessons that MUST appear
    description: str = ""

    def __post_init__(self):
        # Normalize lesson IDs (remove extension, lowercase for comparison)
        self.expected_lesson_ids = [
            lid.replace(".md", "").lower() for lid in self.expected_lesson_ids
        ]


@dataclass
class QueryResult:
    """Result of evaluating a single query."""

    query: str
    expected_ids: list[str]
    retrieved_ids: list[str]
    precision_at_k: float
    recall_at_k: float
    reciprocal_rank: float
    first_relevant_position: Optional[int]  # 1-indexed, None if not found
    k: int


@dataclass
class EvaluationReport:
    """Complete evaluation report across all queries."""

    timestamp: str
    num_queries: int
    k: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr: float  # Mean Reciprocal Rank
    query_results: list[QueryResult] = field(default_factory=list)
    failed_queries: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "timestamp": self.timestamp,
            "num_queries": self.num_queries,
            "k": self.k,
            "metrics": {
                "mean_precision_at_k": round(self.mean_precision_at_k, 4),
                "mean_recall_at_k": round(self.mean_recall_at_k, 4),
                "mrr": round(self.mrr, 4),
            },
            "query_results": [
                {
                    "query": qr.query,
                    "expected_ids": qr.expected_ids,
                    "retrieved_ids": qr.retrieved_ids,
                    "precision_at_k": round(qr.precision_at_k, 4),
                    "recall_at_k": round(qr.recall_at_k, 4),
                    "reciprocal_rank": round(qr.reciprocal_rank, 4),
                    "first_relevant_position": qr.first_relevant_position,
                    "k": qr.k,
                }
                for qr in self.query_results
            ],
            "failed_queries": self.failed_queries,
        }


# Ground truth test cases - queries with expected lesson IDs
# These are based on actual lessons in rag_knowledge/lessons_learned/
DEFAULT_TEST_QUERIES = [
    EvaluationQuery(
        query="iron condor exit strategy",
        expected_lesson_ids=["LL-268_Iron_Condor_Win_Rate_Research"],
        description="Should find LL-268 which discusses 7 DTE exit timing",
    ),
    EvaluationQuery(
        query="iron condor win rate",
        expected_lesson_ids=["LL-268_Iron_Condor_Win_Rate_Research"],
        description="Direct match for LL-268 win rate research",
    ),
    EvaluationQuery(
        query="close position API bug",
        expected_lesson_ids=[
            "LL-291_Alpaca_Close_Position_Bug_Jan22",
            "LL-292_Alpaca_Close_Position_Bug_Jan22",
        ],
        description="Should find Alpaca close position bug lessons",
    ),
    EvaluationQuery(
        query="tax optimization XSP",
        expected_lesson_ids=["LL-296_XSP_Tax_Optimization_Recommendation"],
        description="Should find XSP tax optimization lesson",
    ),
    EvaluationQuery(
        query="financial independence roadmap",
        expected_lesson_ids=[
            "LL-294_Financial_Independence_Roadmap",
            "LL-295_Wealth_Building_Pillars",
        ],
        description="Should find financial independence planning lessons",
    ),
    EvaluationQuery(
        query="position sizing error",
        expected_lesson_ids=["LL-290_Position_Accumulation_Bug_Jan22"],
        description="Should find position sizing/accumulation issues",
    ),
    EvaluationQuery(
        query="SOFI blocked trading",
        expected_lesson_ids=["LL-272_SOFI_Position_Blocked_Trading_Jan21"],
        description="Should find SOFI position blocking lesson",
    ),
    EvaluationQuery(
        query="delta selection options",
        expected_lesson_ids=["LL-268_Iron_Condor_Win_Rate_Research"],
        description="LL-268 covers delta selection (15-20 delta)",
    ),
    EvaluationQuery(
        query="RAG Webhook RAG query",
        expected_lesson_ids=["LL-300_RAG_Webhook_RAG_Query_Fix_Jan23"],
        description="Should find RAG Webhook RAG fix lesson",
    ),
    EvaluationQuery(
        query="iron condor entry signals",
        expected_lesson_ids=["LL-269_Iron_Condor_Entry_Signals"],
        description="Should find entry signals lesson",
    ),
]


class RAGEvaluator:
    """Evaluates RAG retrieval quality using standard IR metrics."""

    def __init__(self, test_queries: Optional[list[EvaluationQuery]] = None):
        """
        Initialize evaluator with test queries.

        Args:
            test_queries: List of EvaluationQuery with ground truth.
                         Defaults to DEFAULT_TEST_QUERIES.
        """
        self.test_queries = test_queries or DEFAULT_TEST_QUERIES
        self._search_engine = None

    def _get_search_engine(self):
        """Lazy load the search engine."""
        if self._search_engine is None:
            try:
                from src.rag.lessons_search import get_lessons_search

                self._search_engine = get_lessons_search()
            except ImportError:
                # Fallback to LessonsLearnedRAG
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                self._search_engine = LessonsLearnedRAG()
        return self._search_engine

    def _search(self, query: str, top_k: int) -> list[str]:
        """
        Execute search and return list of lesson IDs (normalized).

        Args:
            query: Search query string
            top_k: Number of results to retrieve

        Returns:
            List of lesson IDs (lowercase, no extension)
        """
        search = self._get_search_engine()

        # Try search() method first (returns list of tuples)
        if hasattr(search, "search"):
            results = search.search(query, top_k=top_k)
            # Handle (LessonResult, score) tuples
            return [r[0].id.lower() if hasattr(r[0], "id") else r[0].lower() for r in results]

        # Fallback to query() method
        if hasattr(search, "query"):
            results = search.query(query, top_k=top_k)
            return [r["id"].lower() for r in results]

        raise RuntimeError("Search engine has no search() or query() method")

    def precision_at_k(self, retrieved: list[str], relevant: list[str], k: int) -> float:
        """
        Calculate Precision@k.

        Precision@k = (# relevant docs in top-k) / k

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs (ground truth)
            k: Number of top results to consider

        Returns:
            Precision score between 0 and 1
        """
        if k == 0:
            return 0.0

        top_k = retrieved[:k]
        relevant_set = set(relevant)

        relevant_in_top_k = sum(1 for doc in top_k if doc in relevant_set)
        return relevant_in_top_k / k

    def recall_at_k(self, retrieved: list[str], relevant: list[str], k: int) -> float:
        """
        Calculate Recall@k.

        Recall@k = (# relevant docs in top-k) / (total relevant docs)

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs (ground truth)
            k: Number of top results to consider

        Returns:
            Recall score between 0 and 1
        """
        if not relevant:
            return 1.0  # No relevant docs expected, trivially satisfied

        top_k = retrieved[:k]
        relevant_set = set(relevant)

        relevant_in_top_k = sum(1 for doc in top_k if doc in relevant_set)
        return relevant_in_top_k / len(relevant_set)

    def reciprocal_rank(
        self, retrieved: list[str], relevant: list[str]
    ) -> tuple[float, Optional[int]]:
        """
        Calculate Reciprocal Rank.

        RR = 1 / (rank of first relevant document)
        Returns 0 if no relevant document found.

        Args:
            retrieved: List of retrieved document IDs
            relevant: List of relevant document IDs (ground truth)

        Returns:
            Tuple of (reciprocal rank, position of first relevant doc or None)
        """
        relevant_set = set(relevant)

        for i, doc in enumerate(retrieved):
            if doc in relevant_set:
                return 1.0 / (i + 1), i + 1

        return 0.0, None

    def evaluate_query(self, query: EvaluationQuery, k: int = 5) -> QueryResult:
        """
        Evaluate a single query.

        Args:
            query: EvaluationQuery with expected results
            k: Number of top results to consider

        Returns:
            QueryResult with all metrics
        """
        retrieved = self._search(query.query, top_k=k)
        expected = query.expected_lesson_ids

        p_at_k = self.precision_at_k(retrieved, expected, k)
        r_at_k = self.recall_at_k(retrieved, expected, k)
        rr, position = self.reciprocal_rank(retrieved, expected)

        return QueryResult(
            query=query.query,
            expected_ids=expected,
            retrieved_ids=retrieved,
            precision_at_k=p_at_k,
            recall_at_k=r_at_k,
            reciprocal_rank=rr,
            first_relevant_position=position,
            k=k,
        )

    def evaluate_all(self, k: int = 5) -> EvaluationReport:
        """
        Evaluate all test queries and compute aggregate metrics.

        Args:
            k: Number of top results to consider

        Returns:
            EvaluationReport with all metrics
        """
        query_results = []
        failed_queries = []

        precisions = []
        recalls = []
        reciprocal_ranks = []

        for test_query in self.test_queries:
            try:
                result = self.evaluate_query(test_query, k=k)
                query_results.append(result)

                precisions.append(result.precision_at_k)
                recalls.append(result.recall_at_k)
                reciprocal_ranks.append(result.reciprocal_rank)

            except Exception as e:
                logger.error(f"Failed to evaluate query '{test_query.query}': {e}")
                failed_queries.append(f"{test_query.query}: {str(e)}")

        # Calculate mean metrics
        mean_p = sum(precisions) / len(precisions) if precisions else 0.0
        mean_r = sum(recalls) / len(recalls) if recalls else 0.0
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0

        return EvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            num_queries=len(self.test_queries),
            k=k,
            mean_precision_at_k=mean_p,
            mean_recall_at_k=mean_r,
            mrr=mrr,
            query_results=query_results,
            failed_queries=failed_queries,
        )

    def save_report(self, report: EvaluationReport, output_dir: Optional[Path] = None) -> Path:
        """
        Save evaluation report to JSON file.

        Args:
            report: EvaluationReport to save
            output_dir: Directory to save to (default: data/evaluations/rag)

        Returns:
            Path to saved file
        """
        output_dir = output_dir or EVAL_OUTPUT_DIR
        output_dir.mkdir(parents=True, exist_ok=True)

        # Create filename with timestamp
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        filename = f"rag_evaluation_{timestamp}.json"
        output_path = output_dir / filename

        with open(output_path, "w") as f:
            json.dump(report.to_dict(), f, indent=2)

        logger.info(f"Saved evaluation report to {output_path}")
        return output_path


def get_evaluator(test_queries: Optional[list[EvaluationQuery]] = None) -> RAGEvaluator:
    """Get RAG evaluator instance."""
    return RAGEvaluator(test_queries=test_queries)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    evaluator = get_evaluator()
    report = evaluator.evaluate_all(k=5)

    print("\n=== RAG Evaluation Report ===")
    print(f"Timestamp: {report.timestamp}")
    print(f"Queries evaluated: {report.num_queries}")
    print(f"k = {report.k}")
    print("\nMetrics:")
    print(f"  Mean Precision@{report.k}: {report.mean_precision_at_k:.4f}")
    print(f"  Mean Recall@{report.k}: {report.mean_recall_at_k:.4f}")
    print(f"  MRR: {report.mrr:.4f}")

    if report.failed_queries:
        print(f"\nFailed queries: {len(report.failed_queries)}")
        for q in report.failed_queries:
            print(f"  - {q}")

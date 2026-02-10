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
import math
import os
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
    avoid_lesson_ids: list[str] = field(default_factory=list)  # Lessons that should NOT appear
    description: str = ""

    def __post_init__(self):
        # Normalize lesson IDs (remove extension, lowercase for comparison)
        self.expected_lesson_ids = [
            lid.replace(".md", "").lower() for lid in self.expected_lesson_ids
        ]
        self.avoid_lesson_ids = [lid.replace(".md", "").lower() for lid in self.avoid_lesson_ids]


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
    utility_at_k: Optional[float] = None


@dataclass
class EvaluationReport:
    """Complete evaluation report across all queries."""

    timestamp: str
    num_queries: int
    k: int
    mean_precision_at_k: float
    mean_recall_at_k: float
    mrr: float  # Mean Reciprocal Rank
    mean_utility_at_k: float = 0.0
    unanswerable_accuracy: Optional[float] = None
    unanswerable_false_positive_rate: Optional[float] = None
    unanswerable_results: list[dict] = field(default_factory=list)
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
                "mean_utility_at_k": round(self.mean_utility_at_k, 4),
            },
            "unanswerable": {
                "accuracy": (
                    round(self.unanswerable_accuracy, 4)
                    if self.unanswerable_accuracy is not None
                    else None
                ),
                "false_positive_rate": (
                    round(self.unanswerable_false_positive_rate, 4)
                    if self.unanswerable_false_positive_rate is not None
                    else None
                ),
                "results": self.unanswerable_results,
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
                    "utility_at_k": (
                        round(qr.utility_at_k, 4) if qr.utility_at_k is not None else None
                    ),
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
        expected_lesson_ids=[
            "LL-268_Iron_Condor_Win_Rate_Research",
            "LL-301_IC_Position_Management_System_Jan23",
            "LL-323_Iron_Condor_Management_71K_Study_Jan31",
        ],
        description="Exit strategy should include win-rate research and management/exit system lessons",
    ),
    EvaluationQuery(
        query="iron condor win rate",
        expected_lesson_ids=[
            "LL-268_Iron_Condor_Win_Rate_Research",
            "ll_277_iron_condor_optimization_research_jan21",
            "LL-323_Iron_Condor_Management_71K_Study_Jan31",
        ],
        description="Win-rate research spans LL-268, LL-277, and the 71k trade study",
    ),
    EvaluationQuery(
        query="close position API bug",
        expected_lesson_ids=[
            "ll_282_close_position_api_for_orphans_jan22",
            "ll_281_alpaca_api_close_position_bug_jan22",
            "LL-291_Alpaca_Close_Position_Bug_Jan22",
            "LL-292_Alpaca_Close_Position_Bug_Jan22",
        ],
        description="Should find Alpaca close_position() API bug and remediation lessons",
    ),
    EvaluationQuery(
        query="tax optimization XSP",
        expected_lesson_ids=[
            "LL-296_XSP_Tax_Optimization_Recommendation",
            "LL-322_XSP_vs_SPY_Tax_Optimization_Jan31",
            "LL-297_Comprehensive_Tax_Strategy_Planning",
        ],
        description="Should find XSP tax optimization and tax strategy lessons",
    ),
    EvaluationQuery(
        query="financial independence roadmap",
        expected_lesson_ids=[
            "LL-294_Financial_Independence_Roadmap",
            "LL-295_Wealth_Building_Pillars",
            "ll_212_north_star_math_roadmap_jan15",
            "ll_220_north_star_30month_roadmap_jan15",
        ],
        description="Should find financial independence and North Star roadmap lessons",
    ),
    EvaluationQuery(
        query="position sizing error",
        expected_lesson_ids=[
            "LL-290_Position_Accumulation_Bug_Jan22",
            "ll_280_cumulative_position_risk_bypass_jan22",
            "ll_258_5pct_position_limit_enforcement_jan19",
        ],
        description="Should find position sizing/limit enforcement and accumulation issues",
    ),
    EvaluationQuery(
        query="SOFI blocked trading",
        expected_lesson_ids=[
            "LL-272_SOFI_Position_Blocked_Trading_Jan21",
            "ll_247_sofi_pdt_crisis_jan20",
            "ll_158_day74_emergency_fix_jan13",
        ],
        description="Should find SOFI blockage and crisis recovery lessons",
    ),
    EvaluationQuery(
        query="delta selection options",
        expected_lesson_ids=[
            "LL-268_Iron_Condor_Win_Rate_Research",
            "ll_277_iron_condor_optimization_research_jan21",
            "LL-321_VIX_Entry_Rules_Iron_Condor_Jan31",
        ],
        description="Delta selection guidance appears across win-rate research and VIX rules",
    ),
    EvaluationQuery(
        query="RAG Webhook RAG query",
        expected_lesson_ids=[
            "LL-300_RAG_Webhook_RAG_Query_Fix_Jan23",
            "ll_238_lancedb_rag_init_failure_jan16",
            "ll_227_rag_failure_100k_lessons_lost_jan14",
        ],
        description="Should find webhook/query fixes and RAG gap lessons",
    ),
    EvaluationQuery(
        query="iron condor entry signals",
        expected_lesson_ids=[
            "LL-269_Iron_Condor_Entry_Signals",
            "LL-321_VIX_Entry_Rules_Iron_Condor_Jan31",
            "ll_310_vix_timing_iron_condor_entry_jan25",
        ],
        description="Entry signal guidance spans entry signals and VIX timing rules",
    ),
]

# Negative / unanswerable checks (should NOT have confident matches)
UNANSWERABLE_TEST_QUERIES = [
    EvaluationQuery(
        query="quantum gravity trade execution protocol",
        expected_lesson_ids=[],
        description="Should not match any trading lessons",
    ),
    EvaluationQuery(
        query="mars colony funding strategy for options traders",
        expected_lesson_ids=[],
        description="Out-of-domain query should be rejected",
    ),
    EvaluationQuery(
        query="dinosaur extinction hedging playbook",
        expected_lesson_ids=[],
        description="Irrelevant query should return no confident hits",
    ),
]


class RAGEvaluator:
    """Evaluates RAG retrieval quality using standard IR metrics."""

    def __init__(
        self,
        test_queries: Optional[list[EvaluationQuery]] = None,
        prefer_lancedb: Optional[bool] = None,
    ):
        """
        Initialize evaluator with test queries.

        Args:
            test_queries: List of EvaluationQuery with ground truth.
                         Defaults to DEFAULT_TEST_QUERIES.
        """
        self.test_queries = test_queries or DEFAULT_TEST_QUERIES
        if prefer_lancedb is None:
            prefer_lancedb = os.getenv("RAG_EVAL_LANCEDB", "").lower() in {
                "1",
                "true",
                "yes",
            }
        self.prefer_lancedb = prefer_lancedb
        self._search_engine = None

    def _get_search_engine(self):
        """Lazy load the search engine."""
        if self._search_engine is None:
            if self.prefer_lancedb:
                try:
                    from src.rag.lessons_learned_rag import LessonsLearnedRAG

                    self._search_engine = LessonsLearnedRAG()
                    return self._search_engine
                except Exception as e:
                    logger.warning(f"LanceDB RAG unavailable: {e} - using keyword search")

            try:
                from src.rag.lessons_search import get_lessons_search

                self._search_engine = get_lessons_search()
            except ImportError:
                # Fallback to LessonsLearnedRAG
                from src.rag.lessons_learned_rag import LessonsLearnedRAG

                self._search_engine = LessonsLearnedRAG()
        return self._search_engine

    def _search_with_scores(self, query: str, top_k: int) -> list[dict]:
        """
        Execute search and return list of dicts with id + score.

        Returns:
            List of {"id": str, "score": float}
        """
        search = self._get_search_engine()

        results: list[dict] = []

        if hasattr(search, "query"):
            try:
                raw = search.query(query, top_k=top_k)
                for item in raw:
                    lesson_id = item.get("id") or item.get("lesson_id") or "unknown"
                    results.append(
                        {
                            "id": str(lesson_id).replace(".md", "").lower(),
                            "score": float(item.get("score", 0.0) or 0.0),
                            "raw_score": float(
                                item.get("raw_score", item.get("score", 0.0)) or 0.0
                            ),
                        }
                    )
                return results
            except Exception as e:
                logger.warning(f"Query() failed: {e}")

        if hasattr(search, "search"):
            try:
                raw = search.search(query, top_k=top_k)
                for item in raw:
                    if isinstance(item, tuple) and len(item) == 2:
                        lesson, score = item
                        lesson_id = lesson.id if hasattr(lesson, "id") else str(lesson)
                        results.append(
                            {
                                "id": lesson_id.replace(".md", "").lower(),
                                "score": float(score),
                                "raw_score": float(score),
                            }
                        )
                    elif isinstance(item, dict):
                        lesson_id = item.get("id") or item.get("lesson_id") or "unknown"
                        results.append(
                            {
                                "id": str(lesson_id).replace(".md", "").lower(),
                                "score": float(item.get("score", 0.0) or 0.0),
                                "raw_score": float(
                                    item.get("raw_score", item.get("score", 0.0)) or 0.0
                                ),
                            }
                        )
                if results:
                    return results
            except Exception as e:
                logger.warning(f"Search() failed: {e}")

        raise RuntimeError("Search engine has no usable search() or query() method")

    @staticmethod
    def _normalize_match_id(value: str) -> str:
        """Normalize lesson IDs for matching (LL-###)."""
        import re

        if not value:
            return ""
        raw = value.lower().replace(".md", "")
        match = re.search(r"ll[-_]?(\d+)", raw)
        if match:
            return f"ll-{match.group(1)}"
        return raw

    def _search(self, query: str, top_k: int) -> list[str]:
        """
        Execute search and return list of lesson IDs (normalized).

        Args:
            query: Search query string
            top_k: Number of results to retrieve

        Returns:
            List of lesson IDs (lowercase, no extension)
        """
        results = self._search_with_scores(query, top_k)
        return [r["id"] for r in results]

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

        top_k = [self._normalize_match_id(doc) for doc in retrieved[:k]]
        relevant_set = {self._normalize_match_id(doc) for doc in relevant}

        relevant_in_top_k = len({doc for doc in top_k if doc in relevant_set})
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

        top_k = [self._normalize_match_id(doc) for doc in retrieved[:k]]
        relevant_set = {self._normalize_match_id(doc) for doc in relevant}

        relevant_in_top_k = len({doc for doc in top_k if doc in relevant_set})
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
        relevant_set = {self._normalize_match_id(doc) for doc in relevant}

        for i, doc in enumerate(retrieved):
            if self._normalize_match_id(doc) in relevant_set:
                return 1.0 / (i + 1), i + 1

        return 0.0, None

    def utility_at_k(
        self,
        retrieved: list[str],
        relevant: list[str],
        avoid: list[str],
        k: int,
    ) -> float:
        """
        Utility-aware DCG@k (UDCG-style).

        Relevant docs contribute +1, avoid docs contribute -1.
        Scores are discounted by rank position.
        """
        if k == 0:
            return 0.0

        relevant_set = {self._normalize_match_id(doc) for doc in relevant}
        avoid_set = {self._normalize_match_id(doc) for doc in avoid}

        dcg = 0.0
        for i, doc in enumerate(retrieved[:k]):
            gain = 0
            norm_doc = self._normalize_match_id(doc)
            if norm_doc in relevant_set:
                gain = 1
            elif norm_doc in avoid_set:
                gain = -1

            if gain != 0:
                dcg += gain / math.log2(i + 2)

        ideal_dcg = 0.0
        ideal_hits = min(k, len(relevant_set))
        for i in range(ideal_hits):
            ideal_dcg += 1.0 / math.log2(i + 2)

        if ideal_dcg == 0:
            return 0.0

        return dcg / ideal_dcg

    def evaluate_unanswerable(
        self,
        queries: Optional[list[EvaluationQuery]] = None,
        k: int = 5,
        score_threshold: float = 0.04,
    ) -> dict:
        """Evaluate rejection accuracy on unanswerable queries."""
        queries = queries or UNANSWERABLE_TEST_QUERIES
        if not queries:
            return {
                "accuracy": None,
                "false_positive_rate": None,
                "results": [],
            }

        false_positives = 0
        results = []

        for q in queries:
            hits = self._search_with_scores(q.query, top_k=k)
            max_score = 0.0
            for h in hits:
                score = h.get("raw_score")
                if score is None:
                    score = h.get("score", 0.0)
                score = float(score or 0.0)
                if score > 1.0:
                    score = score / (score + 1.0)
                if score > max_score:
                    max_score = score
            predicted_unanswerable = max_score < score_threshold
            passed = predicted_unanswerable

            if not passed:
                false_positives += 1

            results.append(
                {
                    "query": q.query,
                    "max_score": round(max_score, 4),
                    "predicted_unanswerable": predicted_unanswerable,
                    "passed": passed,
                }
            )

        total = len(queries)
        accuracy = (total - false_positives) / total if total else None
        false_positive_rate = false_positives / total if total else None

        return {
            "accuracy": accuracy,
            "false_positive_rate": false_positive_rate,
            "results": results,
        }

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
        avoid = query.avoid_lesson_ids

        p_at_k = self.precision_at_k(retrieved, expected, k)
        r_at_k = self.recall_at_k(retrieved, expected, k)
        rr, position = self.reciprocal_rank(retrieved, expected)
        utility = self.utility_at_k(retrieved, expected, avoid, k)

        return QueryResult(
            query=query.query,
            expected_ids=expected,
            retrieved_ids=retrieved,
            precision_at_k=p_at_k,
            recall_at_k=r_at_k,
            reciprocal_rank=rr,
            first_relevant_position=position,
            k=k,
            utility_at_k=utility,
        )

    def evaluate_all(
        self,
        k: int = 5,
        include_unanswerable: bool = False,
        unanswerable_threshold: float = 0.35,
    ) -> EvaluationReport:
        """
        Evaluate all test queries and compute aggregate metrics.

        Args:
            k: Number of top results to consider
            include_unanswerable: If True, evaluate rejection accuracy
            unanswerable_threshold: Score threshold for "no answer" classification

        Returns:
            EvaluationReport with all metrics
        """
        query_results = []
        failed_queries = []

        precisions = []
        recalls = []
        reciprocal_ranks = []
        utilities = []

        for test_query in self.test_queries:
            try:
                result = self.evaluate_query(test_query, k=k)
                query_results.append(result)

                precisions.append(result.precision_at_k)
                recalls.append(result.recall_at_k)
                reciprocal_ranks.append(result.reciprocal_rank)
                if result.utility_at_k is not None:
                    utilities.append(result.utility_at_k)

            except Exception as e:
                logger.error(f"Failed to evaluate query '{test_query.query}': {e}")
                failed_queries.append(f"{test_query.query}: {str(e)}")

        # Calculate mean metrics
        mean_p = sum(precisions) / len(precisions) if precisions else 0.0
        mean_r = sum(recalls) / len(recalls) if recalls else 0.0
        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks) if reciprocal_ranks else 0.0
        mean_utility = sum(utilities) / len(utilities) if utilities else 0.0

        unanswerable_metrics = {
            "accuracy": None,
            "false_positive_rate": None,
            "results": [],
        }
        if include_unanswerable:
            unanswerable_metrics = self.evaluate_unanswerable(
                queries=UNANSWERABLE_TEST_QUERIES,
                k=k,
                score_threshold=unanswerable_threshold,
            )

        return EvaluationReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            num_queries=len(self.test_queries),
            k=k,
            mean_precision_at_k=mean_p,
            mean_recall_at_k=mean_r,
            mrr=mrr,
            mean_utility_at_k=mean_utility,
            unanswerable_accuracy=unanswerable_metrics.get("accuracy"),
            unanswerable_false_positive_rate=unanswerable_metrics.get("false_positive_rate"),
            unanswerable_results=unanswerable_metrics.get("results", []),
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


def get_evaluator(
    test_queries: Optional[list[EvaluationQuery]] = None,
    prefer_lancedb: Optional[bool] = None,
) -> RAGEvaluator:
    """Get RAG evaluator instance."""
    return RAGEvaluator(test_queries=test_queries, prefer_lancedb=prefer_lancedb)


if __name__ == "__main__":
    # Quick test
    logging.basicConfig(level=logging.INFO)

    evaluator = get_evaluator()
    report = evaluator.evaluate_all(k=5, include_unanswerable=True)

    print("\n=== RAG Evaluation Report ===")
    print(f"Timestamp: {report.timestamp}")
    print(f"Queries evaluated: {report.num_queries}")
    print(f"k = {report.k}")
    print("\nMetrics:")
    print(f"  Mean Precision@{report.k}: {report.mean_precision_at_k:.4f}")
    print(f"  Mean Recall@{report.k}: {report.mean_recall_at_k:.4f}")
    print(f"  MRR: {report.mrr:.4f}")
    print(f"  Mean Utility@{report.k}: {report.mean_utility_at_k:.4f}")

    if report.failed_queries:
        print(f"\nFailed queries: {len(report.failed_queries)}")
        for q in report.failed_queries:
            print(f"  - {q}")

#!/usr/bin/env python3
"""
RAG Evaluation Tests - Retrieval Accuracy, Grounding, and Context Leakage.

Created: Jan 21, 2026 (LL-268)
Purpose: Validate RAG system quality beyond smoke tests.

Tests:
1. Retrieval Accuracy - Do we retrieve relevant documents?
2. Grounding - Is output faithful to retrieved context?
3. Context Leakage - Are secrets protected?

Run weekly in CI, not on every commit.
"""

import json
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Load golden test set
FIXTURES_DIR = Path(__file__).parent / "fixtures"
GOLDEN_SET_PATH = FIXTURES_DIR / "rag_golden_set.json"


def load_golden_set():
    """Load the golden test set."""
    if not GOLDEN_SET_PATH.exists():
        pytest.skip(f"Golden set not found: {GOLDEN_SET_PATH}")
    with open(GOLDEN_SET_PATH) as f:
        return json.load(f)


class TestRAGRetrievalAccuracy:
    """Test retrieval accuracy using golden set queries."""

    @pytest.fixture
    def golden_set(self):
        return load_golden_set()

    def test_golden_set_loads(self, golden_set):
        """Should load golden test set successfully."""
        assert "test_cases" in golden_set
        assert len(golden_set["test_cases"]) >= 10
        assert "context_leakage_tests" in golden_set

    def test_golden_set_structure(self, golden_set):
        """Each test case should have required fields."""
        for case in golden_set["test_cases"]:
            assert "id" in case
            assert "query" in case
            assert "expected_keywords" in case
            assert isinstance(case["expected_keywords"], list)

    @pytest.mark.skipif(
        not os.getenv("GCP_SA_KEY") and not os.getenv("GOOGLE_CLOUD_PROJECT"),
        reason="Vertex AI credentials not available",
    )
    def test_retrieval_keyword_coverage(self, golden_set):
        """Retrieved documents should contain expected keywords."""
        from src.rag.vertex_rag import get_vertex_rag

        rag = get_vertex_rag()
        if not rag.is_initialized:
            pytest.skip("Vertex AI RAG not initialized")

        passed = 0
        failed = 0
        results = []

        for case in golden_set["test_cases"][:5]:  # Test first 5 to save API calls
            query = case["query"]
            expected_keywords = case["expected_keywords"]

            response = rag.query(query, similarity_top_k=5)

            if not response:
                failed += 1
                results.append({"id": case["id"], "status": "no_response"})
                continue

            response_text = " ".join(r.get("text", "") for r in response).lower()
            found_keywords = [kw for kw in expected_keywords if kw.lower() in response_text]

            coverage = len(found_keywords) / len(expected_keywords) if expected_keywords else 1.0

            if coverage >= 0.5:  # At least 50% keyword coverage
                passed += 1
                results.append({"id": case["id"], "status": "passed", "coverage": coverage})
            else:
                failed += 1
                results.append({"id": case["id"], "status": "failed", "coverage": coverage})

        precision = passed / (passed + failed) if (passed + failed) > 0 else 0
        assert precision >= 0.6, f"Retrieval precision too low: {precision:.2%}. Results: {results}"


class TestRAGGrounding:
    """Test that responses are grounded in retrieved context."""

    @pytest.mark.skipif(
        not os.getenv("GCP_SA_KEY") and not os.getenv("GOOGLE_CLOUD_PROJECT"),
        reason="Vertex AI credentials not available",
    )
    def test_response_contains_source_material(self):
        """Response should reference content from retrieved documents."""
        from src.rag.vertex_rag import get_vertex_rag

        rag = get_vertex_rag()
        if not rag.is_initialized:
            pytest.skip("Vertex AI RAG not initialized")

        # Query for something specific we know exists
        query = "What is the trading strategy?"
        response = rag.query(query, similarity_top_k=3)

        if not response:
            pytest.skip("No response from RAG")

        response_text = " ".join(r.get("text", "") for r in response).lower()

        # Should mention concrete strategy terms, not generic advice
        strategy_terms = ["spy", "iron condor", "delta", "option", "spread"]
        found_terms = sum(1 for term in strategy_terms if term in response_text)

        assert found_terms >= 2, f"Response lacks grounding in strategy docs. Found terms: {found_terms}"


class TestRAGContextLeakage:
    """Test that sensitive data is not exposed through RAG queries."""

    @pytest.fixture
    def golden_set(self):
        return load_golden_set()

    def test_leakage_test_cases_exist(self, golden_set):
        """Should have context leakage test cases defined."""
        assert "context_leakage_tests" in golden_set
        assert len(golden_set["context_leakage_tests"]) >= 3

    @pytest.mark.skipif(
        not os.getenv("GCP_SA_KEY") and not os.getenv("GOOGLE_CLOUD_PROJECT"),
        reason="Vertex AI credentials not available",
    )
    def test_no_api_key_leakage(self, golden_set):
        """RAG should not expose API keys or secrets."""
        from src.rag.vertex_rag import get_vertex_rag

        rag = get_vertex_rag()
        if not rag.is_initialized:
            pytest.skip("Vertex AI RAG not initialized")

        for leakage_test in golden_set["context_leakage_tests"]:
            query = leakage_test["query"]
            forbidden_patterns = leakage_test["forbidden_patterns"]

            response = rag.query(query, similarity_top_k=5)

            if not response:
                continue  # No response is safe

            response_text = " ".join(r.get("text", "") for r in response)

            for pattern in forbidden_patterns:
                assert pattern not in response_text, (
                    f"Context leakage detected! Pattern '{pattern}' found in response to: {query}"
                )


class TestLocalRAGFallback:
    """Test local TF-IDF fallback RAG evaluation."""

    def test_local_rag_keyword_search(self):
        """Local RAG should find lessons by keyword."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG
        except ImportError:
            pytest.skip("LessonsLearnedRAG not available")

        rag = LessonsLearnedRAG()

        # Query for a term that should exist
        results = rag.query("trading", top_k=3)

        assert isinstance(results, list)
        # Should find at least one result if lessons exist
        if rag.lessons:
            assert len(results) >= 1, "Local RAG found no results for 'trading'"

    def test_local_rag_critical_lessons(self):
        """Should be able to retrieve critical lessons."""
        try:
            from src.rag.lessons_learned_rag import LessonsLearnedRAG
        except ImportError:
            pytest.skip("LessonsLearnedRAG not available")

        rag = LessonsLearnedRAG()
        critical = rag.get_critical_lessons()

        assert isinstance(critical, list)


class TestRAGEvaluationMetrics:
    """Test RAG evaluation metric calculations (without RAGAS dependency)."""

    def test_precision_at_k_calculation(self):
        """Calculate Precision@K for mock retrieval results."""
        # Simulate retrieval results
        retrieved = ["doc1", "doc2", "doc3", "doc4", "doc5"]
        relevant = {"doc1", "doc3", "doc5"}  # Ground truth relevant docs

        # Precision@5 = relevant_retrieved / k
        relevant_retrieved = sum(1 for doc in retrieved if doc in relevant)
        precision_at_5 = relevant_retrieved / len(retrieved)

        assert precision_at_5 == 0.6  # 3/5 = 0.6

    def test_recall_at_k_calculation(self):
        """Calculate Recall@K for mock retrieval results."""
        retrieved = ["doc1", "doc2", "doc3"]
        relevant = {"doc1", "doc3", "doc5", "doc7"}  # 4 relevant docs total

        # Recall@3 = relevant_retrieved / total_relevant
        relevant_retrieved = sum(1 for doc in retrieved if doc in relevant)
        recall_at_3 = relevant_retrieved / len(relevant)

        assert recall_at_3 == 0.5  # 2/4 = 0.5

    def test_mrr_calculation(self):
        """Calculate Mean Reciprocal Rank for mock results."""
        # MRR = average of 1/rank for first relevant result

        queries_results = [
            (["doc1", "doc2", "doc3"], {"doc1"}),  # rank 1 -> 1/1 = 1.0
            (["doc1", "doc2", "doc3"], {"doc2"}),  # rank 2 -> 1/2 = 0.5
            (["doc1", "doc2", "doc3"], {"doc3"}),  # rank 3 -> 1/3 = 0.33
        ]

        reciprocal_ranks = []
        for retrieved, relevant in queries_results:
            for rank, doc in enumerate(retrieved, 1):
                if doc in relevant:
                    reciprocal_ranks.append(1.0 / rank)
                    break
            else:
                reciprocal_ranks.append(0.0)

        mrr = sum(reciprocal_ranks) / len(reciprocal_ranks)
        assert 0.6 <= mrr <= 0.62  # (1 + 0.5 + 0.33) / 3 ≈ 0.61


class TestRAGASIntegration:
    """Test RAGAS framework integration (if available)."""

    def test_ragas_importable(self):
        """RAGAS should be importable after adding to requirements."""
        try:
            import ragas

            assert ragas is not None
        except ImportError:
            pytest.skip("RAGAS not installed - add to requirements.txt and run pip install")

    @pytest.mark.skip(reason="RAGAS requires LangChain and OpenAI setup - run manually")
    def test_ragas_faithfulness_metric(self):
        """Test RAGAS faithfulness metric calculation."""
        from ragas.metrics import faithfulness

        # This requires actual LLM setup - skip in automated tests
        assert faithfulness is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

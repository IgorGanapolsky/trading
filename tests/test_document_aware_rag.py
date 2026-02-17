"""
Tests for Document-Aware RAG System

This validates the LongRAG-style document retrieval:
1. Section-level chunking preserves lesson sections
2. Metadata enrichment extracts categories and strategies
3. Hybrid retrieval filters by metadata before semantic search
4. Complex queries about position stacking return relevant results
5. Vector flattening optimization for improved precision/recall
"""

from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def rag_with_index():
    """Return a RAG instance only when the document-aware table is available."""
    from src.memory.document_aware_rag import get_document_aware_rag

    rag = get_document_aware_rag()
    if not rag._init_lancedb():
        pytest.skip("LanceDB not available")
    if "document_aware_rag" not in rag._get_table_names():
        pytest.skip("Document-aware RAG table not found (run reindex)")
    return rag


class TestDocumentAwareRAG:
    """Test suite for document-aware RAG system."""

    def test_import_module(self):
        """Verify module can be imported."""
        from src.memory.document_aware_rag import (
            DocumentAwareRAG,
            get_document_aware_rag,
        )

        assert DocumentAwareRAG is not None
        assert get_document_aware_rag is not None

    def test_singleton_instance(self):
        """Verify singleton pattern works."""
        from src.memory.document_aware_rag import get_document_aware_rag

        rag1 = get_document_aware_rag()
        rag2 = get_document_aware_rag()
        assert rag1 is rag2

    def test_search_result_dataclass(self):
        """Verify SearchResult dataclass structure."""
        from src.memory.document_aware_rag import SearchResult

        result = SearchResult(
            document_id="test_doc",
            title="Test Title",
            content="Test content",
            section_title="Test Section",
            score=0.95,
            metadata={"severity": "critical"},
        )

        assert result.document_id == "test_doc"
        assert result.score == 0.95
        assert result.metadata["severity"] == "critical"

    def test_document_section_dataclass(self):
        """Verify DocumentSection dataclass structure."""
        from src.memory.document_aware_rag import DocumentSection

        section = DocumentSection(
            id="test_section",
            title="Test Section",
            content="Test content here",
            section_type="root_cause",
            parent_doc_id="test_doc",
            parent_doc_title="Test Document",
            chunk_index=0,
        )

        assert section.section_type == "root_cause"
        assert section.chunk_index == 0

    def test_classify_section_type(self):
        """Verify section type classification."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        assert rag._classify_section_type("What Happened") == "what_happened"
        assert rag._classify_section_type("Root Cause Analysis") == "root_cause"
        assert rag._classify_section_type("Solution") == "solution"
        assert rag._classify_section_type("Prevention") == "prevention"
        assert rag._classify_section_type("Summary") == "summary"
        assert rag._classify_section_type("Random Title") == "content"

    def test_extract_sections(self):
        """Verify section extraction from markdown."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = """# Test Document

This is the summary.

## What Happened

This is what happened in the incident.
The description continues here with more details.

## Root Cause

The root cause was identified as a bug.
Multiple factors contributed to this issue.

## Solution

We fixed it by adding validation.
The fix was verified in testing.
"""

        sections = rag._extract_sections(content, "test_doc", "Test Document")

        # Should have 3 sections (summary + what_happened + root_cause + solution)
        assert len(sections) >= 3

        # Check section types
        section_types = [s.section_type for s in sections]
        assert "what_happened" in section_types
        assert "root_cause" in section_types
        assert "solution" in section_types

    def test_metadata_extraction(self):
        """Verify metadata extraction from content."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = """# LL-275: Position Stacking Bug

**Severity**: CRITICAL

This lesson documents a position stacking issue with iron condor trades
in the $100K paper account during high VIX environments.

## Prevention

Always validate position limits before executing trades.
"""

        filepath = Path("ll_275_position_stacking_bug_jan22.md")
        metadata = rag._extract_metadata(content, filepath)

        assert metadata["severity"] == "critical"
        assert metadata["lesson_id"] == "LL-275"
        assert "risk_management" in metadata["categories"]
        assert "iron condor" in metadata["strategies"]
        assert metadata["account"] == "100k"
        assert metadata["market_condition"] == "high_volatility"

    def test_search_integration(self, rag_with_index):
        """Integration test for search functionality."""
        rag = rag_with_index

        result = rag.query_with_context("position stacking", limit=2)

        assert "query" in result
        assert "result_count" in result
        assert "results" in result
        assert result["result_count"] >= 0

    def test_complex_query(self, rag_with_index):
        """Test complex query about position stacking in high VIX."""
        rag = rag_with_index

        result = rag.query_with_context(
            "What went wrong with position stacking in high VIX environments?", limit=3
        )

        # Should find relevant results
        assert result["result_count"] > 0

        # Results should be high severity
        for r in result["results"]:
            # Position stacking lessons should be marked as important
            assert r.score > 0.5


class TestVectorFlattening:
    """Test suite for vector flattening optimization."""

    def test_flatten_for_embedding_basic(self):
        """Verify basic metadata flattening to natural language."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = "This is the main content about position sizing."
        metadata = {
            "primary_category": "risk_management",
            "severity": "critical",
            "lesson_id": "LL-275",
        }

        flattened = rag.flatten_for_embedding(content, metadata)

        # Should contain natural language metadata
        assert "Category: risk management." in flattened
        assert "Severity level: CRITICAL." in flattened
        assert "Lesson identifier: LL-275." in flattened
        # Should preserve original content
        assert "position sizing" in flattened

    def test_flatten_for_embedding_with_strategies(self):
        """Verify strategy list flattening."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = "How to trade iron condors."
        metadata = {
            "strategies": ["iron condor", "credit spread"],
            "market_condition": "high_volatility",
            "account": "100k",
        }

        flattened = rag.flatten_for_embedding(content, metadata)

        assert "Trading strategies: iron condor, credit spread." in flattened
        assert "Market condition: high volatility." in flattened
        assert "Account size: $100k." in flattened

    def test_flatten_for_embedding_empty_metadata(self):
        """Verify flattening handles empty metadata gracefully."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = "Plain content with no metadata."
        metadata = {}

        flattened = rag.flatten_for_embedding(content, metadata)

        # Should return original content when no metadata
        assert flattened == content

    def test_flatten_for_embedding_json_strategies(self):
        """Verify flattening handles JSON-encoded strategies."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = "Strategy content."
        metadata = {"strategies": '["iron condor", "put spread"]'}

        flattened = rag.flatten_for_embedding(content, metadata)

        assert "Trading strategies: iron condor, put spread." in flattened

    def test_generate_flattened_text(self):
        """Verify _generate_flattened_text combines section and metadata."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        section_title = "Root Cause Analysis"
        section_content = "The bug was caused by position stacking."
        metadata = {
            "section_type": "root_cause",
            "severity": "high",
            "primary_category": "risk_management",
        }

        flattened = rag._generate_flattened_text(section_title, section_content, metadata)

        # Should have section title and content
        assert "Root Cause Analysis" in flattened
        assert "position stacking" in flattened
        # Should have flattened metadata
        assert "Category: risk management." in flattened
        assert "Section type: root cause." in flattened
        assert "Severity level: HIGH." in flattened


class TestVectorFlatteningBenchmark:
    """
    Benchmark tests comparing retrieval quality with flattening.

    These tests measure precision/recall improvement from the
    vector flattening optimization.
    """

    # Benchmark queries with expected relevant keywords
    BENCHMARK_QUERIES = [
        {
            "query": "position stacking risk management",
            "expected_keywords": ["position", "stacking", "risk"],
            "expected_category": "risk_management",
        },
        {
            "query": "iron condor high volatility VIX",
            "expected_keywords": ["iron condor", "vix", "volatility"],
            "expected_strategy": "iron condor",
        },
        {
            "query": "critical severity trading lesson",
            "expected_keywords": ["critical", "lesson"],
            "expected_severity": "critical",
        },
        {
            "query": "what went wrong with the trade",
            "expected_keywords": ["wrong", "issue", "problem"],
            "expected_section_type": "what_happened",
        },
    ]

    def test_flattening_improves_keyword_density(self):
        """Verify flattened text has higher keyword density for search."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        content = "The trade failed."
        metadata = {
            "primary_category": "risk_management",
            "severity": "critical",
            "strategies": ["iron condor"],
            "market_condition": "high_volatility",
        }

        # Original text (no flattening)
        original = f"{content}"

        # Flattened text
        flattened = rag.flatten_for_embedding(content, metadata)

        # Count searchable terms in each
        search_terms = [
            "risk",
            "management",
            "critical",
            "iron condor",
            "volatility",
        ]

        original_matches = sum(1 for term in search_terms if term.lower() in original.lower())
        flattened_matches = sum(1 for term in search_terms if term.lower() in flattened.lower())

        # Flattened should have more searchable terms
        assert flattened_matches > original_matches, (
            f"Flattened ({flattened_matches}) should have more terms than original ({original_matches})"
        )
        # Specifically, flattened should match at least 4 of 5 terms
        assert flattened_matches >= 4

    def test_flattening_preserves_semantic_content(self):
        """Verify flattening doesn't lose important semantic content."""
        from src.memory.document_aware_rag import DocumentAwareRAG

        rag = DocumentAwareRAG()

        # Complex content with specific details
        content = """
        On January 22nd, the position stacking bug caused a $5,000 loss
        when the system opened 3 overlapping iron condor positions on SPY
        during a VIX spike above 25.
        """
        metadata = {
            "primary_category": "risk_management",
            "severity": "critical",
            "date": "2026-01-22",
        }

        flattened = rag.flatten_for_embedding(content, metadata)

        # Important details from content should be preserved
        assert "$5,000" in flattened
        assert "SPY" in flattened
        assert "VIX spike" in flattened
        assert "25" in flattened

        # Metadata should be added
        assert "risk management" in flattened
        assert "CRITICAL" in flattened

    def test_benchmark_query_relevance(self, rag_with_index):
        """
        Benchmark test: Measure if search results contain expected keywords.

        This is a basic relevance test - results should contain query-related content.
        """
        rag = rag_with_index

        total_queries = 0
        relevant_results = 0

        for benchmark in self.BENCHMARK_QUERIES:
            query = benchmark["query"]
            expected_keywords = benchmark["expected_keywords"]

            results = rag.search(query, limit=3)
            total_queries += 1

            if results:
                # Check if top result contains any expected keyword
                top_result_text = results[0].content.lower()
                if any(kw.lower() in top_result_text for kw in expected_keywords):
                    relevant_results += 1

        # With flattening, we expect at least 50% relevance
        # (This is a baseline - real improvement measurement needs before/after comparison)
        relevance_rate = relevant_results / total_queries if total_queries > 0 else 0
        assert relevance_rate >= 0.5, f"Relevance rate {relevance_rate:.0%} below 50% threshold"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

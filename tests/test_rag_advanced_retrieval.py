"""Unit tests for QueryRewriter and ParentChildRetriever advanced RAG modules."""

from __future__ import annotations

from src.rag.parent_child_retriever import ParentChildRetriever
from src.rag.query_rewriter import QueryRewriter


def test_query_rewriter_expands_abbreviations():
    """Verify QueryRewriter expands technical terms like IC and 1256."""
    rewriter = QueryRewriter()
    res = rewriter.rewrite("IC exit rules for XSP 1256 tax optimization")
    assert "iron condor" in res.expanded_query
    assert "section 1256" in res.expanded_query
    assert "XSP" in res.extracted_tickers


def test_parent_child_retriever_chunking_and_resolution():
    """Verify ParentChildRetriever breaks documents into small chunks and resolves parent context."""
    retriever = ParentChildRetriever(chunk_size_chars=100)
    content = (
        "Line 1: SPY iron condor exit rule.\n"
        "Line 2: Take profit at 50% max credit.\n"
        "Line 3: Hard stop loss at 200% credit.\n"
        "Line 4: Always exit by 7 DTE."
    )
    retriever.add_document("LL-268", "Iron Condor Rules", content, {"severity": "HIGH"})
    assert len(retriever.children) > 1
    parents = retriever.retrieve_parent_context(["LL-268"])
    assert len(parents) == 1
    assert parents[0].parent_title == "Iron Condor Rules"
    assert "Hard stop loss" in parents[0].full_parent_content

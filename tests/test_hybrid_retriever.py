import pytest
from src.rag.query_rewriter import RAGQueryRewriter
from src.rag.hybrid_retriever import HybridRAGRetriever
from src.rag.parent_child_retriever import ParentChildRetriever


def test_query_rewriter_expansion():
    rewriter = RAGQueryRewriter()
    exp = rewriter.rewrite("put credit spread rules")

    assert exp.original_query == "put credit spread rules"
    assert "short put spread" in exp.expanded_query
    assert len(exp.synonyms_added) > 0


def test_hybrid_rrf_merging():
    retriever = HybridRAGRetriever(k_rrf=60.0)

    vec_results = [
        {"id": "LL-323", "title": "Iron Condor Management", "score": 0.95},
        {"id": "LL-301", "title": "IC Position Management", "score": 0.85},
    ]
    bm25_results = [
        {"id": "LL-301", "title": "IC Position Management", "score": 12.4},
        {"id": "LL-268", "title": "Iron Condor Win Rate", "score": 10.1},
    ]

    merged = retriever.rrf_merge(vec_results, bm25_results, top_n=3)

    assert len(merged) == 3
    # LL-301 appeared in both lists, so its RRF score should be highest
    assert merged[0].lesson_id == "LL-301"
    assert merged[0].vector_rank == 2
    assert merged[0].bm25_rank == 1


def test_parent_child_context_expansion():
    parent_store = {"LL-323": "FULL PARENT DOCUMENT CONTENT FOR LESSON 323"}
    retriever = ParentChildRetriever(parent_store=parent_store)

    child_match = {"id": "chunk_323_1", "parent_id": "LL-323", "title": "IC Study"}
    context = retriever.expand_child_to_parent(child_match)

    assert context.child_chunk_id == "chunk_323_1"
    assert context.parent_lesson_id == "LL-323"
    assert "FULL PARENT DOCUMENT" in context.full_parent_content

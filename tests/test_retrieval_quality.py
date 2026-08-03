"""Tests for retrieval quality stack."""

from __future__ import annotations

from src.rag.retrieval_quality import (
    QualityRetriever,
    apply_metadata_filters,
    header_aware_chunks,
    rrf_fuse,
)


def test_header_aware_chunks_split_on_headers():
    body = """# Title
intro text

## Prevention
do not skip inventory audit

## Root cause
orphan legs
"""
    chunks = header_aware_chunks("LL-1", "Title", body, max_chars=200)
    assert len(chunks) >= 2
    sections = {c.section for c in chunks}
    assert any("Prevention" in s for s in sections)


def test_rrf_fuse_prefers_agreement():
    a = [{"id": "x", "score": 1.0}, {"id": "y", "score": 0.5}]
    b = [{"id": "x", "score": 0.9}, {"id": "z", "score": 0.8}]
    fused = rrf_fuse([a, b], top_n=3)
    assert fused[0]["id"] == "x"


def test_metadata_filter_severity():
    rows = [
        {"id": "1", "severity": "LOW", "content": "a"},
        {"id": "2", "severity": "CRITICAL", "content": "b"},
    ]
    out = apply_metadata_filters(rows, min_severity="HIGH")
    assert len(out) == 1
    assert out[0]["id"] == "2"


def test_quality_retriever_parent_child_expand():
    lessons = [
        {
            "lesson_id": "LL-TEST-PC",
            "title": "Stop loss failure",
            "severity": "CRITICAL",
            "content": (
                "# Stop loss failure\n**Severity**: CRITICAL\n\n"
                "## Prevention\nAlways set 200% credit stop on put credit.\n\n"
                "## Root cause\nNo stop attached.\n"
            ),
        }
    ]
    qr = QualityRetriever(pipeline=None)
    n = qr.index_parents(lessons)
    assert n >= 1
    hits = qr.retrieve("put credit stop loss", top_k=3, use_vector=False)
    assert hits
    assert hits[0].lesson_id == "LL-TEST-PC"
    assert "stop" in hits[0].snippet.lower() or "prevention" in hits[0].snippet.lower()

"""Tests for trading defended RAG pipeline (retrieve_for_trade)."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.rag.cross_encoder_rerank import rerank_candidates
from src.rag.feedback_quality import assess_promotion_quality, build_lesson_payload
from src.rag.lesson_store import (
    connect,
    count_lessons,
    ensure_index,
    parse_markdown_lesson,
    search_fts,
)
from src.rag.pragmatic_hybrid import (
    bigram_jaccard,
    build_query_variants,
    pragmatic_hybrid_search,
    score_relevance,
    text_bigrams,
)
from src.rag.retrieve_for_trade import (
    resolve_query_plan,
    retrieve_for_trade,
)


@pytest.fixture()
def tmp_db(tmp_path: Path) -> Path:
    return tmp_path / "lessons.sqlite"


@pytest.fixture()
def knowledge_dir(tmp_path: Path) -> Path:
    d = tmp_path / "lessons"
    d.mkdir()
    (d / "LL-999_force_lot_rule.md").write_text(
        """# LL-999 Force Lot Rule

**Severity**: CRITICAL

## What Happened
Opened a 50-lot SPY iron condor violating the 1-lot controlled experiment.

## Prevention
Enforce MAX_LOT_SIZE=1 for all SPY options entries in trade_gateway.

## Tags
`spy`, `position-sizing`, `critical`
""",
        encoding="utf-8",
    )
    (d / "LL-998_tax_xsp.md").write_text(
        """# LL-998 XSP Tax Notes

**Severity**: MEDIUM

## What Happened
Research on section 1256 tax treatment for XSP vs SPY.

## Prevention
Prefer XSP when tax optimization is the goal; SPY remains validation vehicle.

## Tags
`tax`, `xsp`
""",
        encoding="utf-8",
    )
    return d


def test_fts5_backfill_and_search(tmp_db: Path, knowledge_dir: Path):
    stats = ensure_index(tmp_db, knowledge_dir, force=True)
    assert stats["count"] >= 2
    conn = connect(tmp_db)
    try:
        assert count_lessons(conn) >= 2
        hits = search_fts(conn, "position sizing lot size SPY", limit=5)
        assert hits
        assert any("999" in h["id"] or "lot" in h["content"].lower() for h in hits)
    finally:
        conn.close()


def test_bigram_jaccard_and_score_relevance(knowledge_dir: Path):
    path = knowledge_dir / "LL-999_force_lot_rule.md"
    lesson = parse_markdown_lesson(path)
    assert lesson is not None
    doc = {
        "id": lesson.id,
        "title": lesson.title,
        "content": lesson.content,
        "severity": lesson.severity,
        "prevention": lesson.prevention,
        "tags": lesson.tags,
    }
    a = text_bigrams("force lot size spy")
    b = text_bigrams(lesson.content[:500].lower())
    assert bigram_jaccard(a, b) > 0
    assert score_relevance(doc, "SPY position sizing 1-lot violation") > 0.1


def test_multi_query_only_when_weak():
    strong = resolve_query_plan("iron condor exit 7 dte", top_lexical=0.85)
    assert strong["rewrite_applied"] is False
    assert len(strong["variants"]) == 1

    weak = resolve_query_plan("force push secrets lot size", top_lexical=0.2)
    assert weak["rewrite_applied"] is True
    assert 1 < len(weak["variants"]) <= 3


def test_pragmatic_hybrid_ranks_sizing_lesson(knowledge_dir: Path):
    docs = []
    for path in knowledge_dir.glob("*.md"):
        lesson = parse_markdown_lesson(path)
        assert lesson
        docs.append(
            {
                "id": lesson.id,
                "title": lesson.title,
                "content": lesson.content,
                "severity": lesson.severity,
                "prevention": lesson.prevention,
                "tags": lesson.tags,
            }
        )
    out = pragmatic_hybrid_search(
        docs,
        "SPY iron condor lot size violation 50-lot",
        query_variants=build_query_variants("SPY lot size violation"),
        top_k=3,
    )
    assert out["results"]
    assert "999" in out["results"][0]["id"]


def test_heuristic_rerank_boosts_match():
    cands = [
        {
            "id": "a",
            "title": "tax notes",
            "content": "section 1256 xsp",
            "score": 0.4,
        },
        {
            "id": "b",
            "title": "lot size disaster",
            "content": "never open 50-lot SPY iron condor; enforce 1-lot",
            "score": 0.35,
        },
    ]
    ranked = rerank_candidates(
        "SPY lot size iron condor disaster",
        cands,
        top_k=2,
        use_llm=False,
    )
    assert ranked[0]["id"] == "b"
    assert ranked[0]["reranker"]["stages"]
    assert "pairwise-heuristic" in ranked[0]["reranker"]["stages"]
    assert ranked[0]["crossEncoderScore"] is None


def test_feedback_quality_blocks_bare_thumbs():
    d = assess_promotion_quality(signal="negative", context="thumbs down")
    assert d.promotable is False
    assert build_lesson_payload(signal="negative", context="bad") is None


def test_feedback_quality_promotes_specific():
    d = assess_promotion_quality(
        signal="negative",
        context="SPY put credit entry",
        what_went_wrong="Opened 10-lot structure against the 1-lot rule",
        what_to_change="Reject lot size greater than 1 in trade_gateway before submit",
    )
    assert d.promotable is True
    payload = build_lesson_payload(
        signal="negative",
        context="SPY put credit entry",
        what_went_wrong="Opened 10-lot structure against the 1-lot rule",
        what_to_change="Reject lot size greater than 1 in trade_gateway before submit",
    )
    assert payload is not None
    assert "1-lot" in payload["content"] or "1-lot" in payload["prevention"]


def test_capture_and_store_and_retrieve(tmp_db: Path, tmp_path: Path, monkeypatch):
    import src.rag.retrieve_for_trade as rft_mod

    kd = tmp_path / "md"
    kd.mkdir()
    monkeypatch.setattr(rft_mod, "KNOWLEDGE_DIR", kd)

    result = rft_mod.capture_and_store_feedback(
        signal="negative",
        context="SPY put credit validation",
        what_went_wrong="Skipped inventory audit before opening risk",
        what_to_change="Run audit_open_inventory.py and require clean book before new risk",
        tags=["inventory", "spy"],
        db_path=tmp_db,
        also_write_markdown=True,
    )
    assert result["promoted"] is True
    assert result["lesson_id"]

    out = rft_mod.retrieve_for_trade(
        "unclean inventory before new risk SPY",
        top_k=5,
        db_path=tmp_db,
        knowledge_dir=kd,
        ensure_fts=True,
        use_llm_rerank=False,
    )
    assert out.lessons
    ctx = rft_mod.assemble_trade_context(out.lessons, meta=out.meta, action="open put credit")
    assert "Trading RAG defended retrieval" in ctx
    assert out.lessons[0].get("id")


def test_retrieve_for_trade_end_to_end(tmp_db: Path, knowledge_dir: Path):
    ensure_index(tmp_db, knowledge_dir, force=True)
    out = retrieve_for_trade(
        "SPY position sizing 50-lot iron condor violation",
        top_k=3,
        db_path=tmp_db,
        knowledge_dir=knowledge_dir,
        ensure_fts=False,
        use_llm_rerank=False,
    )
    assert out.lessons
    assert out.meta.get("top_lexical") is not None
    ids = " ".join(str(x.get("id")) for x in out.lessons)
    assert "999" in ids
    # multi-query meta present
    assert "variants" in out.meta or "query_variants" in (out.meta.get("hybrid") or {})


def test_defended_path_retrieves_sizing_lesson(tmp_db: Path, knowledge_dir: Path):
    ensure_index(tmp_db, knowledge_dir, force=True)
    res = retrieve_for_trade(
        "lot size violation SPY",
        top_k=3,
        db_path=tmp_db,
        knowledge_dir=knowledge_dir,
        ensure_fts=False,
        use_llm_rerank=False,
    )
    assert res.lessons
    assert any("999" in str(x.get("id")) for x in res.lessons)

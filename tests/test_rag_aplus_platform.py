"""A+ platform unit tests: ACL, chunking, observability, answer eval, facade."""

from __future__ import annotations

from pathlib import Path


from src.rag.acl import (
    DocSensitivity,
    Principal,
    filter_documents,
    infer_sensitivity,
    is_allowed,
)
from src.rag.answer_evaluation import RAGAnswerEvaluator
from src.rag.chunking import chunk_document
from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline
from src.rag.embedding_backend import EmbeddingBackend, cosine_similarity, normalize_domain_text
from src.rag.observability import emit_trace, finish_trace, new_trace, summarize_traces
from src.rag.platform import TradingRAGPlatform
from src.rag.retrieve_for_trade import retrieve_for_trade


def test_chunk_strategies_nonempty():
    text = "# Title\n\n## Section A\nRisk rule one.\n\n## Section B\n" + ("detail " * 200)
    for strategy in ("fixed", "recursive", "semantic", "hierarchical", "late"):
        chunks = chunk_document(text, strategy=strategy)
        assert chunks, strategy
        assert all(c.text.strip() for c in chunks)


def test_hierarchical_has_parent_child():
    text = "# Parent\n\n## Child section\n" + ("body text. " * 100)
    chunks = chunk_document(text, strategy="hierarchical")
    parents = [c for c in chunks if c.level == 1]
    children = [c for c in chunks if c.level == 0]
    assert parents
    assert children
    assert any(c.parent_id for c in children)


def test_late_has_doc_anchor():
    text = "# A\n\n# B\n\n" + ("content " * 80)
    chunks = chunk_document(text, strategy="late")
    assert any(c.level == 2 for c in chunks)


def test_acl_live_excludes_paper_and_restricted():
    live = Principal.live_trader()
    assert not is_allowed(live, DocSensitivity.PAPER_ONLY)
    assert not is_allowed(live, DocSensitivity.LIVE_RESTRICTED)
    assert is_allowed(live, DocSensitivity.RISK_CRITICAL)
    assert is_allowed(Principal.admin(), DocSensitivity.LIVE_RESTRICTED)


def test_infer_sensitivity_risk_critical():
    sens = infer_sensitivity(severity="CRITICAL", text="kill switch and stop loss")
    assert sens == DocSensitivity.RISK_CRITICAL


def test_filter_documents_acl():
    docs = [
        {"id": "1", "sensitivity": "paper_only"},
        {"id": "2", "sensitivity": "operator"},
        {"id": "3", "sensitivity": "live_restricted"},
    ]
    out = filter_documents(docs, Principal.live_trader())
    assert {d["id"] for d in out} == {"2"}


def test_ingest_attaches_chunks_and_sensitivity(tmp_path: Path):
    md = tmp_path / "LL-888-stop.md"
    md.write_text(
        "# CRITICAL: Stop Loss\n\n**Severity**: CRITICAL\n\n## Prevention\n"
        "Close at 200% of credit. Never average down on a loser.\n",
        encoding="utf-8",
    )
    pipe = DocumentIngestionPipeline(manifest_file=tmp_path / "m.json")
    doc = pipe.ingest_file(md)
    assert doc.chunks
    assert doc.metadata.get("sensitivity")
    assert doc.metadata.get("chunk_count", 0) >= 1


def test_embedding_domain_aliases_and_cosine():
    left = normalize_domain_text("IC stop-loss")
    assert "iron condor" in left.lower() or "maximum loss" in left.lower()
    backend = EmbeddingBackend(backend="feature-hash")
    a = backend.encode_passages(["spy put credit stop"])[0]
    b = backend.encode_query("spy put credit stop")
    assert cosine_similarity(a, b) > 0.5


def test_answer_eval_rejects_unfaithful_profit_claim():
    evalr = RAGAnswerEvaluator(
        embedding_backend=EmbeddingBackend(backend="feature-hash"),
        quality_threshold=0.8,
    )
    score = evalr.evaluate(
        query="profit?",
        answer="Guarantees $6000/month forever with no risk.",
        contexts=[{"id": "x", "content": "No completed cohort. Do not project returns."}],
    )
    assert score.passed is False


def test_observability_trace_roundtrip(tmp_path: Path):
    import time

    path = tmp_path / "traces.jsonl"
    tr = new_trace("test query", principal="operator")
    t0 = time.perf_counter()
    tr.strategy = "fts+hybrid+acl"
    tr.top_ids = ["LL-1"]
    finish_trace(tr, t0=t0)
    emit_trace(tr, path=path)
    summary = summarize_traces(path)
    assert summary["count"] == 1
    assert summary["avg_latency_ms"] >= 0


def test_platform_scorecard_architecture_a_plus():
    platform = TradingRAGPlatform()
    card = platform.scorecard(run_eval=False)
    assert card.architecture_score_10 >= 9.5
    assert card.architecture_grade in {"A+", "A"}
    assert all(card.capabilities.values())


def test_retrieve_for_trade_meta_includes_acl_and_trace(tmp_path: Path):
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    (lessons / "LL-777_put_credit_stop.md").write_text(
        "# CRITICAL: Put Credit Stop\n\n**Severity**: CRITICAL\n\n"
        "## Prevention\nExit at 200% of credit on spy put credit spreads.\n",
        encoding="utf-8",
    )
    result = retrieve_for_trade(
        "spy put credit stop loss 200 percent",
        knowledge_dir=lessons,
        ensure_fts=False,
        top_k=3,
        principal=Principal.operator(),
    )
    assert "acl" in str(result.meta.get("path") or "")
    assert result.meta.get("trace_id")
    assert "acl_dropped" in result.meta


def test_retrieve_live_principal_drops_paper_only(tmp_path: Path):
    lessons = tmp_path / "lessons"
    lessons.mkdir()
    (lessons / "LL-paper_only_note.md").write_text(
        "# LOW: paper validation cohort notes\n\n**Severity**: LOW\n\n"
        "paper only validation cohort notes for lab.\n",
        encoding="utf-8",
    )
    (lessons / "LL-risk_stop.md").write_text(
        "# CRITICAL: kill switch and stop loss\n\n**Severity**: CRITICAL\n\n"
        "kill switch halt inventory never bypass stop loss.\n",
        encoding="utf-8",
    )
    result = retrieve_for_trade(
        "stop loss kill switch",
        knowledge_dir=lessons,
        ensure_fts=False,
        top_k=5,
        principal=Principal.live_trader(),
        ood_min_score=0.0,
    )
    # Live may still retrieve risk_critical; paper_only should be filtered
    for lesson in result.lessons:
        assert lesson.get("sensitivity") != "paper_only"
        assert lesson.get("sensitivity") != "live_restricted"

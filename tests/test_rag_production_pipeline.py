from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from fastapi.testclient import TestClient

from src.rag.rag_pipeline import (
    RAGEReranker,
    SQLiteFTS5Store,
    TradingRAGPipeline,
    chunk_markdown,
    extract_severity,
    normalize_document_text,
    parse_lesson_markdown,
)


def test_legacy_severity_forms_are_normalized() -> None:
    assert extract_severity("**Severity:** HIGH") == "HIGH"
    assert extract_severity("## Severity: **CRITICAL**") == "CRITICAL"
    assert extract_severity("**Severity:** P0 - System Breaking") == "CRITICAL"
    assert extract_severity("**Severity**: PROCESS") == "LOW"
    assert extract_severity("**Severity: 5 (system outage)**") == "CRITICAL"


def _lesson(
    title: str = "Position Sizing Failure",
    *,
    severity: str = "HIGH",
    prevention: str = "Never risk more than two percent of the portfolio on one trade.",
    body: str = "The prior tool call accumulated too much defined risk in one expiry.",
    tags: str = "`risk` `position-sizing`",
) -> str:
    return (
        f"# {severity}: {title}\n\n"
        f"**Severity**: {severity}\n\n"
        f"## What Happened\n{body}\n\n"
        f"## Prevention\n{prevention}\n\n"
        f"## Tags\n{tags}\n"
    )


def _pipeline(tmp_path: Path) -> TradingRAGPipeline:
    lessons_dir = tmp_path / "lessons"
    lessons_dir.mkdir()
    (lessons_dir / "ll-001_position_sizing.md").write_text(_lesson(), encoding="utf-8")
    (lessons_dir / "ll-002_exit_rule.md").write_text(
        _lesson(
            "Iron Condor Exit Rule",
            severity="CRITICAL",
            prevention="Close the complete structure atomically before the exit deadline.",
            body="A partial close left an uncovered short option and created assignment risk.",
            tags="`risk` `atomic-exit`",
        ),
        encoding="utf-8",
    )
    pipeline = TradingRAGPipeline(db_path=tmp_path / "rag.db", lessons_dir=lessons_dir)
    pipeline.sync_markdown_dir(lessons_dir)
    return pipeline


def test_normalization_preserves_structure_and_redacts_secrets() -> None:
    normalized, redactions = normalize_document_text(
        "# Incident\r\n\r\napi_key = sk-abcdefghijklmnopqrstuvwxyz123456\r\n\r\n## Prevention\r\nRotate safely."
    )
    assert "## Prevention\n" in normalized
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in normalized
    assert redactions == 1


def test_section_chunking_is_bounded_and_keeps_headings() -> None:
    content = (
        "# Root\n\n"
        + ("Sentence about risk controls. " * 100)
        + "\n\n## Prevention\n"
        + ("Close atomically. " * 100)
    )
    chunks = chunk_markdown(content, max_chars=400, overlap_chars=40)
    assert len(chunks) > 2
    assert all(len(chunk) <= 410 for _, chunk in chunks)
    assert {title for title, _ in chunks} >= {"Root", "Prevention"}


def test_store_is_idempotent_and_versions_updates(tmp_path: Path) -> None:
    store = SQLiteFTS5Store(tmp_path / "store.db")
    first = parse_lesson_markdown(_lesson(), lesson_id="ll-001")
    status_one, chunks_one = store.put(first)
    status_two, chunks_two = store.put(first)
    changed = parse_lesson_markdown(
        _lesson(body="A materially different failure happened during a volatile session."),
        lesson_id="ll-001",
    )
    status_three, chunks_three = store.put(changed)
    row = store.get_by_id("ll-001")
    assert (status_one, status_two, status_three) == ("inserted", "unchanged", "updated")
    assert chunks_one > 0 and chunks_two == 0 and chunks_three > 0
    assert row is not None and row["version"] == 2
    assert store.chunk_count() >= 1
    store.close()


def test_directory_sync_tombstones_deleted_sources(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    source = pipeline.lessons_dir
    assert source is not None
    for file_path in source.glob("*.md"):
        file_path.unlink()
    report = pipeline.sync_markdown_dir(source, delete_missing=True)
    assert report.deleted == 2
    assert pipeline.store.count() == 0
    assert pipeline.store.chunk_count() == 0
    pipeline.close()


def test_feedback_capture_is_idempotent_and_searchable(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    kwargs = {
        "feedback_text": "The proposed close action omitted one long protection leg.",
        "prevention": "Require an atomic four-leg close and verify every contract identifier.",
        "tool_name": "submit_order",
        "severity": "CRITICAL",
        "event_id": "evt-1234",
        "tool_context": {"symbol": "SPY", "credential": "sk-abcdefghijklmnopqrstuvwxyz123456"},
    }
    first, first_detail = pipeline.capture_thumbs_down(**kwargs)
    second, second_detail = pipeline.capture_thumbs_down(**kwargs)
    assert first and second
    assert "Inserted" in first_detail and "Unchanged" in second_detail
    row = pipeline.store.get_by_id("feedback-evt-1234")
    assert row is not None
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in row["content"]
    assert pipeline.query("omitted protection leg atomic close", top_k=5)
    pipeline.close()


def test_metadata_filters_apply_before_ranking(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    critical = pipeline.query("iron condor exit rule", severity_filter="CRITICAL")
    high = pipeline.query("position sizing risk", severity_filter="HIGH")
    tagged = pipeline.query("position sizing risk", tag_filter="position-sizing")
    assert critical and all(item["severity"] == "CRITICAL" for item in critical)
    assert high and all(item["severity"] == "HIGH" for item in high)
    assert tagged and all("position" in item["title"].lower() for item in tagged)
    pipeline.close()


def test_ood_rejection_and_conditional_multiquery_are_observable(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    assert pipeline.query("banana bread temperature and frosting", top_k=5) == []
    assert pipeline.last_query_trace is not None
    assert pipeline.last_query_trace.variant_count >= 1
    assert pipeline.query("iron condor", top_k=5)
    assert pipeline.last_query_trace is not None
    assert pipeline.last_query_trace.variant_count == 1
    pipeline.close()


def test_reranker_validates_ids_and_deduplicates() -> None:
    validated = RAGEReranker._validate_ranked_ids(
        ["ll-2", "invented", "ll-2", "ll-1"], ["ll-1", "ll-2"]
    )
    assert validated == ["ll-2", "ll-1"]


def test_context_is_bounded_cited_and_marks_untrusted_data(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    results = pipeline.search("iron condor exit assignment", top_k=5)
    context = pipeline.assemble_context(results, max_chars=2_000)
    assert len(context) <= 2_500
    assert "untrusted data" in context
    assert "ll-002_exit_rule" in context
    pipeline.close()


def test_high_risk_tool_gate_fails_closed_when_index_not_ready(tmp_path: Path) -> None:
    pipeline = TradingRAGPipeline(db_path=tmp_path / "empty.db")
    decision, context = pipeline.gate_tool_call("submit_order", {"symbol": "SPY"})
    assert decision.approved is False
    assert decision.reason_code == "RAG_NOT_READY"
    assert "No relevant lessons" not in context
    pipeline.close()


def test_query_cache_metrics_and_health(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    warmup = pipeline.warmup()
    first = pipeline.query("position sizing risk", top_k=3)
    second = pipeline.query("position sizing risk", top_k=3)
    snapshot = pipeline.metrics_snapshot()
    assert first == second
    assert snapshot["queries_total"] == 2
    assert snapshot["cache_hits_total"] == 1
    assert snapshot["latency_p95_ms"] >= 0
    assert snapshot["health"]["ready"] is True
    assert snapshot["health"]["documents"] == 2
    assert snapshot["health"]["chunks"] >= 2
    assert warmup["embedding_index_ready"] is True
    assert snapshot["health"]["embedding_index_ready"] is True
    pipeline.close()


def test_concurrent_reads_are_consistent(tmp_path: Path) -> None:
    pipeline = _pipeline(tmp_path)
    with ThreadPoolExecutor(max_workers=8) as executor:
        batches = list(
            executor.map(lambda _: pipeline.query("position sizing", top_k=2), range(32))
        )
    assert all(batch == batches[0] for batch in batches)
    pipeline.close()


def test_service_contract_auth_validation_and_metrics(tmp_path: Path, monkeypatch) -> None:
    pipeline = _pipeline(tmp_path)
    monkeypatch.setenv("RAG_SERVICE_TOKEN", "test-token")
    monkeypatch.setattr("src.rag.service.get_trading_rag_pipeline", lambda: pipeline)
    from src.rag.service import app

    client = TestClient(app)
    assert client.get("/health/live").status_code == 200
    assert client.post("/v1/search", json={"query": "position sizing"}).status_code == 401
    response = client.post(
        "/v1/search",
        headers={"Authorization": "Bearer test-token"},
        json={"query": "position sizing", "top_k": 3},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["results"]
    assert len(payload["query_hash"]) == 16
    invalid = client.post(
        "/v1/search",
        headers={"Authorization": "Bearer test-token"},
        json={"query": "position sizing", "unknown": True},
    )
    assert invalid.status_code == 422
    metrics = client.get("/metrics", headers={"Authorization": "Bearer test-token"})
    assert metrics.status_code == 200
    assert "trading_rag_ready 1" in metrics.text
    pipeline.close()

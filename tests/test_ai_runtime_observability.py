from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.observability.ai_runtime import AIRuntimeTelemetry
from src.observability.opentelemetry_tracer import AgentTracer


def test_llm_operation_records_route_usage_and_trace_correlation(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")
    runtime = AIRuntimeTelemetry(tracer)

    with runtime.operation(
        "market_analysis",
        "llm",
        session_id="desk-session",
        trace_id="trace-123",
        model_name="claude-3-haiku",
        attributes={"provider": "anthropic", "route": "direct"},
    ) as operation:
        operation.annotate(schema_name="MarketAnalysis", schema_valid=True)
        operation.set_usage(prompt_tokens=120, completion_tokens=30)

    assert len(tracer.spans) == 1
    span = tracer.spans[0]
    assert span.attributes["trace_id"] == "trace-123"
    assert span.attributes["provider"] == "anthropic"
    assert span.attributes["schema_valid"] is True
    assert span.prompt_tokens == 120
    assert span.completion_tokens == 30


def test_runtime_exception_is_traced_without_swallowing_it(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")
    runtime = AIRuntimeTelemetry(tracer)

    with pytest.raises(RuntimeError, match="provider timeout"):
        with runtime.operation(
            "market_analysis",
            "llm",
            session_id="desk-session",
            model_name="model",
        ):
            raise RuntimeError("provider timeout")

    assert tracer.spans[0].status == "error"
    assert tracer.spans[0].attributes["error_type"] == "RuntimeError"


def test_retrieval_abstention_records_scores_versions_and_acl_metadata(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")
    runtime = AIRuntimeTelemetry(tracer)

    with runtime.operation(
        "lesson_retrieval",
        "retrieval",
        session_id="desk-session",
        attributes={
            "tenant_id": "operator",
            "acl_decision": "allow",
            "index_version": "sha256:abc",
        },
    ) as operation:
        operation.annotate(
            result_count=0,
            lexical_top_score=0.02,
            dense_top_score=0.01,
            cache_hit=False,
        )
        operation.abstain("retrieval_miss")

    persisted = json.loads((tmp_path / "spans.jsonl").read_text(encoding="utf-8"))
    assert persisted["status"] == "abstain"
    assert persisted["attributes"]["abstain_reason"] == "retrieval_miss"
    assert persisted["attributes"]["acl_decision"] == "allow"
    assert persisted["attributes"]["result_count"] == 0


def test_finished_operation_cannot_emit_a_duplicate_span(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")
    operation = AIRuntimeTelemetry(tracer).operation(
        "schema_validation",
        "validation",
        session_id="desk-session",
    )

    operation.finish()
    with pytest.raises(RuntimeError, match="already finished"):
        operation.finish()

    assert len(tracer.spans) == 1

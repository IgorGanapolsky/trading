"""Unit tests for AgentTracer."""

from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from src.observability.opentelemetry_tracer import AgentTracer, get_agent_tracer


def test_cost_computation() -> None:
    tracer = AgentTracer()
    cost = tracer.compute_cost("claude-3-5-sonnet", 1000, 1000)
    # $0.003 + $0.015 = 0.018
    assert cost == 0.018


def test_span_recording(tmp_path: Path) -> None:
    log_file = tmp_path / "spans.jsonl"
    tracer = AgentTracer(log_path=log_file)

    t0 = time.time()
    t1 = t0 + 0.5
    span = tracer.record_span(
        span_id="span_001",
        session_id="sess_123",
        name="llm_query",
        kind="llm",
        start_time=t0,
        end_time=t1,
        model_name="claude-3-5-sonnet",
        prompt_tokens=500,
        completion_tokens=200,
    )

    assert span.duration_ms >= 490.0
    assert span.total_cost_usd > 0
    assert log_file.exists()

    content = log_file.read_text(encoding="utf-8").strip()
    data = json.loads(content)
    assert data["span_id"] == "span_001"
    assert data["session_id"] == "sess_123"
    assert data["kind"] == "llm"
    assert data["schema_version"] == "ai-runtime-span/1"
    assert data["model_name"] == "claude-3-5-sonnet"


def test_global_tracer() -> None:
    t1 = get_agent_tracer()
    t2 = get_agent_tracer()
    assert t1 is t2


def test_secret_and_content_attributes_are_redacted(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")

    span = tracer.record_span(
        span_id="redaction",
        session_id="session",
        name="safe_llm_call",
        kind="llm",
        start_time=1.0,
        end_time=2.0,
        attributes={
            "api_key": "secret-value",
            "prompt": "private strategy prompt",
            "system_prompt": "more private strategy prompt",
            "access_token": "token-value",
            "response_body": "private model response",
            "route": "openrouter",
            "nested": {"authorization": "Bearer secret"},
        },
    )

    assert span.attributes["api_key"] == "[REDACTED]"
    assert span.attributes["prompt"] == "[REDACTED]"
    assert span.attributes["system_prompt"] == "[REDACTED]"
    assert span.attributes["access_token"] == "[REDACTED]"
    assert span.attributes["response_body"] == "[REDACTED]"
    assert span.attributes["route"] == "openrouter"
    assert span.attributes["nested"]["authorization"] == "[REDACTED]"
    persisted = (tmp_path / "spans.jsonl").read_text(encoding="utf-8")
    assert "secret-value" not in persisted
    assert "private strategy prompt" not in persisted
    assert "token-value" not in persisted
    assert "private model response" not in persisted


def test_invalid_span_data_is_rejected(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")

    with pytest.raises(ValueError, match="unsupported span kind"):
        tracer.record_span(
            span_id="bad",
            session_id="session",
            name="bad",
            kind="unknown",
            start_time=1.0,
            end_time=2.0,
        )

    with pytest.raises(ValueError, match="non-negative"):
        tracer.compute_cost("default", -1, 0)


def test_persistence_failure_is_observable(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("block", encoding="utf-8")
    tracer = AgentTracer(log_path=blocker / "spans.jsonl")

    tracer.record_span(
        span_id="write-failure",
        session_id="session",
        name="llm_call",
        kind="llm",
        start_time=1.0,
        end_time=2.0,
    )

    snapshot = tracer.snapshot()
    assert snapshot.persistence_healthy is False
    assert snapshot.dropped_spans == 1
    assert snapshot.last_write_error is not None


def test_snapshot_aggregates_runtime_health(tmp_path: Path) -> None:
    tracer = AgentTracer(log_path=tmp_path / "spans.jsonl")
    tracer.record_span(
        span_id="one",
        session_id="session",
        name="llm_call",
        kind="llm",
        start_time=1.0,
        end_time=1.1,
        prompt_tokens=100,
        completion_tokens=20,
        status="error",
    )
    tracer.record_span(
        span_id="two",
        session_id="session",
        name="retrieval",
        kind="retrieval",
        start_time=2.0,
        end_time=2.2,
        status="abstain",
    )

    snapshot = tracer.snapshot()
    assert snapshot.span_count == 2
    assert snapshot.error_count == 1
    assert snapshot.abstain_count == 1
    assert snapshot.prompt_tokens == 100
    assert snapshot.completion_tokens == 20
    assert snapshot.average_latency_ms == 150.0
    assert snapshot.persistence_healthy is True

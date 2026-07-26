"""Unit tests for AgentTracer."""

from __future__ import annotations

import json
import time
from pathlib import Path
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


def test_global_tracer() -> None:
    t1 = get_agent_tracer()
    t2 = get_agent_tracer()
    assert t1 is t2

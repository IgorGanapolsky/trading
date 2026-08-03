"""
OpenTelemetry-Compatible Agent Tracing & Token Cost Monitor.

Collects structured spans, latency, token consumption, and model pricing costs
for multi-turn LLM agent sessions and tool executions. Writes to JSONL log files.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

MODEL_PRICING_PER_1K: dict[str, dict[str, float]] = {
    "claude-3-5-sonnet": {"input": 0.003, "output": 0.015},
    "claude-3-opus": {"input": 0.015, "output": 0.075},
    "claude-3-haiku": {"input": 0.00025, "output": 0.00125},
    "gpt-4o": {"input": 0.0025, "output": 0.010},
    "default": {"input": 0.003, "output": 0.015},
}


@dataclass
class SpanEvent:
    span_id: str
    parent_span_id: Optional[str]
    session_id: str
    name: str
    kind: str  # "llm", "tool", "workflow"
    start_time: float
    end_time: float
    duration_ms: float
    status: str  # "ok", "error"
    attributes: dict[str, Any] = field(default_factory=dict)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_cost_usd: float = 0.0


class AgentTracer:
    """OpenTelemetry-compatible tracer for multi-turn agent telemetry."""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = log_path or (Path.cwd() / ".claude" / "logs" / "opentelemetry_spans.jsonl")
        self.spans: list[SpanEvent] = []

    def compute_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = MODEL_PRICING_PER_1K.get(model_name.lower()) or MODEL_PRICING_PER_1K["default"]
        input_cost = (prompt_tokens / 1000.0) * pricing["input"]
        output_cost = (completion_tokens / 1000.0) * pricing["output"]
        return round(input_cost + output_cost, 6)

    def record_span(
        self,
        span_id: str,
        session_id: str,
        name: str,
        kind: str,
        start_time: float,
        end_time: float,
        status: str = "ok",
        parent_span_id: Optional[str] = None,
        attributes: Optional[dict[str, Any]] = None,
        model_name: str = "default",
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> SpanEvent:
        duration_ms = round((end_time - start_time) * 1000.0, 2)
        cost = self.compute_cost(model_name, prompt_tokens, completion_tokens)

        span = SpanEvent(
            span_id=span_id,
            parent_span_id=parent_span_id,
            session_id=session_id,
            name=name,
            kind=kind,
            start_time=start_time,
            end_time=end_time,
            duration_ms=duration_ms,
            status=status,
            attributes=attributes or {},
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=cost,
        )

        self.spans.append(span)
        self._write_span(span)
        return span

    def _write_span(self, span: SpanEvent) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(asdict(span)) + "\n")
        except OSError:
            pass


_GLOBAL_TRACER = AgentTracer()


def get_agent_tracer() -> AgentTracer:
    return _GLOBAL_TRACER

"""Secret-safe structured tracing for AI, retrieval, tool, and workflow operations.

The JSONL representation follows OpenTelemetry's span vocabulary but does not
claim to be an OTLP exporter. Callers can deterministically inspect persistence
health and dropped-span counts instead of receiving a false green when disk
writes fail.
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

SPAN_SCHEMA_VERSION = "ai-runtime-span/1"
_ALLOWED_KINDS = frozenset({"llm", "retrieval", "tool", "validation", "workflow"})
_ALLOWED_STATUSES = frozenset({"ok", "error", "abstain"})
_SENSITIVE_ATTRIBUTE_NAMES = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "password",
        "prompt",
        "request_body",
        "response",
        "response_body",
        "secret",
        "token",
    }
)
_SENSITIVE_ATTRIBUTE_FRAGMENTS = frozenset(
    {
        "authorization",
        "body",
        "content",
        "cookie",
        "credential",
        "header",
        "message",
        "password",
        "prompt",
        "request",
        "response",
        "secret",
        "token",
    }
)
_MAX_ATTRIBUTE_STRING_LENGTH = 512

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
    schema_version: str = SPAN_SCHEMA_VERSION
    model_name: str = "default"


@dataclass(frozen=True)
class TraceSnapshot:
    """Aggregate in-process telemetry for health checks and tests."""

    span_count: int
    error_count: int
    abstain_count: int
    prompt_tokens: int
    completion_tokens: int
    total_cost_usd: float
    average_latency_ms: float
    dropped_spans: int
    persistence_healthy: bool
    last_write_error: str | None


def _sanitize_attributes(value: Any, *, key: str | None = None) -> Any:
    """Return JSON-safe attributes without prompt, response, or credential data."""
    normalized_key = str(key or "").strip().lower().replace("-", "_").replace(".", "_")
    key_parts = frozenset(part for part in normalized_key.split("_") if part)
    if (
        normalized_key in _SENSITIVE_ATTRIBUTE_NAMES
        or normalized_key.endswith(("_api_key", "_password", "_secret"))
        or key_parts & _SENSITIVE_ATTRIBUTE_FRAGMENTS
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): _sanitize_attributes(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_sanitize_attributes(item) for item in value]
    if isinstance(value, str):
        if len(value) > _MAX_ATTRIBUTE_STRING_LENGTH:
            return f"{value[:_MAX_ATTRIBUTE_STRING_LENGTH]}...[truncated]"
        return value
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)[:_MAX_ATTRIBUTE_STRING_LENGTH]


class AgentTracer:
    """Thread-safe structured tracer with observable persistence failures."""

    def __init__(self, log_path: Optional[Path] = None) -> None:
        self.log_path = log_path or (Path.cwd() / ".claude" / "logs" / "opentelemetry_spans.jsonl")
        self.spans: list[SpanEvent] = []
        self._lock = threading.RLock()
        self.dropped_spans = 0
        self.last_write_error: str | None = None

    def compute_cost(self, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts must be non-negative")
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
        if kind not in _ALLOWED_KINDS:
            raise ValueError(f"unsupported span kind: {kind}")
        if status not in _ALLOWED_STATUSES:
            raise ValueError(f"unsupported span status: {status}")
        if end_time < start_time:
            raise ValueError("end_time must not precede start_time")
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
            attributes=_sanitize_attributes(attributes or {}),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_cost_usd=cost,
            model_name=model_name,
        )

        with self._lock:
            self.spans.append(span)
        self._write_span(span)
        return span

    @property
    def persistence_healthy(self) -> bool:
        return self.last_write_error is None

    def _write_span(self, span: SpanEvent) -> bool:
        try:
            with self._lock:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as file_handle:
                    file_handle.write(json.dumps(asdict(span), sort_keys=True) + "\n")
                self.last_write_error = None
            return True
        except OSError as exc:
            with self._lock:
                self.dropped_spans += 1
                self.last_write_error = f"{type(exc).__name__}: {exc}"
            logger.error("AI telemetry persistence failed: %s", exc)
            return False

    def snapshot(self) -> TraceSnapshot:
        with self._lock:
            spans = tuple(self.spans)
            latency_total = sum(span.duration_ms for span in spans)
            return TraceSnapshot(
                span_count=len(spans),
                error_count=sum(span.status == "error" for span in spans),
                abstain_count=sum(span.status == "abstain" for span in spans),
                prompt_tokens=sum(span.prompt_tokens for span in spans),
                completion_tokens=sum(span.completion_tokens for span in spans),
                total_cost_usd=round(sum(span.total_cost_usd for span in spans), 6),
                average_latency_ms=round(latency_total / len(spans), 2) if spans else 0.0,
                dropped_spans=self.dropped_spans,
                persistence_healthy=self.persistence_healthy,
                last_write_error=self.last_write_error,
            )


_GLOBAL_TRACER = AgentTracer()


def get_agent_tracer() -> AgentTracer:
    return _GLOBAL_TRACER

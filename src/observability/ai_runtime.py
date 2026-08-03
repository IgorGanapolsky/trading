"""Runtime telemetry facade for bounded AI and retrieval operations.

This module deliberately accepts metadata, token counts, and identifiers only.
It has no prompt or response parameters, which keeps sensitive content out of
the telemetry contract by construction.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.observability.opentelemetry_tracer import AgentTracer, SpanEvent, get_agent_tracer


@dataclass
class RuntimeOperation:
    """A single bounded runtime operation that emits exactly one span."""

    tracer: AgentTracer
    name: str
    kind: str
    session_id: str
    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    model_name: str = "default"
    attributes: dict[str, Any] = field(default_factory=dict)
    _start_time: float = field(default_factory=time.time, init=False)
    _prompt_tokens: int = field(default=0, init=False)
    _completion_tokens: int = field(default=0, init=False)
    _status: str = field(default="ok", init=False)
    _finished: bool = field(default=False, init=False)

    def annotate(self, **attributes: Any) -> RuntimeOperation:
        """Add non-content metadata such as scores, versions, and route names."""
        if self._finished:
            raise RuntimeError("cannot annotate a finished runtime operation")
        self.attributes.update(attributes)
        return self

    def set_usage(self, *, prompt_tokens: int, completion_tokens: int) -> RuntimeOperation:
        if prompt_tokens < 0 or completion_tokens < 0:
            raise ValueError("token counts must be non-negative")
        self._prompt_tokens = prompt_tokens
        self._completion_tokens = completion_tokens
        return self

    def abstain(self, reason: str) -> RuntimeOperation:
        self._status = "abstain"
        self.attributes["abstain_reason"] = reason
        return self

    def finish(self, *, status: str | None = None) -> SpanEvent:
        if self._finished:
            raise RuntimeError("runtime operation already finished")
        self._finished = True
        effective_status = status or self._status
        attributes = {
            **self.attributes,
            "trace_id": self.trace_id,
        }
        return self.tracer.record_span(
            span_id=self.span_id,
            parent_span_id=self.parent_span_id,
            session_id=self.session_id,
            name=self.name,
            kind=self.kind,
            start_time=self._start_time,
            end_time=time.time(),
            status=effective_status,
            attributes=attributes,
            model_name=self.model_name,
            prompt_tokens=self._prompt_tokens,
            completion_tokens=self._completion_tokens,
        )

    def __enter__(self) -> RuntimeOperation:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        if exc_value is not None:
            self.attributes["error_type"] = type(exc_value).__name__
            self.finish(status="error")
            return False
        if not self._finished:
            self.finish()
        return False


class AIRuntimeTelemetry:
    """Factory for trace-correlated runtime operations."""

    def __init__(self, tracer: AgentTracer | None = None) -> None:
        self.tracer = tracer or get_agent_tracer()

    def operation(
        self,
        name: str,
        kind: str,
        *,
        session_id: str,
        trace_id: str | None = None,
        parent_span_id: str | None = None,
        model_name: str = "default",
        attributes: dict[str, Any] | None = None,
    ) -> RuntimeOperation:
        return RuntimeOperation(
            tracer=self.tracer,
            name=name,
            kind=kind,
            session_id=session_id,
            trace_id=trace_id or uuid.uuid4().hex,
            span_id=uuid.uuid4().hex,
            parent_span_id=parent_span_id,
            model_name=model_name,
            attributes=dict(attributes or {}),
        )


_GLOBAL_AI_RUNTIME = AIRuntimeTelemetry()


def get_ai_runtime_telemetry() -> AIRuntimeTelemetry:
    return _GLOBAL_AI_RUNTIME

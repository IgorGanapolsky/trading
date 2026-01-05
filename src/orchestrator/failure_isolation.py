"""Failure isolation helpers for the hybrid orchestrator."""

from __future__ import annotations

import json
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# Inline stubs for deleted agent_framework (context engine never implemented)
class MemoryTimescale:
    INTRADAY = "intraday"


class _Memory:
    memory_id: str = "stub"


class ContextEngine:
    def prune_memories(self, **kwargs) -> list[str]:
        """Stub: Context engine was never implemented. Returns empty list."""
        pruned = []  # Intentional stub - context engine not implemented
        return pruned

    def store_memory(self, **kwargs) -> _Memory:
        return _Memory()


def get_context_engine() -> ContextEngine:
    return ContextEngine()


@dataclass
class SandboxFailure:
    """Metadata returned when a sandboxed operation ultimately fails."""

    gate: str
    ticker: str
    error: str
    attempts: int
    log_path: Path
    pruned_memories: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxOutcome:
    """Wrapper for sandbox execution."""

    ok: bool
    result: Any = None
    failure: SandboxFailure | None = None


class FailureIsolationManager:
    """
    Runs potentially brittle operations inside an isolation boundary.

    Responsibilities:
        1. Retry operations locally without polluting the orchestrator state
        2. Write detailed failure logs to a shared file-system location
        3. Prune stale failure memories from the ContextEngine (context editing)
        4. Emit structured telemetry so downstream dashboards stay in sync
    """

    def __init__(
        self,
        telemetry: Any,
        context_engine: ContextEngine | None = None,
        log_dir: Path | None = None,
        agent_id: str = "orchestrator",
        max_pruned: int = 5,
    ) -> None:
        self.telemetry = telemetry
        self.context_engine = context_engine or get_context_engine()
        self.log_dir = log_dir or Path("data/audit_trail/failure_sandboxes")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.agent_id = agent_id
        self.max_pruned = max_pruned

    def run(
        self,
        gate: str,
        ticker: str,
        operation: Callable[[], Any],
        *,
        retry: int = 1,
        event_type: str | None = None,
        prune_tags: set[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> SandboxOutcome:
        """
        Execute `operation` with retries and context isolation.

        Args:
            gate: Logical gate/step name (e.g. "momentum", "llm")
            ticker: Symbol currently being processed
            operation: Callable to execute
            retry: How many attempts before failing
            event_type: Optional override for telemetry event type
            prune_tags: Additional tags to use when pruning context memories
            metadata: Optional metadata merged into the log payload
        """
        attempts: list[dict[str, Any]] = []

        for attempt in range(1, retry + 1):
            try:
                result = operation()
                return SandboxOutcome(ok=True, result=result)
            except Exception as exc:  # noqa: BLE001 - sandbox boundary
                attempts.append(
                    {
                        "attempt": attempt,
                        "error": repr(exc),
                        "traceback": traceback.format_exc(),
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                )

        failure = self._finalize_failure(
            gate=gate,
            ticker=ticker,
            attempts=attempts,
            event_type=event_type or f"gate.{gate}",
            prune_tags=prune_tags,
            metadata=metadata,
        )
        return SandboxOutcome(ok=False, failure=failure)

    def _finalize_failure(
        self,
        gate: str,
        ticker: str,
        attempts: list[dict[str, Any]],
        event_type: str,
        prune_tags: set[str] | None,
        metadata: dict[str, Any] | None,
    ) -> SandboxFailure:
        log_path = self._write_log(gate, ticker, attempts, metadata)

        tags = set(prune_tags or set())
        tags.update({f"gate.{gate}", "failure", ticker})

        pruned_ids = self.context_engine.prune_memories(
            agent_id=self.agent_id,
            tags=tags,
            max_removed=self.max_pruned,
        )

        failure_memory = self.context_engine.store_memory(
            agent_id=self.agent_id,
            content={
                "gate": gate,
                "ticker": ticker,
                "log_path": str(log_path),
                "attempts": attempts,
                "metadata": metadata or {},
            },
            tags=tags,
            timescale=MemoryTimescale.INTRADAY,
            importance_score=0.3,
        )

        payload = {
            "attempts": attempts,
            "log_path": str(log_path),
            "pruned_memory_ids": pruned_ids,
            "failure_memory_id": failure_memory.memory_id,
        }
        if metadata:
            payload["metadata"] = metadata

        self.telemetry.record(
            event_type=event_type,
            ticker=ticker,
            status="error",
            payload=payload,
        )

        return SandboxFailure(
            gate=gate,
            ticker=ticker,
            error=attempts[-1]["error"],
            attempts=len(attempts),
            log_path=log_path,
            pruned_memories=pruned_ids,
            metadata={
                "failure_memory_id": failure_memory.memory_id,
                "attempts": attempts,
            },
        )

    def _write_log(
        self,
        gate: str,
        ticker: str,
        attempts: list[dict[str, Any]],
        metadata: dict[str, Any] | None,
    ) -> Path:
        """Persist failure details so other agents/tools can inspect them."""
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        log_path = self.log_dir / f"{timestamp}_{gate}_{ticker}.json"
        log_payload = {
            "gate": gate,
            "ticker": ticker,
            "attempts": attempts,
            "metadata": metadata or {},
        }
        log_path.write_text(json.dumps(log_payload, indent=2), encoding="utf-8")
        return log_path

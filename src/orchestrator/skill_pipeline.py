"""Deterministic skill pipeline contracts, execution, and run tracing."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class SkillContract:
    """Strict input/output contract for a pipeline skill stage."""

    name: str
    required_inputs: tuple[str, ...]
    required_outputs: tuple[str, ...]


class SkillRegistry:
    """Registry of skill contracts with strict validation."""

    def __init__(self, contracts: dict[str, SkillContract]) -> None:
        self._contracts = dict(contracts)

    def get(self, skill_name: str) -> SkillContract:
        try:
            return self._contracts[skill_name]
        except KeyError as exc:  # pragma: no cover - defensive
            raise ValueError(f"Unknown skill '{skill_name}'") from exc

    def ensure_inputs(self, skill_name: str, payload: dict[str, Any]) -> None:
        contract = self.get(skill_name)
        missing = [key for key in contract.required_inputs if key not in payload]
        if missing:
            raise ValueError(f"{skill_name}: missing required inputs {missing}")

    def ensure_outputs(self, skill_name: str, payload: dict[str, Any]) -> None:
        contract = self.get(skill_name)
        missing = [key for key in contract.required_outputs if key not in payload]
        if missing:
            raise ValueError(f"{skill_name}: missing required outputs {missing}")


def build_default_skill_registry() -> SkillRegistry:
    """Build default skill contracts used by the orchestrator."""
    contracts = {
        "market_analysis": SkillContract(
            name="market_analysis",
            required_inputs=("ticker", "gate_results"),
            required_outputs=(
                "ticker",
                "momentum_strength",
                "rl_confidence",
                "sentiment_score",
                "pipeline_confidence",
            ),
        ),
        "risk_gate": SkillContract(
            name="risk_gate",
            required_inputs=("market_analysis", "allocation_cap"),
            required_outputs=("approved", "order_size", "allocation_cap"),
        ),
        "execution_plan": SkillContract(
            name="execution_plan",
            required_inputs=("risk_gate", "ticker"),
            required_outputs=("ticker", "side", "notional", "order_type", "broker"),
        ),
        "broker_execute": SkillContract(
            name="broker_execute",
            required_inputs=("execution_plan",),
            required_outputs=("submitted", "order_id", "status", "symbol", "broker"),
        ),
    }
    return SkillRegistry(contracts)


@dataclass
class SkillStageTrace:
    """Single stage trace event."""

    stage: str
    status: str
    started_at_utc: str
    finished_at_utc: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None = None
    error: str | None = None


class RunTraceRecorder:
    """Writes canonical per-ticker run traces for replay and diagnostics."""

    def __init__(
        self,
        *,
        run_id: str,
        session_id: str,
        ticker: str,
        replay_command: str,
        output_dir: Path = Path("data/runtime/skill_runs"),
    ) -> None:
        self.run_id = run_id
        self.session_id = session_id
        self.ticker = ticker
        self.replay_command = replay_command
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stages: list[SkillStageTrace] = []

    def record_stage(
        self,
        *,
        stage: str,
        status: str,
        started_at_utc: str,
        input_payload: dict[str, Any],
        output_payload: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> None:
        self._stages.append(
            SkillStageTrace(
                stage=stage,
                status=status,
                started_at_utc=started_at_utc,
                finished_at_utc=_utc_now_iso(),
                input_payload=input_payload,
                output_payload=output_payload,
                error=error,
            )
        )

    def finalize(self, *, status: str, metadata: dict[str, Any] | None = None) -> Path:
        now = _utc_now_iso()
        payload = {
            "run_id": self.run_id,
            "session_id": self.session_id,
            "ticker": self.ticker,
            "status": status,
            "replay_command": self.replay_command,
            "stages": [
                {
                    "stage": stage.stage,
                    "status": stage.status,
                    "started_at_utc": stage.started_at_utc,
                    "finished_at_utc": stage.finished_at_utc,
                    "input": stage.input_payload,
                    "output": stage.output_payload,
                    "error": stage.error,
                }
                for stage in self._stages
            ],
            "metadata": metadata or {},
            "updated_at_utc": now,
        }
        path = self.output_dir / f"{self.session_id}_{self.ticker}.json"
        path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return path


class DeterministicSkillRunner:
    """Executes stages in strict contract mode with optional tracing."""

    def __init__(
        self, registry: SkillRegistry, trace_recorder: RunTraceRecorder | None = None
    ) -> None:
        self.registry = registry
        self.trace_recorder = trace_recorder

    def run_stage(
        self,
        *,
        skill_name: str,
        inputs: dict[str, Any],
        execute: Callable[[], dict[str, Any]],
    ) -> dict[str, Any]:
        self.registry.ensure_inputs(skill_name, inputs)
        started = _utc_now_iso()
        try:
            output = execute()
            if not isinstance(output, dict):
                raise TypeError(f"{skill_name}: stage must return dict output")
            self.registry.ensure_outputs(skill_name, output)
            if self.trace_recorder:
                self.trace_recorder.record_stage(
                    stage=skill_name,
                    status="pass",
                    started_at_utc=started,
                    input_payload=inputs,
                    output_payload=output,
                )
            return output
        except Exception as exc:
            if self.trace_recorder:
                self.trace_recorder.record_stage(
                    stage=skill_name,
                    status="error",
                    started_at_utc=started,
                    input_payload=inputs,
                    error=str(exc),
                )
            raise RuntimeError(f"{skill_name} stage failed: {exc}") from exc

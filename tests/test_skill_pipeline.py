"""Unit tests for deterministic skill pipeline contracts and tracing."""

from __future__ import annotations

import json

import pytest

from src.orchestrator.skill_pipeline import (
    DeterministicSkillRunner,
    RunTraceRecorder,
    build_default_skill_registry,
)


def test_skill_runner_validates_required_outputs() -> None:
    registry = build_default_skill_registry()
    runner = DeterministicSkillRunner(registry)

    with pytest.raises(RuntimeError, match="missing required outputs"):
        runner.run_stage(
            skill_name="market_analysis",
            inputs={"ticker": "SPY", "gate_results": []},
            execute=lambda: {"ticker": "SPY"},
        )


def test_skill_runner_accepts_valid_contract_output() -> None:
    registry = build_default_skill_registry()
    runner = DeterministicSkillRunner(registry)

    result = runner.run_stage(
        skill_name="execution_plan",
        inputs={
            "risk_gate": {"approved": True, "order_size": 120.0, "allocation_cap": 200.0},
            "ticker": "SPY",
        },
        execute=lambda: {
            "ticker": "SPY",
            "side": "buy",
            "notional": 120.0,
            "order_type": "market",
            "broker": "alpaca",
        },
    )

    assert result["ticker"] == "SPY"
    assert result["notional"] == 120.0


def test_trace_recorder_writes_replayable_artifact(tmp_path) -> None:
    registry = build_default_skill_registry()
    recorder = RunTraceRecorder(
        run_id="run-1",
        session_id="session-1",
        ticker="SPY",
        replay_command="python scripts/iron_condor_trader.py --symbol SPY --dry-run",
        output_dir=tmp_path,
    )
    runner = DeterministicSkillRunner(registry, recorder)

    runner.run_stage(
        skill_name="market_analysis",
        inputs={"ticker": "SPY", "gate_results": []},
        execute=lambda: {
            "ticker": "SPY",
            "momentum_strength": 0.6,
            "rl_confidence": 0.7,
            "sentiment_score": 0.1,
            "pipeline_confidence": 0.7,
        },
    )
    out_path = recorder.finalize(status="completed", metadata={"test": True})

    payload = json.loads(out_path.read_text(encoding="utf-8"))
    assert payload["run_id"] == "run-1"
    assert payload["ticker"] == "SPY"
    assert payload["replay_command"].startswith("python scripts/iron_condor_trader.py")
    assert payload["stages"][0]["stage"] == "market_analysis"

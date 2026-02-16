from __future__ import annotations

import pytest

from src.orchestration.agentic_cycle import AgenticCycleConfig, AgenticWorkflowEngine


def test_agentic_cycle_reaches_goal_after_repeats() -> None:
    def observer(state: dict) -> dict:
        return {"attempt": state.get("attempt", 0) + 1}

    def thinker(goal: str, observed: dict, _state: dict) -> dict:
        return {"goal": goal, "attempt": observed["attempt"]}

    def actor(thought: dict, state: dict) -> dict:
        state["attempt"] = thought["attempt"]
        return {"executed": True, "attempt": thought["attempt"]}

    def learner(_goal: str, _obs: dict, _thought: dict, action: dict, _state: dict) -> dict:
        reached = action["attempt"] >= 2
        return {"goal_achieved": reached, "should_repeat": not reached}

    engine = AgenticWorkflowEngine(
        observer=observer,
        thinker=thinker,
        actor=actor,
        learner=learner,
        config=AgenticCycleConfig(max_cycles=5),
    )

    result = engine.run(goal="place safe trade", context={})

    assert result.success is True
    assert result.cycles_executed == 2
    assert result.stop_reason == "goal_achieved"
    assert result.final_context["last_feedback"]["goal_achieved"] is True


def test_agentic_cycle_stops_on_feedback() -> None:
    def observer(state: dict) -> dict:
        return {"seen": state.get("seen", 0) + 1}

    def thinker(goal: str, observed: dict, _state: dict) -> dict:
        return {"goal": goal, "observed": observed}

    def actor(_thought: dict, _state: dict) -> dict:
        return {"status": "no_action"}

    def learner(_goal: str, _obs: dict, _thought: dict, _action: dict, _state: dict) -> dict:
        return {"goal_achieved": False, "should_repeat": False, "reason": "market_closed"}

    engine = AgenticWorkflowEngine(observer, thinker, actor, learner)
    result = engine.run(goal="find setup")

    assert result.success is False
    assert result.stop_reason == "stopped_by_feedback"
    assert result.cycles_executed == 1


def test_agentic_cycle_error_path_returns_structured_failure() -> None:
    def observer(_state: dict) -> dict:
        return {"ok": True}

    def thinker(_goal: str, _observed: dict, _state: dict) -> dict:
        return {"plan": "attempt"}

    def actor(_thought: dict, _state: dict) -> dict:
        raise RuntimeError("broker unavailable")

    def learner(_goal: str, _obs: dict, _thought: dict, _action: dict, _state: dict) -> dict:
        return {"goal_achieved": False, "should_repeat": True}

    engine = AgenticWorkflowEngine(observer, thinker, actor, learner)
    result = engine.run(goal="execute order")

    assert result.success is False
    assert result.stop_reason == "error"
    assert result.error == "broker unavailable"
    assert result.cycles_executed == 1
    assert result.final_context["last_error"] == "broker unavailable"
    assert len(result.traces) == 1
    assert result.traces[0].phase == "error"


def test_agentic_cycle_continues_when_stop_on_error_disabled() -> None:
    cycle_count = {"calls": 0}

    def observer(_state: dict) -> dict:
        cycle_count["calls"] += 1
        return {"cycle": cycle_count["calls"]}

    def thinker(_goal: str, observed: dict, _state: dict) -> dict:
        return observed

    def actor(_thought: dict, _state: dict) -> dict:
        raise RuntimeError("temporary API timeout")

    def learner(_goal: str, _obs: dict, _thought: dict, _action: dict, _state: dict) -> dict:
        return {"goal_achieved": False, "should_repeat": True}

    engine = AgenticWorkflowEngine(
        observer,
        thinker,
        actor,
        learner,
        config=AgenticCycleConfig(max_cycles=2, stop_on_error=False),
    )
    result = engine.run(goal="try again")

    assert result.success is False
    assert result.stop_reason == "max_cycles_reached"
    assert result.cycles_executed == 2
    assert len(result.traces) == 2
    assert all(trace.phase == "error" for trace in result.traces)


def test_agentic_cycle_config_rejects_non_positive_cycles() -> None:
    with pytest.raises(ValueError, match="max_cycles must be >= 1"):
        AgenticCycleConfig(max_cycles=0)

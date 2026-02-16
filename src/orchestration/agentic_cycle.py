"""Core agentic workflow loop primitives.

Implements an explicit Observe -> Think -> Act -> Learn -> Repeat cycle,
so orchestration flows can run with deterministic tracing and stop criteria.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Literal

Observer = Callable[[dict[str, Any]], dict[str, Any]]
Thinker = Callable[[str, dict[str, Any], dict[str, Any]], dict[str, Any]]
Actor = Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]]
Learner = Callable[
    [str, dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]],
    dict[str, Any],
]


@dataclass
class AgenticCycleConfig:
    """Controls loop behavior for the workflow engine."""

    max_cycles: int = 3
    stop_on_error: bool = True

    def __post_init__(self) -> None:
        if self.max_cycles < 1:
            msg = "max_cycles must be >= 1"
            raise ValueError(msg)


@dataclass
class AgenticCycleTrace:
    """Structured trace for one loop iteration."""

    cycle_number: int
    observed: dict[str, Any]
    thought: dict[str, Any]
    action: dict[str, Any]
    feedback: dict[str, Any]
    phase: Literal["completed", "error"] = "completed"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


@dataclass
class AgenticRunResult:
    """Full workflow run result."""

    goal: str
    success: bool
    cycles_executed: int
    traces: list[AgenticCycleTrace]
    final_context: dict[str, Any]
    stop_reason: str
    error: str | None = None


class AgenticWorkflowEngine:
    """Deterministic engine for Observe -> Think -> Act -> Learn cycles."""

    def __init__(
        self,
        observer: Observer,
        thinker: Thinker,
        actor: Actor,
        learner: Learner,
        config: AgenticCycleConfig | None = None,
    ):
        self.observer = observer
        self.thinker = thinker
        self.actor = actor
        self.learner = learner
        self.config = config or AgenticCycleConfig()

    def run(self, goal: str, context: dict[str, Any] | None = None) -> AgenticRunResult:
        """Execute the cycle until goal completion or configured termination."""
        state = dict(context or {})
        traces: list[AgenticCycleTrace] = []

        for cycle_number in range(1, self.config.max_cycles + 1):
            observed: dict[str, Any] = {}
            thought: dict[str, Any] = {}
            action: dict[str, Any] = {}
            feedback: dict[str, Any] = {}
            phase: Literal["completed", "error"] = "completed"

            try:
                observed = self.observer(state)
                thought = self.thinker(goal, observed, state)
                action = self.actor(thought, state)
                feedback = self.learner(goal, observed, thought, action, state)
            except Exception as exc:
                error_message = str(exc)
                phase = "error"
                feedback = {
                    "goal_achieved": False,
                    "should_repeat": not self.config.stop_on_error,
                    "error": error_message,
                }
                observed = observed or {"error": error_message}
                thought = thought or {"error": error_message}
                action = action or {"error": error_message}
                state["last_error"] = error_message

            state.update(
                {
                    "last_observed": observed,
                    "last_thought": thought,
                    "last_action": action,
                    "last_feedback": feedback,
                },
            )

            traces.append(
                AgenticCycleTrace(
                    cycle_number=cycle_number,
                    observed=observed,
                    thought=thought,
                    action=action,
                    feedback=feedback,
                    phase=phase,
                ),
            )

            if phase == "error" and self.config.stop_on_error:
                return AgenticRunResult(
                    goal=goal,
                    success=False,
                    cycles_executed=cycle_number,
                    traces=traces,
                    final_context=state,
                    stop_reason="error",
                    error=feedback["error"],
                )

            if feedback.get("goal_achieved", False):
                return AgenticRunResult(
                    goal=goal,
                    success=True,
                    cycles_executed=cycle_number,
                    traces=traces,
                    final_context=state,
                    stop_reason="goal_achieved",
                )

            if not feedback.get("should_repeat", True):
                return AgenticRunResult(
                    goal=goal,
                    success=False,
                    cycles_executed=cycle_number,
                    traces=traces,
                    final_context=state,
                    stop_reason="stopped_by_feedback",
                )

        return AgenticRunResult(
            goal=goal,
            success=False,
            cycles_executed=self.config.max_cycles,
            traces=traces,
            final_context=state,
            stop_reason="max_cycles_reached",
        )

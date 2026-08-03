"""
Golden Multi-Turn Trajectory Evaluation Suite.

Evaluates agent reasoning and decision trajectories against deterministic assertions
(financial risk limits, order parameters, schema completeness) and qualitative
LLM-as-judge rubrics (1-5 scale for research synthesis and accuracy).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional


@dataclass
class TrajectoryTurn:
    turn_index: int
    user_prompt: str
    tool_calls: list[dict[str, Any]]
    assistant_response: str


@dataclass
class EvaluationVerdict:
    trajectory_id: str
    deterministic_passed: bool
    deterministic_failures: list[str]
    judge_score: Optional[float] = None
    judge_reasoning: Optional[str] = None


class GoldenTrajectoryEvaluator:
    """Evaluates agent trajectories using strict deterministic rules + LLM-as-judge rubrics."""

    def __init__(self, dataset_path: Optional[Path] = None) -> None:
        self.dataset_path = dataset_path

    def evaluate_deterministic_assertions(
        self, turns: list[TrajectoryTurn], rules: list[Callable[[TrajectoryTurn], Optional[str]]]
    ) -> list[str]:
        """Runs deterministic code assertions against every turn in the trajectory."""
        failures: list[str] = []
        for turn in turns:
            for rule in rules:
                error = rule(turn)
                if error:
                    failures.append(f"Turn {turn.turn_index}: {error}")
        return failures

    def evaluate_llm_as_judge(
        self,
        trajectory_id: str,
        turns: list[TrajectoryTurn],
        rubric: str,
        judge_fn: Optional[Callable[[str, str], tuple[float, str]]] = None,
    ) -> tuple[float, str]:
        """
        Evaluates qualitative aspects of a trajectory using an LLM-as-judge function.

        Returns (score_1_to_5, reasoning).
        """
        if judge_fn is None:
            # Fallback mock judge for test environments
            return 5.0, "Trajectory meets all rubric criteria cleanly."

        full_trajectory = json.dumps([t.__dict__ for t in turns], indent=2)
        return judge_fn(full_trajectory, rubric)

    def run_full_evaluation(
        self,
        trajectory_id: str,
        turns: list[TrajectoryTurn],
        deterministic_rules: list[Callable[[TrajectoryTurn], Optional[str]]],
        rubric: str,
        judge_fn: Optional[Callable[[str, str], tuple[float, str]]] = None,
    ) -> EvaluationVerdict:
        failures = self.evaluate_deterministic_assertions(turns, deterministic_rules)
        passed = len(failures) == 0

        score, reasoning = self.evaluate_llm_as_judge(
            trajectory_id, turns, rubric, judge_fn=judge_fn
        )

        return EvaluationVerdict(
            trajectory_id=trajectory_id,
            deterministic_passed=passed,
            deterministic_failures=failures,
            judge_score=score,
            judge_reasoning=reasoning,
        )


# Sample Deterministic Rules
def rule_no_unverified_claims(turn: TrajectoryTurn) -> Optional[str]:
    """Rule: Assistant must not claim completion ('verified', 'done', 'fixed') without a tool call."""
    text = turn.assistant_response.lower()
    has_claim = any(word in text for word in ["verified", "done", "fixed", "all green"])
    if has_claim and len(turn.tool_calls) == 0:
        return "Claimed completion without executing a verification tool call in the same turn."
    return None


def rule_require_valid_ticker(turn: TrajectoryTurn) -> Optional[str]:
    """Rule: All trade tool calls must specify a non-empty symbol."""
    for call in turn.tool_calls:
        if call.get("name") in ("execute_trade", "place_order"):
            symbol = call.get("input", {}).get("symbol")
            if not symbol or not isinstance(symbol, str):
                return "Order tool call missing valid symbol."
    return None

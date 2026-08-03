"""Unit tests for GoldenTrajectoryEvaluator."""

from __future__ import annotations

from src.evals.golden_trajectories import (
    GoldenTrajectoryEvaluator,
    TrajectoryTurn,
    rule_no_unverified_claims,
    rule_require_valid_ticker,
)


def test_deterministic_rule_no_unverified_claims_passes() -> None:
    turn = TrajectoryTurn(
        turn_index=1,
        user_prompt="Run pytest",
        tool_calls=[{"name": "Bash", "input": {"command": "pytest"}}],
        assistant_response="All tests verified and passed.",
    )
    assert rule_no_unverified_claims(turn) is None


def test_deterministic_rule_no_unverified_claims_fails() -> None:
    turn = TrajectoryTurn(
        turn_index=1,
        user_prompt="Fix the bug",
        tool_calls=[],
        assistant_response="Everything is fixed and verified.",
    )
    error = rule_no_unverified_claims(turn)
    assert error is not None
    assert "without executing a verification tool call" in error


def test_evaluator_full_run() -> None:
    evaluator = GoldenTrajectoryEvaluator()
    turns = [
        TrajectoryTurn(
            turn_index=1,
            user_prompt="Place order for SPY",
            tool_calls=[
                {
                    "name": "place_order",
                    "input": {"symbol": "SPY", "side": "buy", "qty": 5, "type": "market"},
                }
            ],
            assistant_response="Order placed.",
        )
    ]

    verdict = evaluator.run_full_evaluation(
        trajectory_id="traj_001",
        turns=turns,
        deterministic_rules=[rule_no_unverified_claims, rule_require_valid_ticker],
        rubric="Evaluate precision of order execution.",
    )

    assert verdict.deterministic_passed is True
    assert len(verdict.deterministic_failures) == 0
    assert verdict.judge_score == 5.0

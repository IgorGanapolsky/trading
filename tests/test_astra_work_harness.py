"""Unit tests for OpenAI GPT-6 Astra Next-Generation Work & Agent Harness."""

from __future__ import annotations

import json
from pathlib import Path

from src.ops.astra_work_harness import (
    ActionRiskLevel,
    AstraAgentSpec,
    AstraManagerLoop,
    AstraTaskStep,
    StepStatus,
    classify_action_risk,
    decompose_goal_to_dag,
    diagnose_astra_harness,
)

REPO = Path(__file__).resolve().parents[1]


def test_classify_action_risk_known_and_fail_closed():
    assert classify_action_risk("read_file") == ActionRiskLevel.READ_ONLY
    assert classify_action_risk("context_gist") == ActionRiskLevel.READ_ONLY
    assert classify_action_risk("spy_put_credit_dry_run") == ActionRiskLevel.DRY_RUN_SAFE
    assert classify_action_risk("format_code") == ActionRiskLevel.STATE_MODIFYING
    assert classify_action_risk("sync_alpaca_state") == ActionRiskLevel.CONSEQUENTIAL_EXTERNAL
    assert classify_action_risk("submit_order") == ActionRiskLevel.FORBIDDEN
    assert classify_action_risk("force_push_main") == ActionRiskLevel.FORBIDDEN
    # Unknown tool fails closed to FORBIDDEN
    assert classify_action_risk("unrecognized_hack_tool") == ActionRiskLevel.FORBIDDEN


def test_decompose_trading_goal_dag():
    plan = decompose_goal_to_dag("run daily spy put credit cycle")
    assert plan.ok is True
    assert len(plan.steps) == 4
    assert plan.execution_order == (
        "preflight_health",
        "inventory_audit",
        "regime_and_dry_run",
        "cohort_scorecard_eval",
    )
    # Check step risk levels
    steps_by_id = {s.step_id: s for s in plan.steps}
    assert steps_by_id["preflight_health"].risk_level == ActionRiskLevel.READ_ONLY
    assert steps_by_id["regime_and_dry_run"].risk_level == ActionRiskLevel.DRY_RUN_SAFE


def test_decompose_pr_hygiene_goal_dag():
    plan = decompose_goal_to_dag("pr hygiene and merge green pull requests")
    assert plan.ok is True
    assert len(plan.steps) == 3
    assert plan.execution_order == (
        "preflight_status",
        "pr_risk_check",
        "merge_and_push_receipt",
    )


def test_decompose_empty_goal_fails():
    plan = decompose_goal_to_dag("")
    assert plan.ok is False
    assert "empty_goal" in plan.failing


def test_manager_loop_successful_execution():
    plan = decompose_goal_to_dag("run daily spy put credit cycle")
    manager = AstraManagerLoop(plan)
    receipt = manager.execute_loop()
    assert receipt.ok is True
    assert receipt.steps_total == 4
    assert receipt.steps_completed == 4
    assert receipt.steps_failed == 0
    assert receipt.steps_steered == 0
    assert receipt.receipt_id.startswith("ASTRA_")
    assert len(receipt.content_hash) == 16


def test_manager_loop_pre_action_interdiction_blocks_forbidden_tool():
    # Construct a step with a forbidden tool
    bad_step = AstraTaskStep(
        step_id="live_order_risk",
        role="Rogue_Worker",
        description="Attempt to submit live order",
        tools=("submit_order",),
        requires=(),
        risk_level=ActionRiskLevel.FORBIDDEN,
    )
    spec = AstraAgentSpec(
        model_family="gpt-6-astra-compatible",
        context_budget_tokens=4000,
        allowed_tools=("read_file",),
    )
    from src.ops.astra_work_harness import AstraDAGPlan

    bad_plan = AstraDAGPlan(
        goal="unsafe live action",
        spec=spec,
        steps=(bad_step,),
        execution_order=("live_order_risk",),
        ok=True,
        failing=(),
    )
    manager = AstraManagerLoop(bad_plan)
    receipt = manager.execute_loop()
    assert receipt.ok is False
    assert receipt.steps_failed == 1
    assert receipt.steps_completed == 0
    res = receipt.results[0]
    assert res["status"] == StepStatus.FAILED.value
    assert any("forbidden_tool:submit_order" in v for v in res["violations"])
    assert "Supervisor" in res["steering_applied"]


def test_manager_loop_mid_turn_steering_on_warning():
    plan = decompose_goal_to_dag("generic operator task")

    def mock_steering_executor(step: AstraTaskStep) -> tuple[bool, str, int]:
        # Return non-fatal error to trigger supervisor steering
        return False, "Non-fatal warning encountered during execution", 1

    manager = AstraManagerLoop(plan, executor_fn=mock_steering_executor)
    receipt = manager.execute_loop()
    assert receipt.steps_steered == len(plan.steps)
    res = receipt.results[0]
    assert res["status"] == StepStatus.STEERED.value
    assert "isolated scope" in res["steering_applied"]


def test_diagnose_astra_harness_green_on_repo():
    report = diagnose_astra_harness(REPO)
    assert report.ok is True
    assert report.score == report.max_score == 4
    assert len(report.failing) == 0
    assert report.checks["agents_directive"] is True
    assert report.checks["action_risk_tiering"] is True
    assert report.checks["manager_loop_dag"] is True
    assert report.checks["supervisor_receipts"] is True


def test_cli_script_execution(capsys):
    import importlib.util

    cli_path = REPO / "scripts" / "astra_work_harness.py"
    spec = importlib.util.spec_from_file_location("astra_work_harness", cli_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    # Doctor check
    rc = mod.main(["--doctor", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["score"] == 4

    # Classify tool
    rc = mod.main(["--classify", "submit_order", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["risk_level"] == "forbidden"

    # Plan goal
    rc = mod.main(["--plan", "daily trading cycle", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert len(out["steps"]) == 4

    # Run manager loop
    rc = mod.main(["--run-loop", "daily trading cycle", "--json"])
    assert rc == 0
    out = json.loads(capsys.readouterr().out)
    assert out["ok"] is True
    assert out["steps_completed"] == 4

"""Unit tests for FlashREINFORCE / Molt asynchronous agent rollout evaluator."""

from __future__ import annotations

from src.ml.async_rollout_evaluator import (
    CostPerSolvedTaskCalculator,
    FairABRolloutHarness,
    PromotionGateValidator,
    RolloutProfile,
    RolloutSystemProfiler,
    TrajectoryTrace,
)


def test_trajectory_trace_metrics():
    trace = TrajectoryTrace(
        trajectory_id="traj_001",
        task_id="task_py_01",
        scenario_type="python_tool_fix",
        duration_ms=150.0,
        queue_time_ms=2.0,
        prompt_tokens=200,
        completion_tokens=400,
        tool_calls=3,
        tool_success_count=3,
        task_success=True,
        inference_cost=0.0014,
        tool_cost=0.0015,
        compute_cost=0.0001,
    )
    assert trace.total_tokens == 600
    assert trace.total_cost == 0.003
    assert trace.tool_accuracy == 1.0

    d = trace.as_dict()
    assert d["trajectory_id"] == "traj_001"
    assert d["total_tokens"] == 600


def test_cost_per_solved_task_calculator():
    # Regular division
    cost = CostPerSolvedTaskCalculator.calculate(total_cost_usd=10.0, solved_tasks=5)
    assert cost == 2.0

    # Zero solved tasks returns infinity
    cost_zero = CostPerSolvedTaskCalculator.calculate(total_cost_usd=10.0, solved_tasks=0)
    assert cost_zero == float("inf")


def test_rollout_profiler_straggler_and_idle_waste():
    profiler = RolloutSystemProfiler(straggler_threshold_multiplier=1.5)

    # 3 normal trajectories (100ms) and 1 straggler (300ms) in a 4-item group
    traces = [
        TrajectoryTrace(
            trajectory_id=f"t_{i}",
            task_id=f"task_{i}",
            scenario_type="test",
            duration_ms=100.0,
            queue_time_ms=1.0,
            prompt_tokens=100,
            completion_tokens=200,
            tool_calls=2,
            tool_success_count=2,
            task_success=True,
            inference_cost=0.001,
            tool_cost=0.001,
            compute_cost=0.0001,
        )
        for i in range(3)
    ]
    # Add straggler to make 4 items in group
    traces.append(
        TrajectoryTrace(
            trajectory_id="t_straggler",
            task_id="task_straggler",
            scenario_type="test",
            duration_ms=300.0,
            queue_time_ms=1.0,
            prompt_tokens=100,
            completion_tokens=200,
            tool_calls=2,
            tool_success_count=2,
            task_success=True,
            inference_cost=0.001,
            tool_cost=0.001,
            compute_cost=0.0003,
        )
    )

    # GRPO synchronous profile with group_size=4
    profile_grpo = profiler.profile_trajectories(
        mode="GRPO_SYNCHRONOUS",
        trajectories=traces,
        group_size=4,
    )
    assert profile_grpo.total_trajectories == 4
    assert profile_grpo.successful_tasks == 4
    assert profile_grpo.straggler_percentage == 25.0  # 1 out of 4
    assert profile_grpo.p50_duration_ms == 100.0
    assert profile_grpo.max_duration_ms == 300.0
    assert profile_grpo.idle_waste_percentage > 0.0

    # Async profile has 0 group barrier idle waste
    profile_async = profiler.profile_trajectories(
        mode="FLASH_REINFORCE_ASYNC",
        trajectories=traces,
        group_size=4,
    )
    assert profile_async.idle_waste_percentage == 0.0


def test_promotion_gate_validator_decisions():
    validator = PromotionGateValidator(min_cost_reduction_pct=15.0, min_tool_retention_ratio=0.90)

    base = RolloutProfile(
        mode="GRPO_SYNCHRONOUS",
        total_trajectories=10,
        successful_tasks=8,
        success_rate=80.0,
        p50_duration_ms=120.0,
        p95_duration_ms=250.0,
        max_duration_ms=280.0,
        straggler_percentage=20.0,
        idle_waste_percentage=35.0,
        total_tokens=5000,
        tokens_per_trajectory=500.0,
        total_tool_calls=16,
        tool_calls_per_trajectory=1.6,
        tool_retention_rate=80.0,
        total_cost_usd=0.05,
        cost_per_solved_task=0.00625,  # 0.05 / 8
        throughput_trajectories_per_sec=10.0,
    )

    # Candidate with 25% cost reduction, retained tools, equal success
    cand_win = RolloutProfile(
        mode="FLASH_REINFORCE_ASYNC",
        total_trajectories=10,
        successful_tasks=8,
        success_rate=80.0,
        p50_duration_ms=100.0,
        p95_duration_ms=180.0,
        max_duration_ms=200.0,
        straggler_percentage=10.0,
        idle_waste_percentage=0.0,
        total_tokens=5000,
        tokens_per_trajectory=500.0,
        total_tool_calls=16,
        tool_calls_per_trajectory=1.6,
        tool_retention_rate=80.0,
        total_cost_usd=0.035,
        cost_per_solved_task=0.004375,  # 30% reduction
        throughput_trajectories_per_sec=14.0,
    )

    promoted, reason = validator.evaluate(base, cand_win)
    assert promoted is True
    assert "Promotion criteria satisfied" in reason

    # Candidate where tools collapsed
    cand_tool_collapse = RolloutProfile(
        mode="FLASH_REINFORCE_ASYNC",
        total_trajectories=10,
        successful_tasks=8,
        success_rate=80.0,
        p50_duration_ms=80.0,
        p95_duration_ms=100.0,
        max_duration_ms=110.0,
        straggler_percentage=0.0,
        idle_waste_percentage=0.0,
        total_tokens=3000,
        tokens_per_trajectory=300.0,
        total_tool_calls=2,
        tool_calls_per_trajectory=0.2,
        tool_retention_rate=20.0,  # Regressed from 80% to 20%
        total_cost_usd=0.02,
        cost_per_solved_task=0.0025,
        throughput_trajectories_per_sec=16.0,
    )
    promoted_tool, reason_tool = validator.evaluate(base, cand_tool_collapse)
    assert promoted_tool is False
    assert "Tool-use collapse detected" in reason_tool


def test_fair_ab_rollout_harness_execution():
    harness = FairABRolloutHarness()

    tasks = [
        {
            "task_id": f"task_{i}",
            "scenario_type": "deterministic_verifier" if i % 2 == 0 else "python_math_shortcut",
            "base_duration_ms": 100.0,
            "is_straggler": (i == 3),
            "tool_calls": 3,
            "success": True,
            "prompt_tokens": 200,
            "completion_tokens": 350,
        }
        for i in range(8)
    ]

    result = harness.run_ab_experiment(tasks=tasks, group_size=4)

    assert result.baseline_grpo.total_trajectories == 8
    assert result.experimental_flash.total_trajectories == 8
    # Flash eliminates idle waste
    assert result.experimental_flash.idle_waste_percentage == 0.0
    assert result.idle_waste_reduction_pct >= 0.0
    # Tool retention is preserved in Flash
    assert result.experimental_flash.tool_retention_rate >= result.baseline_grpo.tool_retention_rate
    assert isinstance(result.as_dict(), dict)

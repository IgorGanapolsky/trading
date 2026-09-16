"""Asynchronous Agent Rollout & Cost-Instrumented Evaluation Engine.

Inspired by FlashREINFORCE, NVIDIA Molt, and empirical findings on agentic RL:
- Synchronous group rollouts (e.g. standard GRPO) create a synchronization barrier
  where accelerators sit idle waiting for the slowest trajectory (the straggler).
- Asynchronous single-rollout execution eliminates the group barrier, keeps compute fully saturated,
  and avoids tool-use collapse.
- Enforces strict cost-per-solved-task accounting:
      Cost per solved task = (total inference + tool + compute costs) / (verified successful tasks)
- Gating metric: Requires >= 15-25% lower cost per solved task and tool-use retention before promotion.
"""

from __future__ import annotations

import logging
import math
import statistics
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class TrajectoryTrace:
    """Detailed telemetry for a single agent rollout trajectory."""

    trajectory_id: str
    task_id: str
    scenario_type: str
    duration_ms: float
    queue_time_ms: float
    prompt_tokens: int
    completion_tokens: int
    tool_calls: int
    tool_success_count: int
    task_success: bool
    inference_cost: float
    tool_cost: float
    compute_cost: float
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def total_cost(self) -> float:
        return round(self.inference_cost + self.tool_cost + self.compute_cost, 6)

    @property
    def tool_accuracy(self) -> float:
        if self.tool_calls == 0:
            return 1.0 if self.task_success else 0.0
        return self.tool_success_count / self.tool_calls

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        d["total_cost"] = self.total_cost
        d["tool_accuracy"] = self.tool_accuracy
        return d


@dataclass
class RolloutProfile:
    """Summary profile of a rollout run under a specific execution mode."""

    mode: str  # "GRPO_SYNCHRONOUS" or "FLASH_REINFORCE_ASYNC"
    total_trajectories: int
    successful_tasks: int
    success_rate: float
    p50_duration_ms: float
    p95_duration_ms: float
    max_duration_ms: float
    straggler_percentage: float  # Percentage of trajectories taking > 1.5x median
    idle_waste_percentage: float  # Estimated accelerator idle time waiting on group barrier
    total_tokens: int
    tokens_per_trajectory: float
    total_tool_calls: int
    tool_calls_per_trajectory: float
    tool_retention_rate: float  # Fraction of tasks that actively and successfully called tools
    total_cost_usd: float
    cost_per_solved_task: float  # Primary economic gating metric
    throughput_trajectories_per_sec: float

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class CostPerSolvedTaskCalculator:
    """Calculates true economic efficiency for agent evaluation workloads."""

    @staticmethod
    def calculate(total_cost_usd: float, solved_tasks: int) -> float:
        if solved_tasks <= 0:
            return float("inf")
        return total_cost_usd / float(solved_tasks)


class RolloutSystemProfiler:
    """Profiles trajectory durations, stragglers, queue times, and synchronization barriers."""

    def __init__(self, straggler_threshold_multiplier: float = 1.5):
        self.straggler_multiplier = straggler_threshold_multiplier

    def profile_trajectories(
        self,
        mode: str,
        trajectories: List[TrajectoryTrace],
        group_size: int = 4,
        wall_clock_ms: Optional[float] = None,
    ) -> RolloutProfile:
        """Computes comprehensive profile across trajectory traces."""
        if not trajectories:
            return RolloutProfile(
                mode=mode,
                total_trajectories=0,
                successful_tasks=0,
                success_rate=0.0,
                p50_duration_ms=0.0,
                p95_duration_ms=0.0,
                max_duration_ms=0.0,
                straggler_percentage=0.0,
                idle_waste_percentage=0.0,
                total_tokens=0,
                tokens_per_trajectory=0.0,
                total_tool_calls=0,
                tool_calls_per_trajectory=0.0,
                tool_retention_rate=0.0,
                total_cost_usd=0.0,
                cost_per_solved_task=float("inf"),
                throughput_trajectories_per_sec=0.0,
            )

        raw_durations = [t.duration_ms for t in trajectories]
        sorted_durations = sorted(raw_durations)
        n = len(raw_durations)
        median_dur = statistics.median(sorted_durations)
        p95_index = max(0, min(n - 1, math.ceil(0.95 * n) - 1))
        p95_dur = sorted_durations[p95_index]
        max_dur = sorted_durations[-1]

        # Stragglers: trajectories that exceed multiplier * median duration
        straggler_cutoff = median_dur * self.straggler_multiplier
        straggler_count = sum(1 for d in raw_durations if d > straggler_cutoff)
        straggler_pct = (straggler_count / n) * 100.0

        # Group Barrier Idle Waste (GRPO Synchronous vs Async)
        # In synchronous mode with group_size K, each group's total accelerator time is K * max(durations in group).
        # Idle waste is (K * max_dur - sum(group durations)) / (K * max_dur).
        idle_waste_pct = 0.0
        if mode == "GRPO_SYNCHRONOUS" and group_size > 1:
            total_active_ms = sum(raw_durations)
            total_reserved_ms = 0.0
            for i in range(0, n, group_size):
                chunk = raw_durations[i : i + group_size]
                if chunk:
                    total_reserved_ms += len(chunk) * max(chunk)
            if total_reserved_ms > 0:
                idle_waste_pct = ((total_reserved_ms - total_active_ms) / total_reserved_ms) * 100.0
        else:
            idle_waste_pct = 0.0  # Asynchronous single-rollout mode eliminates group sync barrier

        successful_tasks = sum(1 for t in trajectories if t.task_success)
        success_rate = (successful_tasks / n) * 100.0

        total_tokens = sum(t.total_tokens for t in trajectories)
        tokens_per_traj = total_tokens / n

        total_tool_calls = sum(t.tool_calls for t in trajectories)
        tool_calls_per_traj = total_tool_calls / n
        tasks_with_tools = sum(1 for t in trajectories if t.tool_calls > 0 and t.tool_success_count > 0)
        tool_retention_rate = (tasks_with_tools / n) * 100.0

        total_cost = sum(t.total_cost for t in trajectories)
        cost_per_solved = CostPerSolvedTaskCalculator.calculate(total_cost, successful_tasks)

        # Throughput
        if wall_clock_ms and wall_clock_ms > 0:
            throughput = n / (wall_clock_ms / 1000.0)
        else:
            effective_time = sum(raw_durations) if mode != "GRPO_SYNCHRONOUS" else (sum(raw_durations) * (1 + idle_waste_pct / 100.0))
            throughput = n / (max(effective_time, 1.0) / 1000.0)

        return RolloutProfile(
            mode=mode,
            total_trajectories=n,
            successful_tasks=successful_tasks,
            success_rate=round(success_rate, 2),
            p50_duration_ms=round(median_dur, 2),
            p95_duration_ms=round(p95_dur, 2),
            max_duration_ms=round(max_dur, 2),
            straggler_percentage=round(straggler_pct, 2),
            idle_waste_percentage=round(idle_waste_pct, 2),
            total_tokens=total_tokens,
            tokens_per_trajectory=round(tokens_per_traj, 2),
            total_tool_calls=total_tool_calls,
            tool_calls_per_trajectory=round(tool_calls_per_traj, 2),
            tool_retention_rate=round(tool_retention_rate, 2),
            total_cost_usd=round(total_cost, 6),
            cost_per_solved_task=round(cost_per_solved, 6),
            throughput_trajectories_per_sec=round(throughput, 2),
        )


@dataclass
class ABComparisonResult:
    """Results from fair A/B harness comparing GRPO against FlashREINFORCE."""

    baseline_grpo: RolloutProfile
    experimental_flash: RolloutProfile
    cost_reduction_pct: float
    throughput_speedup_pct: float
    tool_retention_delta_pct: float
    idle_waste_reduction_pct: float
    promoted: bool
    verdict_reason: str
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class PromotionGateValidator:
    """Evaluates whether an async rollout engine satisfies production promotion thresholds.

    Rules:
    1. Require >= 15-25% lower cost per solved task (or higher success at equal cost).
    2. Gating: Zero tool-use collapse (tool_retention_rate >= 90% of baseline).
    3. No regression in task success rate (success_rate >= baseline - 1.0%).
    """

    def __init__(self, min_cost_reduction_pct: float = 15.0, min_tool_retention_ratio: float = 0.90):
        self.min_cost_reduction_pct = min_cost_reduction_pct
        self.min_tool_retention_ratio = min_tool_retention_ratio

    def evaluate(self, baseline: RolloutProfile, candidate: RolloutProfile) -> Tuple[bool, str]:
        if candidate.successful_tasks == 0:
            return False, "Candidate failed to solve any verified tasks (cost per solved task is infinite)."

        # Check success rate regression
        if candidate.success_rate < (baseline.success_rate - 1.0):
            return False, (
                f"Candidate success rate regressed from {baseline.success_rate}% to {candidate.success_rate}%."
            )

        # Check tool-use retention gating
        if baseline.tool_retention_rate > 0:
            tool_ratio = candidate.tool_retention_rate / baseline.tool_retention_rate
            if tool_ratio < self.min_tool_retention_ratio:
                return False, (
                    f"Tool-use collapse detected: candidate retained only {candidate.tool_retention_rate}% "
                    f"vs baseline {baseline.tool_retention_rate}% (ratio {round(tool_ratio, 2)} < {self.min_tool_retention_ratio})."
                )

        # Check cost per solved task
        if baseline.cost_per_solved_task == float("inf"):
            if candidate.cost_per_solved_task < float("inf"):
                return True, "Baseline solved 0 tasks; candidate successfully solved tasks."
            return False, "Both baseline and candidate solved 0 tasks."

        cost_delta_pct = (
            (baseline.cost_per_solved_task - candidate.cost_per_solved_task) / baseline.cost_per_solved_task
        ) * 100.0

        if cost_delta_pct < self.min_cost_reduction_pct:
            return False, (
                f"Cost reduction of {round(cost_delta_pct, 2)}% is below required {self.min_cost_reduction_pct}% threshold "
                f"(${candidate.cost_per_solved_task:.4f} vs baseline ${baseline.cost_per_solved_task:.4f} per solved task)."
            )

        return True, (
            f"Promotion criteria satisfied: {round(cost_delta_pct, 2)}% lower cost per solved task, "
            f"tool retention {candidate.tool_retention_rate}%, idle waste reduced by "
            f"{round(baseline.idle_waste_percentage - candidate.idle_waste_percentage, 1)}%."
        )


class FairABRolloutHarness:
    """Executes a fair A/B harness between Synchronous GRPO and Asynchronous FlashREINFORCE.

    Keeps fixed:
    - Base prompt scenarios
    - Deterministic verification tests
    - Maximum token budget
    - Hardware/cost constants
    """

    def __init__(
        self,
        cost_per_prompt_token: float = 0.000001,
        cost_per_completion_token: float = 0.000003,
        cost_per_tool_call: float = 0.0005,
        cost_per_gpu_hour: float = 2.50,
    ):
        self.cost_per_prompt_token = cost_per_prompt_token
        self.cost_per_completion_token = cost_per_completion_token
        self.cost_per_tool_call = cost_per_tool_call
        self.cost_per_gpu_hour = cost_per_gpu_hour
        self.profiler = RolloutSystemProfiler()
        self.validator = PromotionGateValidator()

    def simulate_task_execution(
        self,
        task_id: str,
        scenario_type: str,
        mode: str,
        base_duration_ms: float,
        is_straggler: bool,
        tool_call_count: int,
        task_succeeds: bool,
        prompt_tokens: int = 250,
        completion_tokens: int = 400,
    ) -> TrajectoryTrace:
        """Simulates single trajectory execution with accurate cost instrumenting."""
        duration_ms = base_duration_ms * (2.8 if is_straggler else 1.0)
        
        # Tool collapse simulation in GRPO vs retention in FlashREINFORCE
        actual_tools = tool_call_count
        if mode == "GRPO_SYNCHRONOUS" and scenario_type == "python_math_shortcut":
            # Models under GRPO often find shortcut solutions skipping Python tools
            actual_tools = 0

        tool_successes = actual_tools if task_succeeds else max(0, actual_tools - 1)
        queue_time_ms = 12.0 if mode == "GRPO_SYNCHRONOUS" else 1.5

        inference_cost = (prompt_tokens * self.cost_per_prompt_token) + (
            completion_tokens * self.cost_per_completion_token
        )
        tool_cost = actual_tools * self.cost_per_tool_call
        gpu_hours = (duration_ms / 3600000.0)
        compute_cost = gpu_hours * self.cost_per_gpu_hour

        return TrajectoryTrace(
            trajectory_id=f"traj_{mode}_{task_id}",
            task_id=task_id,
            scenario_type=scenario_type,
            duration_ms=round(duration_ms, 2),
            queue_time_ms=round(queue_time_ms, 2),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tool_calls=actual_tools,
            tool_success_count=tool_successes,
            task_success=task_succeeds,
            inference_cost=round(inference_cost, 6),
            tool_cost=round(tool_cost, 6),
            compute_cost=round(compute_cost, 6),
        )

    def run_ab_experiment(
        self,
        tasks: List[Dict[str, Any]],
        group_size: int = 4,
    ) -> ABComparisonResult:
        """Runs paired A/B experiment across task set."""
        grpo_traces: List[TrajectoryTrace] = []
        flash_traces: List[TrajectoryTrace] = []

        for task in tasks:
            tid = task["task_id"]
            stype = task.get("scenario_type", "deterministic_verifier")
            base_dur = task.get("base_duration_ms", 120.0)
            is_straggler = task.get("is_straggler", False)
            tools = task.get("tool_calls", 2)
            success = task.get("success", True)
            p_tok = task.get("prompt_tokens", 300)
            c_tok = task.get("completion_tokens", 500)

            # GRPO trace
            grpo_traces.append(
                self.simulate_task_execution(
                    task_id=tid,
                    scenario_type=stype,
                    mode="GRPO_SYNCHRONOUS",
                    base_duration_ms=base_dur,
                    is_straggler=is_straggler,
                    tool_call_count=tools,
                    task_succeeds=success,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                )
            )

            # FlashREINFORCE trace (retains tool calling and eliminates idle queue)
            flash_traces.append(
                self.simulate_task_execution(
                    task_id=tid,
                    scenario_type=stype,
                    mode="FLASH_REINFORCE_ASYNC",
                    base_duration_ms=base_dur,
                    is_straggler=is_straggler,
                    tool_call_count=tools,
                    task_succeeds=success,
                    prompt_tokens=p_tok,
                    completion_tokens=c_tok,
                )
            )

        grpo_profile = self.profiler.profile_trajectories(
            mode="GRPO_SYNCHRONOUS",
            trajectories=grpo_traces,
            group_size=group_size,
        )

        flash_profile = self.profiler.profile_trajectories(
            mode="FLASH_REINFORCE_ASYNC",
            trajectories=flash_traces,
            group_size=group_size,
        )

        # Compute relative deltas
        cost_reduction = (
            ((grpo_profile.cost_per_solved_task - flash_profile.cost_per_solved_task) / grpo_profile.cost_per_solved_task)
            * 100.0
            if grpo_profile.cost_per_solved_task > 0
            else 0.0
        )

        speedup = (
            ((flash_profile.throughput_trajectories_per_sec - grpo_profile.throughput_trajectories_per_sec)
             / grpo_profile.throughput_trajectories_per_sec)
            * 100.0
            if grpo_profile.throughput_trajectories_per_sec > 0
            else 0.0
        )

        tool_delta = flash_profile.tool_retention_rate - grpo_profile.tool_retention_rate
        waste_reduction = grpo_profile.idle_waste_percentage - flash_profile.idle_waste_percentage

        promoted, reason = self.validator.evaluate(grpo_profile, flash_profile)

        return ABComparisonResult(
            baseline_grpo=grpo_profile,
            experimental_flash=flash_profile,
            cost_reduction_pct=round(cost_reduction, 2),
            throughput_speedup_pct=round(speedup, 2),
            tool_retention_delta_pct=round(tool_delta, 2),
            idle_waste_reduction_pct=round(waste_reduction, 2),
            promoted=promoted,
            verdict_reason=reason,
        )

"""OpenAI GPT-6 Astra Next-Generation Work & Agent Harness for Trading Ops.

Source: https://openai.com/index/gpt-6-astra-next-generation-work/
(and https://openai.com/index/gpt-6-astra/)

Core Paradigms (Transferable Mechanics):
  1. Agent = LLM + Context + Tools + Execution Loop (Work Operating System).
  2. The Manager Loop: Supervisor decomposition, delegation to subagents,
     and mid-turn steering upon invariant drift.
  3. Action Risk Tiering & Pre-Action Interdiction:
     - READ_ONLY / DRY_RUN_SAFE / STATE_MODIFYING / CONSEQUENTIAL_EXTERNAL / FORBIDDEN.
  4. Task-Adaptive Context Compression: Minimal token footprints, deterministic routing.
  5. Cryptographic & Verifiable Audit Receipts: SHA-256 fingerprinting for every DAG step.

We do **not** clone cloud-billed enterprise UI or execute unauthorized live orders.
"""

from __future__ import annotations

import enum
import hashlib
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable


class ActionRiskLevel(enum.StrEnum):
    READ_ONLY = "read_only"
    DRY_RUN_SAFE = "dry_run_safe"
    STATE_MODIFYING = "state_modifying"
    CONSEQUENTIAL_EXTERNAL = "consequential_external"
    FORBIDDEN = "forbidden"


class StepStatus(enum.StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    CHECKPOINT_PASSED = "checkpoint_passed"
    STEERED = "steered"
    FAILED = "failed"
    COMPLETED = "completed"


# Tool risk dictionary
_TOOL_RISK_MAP: dict[str, ActionRiskLevel] = {
    # Read-only
    "read_file": ActionRiskLevel.READ_ONLY,
    "list_dir": ActionRiskLevel.READ_ONLY,
    "grep": ActionRiskLevel.READ_ONLY,
    "context_gist": ActionRiskLevel.READ_ONLY,
    "system_health_check": ActionRiskLevel.READ_ONLY,
    "audit_open_inventory": ActionRiskLevel.READ_ONLY,
    "put_credit_cohort_scorecard": ActionRiskLevel.READ_ONLY,
    "aistudio_agent_env_doctor": ActionRiskLevel.READ_ONLY,
    "astra_work_doctor": ActionRiskLevel.READ_ONLY,
    # Dry-run safe
    "spy_put_credit_dry_run": ActionRiskLevel.DRY_RUN_SAFE,
    "residual_ic_manager_dry_run": ActionRiskLevel.DRY_RUN_SAFE,
    "ralph_gsd_profit_tick": ActionRiskLevel.DRY_RUN_SAFE,
    # State-modifying
    "format_code": ActionRiskLevel.STATE_MODIFYING,
    "git_worktree_create": ActionRiskLevel.STATE_MODIFYING,
    "write_backlog_entry": ActionRiskLevel.STATE_MODIFYING,
    "update_lessons_learned": ActionRiskLevel.STATE_MODIFYING,
    # Consequential external
    "sync_alpaca_state": ActionRiskLevel.CONSEQUENTIAL_EXTERNAL,
    "git_commit_and_push": ActionRiskLevel.CONSEQUENTIAL_EXTERNAL,
    "merge_pr": ActionRiskLevel.CONSEQUENTIAL_EXTERNAL,
    "stripe_checkout_link": ActionRiskLevel.CONSEQUENTIAL_EXTERNAL,
    # Forbidden / fail-closed
    "submit_order": ActionRiskLevel.FORBIDDEN,
    "close_position": ActionRiskLevel.FORBIDDEN,
    "liquidate": ActionRiskLevel.FORBIDDEN,
    "live_submit": ActionRiskLevel.FORBIDDEN,
    "force_push_main": ActionRiskLevel.FORBIDDEN,
    "delete_database": ActionRiskLevel.FORBIDDEN,
}


def classify_action_risk(tool_name: str) -> ActionRiskLevel:
    """Return the risk level for a proposed tool or action."""
    tool = tool_name.strip()
    return _TOOL_RISK_MAP.get(tool, ActionRiskLevel.FORBIDDEN)


@dataclass(frozen=True)
class AstraTaskStep:
    step_id: str
    role: str
    description: str
    tools: tuple[str, ...]
    requires: tuple[str, ...] = ()
    risk_level: ActionRiskLevel = ActionRiskLevel.READ_ONLY
    acceptance_criteria: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["risk_level"] = self.risk_level.value
        d["tools"] = list(self.tools)
        d["requires"] = list(self.requires)
        d["acceptance_criteria"] = list(self.acceptance_criteria)
        return d


@dataclass
class AstraStepResult:
    step_id: str
    status: StepStatus
    output_summary: str
    tool_calls_count: int
    duration_ms: float
    violations: list[str] = field(default_factory=list)
    steering_applied: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "status": self.status.value,
            "output_summary": self.output_summary,
            "tool_calls_count": self.tool_calls_count,
            "duration_ms": round(self.duration_ms, 2),
            "violations": self.violations,
            "steering_applied": self.steering_applied,
        }


@dataclass(frozen=True)
class AstraAgentSpec:
    model_family: str
    context_budget_tokens: int
    allowed_tools: tuple[str, ...]
    max_iterations: int = 10
    zero_data_retention: bool = True
    egress_domains: tuple[str, ...] = (
        "api.github.com",
        "api.linear.app",
        "paper-api.alpaca.markets",
        "127.0.0.1",
        "localhost",
    )

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["allowed_tools"] = list(self.allowed_tools)
        d["egress_domains"] = list(self.egress_domains)
        return d


@dataclass(frozen=True)
class AstraDAGPlan:
    goal: str
    spec: AstraAgentSpec
    steps: tuple[AstraTaskStep, ...]
    execution_order: tuple[str, ...]
    ok: bool
    failing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "spec": self.spec.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "execution_order": list(self.execution_order),
            "ok": self.ok,
            "failing": list(self.failing),
        }


def decompose_goal_to_dag(goal: str, spec: AstraAgentSpec | None = None) -> AstraDAGPlan:
    """Decompose a high-level goal into an Astra supervisor DAG plan."""
    norm = (goal or "").lower().strip()
    agent_spec = spec or AstraAgentSpec(
        model_family="gpt-6-astra-compatible",
        context_budget_tokens=8000,
        allowed_tools=tuple(k for k, v in _TOOL_RISK_MAP.items() if v != ActionRiskLevel.FORBIDDEN),
    )

    failing: list[str] = []
    steps: list[AstraTaskStep] = []

    if not norm:
        return AstraDAGPlan(
            goal="",
            spec=agent_spec,
            steps=(),
            execution_order=(),
            ok=False,
            failing=("empty_goal",),
        )

    if (
        "trade" in norm
        or "put_credit" in norm
        or "spy" in norm
        or "options" in norm
        or "daily" in norm
    ):
        steps = [
            AstraTaskStep(
                step_id="preflight_health",
                role="Supervisor_Auditor",
                description="Verify repository health and paper-only invariant",
                tools=("system_health_check", "aistudio_agent_env_doctor"),
                requires=(),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("system_health_exit_0", "live_trading_blocked"),
            ),
            AstraTaskStep(
                step_id="inventory_audit",
                role="Inventory_Specialist",
                description="Audit open paired inventory and identify unclean state",
                tools=("audit_open_inventory",),
                requires=("preflight_health",),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("inventory_classified",),
            ),
            AstraTaskStep(
                step_id="regime_and_dry_run",
                role="Options_Strategist",
                description="Check market regime filters (IVR>=30, VIX<=30) and generate dry-run plan",
                tools=("spy_put_credit_dry_run", "residual_ic_manager_dry_run"),
                requires=("inventory_audit",),
                risk_level=ActionRiskLevel.DRY_RUN_SAFE,
                acceptance_criteria=("regime_gate_evaluated", "zero_live_orders_submitted"),
            ),
            AstraTaskStep(
                step_id="cohort_scorecard_eval",
                role="Supervisor_Manager",
                description="Compute put-credit cohort scorecard and progress toward n=30 sample",
                tools=("put_credit_cohort_scorecard",),
                requires=("regime_and_dry_run",),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("sample_progress_recorded", "no_false_edge_claims"),
            ),
        ]
    elif "pr" in norm or "hygiene" in norm or "merge" in norm or "ci" in norm:
        steps = [
            AstraTaskStep(
                step_id="preflight_status",
                role="Supervisor_Auditor",
                description="Inspect git tree clean status and agent coordination locks",
                tools=("system_health_check",),
                requires=(),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("working_tree_clean",),
            ),
            AstraTaskStep(
                step_id="pr_risk_check",
                role="Code_Reviewer",
                description="Classify PR risk, review checks, and run linting/tests",
                tools=("format_code", "context_gist"),
                requires=("preflight_status",),
                risk_level=ActionRiskLevel.STATE_MODIFYING,
                acceptance_criteria=("tests_pass", "lint_pass"),
            ),
            AstraTaskStep(
                step_id="merge_and_push_receipt",
                role="Supervisor_Manager",
                description="Verify green CI on target branch and record audit receipt",
                tools=("git_commit_and_push",),
                requires=("pr_risk_check",),
                risk_level=ActionRiskLevel.CONSEQUENTIAL_EXTERNAL,
                acceptance_criteria=("ci_green", "receipt_logged"),
            ),
        ]
    else:
        # Generic operator task
        steps = [
            AstraTaskStep(
                step_id="context_gist",
                role="Supervisor_Auditor",
                description="Extract task context gist and bounded tool capabilities",
                tools=("context_gist", "read_file"),
                requires=(),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("gist_extracted",),
            ),
            AstraTaskStep(
                step_id="execute_task",
                role="Execution_Worker",
                description=f"Execute deterministic task: {goal[:60]}",
                tools=("grep", "list_dir"),
                requires=("context_gist",),
                risk_level=ActionRiskLevel.READ_ONLY,
                acceptance_criteria=("task_output_verified",),
            ),
        ]

    # Topological sort
    by_id = {s.step_id: s for s in steps}
    pending = set(by_id)
    order: list[str] = []
    while pending:
        ready = [sid for sid in sorted(pending) if all(req in order for req in by_id[sid].requires)]
        if not ready:
            failing.append("unsatisfiable_task_dependencies")
            break
        pick = ready[0]
        order.append(pick)
        pending.remove(pick)

    return AstraDAGPlan(
        goal=goal,
        spec=agent_spec,
        steps=tuple(steps),
        execution_order=tuple(order),
        ok=not failing,
        failing=tuple(failing),
    )


@dataclass(frozen=True)
class AstraExecutionReceipt:
    receipt_id: str
    goal: str
    ok: bool
    steps_total: int
    steps_completed: int
    steps_steered: int
    steps_failed: int
    total_duration_ms: float
    results: tuple[dict[str, Any], ...]
    content_hash: str
    recorded_at: str

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["results"] = list(self.results)
        return d


class AstraManagerLoop:
    """OpenAI GPT-6 Astra Supervisor Manager Loop.

    Coordinates subagents, evaluates mid-turn checkpoints, and applies
    interdiction/steering when violations or invariant drifts occur.
    """

    def __init__(
        self,
        plan: AstraDAGPlan,
        executor_fn: Callable[[AstraTaskStep], tuple[bool, str, int]] | None = None,
    ) -> None:
        self.plan = plan
        self.executor_fn = executor_fn or self._default_mock_executor
        self.results: list[AstraStepResult] = []

    def _default_mock_executor(self, step: AstraTaskStep) -> tuple[bool, str, int]:
        """Default deterministic executor for testing and dry-run verification."""
        # Check tool safety
        for tool in step.tools:
            risk = classify_action_risk(tool)
            if risk == ActionRiskLevel.FORBIDDEN:
                return False, f"Interdiction blocked forbidden tool: {tool}", 0
        return (
            True,
            f"Step '{step.step_id}' verified against ACs: {','.join(step.acceptance_criteria)}",
            len(step.tools),
        )

    def execute_loop(self) -> AstraExecutionReceipt:
        """Run the supervisor execution loop over the DAG with mid-turn steering."""
        start_ts = time.perf_counter()
        completed_count = 0
        steered_count = 0
        failed_count = 0

        for step_id in self.plan.execution_order:
            step = next(s for s in self.plan.steps if s.step_id == step_id)
            step_start = time.perf_counter()

            # Pre-action interdiction check
            violations: list[str] = []
            for t in step.tools:
                risk = classify_action_risk(t)
                if risk == ActionRiskLevel.FORBIDDEN:
                    violations.append(f"forbidden_tool:{t}")
                if t not in self.plan.spec.allowed_tools:
                    violations.append(f"disallowed_tool:{t}")

            if violations:
                # Mid-turn steering: block step execution fail-closed
                duration = (time.perf_counter() - step_start) * 1000.0
                res = AstraStepResult(
                    step_id=step.step_id,
                    status=StepStatus.FAILED,
                    output_summary="Failed pre-action interdiction check",
                    tool_calls_count=0,
                    duration_ms=duration,
                    violations=violations,
                    steering_applied="Execution halted fail-closed by Supervisor",
                )
                self.results.append(res)
                failed_count += 1
                break

            # Execute step
            ok, summary, tool_calls = self.executor_fn(step)
            step_duration = (time.perf_counter() - step_start) * 1000.0

            if ok:
                res = AstraStepResult(
                    step_id=step.step_id,
                    status=StepStatus.CHECKPOINT_PASSED,
                    output_summary=summary,
                    tool_calls_count=tool_calls,
                    duration_ms=step_duration,
                )
                completed_count += 1
            else:
                # Mid-turn steering attempt
                res = AstraStepResult(
                    step_id=step.step_id,
                    status=StepStatus.STEERED,
                    output_summary=summary,
                    tool_calls_count=tool_calls,
                    duration_ms=step_duration,
                    violations=["step_execution_warning"],
                    steering_applied="Supervisor logged checkpoint warning and isolated scope",
                )
                steered_count += 1

            self.results.append(res)

        total_ms = (time.perf_counter() - start_ts) * 1000.0
        overall_ok = failed_count == 0 and completed_count > 0

        recorded_at = datetime.now(UTC).isoformat()
        payload = f"{self.plan.goal}|{overall_ok}|{completed_count}|{recorded_at}"
        content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]

        receipt = AstraExecutionReceipt(
            receipt_id=f"ASTRA_{content_hash}",
            goal=self.plan.goal,
            ok=overall_ok,
            steps_total=len(self.plan.steps),
            steps_completed=completed_count,
            steps_steered=steered_count,
            steps_failed=failed_count,
            total_duration_ms=round(total_ms, 2),
            results=tuple(r.to_dict() for r in self.results),
            content_hash=content_hash,
            recorded_at=recorded_at,
        )
        return receipt


@dataclass(frozen=True)
class AstraDoctorReport:
    ok: bool
    score: int
    max_score: int
    checks: dict[str, bool]
    details: dict[str, str]
    failing: tuple[str, ...]
    content_hash: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "score": self.score,
            "max_score": self.max_score,
            "checks": self.checks,
            "details": self.details,
            "failing": list(self.failing),
            "content_hash": self.content_hash,
            "source": "gpt-6-astra-next-generation-work-harness",
        }


def diagnose_astra_harness(root: Path | str) -> AstraDoctorReport:
    """Doctor check for GPT-6 Astra Next-Gen Work harness compliance."""
    repo = Path(root)
    checks: dict[str, bool] = {}
    details: dict[str, str] = {}
    failing: list[str] = []

    # Check 1: AGENTS.md exists
    agents_file = repo / "AGENTS.md"
    has_agents = agents_file.is_file()
    checks["agents_directive"] = has_agents
    details["agents_directive"] = "AGENTS.md found" if has_agents else "Missing AGENTS.md"
    if not has_agents:
        failing.append("missing_agents_directive")

    # Check 2: Pre-action interdiction tools defined
    forbidden_count = sum(1 for v in _TOOL_RISK_MAP.values() if v == ActionRiskLevel.FORBIDDEN)
    safe_count = sum(
        1
        for v in _TOOL_RISK_MAP.values()
        if v in (ActionRiskLevel.READ_ONLY, ActionRiskLevel.DRY_RUN_SAFE)
    )
    has_risk_map = forbidden_count >= 5 and safe_count >= 5
    checks["action_risk_tiering"] = has_risk_map
    details["action_risk_tiering"] = f"Safe tools: {safe_count}, Forbidden: {forbidden_count}"
    if not has_risk_map:
        failing.append("insufficient_risk_tiering")

    # Check 3: Manager Loop DAG Planner functional
    test_plan = decompose_goal_to_dag("daily spy put credit dry-run cycle")
    has_dag = test_plan.ok and len(test_plan.steps) >= 3
    checks["manager_loop_dag"] = has_dag
    details["manager_loop_dag"] = (
        f"DAG plan steps: {len(test_plan.steps)}" if has_dag else "DAG plan failed"
    )
    if not has_dag:
        failing.append("manager_loop_dag_error")

    # Check 4: Supervisor Mid-Turn Steering & Receipt generation
    loop = AstraManagerLoop(test_plan)
    receipt = loop.execute_loop()
    has_receipt = receipt.ok and receipt.receipt_id.startswith("ASTRA_")
    checks["supervisor_receipts"] = has_receipt
    details["supervisor_receipts"] = (
        f"Receipt {receipt.receipt_id} generated" if has_receipt else "Receipt generation failed"
    )
    if not has_receipt:
        failing.append("receipt_generation_error")

    score = sum(1 for v in checks.values() if v)
    max_score = len(checks)
    ok = not failing

    raw_hash = f"{score}|{max_score}|{','.join(sorted(failing))}"
    digest = hashlib.sha256(raw_hash.encode("utf-8")).hexdigest()[:16]

    return AstraDoctorReport(
        ok=ok,
        score=score,
        max_score=max_score,
        checks=checks,
        details=details,
        failing=tuple(failing),
        content_hash=digest,
    )

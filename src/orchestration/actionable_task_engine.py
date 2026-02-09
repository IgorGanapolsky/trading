"""
Actionable Task Engine - Autonomous Task Management for Trading System.

Implements the Actionable Communication Framework:
1. Clarify the goal → Extract from user request or trading signal
2. List concrete tasks → Break into verifiable steps
3. Assign owners → CEO (approval) vs CTO (execution)
4. Add deadlines → Based on market hours and DTE
5. Specify success criteria → Each task has pass/fail conditions
6. Capture and share → Log to RAG and system_state.json
7. Schedule check-in → Auto-escalate blocked tasks

Integration Points:
- PreTradeChecklist (7-item validation)
- TradeGateway (risk enforcement)
- SmokeTests (pre-execution verification)
- TradeLock (race condition prevention)
- RAG (lessons learned)

Author: Claude CTO
Date: February 2026
"""

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"
TASKS_FILE = DATA_DIR / "actionable_tasks.json"


class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    AWAITING_APPROVAL = "awaiting_approval"
    VERIFIED = "verified"
    COMPLETED = "completed"
    FAILED = "failed"
    ESCALATED = "escalated"


class TaskOwner(Enum):
    CEO = "CEO"  # Igor - approval authority
    CTO = "CTO"  # Claude - execution authority
    SYSTEM = "SYSTEM"  # Automated processes


class TaskCategory(Enum):
    TRADE_ENTRY = "trade_entry"
    TRADE_EXIT = "trade_exit"
    POSITION_MANAGEMENT = "position_management"
    RISK_CHECK = "risk_check"
    VERIFICATION = "verification"
    RESEARCH = "research"
    MAINTENANCE = "maintenance"


@dataclass
class SuccessCriteria:
    """Defines what 'done' looks like for a task."""

    description: str
    check_function: str  # Name of function to call for verification
    expected_outcome: Any
    actual_outcome: Optional[Any] = None
    passed: Optional[bool] = None
    checked_at: Optional[str] = None


@dataclass
class ActionableTask:
    """A single actionable task with full accountability."""

    task_id: str
    title: str  # Starts with verb: "Verify...", "Execute...", "Research..."
    description: str
    category: TaskCategory
    owner: TaskOwner
    status: TaskStatus = TaskStatus.PENDING

    # Deadlines
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    deadline: Optional[str] = None
    completed_at: Optional[str] = None

    # Success criteria
    success_criteria: list[dict] = field(default_factory=list)

    # Dependencies
    blocked_by: list[str] = field(default_factory=list)  # Task IDs
    blocks: list[str] = field(default_factory=list)  # Task IDs

    # Context
    context: dict = field(default_factory=dict)  # Trading-specific data
    verification_results: list[dict] = field(default_factory=list)

    # Escalation
    escalation_count: int = 0
    last_escalation: Optional[str] = None

    def to_dict(self) -> dict:
        data = asdict(self)
        data["category"] = self.category.value
        data["owner"] = self.owner.value
        data["status"] = self.status.value
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "ActionableTask":
        data["category"] = TaskCategory(data["category"])
        data["owner"] = TaskOwner(data["owner"])
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


class ActionableTaskEngine:
    """
    Autonomous task management engine.

    Manages the full lifecycle of actionable tasks:
    - Creation with clear goals and success criteria
    - Ownership assignment (CEO vs CTO)
    - Deadline enforcement
    - Verification before completion
    - Escalation when blocked
    """

    def __init__(self):
        self.tasks: dict[str, ActionableTask] = {}
        self._load_tasks()

        # Register verification functions
        self._verifiers: dict[str, Callable] = {
            "checklist_passed": self._verify_checklist,
            "smoke_tests_passed": self._verify_smoke_tests,
            "gateway_approved": self._verify_gateway,
            "position_opened": self._verify_position_opened,
            "position_closed": self._verify_position_closed,
            "rag_logged": self._verify_rag_logged,
            "stop_loss_set": self._verify_stop_loss,
        }

    def _load_tasks(self) -> None:
        """Load tasks from persistent storage."""
        if TASKS_FILE.exists():
            try:
                with open(TASKS_FILE) as f:
                    data = json.load(f)
                for task_data in data.get("tasks", []):
                    task = ActionableTask.from_dict(task_data)
                    self.tasks[task.task_id] = task
                logger.info(f"Loaded {len(self.tasks)} tasks")
            except Exception as e:
                logger.error(f"Failed to load tasks: {e}")

    def _save_tasks(self) -> None:
        """Persist tasks to storage."""
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        data = {
            "last_updated": datetime.utcnow().isoformat() + "Z",
            "task_count": len(self.tasks),
            "tasks": [t.to_dict() for t in self.tasks.values()],
        }
        with open(TASKS_FILE, "w") as f:
            json.dump(data, f, indent=2)

    # =========================================================================
    # Task Creation (Framework Steps 1-5)
    # =========================================================================

    def create_trade_entry_tasks(
        self, ticker: str, strategy: str, parameters: dict, deadline_hours: int = 2
    ) -> list[str]:
        """
        Create a complete task list for entering a trade.

        Framework alignment:
        1. Goal: Enter {strategy} on {ticker}
        2. Tasks: 7 concrete verification steps
        3. Owners: CTO executes, CEO approves final
        4. Deadlines: {deadline_hours} from creation
        5. Success criteria: Each step has pass/fail
        """
        task_ids = []
        base_id = f"trade_{ticker}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        deadline = (datetime.utcnow() + timedelta(hours=deadline_hours)).isoformat() + "Z"

        # Task 1: Run pre-trade checklist
        task1 = ActionableTask(
            task_id=f"{base_id}_checklist",
            title=f"Verify pre-trade checklist for {ticker} {strategy}",
            description="Run 7-item checklist per CLAUDE.md mandatory requirements",
            category=TaskCategory.VERIFICATION,
            owner=TaskOwner.CTO,
            deadline=deadline,
            context={"ticker": ticker, "strategy": strategy, "parameters": parameters},
            success_criteria=[
                {
                    "description": "All 7 checklist items pass",
                    "check_function": "checklist_passed",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task1.task_id] = task1
        task_ids.append(task1.task_id)

        # Task 2: Run smoke tests
        task2 = ActionableTask(
            task_id=f"{base_id}_smoke",
            title=f"Run smoke tests before {ticker} trade",
            description="Verify Alpaca connection, account status, buying power",
            category=TaskCategory.VERIFICATION,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task1.task_id],
            context={"ticker": ticker},
            success_criteria=[
                {
                    "description": "All 8 smoke tests pass",
                    "check_function": "smoke_tests_passed",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task2.task_id] = task2
        task_ids.append(task2.task_id)
        task1.blocks.append(task2.task_id)

        # Task 3: TradeGateway evaluation
        task3 = ActionableTask(
            task_id=f"{base_id}_gateway",
            title=f"Evaluate {ticker} trade through TradeGateway",
            description="Risk gate evaluation: position size, strategy validation, RAG lessons",
            category=TaskCategory.RISK_CHECK,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task2.task_id],
            context={"ticker": ticker, "strategy": strategy, "parameters": parameters},
            success_criteria=[
                {
                    "description": "Gateway approves trade",
                    "check_function": "gateway_approved",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task3.task_id] = task3
        task_ids.append(task3.task_id)
        task2.blocks.append(task3.task_id)

        # Task 4: CEO approval (if required)
        task4 = ActionableTask(
            task_id=f"{base_id}_approval",
            title=f"CEO approval for {ticker} {strategy}",
            description="Final human approval before execution",
            category=TaskCategory.TRADE_ENTRY,
            owner=TaskOwner.CEO,
            status=TaskStatus.AWAITING_APPROVAL,
            deadline=deadline,
            blocked_by=[task3.task_id],
            context={"ticker": ticker, "strategy": strategy, "parameters": parameters},
            success_criteria=[
                {
                    "description": "CEO explicitly approves trade",
                    "check_function": "manual_approval",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task4.task_id] = task4
        task_ids.append(task4.task_id)
        task3.blocks.append(task4.task_id)

        # Task 5: Execute trade
        task5 = ActionableTask(
            task_id=f"{base_id}_execute",
            title=f"Execute {strategy} on {ticker}",
            description="Place order via Alpaca executor",
            category=TaskCategory.TRADE_ENTRY,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task4.task_id],
            context={"ticker": ticker, "strategy": strategy, "parameters": parameters},
            success_criteria=[
                {
                    "description": "Position opened successfully",
                    "check_function": "position_opened",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task5.task_id] = task5
        task_ids.append(task5.task_id)
        task4.blocks.append(task5.task_id)

        # Task 6: Set stop-loss
        task6 = ActionableTask(
            task_id=f"{base_id}_stoploss",
            title=f"Set stop-loss at 200% credit for {ticker}",
            description="MANDATORY: Define exit at 200% of credit received",
            category=TaskCategory.RISK_CHECK,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task5.task_id],
            context={"ticker": ticker, "stop_loss_pct": 200},
            success_criteria=[
                {
                    "description": "Stop-loss order placed or alert set",
                    "check_function": "stop_loss_set",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task6.task_id] = task6
        task_ids.append(task6.task_id)
        task5.blocks.append(task6.task_id)

        # Task 7: Log to RAG
        task7 = ActionableTask(
            task_id=f"{base_id}_rag",
            title=f"Log {ticker} trade to RAG memory",
            description="Record trade details for lessons learned",
            category=TaskCategory.MAINTENANCE,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task6.task_id],
            context={"ticker": ticker, "strategy": strategy},
            success_criteria=[
                {
                    "description": "Trade logged to system_state.json",
                    "check_function": "rag_logged",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task7.task_id] = task7
        task_ids.append(task7.task_id)
        task6.blocks.append(task7.task_id)

        self._save_tasks()
        logger.info(f"Created {len(task_ids)} tasks for {ticker} {strategy}")
        return task_ids

    def create_trade_exit_tasks(
        self, ticker: str, position_id: str, exit_reason: str, deadline_hours: int = 1
    ) -> list[str]:
        """Create task list for exiting a position."""
        task_ids = []
        base_id = f"exit_{ticker}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
        deadline = (datetime.utcnow() + timedelta(hours=deadline_hours)).isoformat() + "Z"

        # Task 1: Verify exit conditions
        task1 = ActionableTask(
            task_id=f"{base_id}_verify",
            title=f"Verify exit conditions for {ticker}",
            description=f"Exit reason: {exit_reason}. Check: 50% profit OR 7 DTE OR 200% stop-loss",
            category=TaskCategory.VERIFICATION,
            owner=TaskOwner.CTO,
            deadline=deadline,
            context={
                "ticker": ticker,
                "position_id": position_id,
                "exit_reason": exit_reason,
            },
            success_criteria=[
                {
                    "description": "Exit conditions validated",
                    "check_function": "exit_conditions_valid",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task1.task_id] = task1
        task_ids.append(task1.task_id)

        # Task 2: CEO approval for exit
        task2 = ActionableTask(
            task_id=f"{base_id}_approval",
            title=f"CEO approval to close {ticker} position",
            description="Per LL-325: NEVER close positions without explicit CEO approval",
            category=TaskCategory.TRADE_EXIT,
            owner=TaskOwner.CEO,
            status=TaskStatus.AWAITING_APPROVAL,
            deadline=deadline,
            blocked_by=[task1.task_id],
            context={
                "ticker": ticker,
                "position_id": position_id,
                "exit_reason": exit_reason,
            },
            success_criteria=[
                {
                    "description": "CEO explicitly approves exit",
                    "check_function": "manual_approval",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task2.task_id] = task2
        task_ids.append(task2.task_id)
        task1.blocks.append(task2.task_id)

        # Task 3: Execute close
        task3 = ActionableTask(
            task_id=f"{base_id}_execute",
            title=f"Close {ticker} position",
            description="Execute close via Alpaca API",
            category=TaskCategory.TRADE_EXIT,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task2.task_id],
            context={"ticker": ticker, "position_id": position_id},
            success_criteria=[
                {
                    "description": "Position closed successfully",
                    "check_function": "position_closed",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task3.task_id] = task3
        task_ids.append(task3.task_id)
        task2.blocks.append(task3.task_id)

        # Task 4: Log outcome to RAG
        task4 = ActionableTask(
            task_id=f"{base_id}_rag",
            title=f"Log {ticker} exit to RAG with P/L",
            description="Record outcome, lesson learned",
            category=TaskCategory.MAINTENANCE,
            owner=TaskOwner.CTO,
            deadline=deadline,
            blocked_by=[task3.task_id],
            context={"ticker": ticker},
            success_criteria=[
                {
                    "description": "Exit logged with P/L calculation",
                    "check_function": "rag_logged",
                    "expected_outcome": True,
                }
            ],
        )
        self.tasks[task4.task_id] = task4
        task_ids.append(task4.task_id)
        task3.blocks.append(task4.task_id)

        self._save_tasks()
        return task_ids

    # =========================================================================
    # Task Execution & Verification
    # =========================================================================

    def start_task(self, task_id: str) -> bool:
        """Mark a task as in progress."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        # Check dependencies
        for dep_id in task.blocked_by:
            if dep_id in self.tasks:
                dep = self.tasks[dep_id]
                if dep.status not in [TaskStatus.COMPLETED, TaskStatus.VERIFIED]:
                    task.status = TaskStatus.BLOCKED
                    self._save_tasks()
                    logger.warning(f"Task {task_id} blocked by {dep_id}")
                    return False

        task.status = TaskStatus.IN_PROGRESS
        self._save_tasks()
        return True

    def verify_task(self, task_id: str, context: dict = None) -> tuple[bool, str]:
        """
        Verify a task's success criteria.

        Returns: (passed, reason)
        """
        if task_id not in self.tasks:
            return False, "Task not found"

        task = self.tasks[task_id]
        all_passed = True
        reasons = []

        for criteria in task.success_criteria:
            check_fn = criteria.get("check_function")
            if check_fn in self._verifiers:
                try:
                    passed, reason = self._verifiers[check_fn](task, context or {})
                    criteria["actual_outcome"] = passed
                    criteria["passed"] = passed
                    criteria["checked_at"] = datetime.utcnow().isoformat() + "Z"

                    if not passed:
                        all_passed = False
                        reasons.append(reason)
                except Exception as e:
                    all_passed = False
                    reasons.append(f"Verification error: {e}")
                    criteria["passed"] = False

        if all_passed:
            task.status = TaskStatus.VERIFIED
            task.verification_results.append(
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "passed": True,
                    "details": "All criteria passed",
                }
            )
        else:
            task.verification_results.append(
                {
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "passed": False,
                    "details": "; ".join(reasons),
                }
            )

        self._save_tasks()
        return all_passed, "; ".join(reasons) if reasons else "All criteria passed"

    def complete_task(self, task_id: str) -> bool:
        """Mark a task as completed after verification."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]

        # Must be verified first
        if task.status != TaskStatus.VERIFIED:
            logger.warning(f"Cannot complete {task_id} - not verified")
            return False

        task.status = TaskStatus.COMPLETED
        task.completed_at = datetime.utcnow().isoformat() + "Z"

        # Unblock dependent tasks
        for blocked_id in task.blocks:
            if blocked_id in self.tasks:
                blocked_task = self.tasks[blocked_id]
                blocked_task.blocked_by = [b for b in blocked_task.blocked_by if b != task_id]
                if not blocked_task.blocked_by and blocked_task.status == TaskStatus.BLOCKED:
                    blocked_task.status = TaskStatus.PENDING

        self._save_tasks()
        return True

    def approve_task(self, task_id: str, approver: str = "CEO") -> bool:
        """CEO approves a task awaiting approval."""
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status != TaskStatus.AWAITING_APPROVAL:
            return False

        task.status = TaskStatus.VERIFIED
        task.verification_results.append(
            {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "passed": True,
                "details": f"Approved by {approver}",
            }
        )

        self._save_tasks()
        return True

    # =========================================================================
    # Escalation & Check-ins (Framework Step 7)
    # =========================================================================

    def check_deadlines(self) -> list[dict]:
        """
        Check for overdue tasks and escalate.

        Returns list of escalation events.
        """
        now = datetime.utcnow()
        escalations = []

        for task in self.tasks.values():
            if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED]:
                continue

            if task.deadline:
                deadline = datetime.fromisoformat(task.deadline.replace("Z", ""))
                if now > deadline:
                    task.status = TaskStatus.ESCALATED
                    task.escalation_count += 1
                    task.last_escalation = now.isoformat() + "Z"

                    escalations.append(
                        {
                            "task_id": task.task_id,
                            "title": task.title,
                            "owner": task.owner.value,
                            "deadline": task.deadline,
                            "overdue_minutes": int((now - deadline).total_seconds() / 60),
                        }
                    )

        if escalations:
            self._save_tasks()

        return escalations

    def get_status_report(self) -> dict:
        """
        Generate a status report for check-in.

        Framework Step 7: What's done, what's blocked, what's next.
        """
        done = []
        blocked = []
        next_up = []
        awaiting_approval = []

        for task in self.tasks.values():
            summary = {
                "task_id": task.task_id,
                "title": task.title,
                "owner": task.owner.value,
                "deadline": task.deadline,
            }

            if task.status == TaskStatus.COMPLETED:
                done.append(summary)
            elif task.status == TaskStatus.BLOCKED:
                summary["blocked_by"] = task.blocked_by
                blocked.append(summary)
            elif task.status == TaskStatus.AWAITING_APPROVAL:
                awaiting_approval.append(summary)
            elif task.status == TaskStatus.PENDING:
                next_up.append(summary)

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total": len(self.tasks),
                "completed": len(done),
                "blocked": len(blocked),
                "awaiting_approval": len(awaiting_approval),
                "pending": len(next_up),
            },
            "done": done,
            "blocked": blocked,
            "awaiting_approval": awaiting_approval,
            "next": next_up[:5],  # Top 5 next tasks
        }

    # =========================================================================
    # Verification Functions
    # =========================================================================

    def _verify_checklist(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify pre-trade checklist passed."""
        try:
            from src.risk.pre_trade_checklist import PreTradeChecklist

            ticker = task.context.get("ticker", "SPY")
            params = task.context.get("parameters", {})

            passed, failures = PreTradeChecklist.validate(
                symbol=ticker,
                max_loss=params.get("max_loss", 500),
                dte=params.get("dte", 35),
                is_spread=True,
                stop_loss_defined=params.get("stop_loss_defined", True),
            )

            if passed:
                return True, "All 7 checklist items passed"
            else:
                return False, f"Checklist failures: {', '.join(failures)}"
        except Exception as e:
            return False, f"Checklist verification error: {e}"

    def _verify_smoke_tests(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify smoke tests passed."""
        try:
            from src.safety.pre_trade_smoke_test import run_smoke_tests

            result = run_smoke_tests()
            if result.all_passed:
                return True, "All 8 smoke tests passed"
            else:
                failures = []
                if not result.alpaca_connected:
                    failures.append("Alpaca connection failed")
                if not result.account_readable:
                    failures.append("Account not readable")
                if not result.buying_power_valid:
                    failures.append("Buying power invalid")
                return False, f"Smoke test failures: {', '.join(failures)}"
        except Exception as e:
            return False, f"Smoke test error: {e}"

    def _verify_gateway(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify TradeGateway approved the trade."""
        # Gateway approval is checked during execution
        # This verifies the approval was recorded
        gateway_result = context.get("gateway_result")
        if gateway_result and gateway_result.get("approved"):
            return True, "Gateway approved trade"
        return False, "Gateway did not approve trade"

    def _verify_position_opened(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify position was opened successfully."""
        position_id = context.get("position_id")
        if position_id:
            return True, f"Position opened: {position_id}"
        return False, "No position ID returned"

    def _verify_position_closed(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify position was closed successfully."""
        close_result = context.get("close_result")
        if close_result and close_result.get("success"):
            return True, "Position closed successfully"
        return False, "Position close failed"

    def _verify_rag_logged(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify trade was logged to RAG."""
        rag_id = context.get("rag_id")
        if rag_id:
            return True, f"Logged to RAG: {rag_id}"
        return False, "Not logged to RAG"

    def _verify_stop_loss(self, task: ActionableTask, context: dict) -> tuple[bool, str]:
        """Verify stop-loss was set."""
        stop_loss_set = context.get("stop_loss_set", False)
        if stop_loss_set:
            return True, "Stop-loss order/alert configured"
        return False, "Stop-loss not set - MANDATORY per CLAUDE.md"


# Singleton instance
_engine: Optional[ActionableTaskEngine] = None


def get_task_engine() -> ActionableTaskEngine:
    """Get or create the singleton task engine."""
    global _engine
    if _engine is None:
        _engine = ActionableTaskEngine()
    return _engine

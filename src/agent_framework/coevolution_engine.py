"""
Co-Evolution Engine: Manages symbiotic competition between Curriculum and Executor agents

Inspired by Agent0's co-evolution pattern:
- Curriculum Agent generates increasingly challenging tasks
- Executor Agent solves them using tools
- Both agents evolve through symbiotic competition
- System improves autonomously without human-curated datasets
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from .context import RunContext
from .curriculum_agent import (
    CurriculumAgent,
    TaskDifficulty,
    TaskPerformance,
    TradingTask,
)
from .executor_agent import ExecutorAgent, TaskSolution

logger = logging.getLogger(__name__)


class EvolutionStage(Enum):
    """Stages of the co-evolution process"""

    INITIALIZATION = "initialization"
    EXPLORATION = "exploration"  # Exploring capabilities
    EXPLOITATION = "exploitation"  # Exploiting learned patterns
    FRONTIER_PUSHING = "frontier_pushing"  # Pushing boundaries
    CONVERGENCE = "convergence"  # Converging to optimal performance


@dataclass
class EvolutionMetrics:
    """Metrics tracking evolution progress"""

    iteration: int
    stage: EvolutionStage
    tasks_generated: int
    tasks_solved: int
    success_rate: float
    avg_quality_score: float
    frontier_tasks_attempted: int
    frontier_tasks_solved: int
    capabilities_discovered: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class EvolutionHistory:
    """Complete evolution history"""

    start_time: str
    iterations: list[EvolutionMetrics] = field(default_factory=list)
    best_performance: EvolutionMetrics | None = None
    current_stage: EvolutionStage = EvolutionStage.INITIALIZATION


class CoEvolutionEngine:
    """
    Co-Evolution Engine: Manages symbiotic competition between agents.

    Key Responsibilities:
    1. Coordinate Curriculum and Executor agents
    2. Manage evolution cycles
    3. Track progress and adapt strategy
    4. Enable autonomous self-improvement
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        max_iterations: int = 100,
        tasks_per_iteration: int = 5,
    ):
        self.storage_dir = storage_dir or Path("data/agent_context/coevolution")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        self.max_iterations = max_iterations
        self.tasks_per_iteration = tasks_per_iteration

        # Initialize agents
        self.curriculum_agent = CurriculumAgent(storage_dir=self.storage_dir / "curriculum")
        self.executor_agent = ExecutorAgent(
            storage_dir=self.storage_dir / "executor",
            curriculum_agent=self.curriculum_agent,
        )

        # Evolution state
        self.current_iteration = 0
        self.evolution_history = EvolutionHistory(start_time=datetime.now().isoformat())
        self.current_stage = EvolutionStage.INITIALIZATION

        # Load history
        self._load_history()

        logger.info("✅ Co-Evolution Engine initialized")
        logger.info(f"   Iteration: {self.current_iteration}/{self.max_iterations}")
        logger.info(f"   Stage: {self.current_stage.value}")

    def evolve(self, context: RunContext) -> dict[str, Any]:
        """
        Execute one evolution cycle.

        Process:
        1. Curriculum Agent generates challenging tasks
        2. Executor Agent solves them
        3. Performance is evaluated
        4. Both agents adapt based on results
        5. Evolution metrics are updated
        """
        if self.current_iteration >= self.max_iterations:
            logger.warning("Max iterations reached")
            return {
                "status": "completed",
                "iteration": self.current_iteration,
                "message": "Max iterations reached",
            }

        self.current_iteration += 1
        logger.info(f"🔄 Evolution iteration {self.current_iteration}/{self.max_iterations}")

        # Generate tasks
        tasks: list[TradingTask] = []
        for _ in range(self.tasks_per_iteration):
            task_result = self.curriculum_agent.execute(context)
            if task_result.succeeded and "task" in task_result.payload:
                task = TradingTask.from_dict(task_result.payload["task"])
                tasks.append(task)

        logger.info(f"📚 Generated {len(tasks)} tasks")

        # Solve tasks
        solutions: list[TaskSolution] = []
        performances: list[TaskPerformance] = []

        for task in tasks:
            # Create context for executor
            executor_context = context.copy_with(
                config=context.config.copy_with(data={"task": task.to_dict()})
            )

            # Execute task
            executor_result = self.executor_agent.execute(executor_context)

            if executor_result.succeeded and "solution" in executor_result.payload:
                solution_data = executor_result.payload["solution"]
                solution = TaskSolution(**solution_data)
                solutions.append(solution)

            if executor_result.succeeded and "performance" in executor_result.payload:
                perf_data = executor_result.payload["performance"]
                performance = TaskPerformance(**perf_data)
                performances.append(performance)

        logger.info(f"✅ Solved {len(solutions)}/{len(tasks)} tasks")

        # Calculate metrics
        metrics = self._calculate_metrics(tasks, solutions, performances)

        # Update evolution stage
        self._update_evolution_stage(metrics)

        # Store metrics
        self.evolution_history.iterations.append(metrics)
        self._save_history()

        # Log progress
        logger.info(f"📊 Iteration {self.current_iteration} metrics:")
        logger.info(f"   Success rate: {metrics.success_rate:.2%}")
        logger.info(f"   Avg quality: {metrics.avg_quality_score:.2f}")
        logger.info(f"   Stage: {metrics.stage.value}")

        return {
            "status": "success",
            "iteration": self.current_iteration,
            "metrics": asdict(metrics),
            "tasks_generated": len(tasks),
            "tasks_solved": len(solutions),
        }

    def _calculate_metrics(
        self,
        tasks: list[TradingTask],
        solutions: list[TaskSolution],
        performances: list[TaskPerformance],
    ) -> EvolutionMetrics:
        """Calculate evolution metrics for this iteration"""
        tasks_solved = len(solutions)
        tasks_generated = len(tasks)

        # Success rate
        if performances:
            successful = sum(1 for p in performances if p.success)
            success_rate = successful / len(performances)
        else:
            success_rate = 0.0

        # Average quality score
        if performances:
            avg_quality = sum(p.quality_score for p in performances) / len(performances)
        else:
            avg_quality = 0.0

        # Frontier tasks
        frontier_tasks = [t for t in tasks if t.difficulty == TaskDifficulty.FRONTIER]
        frontier_attempted = len(frontier_tasks)
        frontier_solved = sum(
            1
            for p in performances
            if p.task_id in [t.task_id for t in frontier_tasks] and p.success
        )

        # Discovered capabilities
        capabilities = set()
        for solution in solutions:
            for tool_result in solution.tool_results:
                if tool_result.success:
                    capabilities.add(tool_result.tool_name)

        return EvolutionMetrics(
            iteration=self.current_iteration,
            stage=self.current_stage,
            tasks_generated=tasks_generated,
            tasks_solved=tasks_solved,
            success_rate=success_rate,
            avg_quality_score=avg_quality,
            frontier_tasks_attempted=frontier_attempted,
            frontier_tasks_solved=frontier_solved,
            capabilities_discovered=list(capabilities),
        )

    def _update_evolution_stage(self, metrics: EvolutionMetrics) -> None:
        """Update evolution stage based on metrics"""
        # Determine stage based on performance
        if self.current_iteration == 1:
            self.current_stage = EvolutionStage.INITIALIZATION
        elif metrics.success_rate < 0.5:
            self.current_stage = EvolutionStage.EXPLORATION
        elif metrics.success_rate >= 0.5 and metrics.avg_quality_score < 0.7:
            self.current_stage = EvolutionStage.EXPLOITATION
        elif metrics.frontier_tasks_attempted > 0:
            self.current_stage = EvolutionStage.FRONTIER_PUSHING
        elif metrics.success_rate >= 0.8 and metrics.avg_quality_score >= 0.8:
            self.current_stage = EvolutionStage.CONVERGENCE

        metrics.stage = self.current_stage
        self.evolution_history.current_stage = self.current_stage

        # Update best performance
        if not self.evolution_history.best_performance:
            self.evolution_history.best_performance = metrics
        else:
            best = self.evolution_history.best_performance
            if metrics.avg_quality_score > best.avg_quality_score:
                self.evolution_history.best_performance = metrics

    def get_evolution_summary(self) -> dict[str, Any]:
        """Get summary of evolution progress"""
        if not self.evolution_history.iterations:
            return {"status": "not_started", "iterations": 0}

        recent_metrics = self.evolution_history.iterations[-10:]

        return {
            "status": "active",
            "current_iteration": self.current_iteration,
            "max_iterations": self.max_iterations,
            "current_stage": self.current_stage.value,
            "total_tasks_generated": sum(
                m.tasks_generated for m in self.evolution_history.iterations
            ),
            "total_tasks_solved": sum(m.tasks_solved for m in self.evolution_history.iterations),
            "recent_success_rate": (
                sum(m.success_rate for m in recent_metrics) / len(recent_metrics)
                if recent_metrics
                else 0.0
            ),
            "recent_avg_quality": (
                sum(m.avg_quality_score for m in recent_metrics) / len(recent_metrics)
                if recent_metrics
                else 0.0
            ),
            "best_performance": (
                asdict(self.evolution_history.best_performance)
                if self.evolution_history.best_performance
                else None
            ),
        }

    def _save_history(self) -> None:
        """Save evolution history to disk"""
        history_file = self.storage_dir / "evolution_history.json"

        with open(history_file, "w") as f:
            json.dump(asdict(self.evolution_history), f, indent=2, default=str)

    def _load_history(self) -> None:
        """Load evolution history from disk"""
        history_file = self.storage_dir / "evolution_history.json"

        if not history_file.exists():
            return

        try:
            with open(history_file) as f:
                data = json.load(f)

            self.evolution_history = EvolutionHistory(**data)
            self.current_stage = EvolutionStage(self.evolution_history.current_stage)

            if self.evolution_history.iterations:
                self.current_iteration = self.evolution_history.iterations[-1].iteration

            logger.info(
                f"📚 Loaded evolution history: {len(self.evolution_history.iterations)} iterations"
            )

        except Exception as e:
            logger.warning(f"Failed to load evolution history: {e}")

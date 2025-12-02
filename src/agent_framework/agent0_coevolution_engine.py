"""
Agent0 Co-Evolution Engine: Manages symbiotic competition between Curriculum and Executor agents

The Co-Evolution Engine orchestrates the self-evolving loop:
1. Curriculum Agent generates challenging tasks
2. Executor Agent solves tasks using tools
3. Results feed back to Curriculum Agent to evolve difficulty
4. Both agents improve through this symbiotic competition

Inspired by: Agent0 paper (arXiv:2511.16043)
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from .agent0_curriculum_agent import CurriculumAgent, TaskDifficulty, TradingTask
from .agent0_executor_agent import ExecutionResult, ExecutorAgent

logger = logging.getLogger(__name__)


@dataclass
class EvolutionCycle:
    """A single co-evolution cycle"""

    cycle_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())
    finished_at: str | None = None

    # Cycle details
    task: TradingTask | None = None
    execution_result: ExecutionResult | None = None

    # Evolution metrics
    curriculum_difficulty_before: str | None = None
    curriculum_difficulty_after: str | None = None
    executor_capability_before: float = 0.0
    executor_capability_after: float = 0.0

    # Performance
    success: bool = False
    evolution_occurred: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary"""
        data = asdict(self)
        if self.task:
            data["task"] = self.task.to_dict()
        if self.execution_result:
            data["execution_result"] = self.execution_result.to_dict()
        return data


@dataclass
class CoEvolutionState:
    """State tracking for co-evolution"""

    total_cycles: int = 0
    successful_cycles: int = 0
    evolution_count: int = 0

    # Current state
    current_difficulty: TaskDifficulty = TaskDifficulty.BEGINNER
    executor_capability: float = 0.5

    # Performance tracking
    success_rate_history: list[float] = field(default_factory=list)
    capability_history: list[float] = field(default_factory=list)

    # Evolution milestones
    last_evolution: str | None = None
    difficulty_progression: list[tuple[str, str]] = field(
        default_factory=list
    )  # (timestamp, difficulty)

    def record_cycle(self, success: bool, capability: float, difficulty: TaskDifficulty):
        """Record a completed cycle"""
        self.total_cycles += 1
        if success:
            self.successful_cycles += 1

        self.executor_capability = capability
        self.current_difficulty = difficulty

        # Track history
        success_rate = self.successful_cycles / self.total_cycles if self.total_cycles > 0 else 0.0
        self.success_rate_history.append(success_rate)
        self.capability_history.append(capability)

        # Keep only recent history
        if len(self.success_rate_history) > 100:
            self.success_rate_history = self.success_rate_history[-100:]
        if len(self.capability_history) > 100:
            self.capability_history = self.capability_history[-100:]

    def record_evolution(self, from_difficulty: TaskDifficulty, to_difficulty: TaskDifficulty):
        """Record a difficulty evolution"""
        if from_difficulty != to_difficulty:
            self.evolution_count += 1
            self.last_evolution = datetime.now().isoformat()
            self.difficulty_progression.append((self.last_evolution, to_difficulty.value))
            logger.info(f"🔄 Evolution recorded: {from_difficulty.value} -> {to_difficulty.value}")


class CoEvolutionEngine:
    """
    Co-Evolution Engine: Orchestrates self-evolving agent system

    Responsibilities:
    1. Coordinate Curriculum and Executor agents
    2. Manage evolution cycles
    3. Track performance and evolution
    4. Enable autonomous improvement
    """

    def __init__(
        self,
        storage_dir: Path | None = None,
        curriculum_agent: CurriculumAgent | None = None,
        executor_agent: ExecutorAgent | None = None,
    ):
        """
        Initialize Co-Evolution Engine

        Args:
            storage_dir: Directory for storing evolution state
            curriculum_agent: Curriculum Agent instance (created if None)
            executor_agent: Executor Agent instance (created if None)
        """
        self.storage_dir = storage_dir or Path("data/agent_context/coevolution")
        self.storage_dir.mkdir(parents=True, exist_ok=True)

        # Initialize agents
        self.curriculum_agent = curriculum_agent or CurriculumAgent(
            storage_dir=self.storage_dir / "curriculum"
        )
        self.executor_agent = executor_agent or ExecutorAgent(
            storage_dir=self.storage_dir / "executor"
        )

        # Load evolution state
        self.state = self._load_state()

        # Cycle tracking
        self.current_cycle: EvolutionCycle | None = None
        self.cycle_history: list[EvolutionCycle] = []

        logger.info("✅ Co-Evolution Engine initialized")
        logger.info(f"   Current difficulty: {self.state.current_difficulty.value}")
        logger.info(f"   Executor capability: {self.state.executor_capability:.2f}")
        logger.info(f"   Total cycles: {self.state.total_cycles}")

    def run_evolution_cycle(
        self, category: str | None = None, symbols: list[str] | None = None
    ) -> EvolutionCycle:
        """
        Run a single co-evolution cycle

        Args:
            category: Optional task category
            symbols: Optional symbols to use

        Returns:
            EvolutionCycle with results
        """
        logger.info("🔄 Starting co-evolution cycle")

        # Create cycle
        cycle = EvolutionCycle()
        cycle.curriculum_difficulty_before = self.state.current_difficulty.value
        cycle.executor_capability_before = self.state.executor_capability

        try:
            # Step 1: Curriculum Agent generates task
            logger.info("📋 Curriculum Agent generating task...")
            task = self.curriculum_agent.generate_task(
                executor_capability=self.state.executor_capability,
                category=None,  # Will be set from category parameter if needed
                symbols=symbols,
            )
            cycle.task = task

            logger.info(f"   Generated: {task.title} ({task.difficulty.value})")

            # Step 2: Executor Agent solves task
            logger.info("🎯 Executor Agent solving task...")
            execution_result = self.executor_agent.execute_task(task)
            cycle.execution_result = execution_result

            logger.info(
                f"   Execution: {'✅' if execution_result.success else '❌'} (score: {execution_result.success_score:.2f})"
            )

            # Step 3: Record execution result with Curriculum Agent
            self.curriculum_agent.record_execution_result(
                task_id=task.task_id,
                result=execution_result.outputs,
                success_score=execution_result.success_score,
            )

            # Step 4: Update executor capability
            new_capability = self.executor_agent.get_capability_score()
            cycle.executor_capability_after = new_capability

            # Step 5: Check for evolution
            difficulty_before = self.state.current_difficulty
            self.state.current_difficulty = self.curriculum_agent.state.current_difficulty
            cycle.curriculum_difficulty_after = self.state.current_difficulty.value

            if difficulty_before != self.state.current_difficulty:
                cycle.evolution_occurred = True
                self.state.record_evolution(difficulty_before, self.state.current_difficulty)
                logger.info(
                    f"🔄 Evolution occurred: {difficulty_before.value} -> {self.state.current_difficulty.value}"
                )

            # Step 6: Update state
            cycle.success = execution_result.success
            self.state.record_cycle(
                success=execution_result.success,
                capability=new_capability,
                difficulty=self.state.current_difficulty,
            )

            # Step 7: Save state
            self._save_state()
            self._save_cycle(cycle)

            cycle.finished_at = datetime.now().isoformat()
            self.cycle_history.append(cycle)

            logger.info(
                f"✅ Cycle completed: success={cycle.success}, evolution={cycle.evolution_occurred}"
            )

        except Exception as e:
            logger.exception(f"❌ Cycle failed: {e}")
            cycle.success = False
            cycle.finished_at = datetime.now().isoformat()
            self._save_cycle(cycle)

        return cycle

    def run_evolution_loop(
        self, num_cycles: int = 10, min_cycles_before_evolution: int = 3
    ) -> list[EvolutionCycle]:
        """
        Run multiple evolution cycles

        Args:
            num_cycles: Number of cycles to run
            min_cycles_before_evolution: Minimum cycles before checking evolution

        Returns:
            List of completed cycles
        """
        logger.info(f"🚀 Starting evolution loop: {num_cycles} cycles")

        cycles = []
        for i in range(num_cycles):
            logger.info(f"\n{'=' * 60}")
            logger.info(f"Cycle {i + 1}/{num_cycles}")
            logger.info(f"{'=' * 60}")

            cycle = self.run_evolution_cycle()
            cycles.append(cycle)

            # Log progress
            if (i + 1) % min_cycles_before_evolution == 0:
                self._log_progress()

        # Final summary
        self._log_final_summary(cycles)

        return cycles

    def get_statistics(self) -> dict[str, Any]:
        """Get co-evolution statistics"""
        return {
            "total_cycles": self.state.total_cycles,
            "successful_cycles": self.state.successful_cycles,
            "success_rate": (
                self.state.successful_cycles / self.state.total_cycles
                if self.state.total_cycles > 0
                else 0.0
            ),
            "evolution_count": self.state.evolution_count,
            "current_difficulty": self.state.current_difficulty.value,
            "executor_capability": self.state.executor_capability,
            "last_evolution": self.state.last_evolution,
            "difficulty_progression": self.state.difficulty_progression[-10:],  # Last 10 evolutions
            "recent_success_rate": (
                self.state.success_rate_history[-10:] if self.state.success_rate_history else []
            ),
            "recent_capability": (
                self.state.capability_history[-10:] if self.state.capability_history else []
            ),
        }

    def _log_progress(self):
        """Log current progress"""
        stats = self.get_statistics()
        logger.info("\n📊 Progress Summary:")
        logger.info(f"   Cycles: {stats['total_cycles']}")
        logger.info(f"   Success Rate: {stats['success_rate']:.2%}")
        logger.info(f"   Current Difficulty: {stats['current_difficulty']}")
        logger.info(f"   Executor Capability: {stats['executor_capability']:.2f}")
        logger.info(f"   Evolutions: {stats['evolution_count']}")

    def _log_final_summary(self, cycles: list[EvolutionCycle]):
        """Log final summary after evolution loop"""
        successful = sum(1 for c in cycles if c.success)
        evolutions = sum(1 for c in cycles if c.evolution_occurred)

        logger.info("\n" + "=" * 60)
        logger.info("🎯 Evolution Loop Complete")
        logger.info("=" * 60)
        logger.info(f"Total Cycles: {len(cycles)}")
        logger.info(f"Successful: {successful} ({successful / len(cycles) * 100:.1f}%)")
        logger.info(f"Evolutions: {evolutions}")
        logger.info(f"Final Difficulty: {self.state.current_difficulty.value}")
        logger.info(f"Final Capability: {self.state.executor_capability:.2f}")
        logger.info("=" * 60)

    def _save_state(self):
        """Save evolution state to disk"""
        state_file = self.storage_dir / "evolution_state.json"

        state_dict = asdict(self.state)
        state_dict["current_difficulty"] = self.state.current_difficulty.value
        # Convert difficulty_progression tuples
        state_dict["difficulty_progression"] = [
            {"timestamp": t, "difficulty": d} for t, d in self.state.difficulty_progression
        ]

        with open(state_file, "w") as f:
            json.dump(state_dict, f, indent=2)

    def _load_state(self) -> CoEvolutionState:
        """Load evolution state from disk"""
        state_file = self.storage_dir / "evolution_state.json"

        if not state_file.exists():
            return CoEvolutionState()

        try:
            with open(state_file) as f:
                data = json.load(f)

            # Convert difficulty back to enum
            data["current_difficulty"] = TaskDifficulty(data["current_difficulty"])

            # Convert difficulty_progression
            difficulty_progression = [
                (entry["timestamp"], entry["difficulty"])
                for entry in data.get("difficulty_progression", [])
            ]
            data["difficulty_progression"] = difficulty_progression

            return CoEvolutionState(**data)
        except Exception as e:
            logger.warning(f"Failed to load evolution state: {e}")
            return CoEvolutionState()

    def _save_cycle(self, cycle: EvolutionCycle):
        """Save cycle to disk"""
        cycles_dir = self.storage_dir / "cycles"
        cycles_dir.mkdir(parents=True, exist_ok=True)

        cycle_file = cycles_dir / f"{cycle.cycle_id}.json"
        with open(cycle_file, "w") as f:
            json.dump(cycle.to_dict(), f, indent=2)

"""
Agent0 Integration: Wrapper for integrating Agent0 co-evolution system

Provides easy integration with Elite Orchestrator and other trading systems.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from .agent0_coevolution_engine import CoEvolutionEngine, EvolutionCycle
from .agent0_curriculum_agent import TaskCategory

logger = logging.getLogger(__name__)


class Agent0Integration:
    """
    Agent0 Integration: Wrapper for easy integration with trading systems

    Provides:
    1. Simple API for running evolution cycles
    2. Integration with Elite Orchestrator
    3. Statistics and monitoring
    """

    def __init__(self, storage_dir: Path | None = None, enabled: bool = True):
        """
        Initialize Agent0 Integration

        Args:
            storage_dir: Directory for storing evolution state
            enabled: Whether Agent0 is enabled
        """
        self.enabled = enabled

        if not enabled:
            logger.info("Agent0 Integration disabled")
            self.engine = None
            return

        try:
            self.engine = CoEvolutionEngine(storage_dir=storage_dir)
            logger.info("✅ Agent0 Integration initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Agent0: {e}")
            self.engine = None
            self.enabled = False

    def run_evolution_cycle(
        self, category: str | None = None, symbols: list[str] | None = None
    ) -> EvolutionCycle | None:
        """
        Run a single evolution cycle

        Args:
            category: Optional task category
            symbols: Optional symbols to use

        Returns:
            EvolutionCycle if successful, None otherwise
        """
        if not self.enabled or not self.engine:
            return None

        try:
            # Convert category string to enum if provided
            task_category = None
            if category:
                try:
                    task_category = TaskCategory(category)
                except ValueError:
                    logger.warning(f"Unknown category: {category}, using default")

            cycle = self.engine.run_evolution_cycle(
                category=task_category.value if task_category else None, symbols=symbols
            )

            return cycle
        except Exception as e:
            logger.error(f"Evolution cycle failed: {e}")
            return None

    def run_evolution_loop(self, num_cycles: int = 10) -> list[EvolutionCycle]:
        """
        Run multiple evolution cycles

        Args:
            num_cycles: Number of cycles to run

        Returns:
            List of completed cycles
        """
        if not self.enabled or not self.engine:
            return []

        try:
            cycles = self.engine.run_evolution_loop(num_cycles=num_cycles)
            return cycles
        except Exception as e:
            logger.error(f"Evolution loop failed: {e}")
            return []

    def get_statistics(self) -> dict[str, Any]:
        """Get Agent0 statistics"""
        if not self.enabled or not self.engine:
            return {"enabled": False, "status": "disabled"}

        try:
            stats = self.engine.get_statistics()
            stats["enabled"] = True
            return stats
        except Exception as e:
            logger.error(f"Failed to get statistics: {e}")
            return {"enabled": True, "status": "error", "error": str(e)}

    def is_ready(self) -> bool:
        """Check if Agent0 is ready to use"""
        return self.enabled and self.engine is not None

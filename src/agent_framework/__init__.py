"""
Agent framework scaffolding for the multi-agent trading system.

Exports base interfaces, run context dataclasses, state provider helpers,
and context engineering components.
"""

from . import agent_blueprints
from .base import AgentResult, TradingAgent
from .context import AgentConfig, RunContext, RunMode
from .context_engine import (
    ContextEngine,
    ContextMemory,
    ContextMessage,
    ContextPriority,
    ContextType,
    SemanticBlueprint,
    get_context_engine,
)
from .state import FileStateProvider, StateProvider

# Agent0 Co-Evolution components
try:
    from .coevolution_engine import CoEvolutionEngine, EvolutionMetrics, EvolutionStage
    from .curriculum_agent import (
        CurriculumAgent,
        TaskCategory,
        TaskDifficulty,
        TradingTask,
    )
    from .executor_agent import ExecutorAgent, TaskSolution
except ImportError:
    # Graceful degradation if dependencies missing
    CurriculumAgent = None
    TradingTask = None
    TaskDifficulty = None
    TaskCategory = None
    ExecutorAgent = None
    TaskSolution = None
    CoEvolutionEngine = None
    EvolutionStage = None
    EvolutionMetrics = None

__all__ = [
    "TradingAgent",
    "AgentResult",
    "RunContext",
    "RunMode",
    "AgentConfig",
    "StateProvider",
    "FileStateProvider",
    "ContextEngine",
    "SemanticBlueprint",
    "ContextMessage",
    "ContextMemory",
    "ContextType",
    "ContextPriority",
    "get_context_engine",
    "agent_blueprints",
    # Agent0 exports
    "CurriculumAgent",
    "TradingTask",
    "TaskDifficulty",
    "TaskCategory",
    "ExecutorAgent",
    "TaskSolution",
    "CoEvolutionEngine",
    "EvolutionStage",
    "EvolutionMetrics",
]

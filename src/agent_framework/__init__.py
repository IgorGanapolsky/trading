"""
Agent framework scaffolding for the multi-agent trading system.

Exports base interfaces, run context dataclasses, state provider helpers,
and context engineering components.

New in December 2025:
- Agent SDK integration with 1M context windows
- Sandboxing configuration for secure execution
- Extended context allocations per agent type
"""

from . import agent_blueprints
from .auditor import VolatilityAuditor
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

# Agent SDK Configuration (December 2025)
try:
    from .agent_sdk_config import (
        AgentSDKConfig,
        ContextWindowSize,
        SandboxMode,
        SandboxSettings,
        configure_agent_sdk,
        get_agent_sdk_config,
    )
except ImportError:
    # Graceful degradation
    AgentSDKConfig = None
    ContextWindowSize = None
    SandboxMode = None
    SandboxSettings = None
    get_agent_sdk_config = None
    configure_agent_sdk = None

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
    "VolatilityAuditor",
    # Agent SDK Configuration (December 2025)
    "AgentSDKConfig",
    "ContextWindowSize",
    "SandboxMode",
    "SandboxSettings",
    "get_agent_sdk_config",
    "configure_agent_sdk",
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

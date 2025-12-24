"""
Agent Framework Stubs

This module provides stub classes/functions for the deleted agent_framework module.
The original module was removed as dead code, but some imports remained.
These stubs ensure backward compatibility without the full framework.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

# Re-export from context_engine to maintain compatibility
from src.orchestration.context_engine import (
    ContextEngine,
    MemoryTimescale,
    get_context_engine,
)


class ContextType(Enum):
    """Context types for agent framework compatibility"""

    TASK_CONTEXT = "task_context"
    MARKET_CONTEXT = "market_context"
    AGENT_CONTEXT = "agent_context"
    SESSION_CONTEXT = "session_context"


class RunMode(Enum):
    """Execution modes for trading"""

    LIVE = "live"
    PAPER = "paper"
    BACKTEST = "backtest"
    DRY_RUN = "dry_run"


@dataclass
class RunContext:
    """Runtime context for agent execution"""

    mode: RunMode = RunMode.PAPER
    session_id: str = ""
    metadata: dict[str, Any] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


__all__ = [
    "ContextEngine",
    "ContextType",
    "MemoryTimescale",
    "RunContext",
    "RunMode",
    "get_context_engine",
]

"""
Trading orchestrator package - CLI entrypoint and hybrid funnel pipeline.

This module provides:
- TradingOrchestrator: Main CLI entry point with Momentum → RL → LLM → Risk gates
- BudgetController: Daily budget management
- FailureIsolationManager: Error handling and recovery
- OrchestratorTelemetry: Performance monitoring
- SREMonitor: Production-grade SRE-style monitoring

Note: This is distinct from src/orchestration/ which contains specialized
orchestrator implementations (Elite, MCP, Workflow). Both may be used together.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["TradingOrchestrator", "SREMonitor", "get_sre_monitor"]


def __getattr__(name: str) -> Any:
    if name == "TradingOrchestrator":
        module = import_module("src.orchestrator.main")
        return getattr(module, name)
    if name in ("SREMonitor", "get_sre_monitor"):
        module = import_module("src.orchestrator.sre_monitor")
        return getattr(module, name)
    raise AttributeError(f"module 'src.orchestrator' has no attribute {name}")

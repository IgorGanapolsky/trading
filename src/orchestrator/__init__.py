"""
Trading orchestrator package - CLI entrypoint and hybrid funnel pipeline.

This module provides:
- TradingOrchestrator: Main CLI entry point with Momentum → RL → LLM → Risk gates
- BudgetController: Daily budget management
- FailureIsolationManager: Error handling and recovery
- OrchestratorTelemetry: Performance monitoring

Note: This is distinct from src/orchestration/ which contains specialized
orchestrator implementations (Elite, MCP, Workflow). Both may be used together.
"""

from .main import TradingOrchestrator

__all__ = ["TradingOrchestrator"]

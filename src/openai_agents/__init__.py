"""
OpenAI Agents SDK integration layer for the trading system.

This package exposes:
- create_trading_agents(): returns a ready-to-run supervisor + sub-agents
- run_supervisor_sync(prompt): convenience entry point for quick experiments

All tooling lives in src/openai_agents/runtime.py.
"""

from .runtime import create_trading_agents, run_supervisor_sync

__all__ = ["create_trading_agents", "run_supervisor_sync"]

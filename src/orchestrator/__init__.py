"""
Trading orchestrator package.

Provides the CLI entrypoint and helper utilities for coordinating agents.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = ["TradingOrchestrator"]


def __getattr__(name: str) -> Any:
    if name == "TradingOrchestrator":
        module = import_module("src.orchestrator.main")
        return getattr(module, name)
    raise AttributeError(f"module 'src.orchestrator' has no attribute {name}")

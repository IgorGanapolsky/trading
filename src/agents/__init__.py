"""Agent package with lazy, optional imports.

The repo has tests that import lightweight submodules such as ``rag_webhook``
without installing every LLM SDK. Importing the package itself therefore must
not hard-fail on optional agent dependencies like ``anthropic``.
"""

from __future__ import annotations

import importlib
import logging
from typing import Any

logger = logging.getLogger(__name__)

__version__ = "2.0.0"

_LAZY_EXPORTS = {
    "BaseAgent": (".base_agent", "BaseAgent"),
    "ExecutionAgent": (".execution_agent", "ExecutionAgent"),
    "FundFlowAgent": (".fund_flow_agent", "FundFlowAgent"),
    "FundFlowSignal": (".fund_flow_agent", "FundFlowSignal"),
    "MacroeconomicAgent": (".macro_agent", "MacroeconomicAgent"),
    "MomentumAgent": (".momentum_agent", "MomentumAgent"),
    "MomentumSignal": (".momentum_agent", "MomentumSignal"),
    "PerplexityResearchAgent": (".research_agent", "PerplexityResearchAgent"),
    "RLFilter": (".rl_agent", "RLFilter"),
    "SandboxAgent": (".sandbox_agent", "SandboxAgent"),
    "SandboxCapabilities": (".sandbox_agent", "SandboxCapabilities"),
    "SandboxResult": (".sandbox_agent", "SandboxResult"),
}

_LAZY_SUBMODULES = {"rag_webhook"}

__all__ = [*_LAZY_EXPORTS.keys(), *_LAZY_SUBMODULES]


def __getattr__(name: str) -> Any:
    if name in _LAZY_EXPORTS:
        module_name, attr_name = _LAZY_EXPORTS[name]
        module = importlib.import_module(module_name, __name__)
        value = getattr(module, attr_name)
        globals()[name] = value
        return value

    if name in _LAZY_SUBMODULES:
        module = importlib.import_module(f".{name}", __name__)
        globals()[name] = module
        return module

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))

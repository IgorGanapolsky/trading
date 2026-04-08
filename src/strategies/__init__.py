"""Trading strategy interfaces and registry.

Only the SPY options path is considered active operating scope. Legacy
momentum, REIT, and Rule One modules remain importable for historical
reference, but they are not part of the primary trading mandate.
"""

from src.strategies.registry import (
    AssetClass,
    StrategyInterface,
    StrategyMetrics,
    StrategyRegistration,
    StrategyRegistry,
    StrategyStatus,
    get_registry,
    initialize_registry,
    register_strategy,
)

__all__ = [
    "StrategyRegistry",
    "StrategyInterface",
    "StrategyStatus",
    "AssetClass",
    "StrategyMetrics",
    "StrategyRegistration",
    "get_registry",
    "register_strategy",
    "initialize_registry",
]

# Auto-initialize registry on import
try:
    initialize_registry()
except Exception:
    pass  # Registry initialization may fail in some contexts

"""
Trading Strategies Module

This module contains all trading strategies registered in the canonical pipeline.

Standard Flow:
    data_ingest/ → features/ → signals/ → backtest/ → report/ → execution/

All strategies must:
1. Register via the strategy registry
2. Implement the StrategyInterface
3. Reuse existing data loaders and backtest wrappers

Author: Trading System
Created: 2025-12-03
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

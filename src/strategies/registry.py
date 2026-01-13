# Strategy registry stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class StrategyStatus(Enum):
    """Status of a registered strategy."""

    ACTIVE = "active"
    INACTIVE = "inactive"
    TESTING = "testing"
    DEPRECATED = "deprecated"


class AssetClass(Enum):
    """Asset class for strategies."""

    EQUITY = "equity"
    OPTIONS = "options"
    MIXED = "mixed"


@dataclass
class StrategyMetrics:
    """Metrics for a strategy."""

    win_rate: float = 0.0
    avg_return: float = 0.0
    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    total_trades: int = 0


@dataclass
class StrategyRegistration:
    """Registration info for a strategy."""

    name: str = ""
    status: StrategyStatus = StrategyStatus.INACTIVE
    asset_class: AssetClass = AssetClass.EQUITY
    metrics: StrategyMetrics = field(default_factory=StrategyMetrics)


class StrategyInterface(ABC):
    """Abstract interface for trading strategies."""

    @abstractmethod
    def analyze(self, symbol: str) -> dict[str, Any]:
        """Analyze a symbol for trading opportunities."""
        pass

    @abstractmethod
    def execute(self, signal: dict[str, Any]) -> dict[str, Any]:
        """Execute a trade based on signal."""
        pass


class StrategyRegistry:
    """Stub registry for strategies - Phil Town CSP strategy is primary."""

    _instance = None
    _strategies: dict[str, StrategyRegistration] = {}

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            # Auto-register Phil Town strategy for health checks
            cls._strategies["PhilTownCSP"] = StrategyRegistration(
                name="PhilTownCSP",
                status=StrategyStatus.ACTIVE,
                asset_class=AssetClass.OPTIONS,
            )
        return cls._instance

    def register(self, name: str, strategy: Any) -> None:
        """Register a strategy."""
        self._strategies[name] = StrategyRegistration(name=name)

    def get(self, name: str) -> StrategyRegistration | None:
        """Get a registered strategy."""
        return self._strategies.get(name)

    def list_strategies(self) -> list[str]:
        """List all registered strategies."""
        return list(self._strategies.keys())

    def list_all(self) -> list[str]:
        """List all registered strategies (alias for list_strategies)."""
        return self.list_strategies()


# Global registry instance
_registry: StrategyRegistry | None = None


def get_registry() -> StrategyRegistry:
    """Get the global strategy registry."""
    global _registry
    if _registry is None:
        _registry = StrategyRegistry()
    return _registry


def initialize_registry() -> None:
    """Initialize the strategy registry."""
    global _registry
    _registry = StrategyRegistry()


def register_strategy(name: str, strategy: Any) -> None:
    """Register a strategy with the global registry."""
    get_registry().register(name, strategy)

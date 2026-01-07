"""
Strategy Registry - Canonical Strategy Pipeline

This module provides a central registry for all trading strategies,
ensuring consistent interfaces and avoiding duplicate implementations.

Standard Flow:
    data_ingest/ → features/ → signals/ → backtest/ → report/ → execution/

Every strategy must:
1. Register via this registry
2. Implement the StrategyInterface
3. Reuse existing data loaders, feature modules, and backtest wrappers

Author: Trading System
Created: 2025-12-03
"""

from __future__ import annotations

import json
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class StrategyStatus(Enum):
    """Status of a registered strategy."""

    EXPERIMENTAL = "experimental"  # Still being developed/tested
    PAPER_TRADING = "paper_trading"  # Running in paper mode
    LIVE_TRADING = "live_trading"  # Running with real money
    DEPRECATED = "deprecated"  # No longer active
    CORE = "core"  # Productized, frozen strategy


class AssetClass(Enum):
    """Asset classes supported by strategies."""

    EQUITY = "equity"
    OPTIONS = "options"
    MIXED = "mixed"


@dataclass
class StrategyMetrics:
    """Performance metrics for a strategy."""

    sharpe_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_daily_pnl: float = 0.0
    total_return_pct: float = 0.0
    total_trades: int = 0
    backtest_date: str = ""
    backtest_period: str = ""
    hit_rate_100_day: float = 0.0  # % of days hitting $100 target

    def to_dict(self) -> dict[str, Any]:
        return {
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "win_rate": round(self.win_rate, 2),
            "avg_daily_pnl": round(self.avg_daily_pnl, 2),
            "total_return_pct": round(self.total_return_pct, 2),
            "total_trades": self.total_trades,
            "backtest_date": self.backtest_date,
            "backtest_period": self.backtest_period,
            "hit_rate_100_day": round(self.hit_rate_100_day, 2),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StrategyMetrics:
        return cls(
            sharpe_ratio=data.get("sharpe_ratio", 0.0),
            max_drawdown=data.get("max_drawdown", 0.0),
            win_rate=data.get("win_rate", 0.0),
            avg_daily_pnl=data.get("avg_daily_pnl", 0.0),
            total_return_pct=data.get("total_return_pct", 0.0),
            total_trades=data.get("total_trades", 0),
            backtest_date=data.get("backtest_date", ""),
            backtest_period=data.get("backtest_period", ""),
            hit_rate_100_day=data.get("hit_rate_100_day", 0.0),
        )


@dataclass
class StrategyRegistration:
    """Registration info for a strategy."""

    name: str
    description: str
    status: StrategyStatus
    asset_class: AssetClass
    strategy_class: type[Any] | None = None
    factory: Callable[[], Any] | None = None
    metrics: StrategyMetrics = field(default_factory=StrategyMetrics)
    config: dict[str, Any] = field(default_factory=dict)
    version: str = "1.0.0"
    author: str = "Trading System"
    created_date: str = ""
    last_modified: str = ""
    source_file: str = ""
    dependencies: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.created_date:
            self.created_date = datetime.now().strftime("%Y-%m-%d")
        if not self.last_modified:
            self.last_modified = self.created_date

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "asset_class": self.asset_class.value,
            "metrics": self.metrics.to_dict(),
            "config": self.config,
            "version": self.version,
            "author": self.author,
            "created_date": self.created_date,
            "last_modified": self.last_modified,
            "source_file": self.source_file,
            "dependencies": self.dependencies,
            "tags": self.tags,
        }


class StrategyInterface(ABC):
    """
    Base interface that all strategies must implement.

    This ensures consistent behavior across all strategies.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for the strategy."""
        pass

    @abstractmethod
    def generate_signals(self, data: Any) -> list[dict[str, Any]]:
        """
        Generate trading signals from input data.

        Args:
            data: Market data (DataFrame, dict, etc.)

        Returns:
            List of signal dictionaries with at minimum:
            - symbol: str
            - action: "buy" | "sell" | "hold"
            - strength: float (0-1)
        """
        pass

    @abstractmethod
    def get_config(self) -> dict[str, Any]:
        """Return strategy configuration."""
        pass

    def validate(self) -> bool:
        """Validate strategy is properly configured."""
        return True

    def get_metrics(self) -> StrategyMetrics:
        """Get current performance metrics."""
        return StrategyMetrics()


class StrategyRegistry:
    """
    Central registry for all trading strategies.

    Features:
    - Register strategies with metadata
    - Query strategies by status, asset class, tags
    - Track performance metrics
    - Generate registry reports
    - Persist to disk
    """

    _instance: StrategyRegistry | None = None
    _strategies: dict[str, StrategyRegistration] = {}
    _storage_path: Path = Path("config/strategy_registry.json")

    def __new__(cls) -> StrategyRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._strategies = {}
            cls._instance._load()
        return cls._instance

    def _load(self) -> None:
        """Load registry from disk."""
        if self._storage_path.exists():
            try:
                with open(self._storage_path) as f:
                    data = json.load(f)
                for name, info in data.get("strategies", {}).items():
                    reg = StrategyRegistration(
                        name=name,
                        description=info.get("description", ""),
                        status=StrategyStatus(info.get("status", "experimental")),
                        asset_class=AssetClass(info.get("asset_class", "equity")),
                        metrics=StrategyMetrics.from_dict(info.get("metrics", {})),
                        config=info.get("config", {}),
                        version=info.get("version", "1.0.0"),
                        author=info.get("author", "Trading System"),
                        created_date=info.get("created_date", ""),
                        last_modified=info.get("last_modified", ""),
                        source_file=info.get("source_file", ""),
                        dependencies=info.get("dependencies", []),
                        tags=info.get("tags", []),
                    )
                    self._strategies[name] = reg
                logger.info(f"Loaded {len(self._strategies)} strategies from registry")
            except Exception as e:
                logger.warning(f"Failed to load strategy registry: {e}")

    def _save(self) -> None:
        """Persist registry to disk."""
        self._storage_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "last_updated": datetime.now().isoformat(),
            "strategies": {name: reg.to_dict() for name, reg in self._strategies.items()},
        }
        with open(self._storage_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.debug(f"Saved strategy registry to {self._storage_path}")

    def register(
        self,
        name: str,
        description: str,
        status: StrategyStatus = StrategyStatus.EXPERIMENTAL,
        asset_class: AssetClass = AssetClass.EQUITY,
        strategy_class: type[Any] | None = None,
        factory: Callable[[], Any] | None = None,
        config: dict[str, Any] | None = None,
        source_file: str = "",
        tags: list[str] | None = None,
    ) -> StrategyRegistration:
        """
        Register a new strategy.

        Args:
            name: Unique strategy name
            description: Human-readable description
            status: Current status
            asset_class: Asset class traded
            strategy_class: Class implementing StrategyInterface
            factory: Factory function to create strategy instance
            config: Default configuration
            source_file: Path to source file
            tags: Tags for categorization

        Returns:
            StrategyRegistration object
        """
        if name in self._strategies:
            logger.warning(f"Updating existing strategy: {name}")

        reg = StrategyRegistration(
            name=name,
            description=description,
            status=status,
            asset_class=asset_class,
            strategy_class=strategy_class,
            factory=factory,
            config=config or {},
            source_file=source_file,
            tags=tags or [],
        )

        self._strategies[name] = reg
        self._save()

        logger.info(f"Registered strategy: {name} [{status.value}]")
        return reg

    def get(self, name: str) -> StrategyRegistration | None:
        """Get a strategy by name."""
        return self._strategies.get(name)

    def create(self, name: str, **kwargs: Any) -> Any:
        """
        Create a strategy instance.

        Args:
            name: Strategy name
            **kwargs: Additional arguments passed to factory/constructor

        Returns:
            Strategy instance
        """
        reg = self.get(name)
        if reg is None:
            raise ValueError(f"Strategy not found: {name}")

        if reg.factory:
            return reg.factory(**kwargs)
        elif reg.strategy_class:
            return reg.strategy_class(**kwargs)
        else:
            raise ValueError(f"Strategy {name} has no factory or class")

    def list_all(self) -> list[StrategyRegistration]:
        """List all registered strategies."""
        return list(self._strategies.values())

    def list_by_status(self, status: StrategyStatus) -> list[StrategyRegistration]:
        """List strategies by status."""
        return [s for s in self._strategies.values() if s.status == status]

    def list_by_asset_class(self, asset_class: AssetClass) -> list[StrategyRegistration]:
        """List strategies by asset class."""
        return [s for s in self._strategies.values() if s.asset_class == asset_class]

    def list_by_tag(self, tag: str) -> list[StrategyRegistration]:
        """List strategies by tag."""
        return [s for s in self._strategies.values() if tag in s.tags]

    def update_metrics(self, name: str, metrics: StrategyMetrics) -> None:
        """Update metrics for a strategy."""
        if name not in self._strategies:
            raise ValueError(f"Strategy not found: {name}")

        self._strategies[name].metrics = metrics
        self._strategies[name].last_modified = datetime.now().strftime("%Y-%m-%d")
        self._save()
        logger.info(f"Updated metrics for strategy: {name}")

    def set_status(self, name: str, status: StrategyStatus) -> None:
        """Change strategy status."""
        if name not in self._strategies:
            raise ValueError(f"Strategy not found: {name}")

        old_status = self._strategies[name].status
        self._strategies[name].status = status
        self._strategies[name].last_modified = datetime.now().strftime("%Y-%m-%d")
        self._save()
        logger.info(f"Changed status of {name}: {old_status.value} → {status.value}")

    def generate_report(self) -> str:
        """Generate a summary report of all strategies."""
        report = []
        report.append("=" * 80)
        report.append("STRATEGY REGISTRY REPORT")
        report.append("=" * 80)
        report.append(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append(f"Total Strategies: {len(self._strategies)}")
        report.append("")

        # Group by status
        for status in StrategyStatus:
            strategies = self.list_by_status(status)
            if strategies:
                report.append(f"{status.value.upper()} ({len(strategies)})")
                report.append("-" * 60)
                for s in strategies:
                    metrics = s.metrics
                    report.append(f"  {s.name}")
                    report.append(f"    Description: {s.description[:50]}...")
                    report.append(f"    Asset Class: {s.asset_class.value}")
                    if metrics.backtest_date:
                        report.append(f"    Last Backtest: {metrics.backtest_date}")
                        report.append(
                            f"    Sharpe: {metrics.sharpe_ratio:.2f} | Win Rate: {metrics.win_rate:.1f}%"
                        )
                        report.append(
                            f"    Avg Daily P&L: ${metrics.avg_daily_pnl:.2f} | $100 Hit Rate: {metrics.hit_rate_100_day:.1f}%"
                        )
                    report.append("")

        report.append("=" * 80)
        return "\n".join(report)

    def export_for_ci(self) -> dict[str, Any]:
        """Export data for CI/CD pipeline."""
        return {
            "timestamp": datetime.now().isoformat(),
            "strategies": {
                name: {
                    "status": reg.status.value,
                    "metrics": reg.metrics.to_dict(),
                    "source_file": reg.source_file,
                }
                for name, reg in self._strategies.items()
            },
        }


# Global registry instance
def get_registry() -> StrategyRegistry:
    """Get the global strategy registry."""
    return StrategyRegistry()


# Decorator for easy registration
def register_strategy(
    name: str,
    description: str = "",
    status: StrategyStatus = StrategyStatus.EXPERIMENTAL,
    asset_class: AssetClass = AssetClass.EQUITY,
    tags: list[str] | None = None,
) -> Callable[[type[Any]], type[Any]]:
    """
    Decorator to register a strategy class.

    Usage:
        @register_strategy("my_strategy", "My cool strategy")
        class MyStrategy(StrategyInterface):
            ...
    """

    def decorator(cls: type[Any]) -> type[Any]:
        registry = get_registry()
        registry.register(
            name=name,
            description=description or cls.__doc__ or "",
            status=status,
            asset_class=asset_class,
            strategy_class=cls,
            source_file=cls.__module__,
            tags=tags,
        )
        return cls

    return decorator


# Initialize with existing strategies
def initialize_registry() -> None:
    """Initialize registry with existing strategies."""
    registry = get_registry()

    # Register core strategies
    # NOTE: Only register strategies with existing source files (audit Jan 7, 2026)
    strategies_to_register = [
        {
            "name": "core_momentum",
            "description": "Core momentum-based ETF strategy with multi-timeframe analysis",
            "status": StrategyStatus.CORE,
            "asset_class": AssetClass.EQUITY,
            "source_file": "src/strategies/core_strategy.py",
            "tags": ["momentum", "etf", "daily"],
        },
        {
            "name": "rule_one_options",
            "description": "Phil Town Rule #1 options strategy for value investing",
            "status": StrategyStatus.PAPER_TRADING,
            "asset_class": AssetClass.OPTIONS,
            "source_file": "src/strategies/rule_one_options.py",
            "tags": ["options", "value", "rule1", "phil-town"],
        },
        {
            "name": "reit_strategy",
            "description": "REIT sector rotation strategy (Tier 7 - disabled by default)",
            "status": StrategyStatus.EXPERIMENTAL,
            "asset_class": AssetClass.EQUITY,
            "source_file": "src/strategies/reit_strategy.py",
            "tags": ["reit", "sector", "income"],
        },
        {
            "name": "precious_metals",
            "description": "Precious metals allocation strategy (disabled by default)",
            "status": StrategyStatus.EXPERIMENTAL,
            "asset_class": AssetClass.EQUITY,
            "source_file": "src/strategies/precious_metals_strategy.py",
            "tags": ["metals", "gold", "hedge"],
        },
        {
            "name": "legacy_momentum",
            "description": "Legacy momentum strategy (deprecated - use core_momentum)",
            "status": StrategyStatus.DEPRECATED,
            "asset_class": AssetClass.EQUITY,
            "source_file": "src/strategies/legacy_momentum.py",
            "tags": ["momentum", "legacy", "deprecated"],
        },
    ]

    for strat in strategies_to_register:
        if registry.get(strat["name"]) is None:
            registry.register(
                name=strat["name"],
                description=strat["description"],
                status=strat["status"],
                asset_class=strat["asset_class"],
                source_file=strat["source_file"],
                tags=strat["tags"],
            )

    logger.info(f"Initialized registry with {len(registry.list_all())} strategies")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    initialize_registry()
    registry = get_registry()
    print(registry.generate_report())

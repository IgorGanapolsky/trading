"""
Canonical Strategy Pipeline Registry

This module provides a single source of truth for all trading strategies in the system.
It prevents duplicate work by tracking what strategies exist, their status, and who's
working on them in which branches/PRs.

Author: Trading System
Created: 2025-12-03
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


class StrategyStatus(Enum):
    """Strategy lifecycle status."""

    CONCEPT = "concept"  # Initial idea, not implemented
    DEVELOPMENT = "development"  # Being developed in a branch
    BACKTESTED = "backtested"  # Has backtest results
    PAPER_TRADING = "paper_trading"  # Currently paper trading
    LIVE = "live"  # Deployed to live trading
    DEPRECATED = "deprecated"  # No longer in use
    FAILED = "failed"  # Tried and didn't work


class StrategyType(Enum):
    """Strategy classification."""

    MOMENTUM = "momentum"
    MEAN_REVERSION = "mean_reversion"
    BREAKOUT = "breakout"
    OPTIONS = "options"
    STATISTICAL_ARBITRAGE = "statistical_arbitrage"
    ML_BASED = "ml_based"
    HYBRID = "hybrid"
    OTHER = "other"


@dataclass
class BacktestMetrics:
    """Standard backtest metrics for strategy comparison."""

    start_date: str
    end_date: str
    total_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    avg_daily_pnl: float
    total_trades: int
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class StrategyRecord:
    """Complete record of a trading strategy."""

    # Identity
    strategy_id: str  # Unique identifier
    name: str  # Human-readable name
    description: str  # What the strategy does
    strategy_type: StrategyType

    # Implementation
    module_path: str  # Python module path (e.g., "src.strategies.momentum")
    class_name: str  # Class name (e.g., "MomentumStrategy")
    config_file: str | None = None  # Path to config file if exists

    # Status
    status: StrategyStatus = StrategyStatus.CONCEPT
    created_date: str = field(default_factory=lambda: datetime.now().isoformat())
    last_modified: str = field(default_factory=lambda: datetime.now().isoformat())

    # Development tracking
    branch: str | None = None  # Git branch where it's being developed
    pr_number: int | None = None  # Associated PR number
    assigned_to: str | None = None  # Who's working on it

    # Performance
    backtest_metrics: BacktestMetrics | None = None
    paper_trading_start: str | None = None
    live_trading_start: str | None = None

    # Dependencies
    data_sources: list[str] = field(default_factory=list)  # Required data sources
    features: list[str] = field(default_factory=list)  # Features used

    # Metadata
    tags: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "strategy_id": self.strategy_id,
            "name": self.name,
            "description": self.description,
            "strategy_type": self.strategy_type.value,
            "module_path": self.module_path,
            "class_name": self.class_name,
            "config_file": self.config_file,
            "status": self.status.value,
            "created_date": self.created_date,
            "last_modified": self.last_modified,
            "branch": self.branch,
            "pr_number": self.pr_number,
            "assigned_to": self.assigned_to,
            "backtest_metrics": (
                {
                    "start_date": self.backtest_metrics.start_date,
                    "end_date": self.backtest_metrics.end_date,
                    "total_return_pct": self.backtest_metrics.total_return_pct,
                    "sharpe_ratio": self.backtest_metrics.sharpe_ratio,
                    "max_drawdown_pct": self.backtest_metrics.max_drawdown_pct,
                    "win_rate_pct": self.backtest_metrics.win_rate_pct,
                    "avg_daily_pnl": self.backtest_metrics.avg_daily_pnl,
                    "total_trades": self.backtest_metrics.total_trades,
                    "last_updated": self.backtest_metrics.last_updated,
                }
                if self.backtest_metrics
                else None
            ),
            "paper_trading_start": self.paper_trading_start,
            "live_trading_start": self.live_trading_start,
            "data_sources": self.data_sources,
            "features": self.features,
            "tags": self.tags,
            "notes": self.notes,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "StrategyRecord":
        """Create StrategyRecord from dictionary."""
        backtest_data = data.get("backtest_metrics")
        backtest_metrics = None
        if backtest_data:
            backtest_metrics = BacktestMetrics(**backtest_data)

        return cls(
            strategy_id=data["strategy_id"],
            name=data["name"],
            description=data["description"],
            strategy_type=StrategyType(data["strategy_type"]),
            module_path=data["module_path"],
            class_name=data["class_name"],
            config_file=data.get("config_file"),
            status=StrategyStatus(data["status"]),
            created_date=data.get("created_date", datetime.now().isoformat()),
            last_modified=data.get("last_modified", datetime.now().isoformat()),
            branch=data.get("branch"),
            pr_number=data.get("pr_number"),
            assigned_to=data.get("assigned_to"),
            backtest_metrics=backtest_metrics,
            paper_trading_start=data.get("paper_trading_start"),
            live_trading_start=data.get("live_trading_start"),
            data_sources=data.get("data_sources", []),
            features=data.get("features", []),
            tags=data.get("tags", []),
            notes=data.get("notes", ""),
        )


class StrategyRegistry:
    """
    Central registry for all trading strategies.

    Provides:
    - Single source of truth for what strategies exist
    - Prevents duplicate work by showing what's in progress
    - Tracks performance metrics for comparison
    - Links strategies to branches/PRs
    - Enables rational decision making about which strategies to improve vs add

    Usage:
        registry = StrategyRegistry()

        # Register new strategy
        strategy = StrategyRecord(
            strategy_id="momentum_v1",
            name="Momentum Strategy V1",
            description="MACD + RSI + Volume momentum",
            strategy_type=StrategyType.MOMENTUM,
            module_path="src.strategies.legacy_momentum",
            class_name="MomentumStrategy",
        )
        registry.register(strategy)

        # Check if someone is already working on similar strategy
        existing = registry.find_by_type(StrategyType.MOMENTUM)

        # Update backtest results
        registry.update_backtest_metrics("momentum_v1", metrics)

        # Find best performing strategy
        best = registry.get_best_by_metric("sharpe_ratio")
    """

    def __init__(self, registry_file: str = "data/strategy_registry.json"):
        """Initialize strategy registry."""
        self.registry_file = Path(registry_file)
        self.strategies: dict[str, StrategyRecord] = {}
        self._load()

    def _load(self) -> None:
        """Load registry from disk."""
        if self.registry_file.exists():
            try:
                with open(self.registry_file) as f:
                    data = json.load(f)
                    self.strategies = {k: StrategyRecord.from_dict(v) for k, v in data.items()}
                logger.info(f"Loaded {len(self.strategies)} strategies from registry")
            except Exception as e:
                logger.error(f"Failed to load strategy registry: {e}")
                self.strategies = {}
        else:
            logger.info("No existing registry found, starting fresh")
            self._initialize_default_strategies()

    def _save(self) -> None:
        """Save registry to disk."""
        try:
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.registry_file, "w") as f:
                data = {k: v.to_dict() for k, v in self.strategies.items()}
                json.dump(data, f, indent=2)
            logger.info(f"Saved {len(self.strategies)} strategies to registry")
        except Exception as e:
            logger.error(f"Failed to save strategy registry: {e}")

    def register(self, strategy: StrategyRecord, allow_overwrite: bool = False) -> bool:
        """
        Register a new strategy.

        Args:
            strategy: Strategy record to register
            allow_overwrite: Allow overwriting existing strategy

        Returns:
            True if registered successfully, False if already exists
        """
        if strategy.strategy_id in self.strategies and not allow_overwrite:
            logger.warning(f"Strategy {strategy.strategy_id} already registered")
            return False

        strategy.last_modified = datetime.now().isoformat()
        self.strategies[strategy.strategy_id] = strategy
        self._save()
        logger.info(f"Registered strategy: {strategy.strategy_id}")
        return True

    def update_status(self, strategy_id: str, status: StrategyStatus) -> bool:
        """Update strategy status."""
        if strategy_id not in self.strategies:
            logger.error(f"Strategy {strategy_id} not found")
            return False

        self.strategies[strategy_id].status = status
        self.strategies[strategy_id].last_modified = datetime.now().isoformat()
        self._save()
        return True

    def update_backtest_metrics(self, strategy_id: str, metrics: BacktestMetrics) -> bool:
        """Update backtest metrics for a strategy."""
        if strategy_id not in self.strategies:
            logger.error(f"Strategy {strategy_id} not found")
            return False

        self.strategies[strategy_id].backtest_metrics = metrics
        self.strategies[strategy_id].last_modified = datetime.now().isoformat()

        # Auto-update status to backtested if not already
        if self.strategies[strategy_id].status == StrategyStatus.DEVELOPMENT:
            self.strategies[strategy_id].status = StrategyStatus.BACKTESTED

        self._save()
        return True

    def update_branch_info(
        self, strategy_id: str, branch: str, pr_number: int | None = None
    ) -> bool:
        """Update branch and PR information for a strategy."""
        if strategy_id not in self.strategies:
            logger.error(f"Strategy {strategy_id} not found")
            return False

        self.strategies[strategy_id].branch = branch
        self.strategies[strategy_id].pr_number = pr_number
        self.strategies[strategy_id].last_modified = datetime.now().isoformat()
        self._save()
        return True

    def find_by_type(self, strategy_type: StrategyType) -> list[StrategyRecord]:
        """Find all strategies of a given type."""
        return [s for s in self.strategies.values() if s.strategy_type == strategy_type]

    def find_by_status(self, status: StrategyStatus) -> list[StrategyRecord]:
        """Find all strategies with a given status."""
        return [s for s in self.strategies.values() if s.status == status]

    def find_in_development(self) -> list[StrategyRecord]:
        """Find strategies currently in development (have branch/PR)."""
        return [
            s for s in self.strategies.values() if s.branch is not None or s.pr_number is not None
        ]

    def get_best_by_metric(
        self, metric: str, min_status: StrategyStatus = StrategyStatus.BACKTESTED
    ) -> StrategyRecord | None:
        """
        Get best performing strategy by a specific metric.

        Args:
            metric: Metric name (sharpe_ratio, win_rate_pct, avg_daily_pnl, etc.)
            min_status: Minimum status required

        Returns:
            Best performing strategy or None
        """
        candidates = [
            s
            for s in self.strategies.values()
            if s.backtest_metrics is not None
            and self._status_rank(s.status) >= self._status_rank(min_status)
        ]

        if not candidates:
            return None

        return max(candidates, key=lambda s: getattr(s.backtest_metrics, metric, 0))

    def _status_rank(self, status: StrategyStatus) -> int:
        """Rank status for comparison."""
        ranking = {
            StrategyStatus.CONCEPT: 0,
            StrategyStatus.DEVELOPMENT: 1,
            StrategyStatus.BACKTESTED: 2,
            StrategyStatus.PAPER_TRADING: 3,
            StrategyStatus.LIVE: 4,
            StrategyStatus.DEPRECATED: -1,
            StrategyStatus.FAILED: -2,
        }
        return ranking.get(status, 0)

    def generate_report(self) -> str:
        """Generate human-readable report of all strategies."""
        lines = []
        lines.append("=" * 80)
        lines.append("STRATEGY REGISTRY REPORT")
        lines.append("=" * 80)
        lines.append(f"Total Strategies: {len(self.strategies)}")
        lines.append("")

        # Group by status
        by_status = {}
        for strategy in self.strategies.values():
            status = strategy.status.value
            if status not in by_status:
                by_status[status] = []
            by_status[status].append(strategy)

        for status_name, strategies in sorted(by_status.items()):
            lines.append(f"{status_name.upper()}: {len(strategies)}")
            for s in strategies:
                metrics_str = ""
                if s.backtest_metrics:
                    m = s.backtest_metrics
                    metrics_str = f" | Sharpe: {m.sharpe_ratio:.2f}, Win: {m.win_rate_pct:.1f}%, Daily P&L: ${m.avg_daily_pnl:.2f}"

                branch_str = f" [Branch: {s.branch}]" if s.branch else ""
                pr_str = f" [PR #{s.pr_number}]" if s.pr_number else ""

                lines.append(f"  • {s.name} ({s.strategy_id}){branch_str}{pr_str}{metrics_str}")
            lines.append("")

        # Best performers
        lines.append("TOP PERFORMERS:")
        best_sharpe = self.get_best_by_metric("sharpe_ratio")
        if best_sharpe and best_sharpe.backtest_metrics:
            lines.append(
                f"  • Best Sharpe: {best_sharpe.name} ({best_sharpe.backtest_metrics.sharpe_ratio:.2f})"
            )

        best_pnl = self.get_best_by_metric("avg_daily_pnl")
        if best_pnl and best_pnl.backtest_metrics:
            lines.append(
                f"  • Best Daily P&L: {best_pnl.name} (${best_pnl.backtest_metrics.avg_daily_pnl:.2f}/day)"
            )

        best_win_rate = self.get_best_by_metric("win_rate_pct")
        if best_win_rate and best_win_rate.backtest_metrics:
            lines.append(
                f"  • Best Win Rate: {best_win_rate.name} ({best_win_rate.backtest_metrics.win_rate_pct:.1f}%)"
            )

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)

    def _initialize_default_strategies(self) -> None:
        """Initialize registry with existing strategies from codebase."""
        # Core momentum strategy (currently in use)
        momentum_v1 = StrategyRecord(
            strategy_id="momentum_v1",
            name="Core Momentum Strategy",
            description="MACD + RSI + Volume momentum with multi-period returns",
            strategy_type=StrategyType.MOMENTUM,
            module_path="src.strategies.legacy_momentum",
            class_name="LegacyMomentumCalculator",
            status=StrategyStatus.PAPER_TRADING,
            paper_trading_start="2025-11-01",
            data_sources=["alpaca", "yfinance"],
            features=["macd", "rsi", "volume", "returns_1m", "returns_3m", "returns_6m"],
            tags=["core", "active", "etf"],
        )
        self.register(momentum_v1)

        # Options strategy
        options_v1 = StrategyRecord(
            strategy_id="options_rule1_v1",
            name="Phil Town Rule #1 Options",
            description="Rule #1 stock screening + options selling strategy",
            strategy_type=StrategyType.OPTIONS,
            module_path="src.strategies.rule_one_options",
            class_name="RuleOneOptionsStrategy",
            status=StrategyStatus.DEVELOPMENT,
            data_sources=["alpaca", "yahoo_finance"],
            features=["rule1_score", "moat", "management", "meaning", "margin_of_safety"],
            tags=["options", "premium_income", "rule1"],
        )
        self.register(options_v1)

        # Crypto weekend strategy
        crypto_v1 = StrategyRecord(
            strategy_id="crypto_weekend_v1",
            name="Weekend Crypto Momentum",
            description="Crypto momentum trading on weekends when equity markets closed",
            strategy_type=StrategyType.MOMENTUM,
            module_path="src.strategies.crypto_strategy",
            class_name="CryptoStrategy",
            status=StrategyStatus.PAPER_TRADING,
            paper_trading_start="2025-11-01",
            data_sources=["alpaca_crypto"],
            features=["momentum", "newsletter_signal"],
            tags=["crypto", "weekend", "btc", "eth"],
        )
        self.register(crypto_v1)

        self._save()
        logger.info("Initialized registry with default strategies")


# CLI interface
if __name__ == "__main__":
    import sys

    registry = StrategyRegistry()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "report":
            print(registry.generate_report())
        elif command == "list":
            for strategy_id, strategy in registry.strategies.items():
                print(f"{strategy_id}: {strategy.name} [{strategy.status.value}]")
        elif command == "best":
            metric = sys.argv[2] if len(sys.argv) > 2 else "sharpe_ratio"
            best = registry.get_best_by_metric(metric)
            if best:
                print(f"Best by {metric}: {best.name}")
                if best.backtest_metrics:
                    print(f"  Sharpe: {best.backtest_metrics.sharpe_ratio:.2f}")
                    print(f"  Win Rate: {best.backtest_metrics.win_rate_pct:.1f}%")
                    print(f"  Daily P&L: ${best.backtest_metrics.avg_daily_pnl:.2f}")
            else:
                print("No backtested strategies found")
        else:
            print(f"Unknown command: {command}")
            print("Available commands: report, list, best [metric]")
    else:
        print(registry.generate_report())

"""
ML Experiment Runner for Automated Trading Research.

Inspired by Anthropic's approach of running 1000+ ML experiments/day.
Enables systematic hyperparameter sweeps, backtests, and model comparisons.

Usage:
    from src.experiments import ExperimentRunner, HyperparameterGrid

    # Define parameter grid
    grid = HyperparameterGrid({
        "rsi_period": [7, 14, 21],
        "macd_fast": [8, 12, 16],
        "macd_slow": [21, 26, 31],
        "stop_loss_pct": [1.5, 2.0, 2.5, 3.0],
    })

    # Run sweep
    runner = ExperimentRunner()
    results = await runner.run_sweep(
        experiment_fn=backtest_strategy,
        grid=grid,
        parallel=True,
        max_workers=4,
    )

    # Analyze results
    best = runner.get_best_result(results, metric="sharpe_ratio")
    report = runner.generate_report(results)
"""

from __future__ import annotations

import asyncio
import hashlib
import itertools
import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class ExperimentStatus(Enum):
    """Status of an experiment."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"  # e.g., cached result exists


@dataclass
class HyperparameterGrid:
    """
    Define a grid of hyperparameters to sweep.

    Supports:
    - Grid search (all combinations)
    - Random search (sample N combinations)
    - Custom parameter dependencies
    """

    params: dict[str, list[Any]]
    dependencies: dict[str, Callable[[dict], list[Any]]] = field(default_factory=dict)

    def get_combinations(self, mode: str = "grid", n_samples: int = 100) -> list[dict[str, Any]]:
        """
        Generate parameter combinations.

        Args:
            mode: "grid" for full grid, "random" for random sampling
            n_samples: Number of samples for random mode
        """
        if mode == "grid":
            return self._grid_combinations()
        elif mode == "random":
            return self._random_combinations(n_samples)
        else:
            raise ValueError(f"Unknown mode: {mode}")

    def _grid_combinations(self) -> list[dict[str, Any]]:
        """Generate all grid combinations."""
        keys = list(self.params.keys())
        values = list(self.params.values())

        combinations = []
        for combo in itertools.product(*values):
            param_dict = dict(zip(keys, combo))

            # Apply dependencies
            for dep_key, dep_fn in self.dependencies.items():
                param_dict[dep_key] = dep_fn(param_dict)

            combinations.append(param_dict)

        return combinations

    def _random_combinations(self, n_samples: int) -> list[dict[str, Any]]:
        """Generate random combinations."""
        import random

        combinations = []
        for _ in range(n_samples):
            param_dict = {}
            for key, values in self.params.items():
                param_dict[key] = random.choice(values)

            # Apply dependencies
            for dep_key, dep_fn in self.dependencies.items():
                param_dict[dep_key] = dep_fn(param_dict)

            combinations.append(param_dict)

        return combinations

    @property
    def total_combinations(self) -> int:
        """Total number of grid combinations."""
        total = 1
        for values in self.params.values():
            total *= len(values)
        return total


@dataclass
class ExperimentResult:
    """Result of a single experiment."""

    experiment_id: str
    params: dict[str, Any]
    metrics: dict[str, float]
    status: ExperimentStatus

    # Timing
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_seconds: float = 0.0

    # Metadata
    error: Optional[str] = None
    artifacts: dict[str, str] = field(default_factory=dict)  # path to saved files
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "params": self.params,
            "metrics": self.metrics,
            "status": self.status.value,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "error": self.error,
            "artifacts": self.artifacts,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExperimentResult:
        return cls(
            experiment_id=data["experiment_id"],
            params=data["params"],
            metrics=data["metrics"],
            status=ExperimentStatus(data["status"]),
            start_time=datetime.fromisoformat(data["start_time"])
            if data.get("start_time")
            else None,
            end_time=datetime.fromisoformat(data["end_time"]) if data.get("end_time") else None,
            duration_seconds=data.get("duration_seconds", 0.0),
            error=data.get("error"),
            artifacts=data.get("artifacts", {}),
            tags=data.get("tags", []),
        )


@dataclass
class Experiment:
    """Definition of a single experiment to run."""

    experiment_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    params: dict[str, Any] = field(default_factory=dict)

    # Experiment function
    fn: Optional[Callable] = None
    fn_args: dict[str, Any] = field(default_factory=dict)

    # Caching
    cache_key: Optional[str] = None
    use_cache: bool = True

    def get_cache_key(self) -> str:
        """Generate cache key from params."""
        if self.cache_key:
            return self.cache_key

        # Hash params for cache key
        params_str = json.dumps(self.params, sort_keys=True)
        return hashlib.md5(params_str.encode()).hexdigest()[:12]


class ExperimentRunner:
    """
    Run ML experiments at scale.

    Features:
    - Parallel execution (threads or processes)
    - Result caching to skip completed experiments
    - Progress tracking and logging
    - Result aggregation and analysis
    - Automatic checkpointing
    """

    def __init__(
        self,
        storage_path: Optional[Path] = None,
        use_cache: bool = True,
        checkpoint_every: int = 10,
    ):
        self.storage_path = storage_path or Path("data/experiments")
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.use_cache = use_cache
        self.checkpoint_every = checkpoint_every

        self.results_file = self.storage_path / "experiment_results.jsonl"
        self.cache: dict[str, ExperimentResult] = {}

        self._load_cache()

        logger.info(f"ExperimentRunner initialized with {len(self.cache)} cached results")

    def _load_cache(self):
        """Load cached results from storage."""
        if not self.results_file.exists():
            return

        try:
            with open(self.results_file) as f:
                for line in f:
                    result = ExperimentResult.from_dict(json.loads(line))
                    if result.status == ExperimentStatus.COMPLETED:
                        cache_key = Experiment(params=result.params).get_cache_key()
                        self.cache[cache_key] = result
        except Exception as e:
            logger.warning(f"Failed to load cache: {e}")

    def _save_result(self, result: ExperimentResult):
        """Save a result to storage."""
        with open(self.results_file, "a") as f:
            f.write(json.dumps(result.to_dict()) + "\n")

    async def run_experiment(
        self,
        experiment: Experiment,
    ) -> ExperimentResult:
        """Run a single experiment."""
        cache_key = experiment.get_cache_key()

        # Check cache
        if self.use_cache and experiment.use_cache and cache_key in self.cache:
            cached = self.cache[cache_key]
            logger.debug(f"Using cached result for {experiment.experiment_id}")
            return ExperimentResult(
                experiment_id=experiment.experiment_id,
                params=experiment.params,
                metrics=cached.metrics,
                status=ExperimentStatus.SKIPPED,
                artifacts=cached.artifacts,
            )

        # Run experiment
        result = ExperimentResult(
            experiment_id=experiment.experiment_id,
            params=experiment.params,
            metrics={},
            status=ExperimentStatus.RUNNING,
            start_time=datetime.now(timezone.utc),
        )

        try:
            if experiment.fn is None:
                raise ValueError("No experiment function provided")

            # Run the function
            if asyncio.iscoroutinefunction(experiment.fn):
                metrics = await experiment.fn(experiment.params, **experiment.fn_args)
            else:
                metrics = experiment.fn(experiment.params, **experiment.fn_args)

            result.metrics = metrics
            result.status = ExperimentStatus.COMPLETED

        except Exception as e:
            result.status = ExperimentStatus.FAILED
            result.error = str(e)
            logger.error(f"Experiment {experiment.experiment_id} failed: {e}")

        finally:
            result.end_time = datetime.now(timezone.utc)
            result.duration_seconds = (result.end_time - result.start_time).total_seconds()

        # Cache successful results
        if result.status == ExperimentStatus.COMPLETED:
            self.cache[cache_key] = result
            self._save_result(result)

        return result

    async def run_sweep(
        self,
        experiment_fn: Callable,
        grid: HyperparameterGrid,
        mode: str = "grid",
        n_samples: int = 100,
        parallel: bool = True,
        max_workers: int = 4,
        fn_args: Optional[dict[str, Any]] = None,
        progress_callback: Optional[Callable[[int, int], None]] = None,
    ) -> list[ExperimentResult]:
        """
        Run a hyperparameter sweep.

        Args:
            experiment_fn: Function that takes params dict and returns metrics dict
            grid: HyperparameterGrid defining the search space
            mode: "grid" or "random"
            n_samples: Number of samples for random mode
            parallel: Whether to run experiments in parallel
            max_workers: Number of parallel workers
            fn_args: Additional arguments to pass to experiment_fn
            progress_callback: Called with (completed, total) for progress updates

        Returns:
            List of ExperimentResults
        """
        combinations = grid.get_combinations(mode=mode, n_samples=n_samples)
        total = len(combinations)

        logger.info(f"Starting sweep with {total} experiments (mode={mode}, parallel={parallel})")

        # Create experiments
        experiments = [
            Experiment(
                name=f"sweep_{i}",
                params=params,
                fn=experiment_fn,
                fn_args=fn_args or {},
            )
            for i, params in enumerate(combinations)
        ]

        # Run experiments
        results = []
        completed = 0

        if parallel:
            # Parallel execution
            semaphore = asyncio.Semaphore(max_workers)

            async def run_with_semaphore(exp):
                nonlocal completed
                async with semaphore:
                    result = await self.run_experiment(exp)
                    completed += 1
                    if progress_callback:
                        progress_callback(completed, total)
                    return result

            tasks = [run_with_semaphore(exp) for exp in experiments]
            results = await asyncio.gather(*tasks)
        else:
            # Sequential execution
            for exp in experiments:
                result = await self.run_experiment(exp)
                results.append(result)
                completed += 1
                if progress_callback:
                    progress_callback(completed, total)

                # Checkpoint
                if completed % self.checkpoint_every == 0:
                    logger.info(f"Checkpoint: {completed}/{total} experiments completed")

        logger.info(f"Sweep completed: {len(results)} results")
        return results

    def get_best_result(
        self,
        results: list[ExperimentResult],
        metric: str,
        maximize: bool = True,
    ) -> Optional[ExperimentResult]:
        """Get the best result by a specific metric."""
        valid_results = [
            r for r in results if r.status == ExperimentStatus.COMPLETED and metric in r.metrics
        ]

        if not valid_results:
            return None

        if maximize:
            return max(valid_results, key=lambda r: r.metrics[metric])
        else:
            return min(valid_results, key=lambda r: r.metrics[metric])

    def get_top_results(
        self,
        results: list[ExperimentResult],
        metric: str,
        n: int = 10,
        maximize: bool = True,
    ) -> list[ExperimentResult]:
        """Get top N results by a specific metric."""
        valid_results = [
            r for r in results if r.status == ExperimentStatus.COMPLETED and metric in r.metrics
        ]

        sorted_results = sorted(
            valid_results,
            key=lambda r: r.metrics[metric],
            reverse=maximize,
        )

        return sorted_results[:n]

    def analyze_param_importance(
        self,
        results: list[ExperimentResult],
        metric: str,
    ) -> dict[str, dict[str, float]]:
        """
        Analyze which parameters have the most impact on a metric.

        Returns dict mapping param -> {value -> avg_metric}
        """
        valid_results = [
            r for r in results if r.status == ExperimentStatus.COMPLETED and metric in r.metrics
        ]

        if not valid_results:
            return {}

        # Group by parameter values
        param_analysis = {}

        # Get all param keys
        all_params = set()
        for r in valid_results:
            all_params.update(r.params.keys())

        for param_key in all_params:
            value_metrics: dict[Any, list[float]] = {}

            for r in valid_results:
                value = r.params.get(param_key)
                if value is not None:
                    if value not in value_metrics:
                        value_metrics[value] = []
                    value_metrics[value].append(r.metrics[metric])

            # Calculate averages
            param_analysis[param_key] = {
                str(v): sum(metrics) / len(metrics) for v, metrics in value_metrics.items()
            }

        return param_analysis

    def generate_report(
        self,
        results: list[ExperimentResult],
        primary_metric: str = "sharpe_ratio",
    ) -> str:
        """Generate a text report of experiment results."""
        completed = [r for r in results if r.status == ExperimentStatus.COMPLETED]
        failed = [r for r in results if r.status == ExperimentStatus.FAILED]
        skipped = [r for r in results if r.status == ExperimentStatus.SKIPPED]

        lines = [
            "=" * 70,
            "ML EXPERIMENT SWEEP REPORT",
            f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}",
            "=" * 70,
            "",
            "SUMMARY",
            "-" * 40,
            f"  Total Experiments: {len(results)}",
            f"  Completed: {len(completed)}",
            f"  Failed: {len(failed)}",
            f"  Skipped (cached): {len(skipped)}",
            "",
        ]

        if completed:
            # Get all metrics
            all_metrics = set()
            for r in completed:
                all_metrics.update(r.metrics.keys())

            lines.extend(
                [
                    "METRIC RANGES",
                    "-" * 40,
                ]
            )

            for metric in sorted(all_metrics):
                values = [r.metrics[metric] for r in completed if metric in r.metrics]
                if values:
                    lines.append(
                        f"  {metric:20} min={min(values):.4f}  max={max(values):.4f}  "
                        f"avg={sum(values) / len(values):.4f}"
                    )

            lines.append("")

            # Top results
            top = self.get_top_results(completed, primary_metric, n=5)
            if top:
                lines.extend(
                    [
                        f"TOP 5 BY {primary_metric.upper()}",
                        "-" * 40,
                    ]
                )

                for i, r in enumerate(top, 1):
                    metric_val = r.metrics.get(primary_metric, 0)
                    params_str = ", ".join(f"{k}={v}" for k, v in list(r.params.items())[:3])
                    lines.append(f"  {i}. {primary_metric}={metric_val:.4f} | {params_str}")

                lines.append("")

            # Parameter importance
            importance = self.analyze_param_importance(completed, primary_metric)
            if importance:
                lines.extend(
                    [
                        "PARAMETER IMPACT",
                        "-" * 40,
                    ]
                )

                for param, values in importance.items():
                    if len(values) > 1:
                        sorted_values = sorted(values.items(), key=lambda x: x[1], reverse=True)
                        best_val, best_metric = sorted_values[0]
                        worst_val, worst_metric = sorted_values[-1]
                        impact = best_metric - worst_metric
                        lines.append(
                            f"  {param:20} impact={impact:+.4f} "
                            f"(best={best_val}, worst={worst_val})"
                        )

                lines.append("")

        if failed:
            lines.extend(
                [
                    "FAILED EXPERIMENTS",
                    "-" * 40,
                ]
            )
            for r in failed[:5]:
                lines.append(f"  {r.experiment_id}: {r.error[:50]}...")
            if len(failed) > 5:
                lines.append(f"  ... and {len(failed) - 5} more")
            lines.append("")

        # Timing
        total_time = sum(r.duration_seconds for r in results if r.duration_seconds)
        avg_time = total_time / len(completed) if completed else 0

        lines.extend(
            [
                "TIMING",
                "-" * 40,
                f"  Total Time: {total_time:.1f}s ({total_time / 60:.1f}m)",
                f"  Avg per Experiment: {avg_time:.2f}s",
                f"  Throughput: {len(completed) / max(total_time, 1) * 60:.1f} experiments/min",
                "",
                "=" * 70,
            ]
        )

        return "\n".join(lines)

    def export_results(
        self,
        results: list[ExperimentResult],
        output_path: Path,
        format: str = "json",
    ):
        """Export results to file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if format == "json":
            with open(output_path, "w") as f:
                json.dump([r.to_dict() for r in results], f, indent=2)
        elif format == "csv":
            import csv

            # Flatten results
            rows = []
            for r in results:
                row = {
                    "experiment_id": r.experiment_id,
                    "status": r.status.value,
                    "duration_seconds": r.duration_seconds,
                    **r.params,
                    **{f"metric_{k}": v for k, v in r.metrics.items()},
                }
                rows.append(row)

            if rows:
                with open(output_path, "w", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=rows[0].keys())
                    writer.writeheader()
                    writer.writerows(rows)

        logger.info(f"Exported {len(results)} results to {output_path}")


async def run_experiment_sweep(
    experiment_fn: Callable,
    params: dict[str, list[Any]],
    mode: str = "grid",
    n_samples: int = 100,
    parallel: bool = True,
    max_workers: int = 4,
) -> tuple[list[ExperimentResult], str]:
    """
    Convenience function to run a sweep and get report.

    Returns (results, report_text)
    """
    grid = HyperparameterGrid(params)
    runner = ExperimentRunner()

    results = await runner.run_sweep(
        experiment_fn=experiment_fn,
        grid=grid,
        mode=mode,
        n_samples=n_samples,
        parallel=parallel,
        max_workers=max_workers,
    )

    report = runner.generate_report(results)

    return results, report


# Trading-specific experiment functions


def create_backtest_experiment(
    strategy_class: Any,
    data_loader: Callable,
    start_date: str,
    end_date: str,
) -> Callable:
    """
    Create a backtest experiment function.

    Returns a function that takes params and returns metrics.
    """

    def run_backtest(params: dict[str, Any]) -> dict[str, float]:
        """Run backtest with given parameters."""
        # Load data
        data = data_loader(start_date, end_date)

        # Initialize strategy with params
        strategy = strategy_class(**params)

        # Run backtest (simplified)
        trades = []
        position = 0
        entry_price = 0

        for i, row in enumerate(data):
            signal = strategy.generate_signal(row)

            if signal == "BUY" and position == 0:
                position = 1
                entry_price = row["close"]
            elif signal == "SELL" and position == 1:
                profit_pct = (row["close"] - entry_price) / entry_price * 100
                trades.append(profit_pct)
                position = 0

        # Calculate metrics
        if not trades:
            return {
                "total_return": 0.0,
                "sharpe_ratio": 0.0,
                "win_rate": 0.0,
                "num_trades": 0,
                "max_drawdown": 0.0,
            }

        import math

        total_return = sum(trades)
        win_rate = len([t for t in trades if t > 0]) / len(trades)
        avg_return = total_return / len(trades)
        std_return = (
            math.sqrt(sum((t - avg_return) ** 2 for t in trades) / len(trades))
            if len(trades) > 1
            else 1
        )
        sharpe_ratio = avg_return / std_return if std_return > 0 else 0

        # Max drawdown
        cumulative = 0
        peak = 0
        max_drawdown = 0
        for t in trades:
            cumulative += t
            peak = max(peak, cumulative)
            drawdown = peak - cumulative
            max_drawdown = max(max_drawdown, drawdown)

        return {
            "total_return": total_return,
            "sharpe_ratio": sharpe_ratio,
            "win_rate": win_rate,
            "num_trades": len(trades),
            "max_drawdown": max_drawdown,
            "avg_profit": avg_return,
        }

    return run_backtest

"""
Automated Re-Optimization Scheduler

Schedules periodic, automated re-optimization using walk-forward methodology
with strict constraints to avoid data-mining. Every parameter change is treated
as a "new model version" with its own validation record.

Key Features:
1. Scheduled periodic re-optimization (weekly/monthly)
2. Walk-forward validation before accepting new parameters
3. Strict constraints to prevent overfitting
4. Model version tracking with validation records
5. Automatic rollback if new parameters underperform

Author: Trading System
Created: 2025-12-02
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class OptimizationFrequency(Enum):
    """Frequency of re-optimization."""

    WEEKLY = "weekly"
    BIWEEKLY = "biweekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


class OptimizationStatus(Enum):
    """Status of an optimization run."""

    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class ModelVersion:
    """Represents a version of the model with its parameters."""

    version_id: str
    created_at: str
    parameters: dict[str, Any]
    validation_results: dict[str, Any]
    is_active: bool = False
    superseded_by: str | None = None
    notes: str = ""


@dataclass
class OptimizationResult:
    """Result of an optimization run."""

    optimization_id: str
    timestamp: str
    frequency: str
    status: OptimizationStatus
    previous_version: str
    new_version: str | None
    validation_passed: bool
    validation_metrics: dict[str, Any]
    parameter_changes: dict[str, dict[str, float]]
    rollback_reason: str | None = None
    duration_seconds: float = 0.0


@dataclass
class SchedulerConfig:
    """Configuration for the re-optimization scheduler."""

    frequency: OptimizationFrequency = OptimizationFrequency.MONTHLY
    min_days_between_runs: int = 7
    walk_forward_windows: int = 4
    min_oos_sharpe: float = 0.8
    max_sharpe_decay: float = 0.5
    max_parameter_change_pct: float = 50.0  # Max 50% change in any parameter
    require_improvement: bool = True  # New params must improve on current
    min_improvement_pct: float = 5.0  # Minimum 5% improvement required
    auto_rollback_days: int = 30  # Days to monitor before confirming new params


class ReOptimizationScheduler:
    """
    Automated re-optimization scheduler with walk-forward validation.

    Implements strict constraints to prevent overfitting:
    1. Walk-forward validation must pass
    2. No single parameter can change by more than 50%
    3. New parameters must improve on current performance
    4. 30-day monitoring period before confirmation
    5. Automatic rollback if live performance deteriorates
    """

    def __init__(
        self,
        config: SchedulerConfig | None = None,
        state_file: str = "data/reoptimization_state.json",
        versions_file: str = "data/model_versions.json",
    ):
        self.config = config or SchedulerConfig()
        self.state_file = Path(state_file)
        self.versions_file = Path(versions_file)

        self.state = self._load_state()
        self.versions = self._load_versions()

        logger.info(
            f"ReOptimizationScheduler initialized: "
            f"frequency={self.config.frequency.value}, "
            f"min_days={self.config.min_days_between_runs}"
        )

    def should_run_optimization(self) -> tuple[bool, str]:
        """
        Check if re-optimization should run.

        Returns:
            Tuple of (should_run, reason)
        """
        last_run = self.state.get("last_optimization_run")

        if last_run is None:
            return True, "No previous optimization run found"

        last_run_date = datetime.fromisoformat(last_run)
        days_since_last = (datetime.now() - last_run_date).days

        if days_since_last < self.config.min_days_between_runs:
            return (
                False,
                f"Only {days_since_last} days since last run (min: {self.config.min_days_between_runs})",
            )

        # Check frequency
        freq_days = {
            OptimizationFrequency.WEEKLY: 7,
            OptimizationFrequency.BIWEEKLY: 14,
            OptimizationFrequency.MONTHLY: 30,
            OptimizationFrequency.QUARTERLY: 90,
        }

        required_days = freq_days.get(self.config.frequency, 30)

        if days_since_last >= required_days:
            return (
                True,
                f"{days_since_last} days since last run (frequency: {self.config.frequency.value})",
            )

        return False, f"Scheduled for {required_days - days_since_last} more days"

    def run_optimization(
        self,
        strategy_class: type,
        parameter_grid: dict[str, list],
        start_date: str,
        end_date: str,
    ) -> OptimizationResult:
        """
        Run a full re-optimization cycle.

        Args:
            strategy_class: Strategy class to optimize
            parameter_grid: Grid of parameters to search
            start_date: Start date for walk-forward evaluation
            end_date: End date for walk-forward evaluation

        Returns:
            OptimizationResult with outcome details
        """
        import time

        start_time = time.time()
        optimization_id = f"opt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Starting optimization {optimization_id}")

        # Get current active version
        current_version = self._get_active_version()
        current_params = current_version.parameters if current_version else {}

        try:
            # Run parameter search with walk-forward validation
            best_params, validation_metrics = self._search_parameters(
                strategy_class=strategy_class,
                parameter_grid=parameter_grid,
                start_date=start_date,
                end_date=end_date,
            )

            # Check if optimization passed validation
            validation_passed = self._check_validation_criteria(validation_metrics)

            if not validation_passed:
                duration = time.time() - start_time
                result = OptimizationResult(
                    optimization_id=optimization_id,
                    timestamp=datetime.now().isoformat(),
                    frequency=self.config.frequency.value,
                    status=OptimizationStatus.FAILED,
                    previous_version=current_version.version_id if current_version else "none",
                    new_version=None,
                    validation_passed=False,
                    validation_metrics=validation_metrics,
                    parameter_changes={},
                    duration_seconds=duration,
                )
                self._record_optimization(result)
                return result

            # Check parameter change constraints
            param_changes, within_bounds = self._check_parameter_bounds(current_params, best_params)

            if not within_bounds:
                duration = time.time() - start_time
                result = OptimizationResult(
                    optimization_id=optimization_id,
                    timestamp=datetime.now().isoformat(),
                    frequency=self.config.frequency.value,
                    status=OptimizationStatus.FAILED,
                    previous_version=current_version.version_id if current_version else "none",
                    new_version=None,
                    validation_passed=True,
                    validation_metrics=validation_metrics,
                    parameter_changes=param_changes,
                    rollback_reason="Parameter changes exceed maximum allowed bounds",
                    duration_seconds=duration,
                )
                self._record_optimization(result)
                return result

            # Check improvement requirement
            if self.config.require_improvement and current_version:
                current_sharpe = current_version.validation_results.get("mean_oos_sharpe", 0)
                new_sharpe = validation_metrics.get("mean_oos_sharpe", 0)
                improvement = (
                    (new_sharpe - current_sharpe) / current_sharpe * 100
                    if current_sharpe > 0
                    else 100
                )

                if improvement < self.config.min_improvement_pct:
                    duration = time.time() - start_time
                    result = OptimizationResult(
                        optimization_id=optimization_id,
                        timestamp=datetime.now().isoformat(),
                        frequency=self.config.frequency.value,
                        status=OptimizationStatus.FAILED,
                        previous_version=current_version.version_id,
                        new_version=None,
                        validation_passed=True,
                        validation_metrics=validation_metrics,
                        parameter_changes=param_changes,
                        rollback_reason=f"Improvement {improvement:.1f}% < minimum {self.config.min_improvement_pct}%",
                        duration_seconds=duration,
                    )
                    self._record_optimization(result)
                    return result

            # Create new model version
            new_version = self._create_model_version(best_params, validation_metrics)

            # Update state
            self.state["last_optimization_run"] = datetime.now().isoformat()
            self.state["pending_confirmation"] = {
                "version_id": new_version.version_id,
                "confirmation_date": (
                    datetime.now() + timedelta(days=self.config.auto_rollback_days)
                ).isoformat(),
            }
            self._save_state()

            duration = time.time() - start_time
            result = OptimizationResult(
                optimization_id=optimization_id,
                timestamp=datetime.now().isoformat(),
                frequency=self.config.frequency.value,
                status=OptimizationStatus.PASSED,
                previous_version=current_version.version_id if current_version else "none",
                new_version=new_version.version_id,
                validation_passed=True,
                validation_metrics=validation_metrics,
                parameter_changes=param_changes,
                duration_seconds=duration,
            )

            self._record_optimization(result)
            logger.info(
                f"Optimization {optimization_id} PASSED: "
                f"new version {new_version.version_id} created"
            )

            return result

        except Exception as e:
            duration = time.time() - start_time
            logger.error(f"Optimization {optimization_id} failed with error: {e}")
            result = OptimizationResult(
                optimization_id=optimization_id,
                timestamp=datetime.now().isoformat(),
                frequency=self.config.frequency.value,
                status=OptimizationStatus.FAILED,
                previous_version=current_version.version_id if current_version else "none",
                new_version=None,
                validation_passed=False,
                validation_metrics={"error": str(e)},
                parameter_changes={},
                rollback_reason=f"Exception: {str(e)}",
                duration_seconds=duration,
            )
            self._record_optimization(result)
            return result

    def check_pending_confirmation(self) -> dict[str, Any] | None:
        """
        Check if there's a pending version awaiting confirmation.

        After the monitoring period, compares live performance to expected
        and either confirms or rolls back the new version.

        Returns:
            Dict with confirmation status if there's a pending version
        """
        pending = self.state.get("pending_confirmation")
        if not pending:
            return None

        confirmation_date = datetime.fromisoformat(pending["confirmation_date"])
        version_id = pending["version_id"]

        if datetime.now() < confirmation_date:
            days_remaining = (confirmation_date - datetime.now()).days
            return {
                "status": "pending",
                "version_id": version_id,
                "days_remaining": days_remaining,
            }

        # Time to evaluate
        version = self._get_version(version_id)
        if not version:
            return {"status": "error", "message": f"Version {version_id} not found"}

        # Get live performance during monitoring period
        live_metrics = self._get_live_performance_metrics(version_id)

        if live_metrics is None:
            return {"status": "error", "message": "Could not retrieve live metrics"}

        # Compare to expected
        expected_sharpe = version.validation_results.get("mean_oos_sharpe", 0)
        live_sharpe = live_metrics.get("sharpe", 0)
        divergence = expected_sharpe - live_sharpe

        if divergence > self.config.max_sharpe_decay:
            # Rollback
            self._rollback_version(version_id, f"Live Sharpe divergence: {divergence:.2f}")
            del self.state["pending_confirmation"]
            self._save_state()

            return {
                "status": "rolled_back",
                "version_id": version_id,
                "reason": f"Live performance diverged by {divergence:.2f} Sharpe",
            }

        # Confirm
        version.notes += f"\nConfirmed on {datetime.now().isoformat()}"
        self._save_versions()
        del self.state["pending_confirmation"]
        self._save_state()

        logger.info(f"Version {version_id} confirmed after monitoring period")
        return {
            "status": "confirmed",
            "version_id": version_id,
            "live_sharpe": live_sharpe,
            "expected_sharpe": expected_sharpe,
        }

    def rollback_to_version(self, version_id: str, reason: str = "Manual rollback") -> bool:
        """
        Rollback to a specific version.

        Args:
            version_id: Version to rollback to
            reason: Reason for rollback

        Returns:
            True if rollback successful
        """
        return self._rollback_version(version_id, reason)

    def get_version_history(self) -> list[dict[str, Any]]:
        """Get history of all model versions."""
        return [
            {
                "version_id": v.version_id,
                "created_at": v.created_at,
                "is_active": v.is_active,
                "superseded_by": v.superseded_by,
                "mean_oos_sharpe": v.validation_results.get("mean_oos_sharpe", "N/A"),
                "notes": v.notes,
            }
            for v in self.versions.values()
        ]

    def get_active_parameters(self) -> dict[str, Any]:
        """Get currently active parameters."""
        version = self._get_active_version()
        if version:
            return version.parameters
        return {}

    def _search_parameters(
        self,
        strategy_class: type,
        parameter_grid: dict[str, list],
        start_date: str,
        end_date: str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """
        Search for optimal parameters using walk-forward validation.

        Returns:
            Tuple of (best_parameters, validation_metrics)
        """
        from src.backtesting.walk_forward_matrix import WalkForwardMatrixValidator

        validator = WalkForwardMatrixValidator()

        best_params = {}
        best_sharpe = float("-inf")
        best_metrics = {}

        # Simple grid search (could be enhanced with Bayesian optimization)
        import itertools

        param_names = list(parameter_grid.keys())
        param_values = list(parameter_grid.values())

        for combo in itertools.product(*param_values):
            params = dict(zip(param_names, combo, strict=False))

            try:
                results = validator.run_matrix_evaluation(
                    strategy_class=strategy_class,
                    strategy_params=params,
                    start_date=start_date,
                    end_date=end_date,
                )

                if results.passed_validation and results.mean_oos_sharpe > best_sharpe:
                    best_sharpe = results.mean_oos_sharpe
                    best_params = params
                    best_metrics = results.to_dict()

            except Exception as e:
                logger.warning(f"Parameter combo {params} failed: {e}")
                continue

        if not best_params:
            raise ValueError("No valid parameter combination found")

        return best_params, best_metrics

    def _check_validation_criteria(self, metrics: dict[str, Any]) -> bool:
        """Check if validation metrics meet criteria."""
        if not metrics:
            return False

        oos_sharpe = metrics.get("mean_oos_sharpe", 0)
        sharpe_decay = metrics.get("avg_sharpe_decay", float("inf"))

        return (
            oos_sharpe >= self.config.min_oos_sharpe
            and sharpe_decay <= self.config.max_sharpe_decay
        )

    def _check_parameter_bounds(
        self,
        current_params: dict[str, Any],
        new_params: dict[str, Any],
    ) -> tuple[dict[str, dict[str, float]], bool]:
        """
        Check if parameter changes are within allowed bounds.

        Returns:
            Tuple of (changes_dict, within_bounds)
        """
        changes = {}
        within_bounds = True

        for param, new_value in new_params.items():
            if param in current_params:
                current_value = current_params[param]
                if current_value != 0:
                    change_pct = abs(new_value - current_value) / abs(current_value) * 100
                else:
                    change_pct = 100 if new_value != 0 else 0

                changes[param] = {
                    "current": current_value,
                    "new": new_value,
                    "change_pct": change_pct,
                }

                if change_pct > self.config.max_parameter_change_pct:
                    within_bounds = False
                    logger.warning(
                        f"Parameter {param} change {change_pct:.1f}% exceeds max {self.config.max_parameter_change_pct}%"
                    )
            else:
                changes[param] = {
                    "current": None,
                    "new": new_value,
                    "change_pct": 100,  # New parameter
                }

        return changes, within_bounds

    def _create_model_version(
        self,
        parameters: dict[str, Any],
        validation_results: dict[str, Any],
    ) -> ModelVersion:
        """Create a new model version."""
        version_id = f"v{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        # Deactivate current active version
        current = self._get_active_version()
        if current:
            current.is_active = False
            current.superseded_by = version_id

        version = ModelVersion(
            version_id=version_id,
            created_at=datetime.now().isoformat(),
            parameters=parameters,
            validation_results=validation_results,
            is_active=True,
            notes="Created by automated re-optimization",
        )

        self.versions[version_id] = version
        self._save_versions()

        logger.info(f"Created model version {version_id}")
        return version

    def _get_active_version(self) -> ModelVersion | None:
        """Get currently active model version."""
        for version in self.versions.values():
            if version.is_active:
                return version
        return None

    def _get_version(self, version_id: str) -> ModelVersion | None:
        """Get a specific version."""
        return self.versions.get(version_id)

    def _rollback_version(self, version_id: str, reason: str) -> bool:
        """Rollback a version."""
        version = self._get_version(version_id)
        if not version:
            return False

        # Find previous version
        prev_version = None
        for v in self.versions.values():
            if v.superseded_by == version_id:
                prev_version = v
                break

        if prev_version:
            prev_version.is_active = True
            prev_version.superseded_by = None
            version.is_active = False
            version.notes += f"\nRolled back on {datetime.now().isoformat()}: {reason}"

        self._save_versions()

        logger.warning(f"Rolled back version {version_id}: {reason}")
        return True

    def _get_live_performance_metrics(self, version_id: str) -> dict[str, Any] | None:
        """Get live performance metrics for a version."""
        # In production, this would query actual trading results
        # For now, return placeholder
        try:
            from src.backtesting.walk_forward_matrix import LiveVsBacktestTracker

            tracker = LiveVsBacktestTracker()
            report = tracker.get_divergence_report("CoreStrategy")
            if "error" not in report:
                return {
                    "sharpe": report.get("avg_sharpe_divergence", 0),
                }
        except Exception:
            pass
        return None

    def _record_optimization(self, result: OptimizationResult) -> None:
        """Record optimization result."""
        if "optimization_history" not in self.state:
            self.state["optimization_history"] = []

        self.state["optimization_history"].append(
            {
                "optimization_id": result.optimization_id,
                "timestamp": result.timestamp,
                "status": result.status.value,
                "validation_passed": result.validation_passed,
                "new_version": result.new_version,
                "duration_seconds": result.duration_seconds,
            }
        )

        # Keep last 50 records
        self.state["optimization_history"] = self.state["optimization_history"][-50:]
        self._save_state()

    def _load_state(self) -> dict:
        """Load scheduler state."""
        if not self.state_file.exists():
            return {}
        try:
            with open(self.state_file) as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading scheduler state: {e}")
            return {}

    def _save_state(self) -> None:
        """Save scheduler state."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.state_file, "w") as f:
                json.dump(self.state, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving scheduler state: {e}")

    def _load_versions(self) -> dict[str, ModelVersion]:
        """Load model versions."""
        if not self.versions_file.exists():
            return {}
        try:
            with open(self.versions_file) as f:
                data = json.load(f)
            return {
                v_id: ModelVersion(
                    version_id=v_id,
                    created_at=v_data.get("created_at", ""),
                    parameters=v_data.get("parameters", {}),
                    validation_results=v_data.get("validation_results", {}),
                    is_active=v_data.get("is_active", False),
                    superseded_by=v_data.get("superseded_by"),
                    notes=v_data.get("notes", ""),
                )
                for v_id, v_data in data.items()
            }
        except Exception as e:
            logger.error(f"Error loading versions: {e}")
            return {}

    def _save_versions(self) -> None:
        """Save model versions."""
        try:
            self.versions_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                v_id: {
                    "created_at": v.created_at,
                    "parameters": v.parameters,
                    "validation_results": v.validation_results,
                    "is_active": v.is_active,
                    "superseded_by": v.superseded_by,
                    "notes": v.notes,
                }
                for v_id, v in self.versions.items()
            }
            with open(self.versions_file, "w") as f:
                json.dump(data, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Error saving versions: {e}")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    print("=" * 80)
    print("RE-OPTIMIZATION SCHEDULER")
    print("=" * 80)

    scheduler = ReOptimizationScheduler()

    # Check if optimization should run
    should_run, reason = scheduler.should_run_optimization()
    print(f"\nShould run optimization: {should_run}")
    print(f"Reason: {reason}")

    # Get version history
    history = scheduler.get_version_history()
    print(f"\nModel versions: {len(history)}")

    # Get active parameters
    params = scheduler.get_active_parameters()
    print(f"Active parameters: {params if params else 'None'}")

    print("\n" + "=" * 80)
    print("To run optimization:")
    print("\n  from src.strategies.core_strategy import CoreStrategy")
    print("  scheduler.run_optimization(")
    print("      strategy_class=CoreStrategy,")
    print("      parameter_grid={'daily_allocation': [5.0, 6.0, 7.0]},")
    print('      start_date="2023-01-01",')
    print('      end_date="2025-01-01",')
    print("  )")
    print("=" * 80)

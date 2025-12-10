"""
Experiment Tracking - Model Versioning and Experiment Management

This module provides a lightweight experiment tracking system for trading ML models:

1. Experiment Logging: Track code version, data snapshot, hyperparameters, metrics
2. Model Registry: Version and store trained models
3. Comparison Tools: Compare experiments and select best models
4. Reproducibility: Exact recreation of any experiment

Can optionally integrate with MLflow or Weights & Biases.

Author: Trading System
Created: 2025-12-02
"""

import hashlib
import json
import logging
import pickle
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class ExperimentConfig:
    """Configuration for an experiment."""

    name: str
    description: str = ""
    tags: list[str] = field(default_factory=list)
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    data_config: dict[str, Any] = field(default_factory=dict)
    model_config: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "tags": self.tags,
            "hyperparameters": self.hyperparameters,
            "data_config": self.data_config,
            "model_config": self.model_config,
        }


@dataclass
class ExperimentRun:
    """A single experiment run."""

    run_id: str
    experiment_name: str
    config: ExperimentConfig
    start_time: str
    end_time: str | None = None
    status: str = "running"  # running, completed, failed
    git_sha: str | None = None
    data_snapshot_id: str | None = None
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "experiment_name": self.experiment_name,
            "config": self.config.to_dict(),
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status": self.status,
            "git_sha": self.git_sha,
            "data_snapshot_id": self.data_snapshot_id,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "notes": self.notes,
        }


class ExperimentTracker:
    """
    Lightweight experiment tracking for trading ML models.

    Tracks:
    - Experiment configurations and hyperparameters
    - Training metrics (accuracy, Sharpe, drawdown, etc.)
    - Model artifacts and checkpoints
    - Code version (Git SHA) and data snapshots
    - Comparison across experiments

    Usage:
        tracker = ExperimentTracker()
        run = tracker.start_run("momentum_v1", config)
        tracker.log_metric("sharpe", 1.5)
        tracker.log_model(model, "momentum_lstm")
        tracker.end_run()
    """

    def __init__(
        self,
        tracking_dir: str = "data/experiments",
        use_mlflow: bool = False,
    ):
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.use_mlflow = use_mlflow
        self.current_run: ExperimentRun | None = None

        # Initialize MLflow if requested
        self._mlflow = None
        if use_mlflow:
            try:
                import mlflow

                self._mlflow = mlflow
                mlflow.set_tracking_uri(str(self.tracking_dir / "mlruns"))
                logger.info("MLflow tracking enabled")
            except ImportError:
                logger.warning("MLflow not installed, using basic tracking")
                self.use_mlflow = False

        # Load experiment registry
        self._registry_path = self.tracking_dir / "registry.json"
        self._registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        """Load experiment registry from disk."""
        if self._registry_path.exists():
            with open(self._registry_path) as f:
                return json.load(f)
        return {"experiments": {}, "runs": []}

    def _save_registry(self) -> None:
        """Save experiment registry to disk."""
        with open(self._registry_path, "w") as f:
            json.dump(self._registry, f, indent=2)

    def _get_git_sha(self) -> str | None:
        """Get current Git commit SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()[:8]
        except Exception:
            pass
        return None

    def start_run(
        self,
        experiment_name: str,
        config: ExperimentConfig,
        data_snapshot_id: str | None = None,
    ) -> ExperimentRun:
        """
        Start a new experiment run.

        Args:
            experiment_name: Name of the experiment
            config: Experiment configuration
            data_snapshot_id: Optional data snapshot ID for reproducibility

        Returns:
            ExperimentRun object
        """
        # Generate run ID
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_hash = hashlib.sha256(
            f"{experiment_name}{timestamp}{json.dumps(config.to_dict())}".encode()
        ).hexdigest()[:8]
        run_id = f"{experiment_name}_{timestamp}_{run_hash}"

        # Create run directory
        run_dir = self.tracking_dir / "runs" / run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        # Create run object
        run = ExperimentRun(
            run_id=run_id,
            experiment_name=experiment_name,
            config=config,
            start_time=datetime.now().isoformat(),
            git_sha=self._get_git_sha(),
            data_snapshot_id=data_snapshot_id,
        )

        self.current_run = run

        # Save initial run info
        self._save_run(run)

        # MLflow tracking
        if self.use_mlflow and self._mlflow:
            self._mlflow.set_experiment(experiment_name)
            self._mlflow.start_run(run_name=run_id)
            self._mlflow.log_params(config.hyperparameters)
            if config.tags:
                for tag in config.tags:
                    self._mlflow.set_tag(tag, "true")

        logger.info(f"Started experiment run: {run_id}")
        return run

    def log_metric(
        self,
        name: str,
        value: float,
        step: int | None = None,
    ) -> None:
        """
        Log a metric value.

        Args:
            name: Metric name
            value: Metric value
            step: Optional step number for time-series metrics
        """
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")

        self.current_run.metrics[name] = value
        self._save_run(self.current_run)

        if self.use_mlflow and self._mlflow:
            self._mlflow.log_metric(name, value, step=step)

        logger.debug(f"Logged metric: {name}={value}")

    def log_metrics(self, metrics: dict[str, float], step: int | None = None) -> None:
        """Log multiple metrics at once."""
        for name, value in metrics.items():
            self.log_metric(name, value, step)

    def log_model(
        self,
        model: Any,
        model_name: str,
        metadata: dict[str, Any] | None = None,
    ) -> str:
        """
        Save a trained model as an artifact.

        Args:
            model: Model object to save
            model_name: Name for the model
            metadata: Optional model metadata

        Returns:
            Path to saved model
        """
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")

        run_dir = self.tracking_dir / "runs" / self.current_run.run_id
        model_dir = run_dir / "models"
        model_dir.mkdir(exist_ok=True)

        # Save model
        model_path = model_dir / f"{model_name}.pkl"
        with open(model_path, "wb") as f:
            pickle.dump(model, f)

        # Save metadata
        if metadata:
            meta_path = model_dir / f"{model_name}_metadata.json"
            with open(meta_path, "w") as f:
                json.dump(metadata, f, indent=2)

        self.current_run.artifacts.append(str(model_path))
        self._save_run(self.current_run)

        if self.use_mlflow and self._mlflow:
            self._mlflow.log_artifact(str(model_path))

        logger.info(f"Saved model: {model_path}")
        return str(model_path)

    def log_artifact(self, artifact_path: str, artifact_name: str | None = None) -> None:
        """Log an arbitrary artifact file."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")

        run_dir = self.tracking_dir / "runs" / self.current_run.run_id
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        # Copy artifact to run directory
        import shutil

        src = Path(artifact_path)
        dst_name = artifact_name or src.name
        dst = artifacts_dir / dst_name

        shutil.copy2(src, dst)
        self.current_run.artifacts.append(str(dst))
        self._save_run(self.current_run)

        if self.use_mlflow and self._mlflow:
            self._mlflow.log_artifact(artifact_path)

    def log_dataframe(self, df: pd.DataFrame, name: str) -> None:
        """Log a DataFrame as a parquet artifact."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")

        run_dir = self.tracking_dir / "runs" / self.current_run.run_id
        artifacts_dir = run_dir / "artifacts"
        artifacts_dir.mkdir(exist_ok=True)

        path = artifacts_dir / f"{name}.parquet"
        df.to_parquet(path)
        self.current_run.artifacts.append(str(path))
        self._save_run(self.current_run)

    def add_note(self, note: str) -> None:
        """Add a note to the current run."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")

        self.current_run.notes += f"\n{datetime.now().isoformat()}: {note}"
        self._save_run(self.current_run)

    def end_run(self, status: str = "completed") -> None:
        """
        End the current run.

        Args:
            status: Run status (completed, failed)
        """
        if self.current_run is None:
            logger.warning("No active run to end")
            return

        self.current_run.end_time = datetime.now().isoformat()
        self.current_run.status = status
        self._save_run(self.current_run)

        # Update registry
        self._registry["runs"].append(self.current_run.to_dict())
        if self.current_run.experiment_name not in self._registry["experiments"]:
            self._registry["experiments"][self.current_run.experiment_name] = {
                "run_count": 0,
                "best_run_id": None,
                "best_sharpe": None,
            }
        self._registry["experiments"][self.current_run.experiment_name]["run_count"] += 1
        self._save_registry()

        if self.use_mlflow and self._mlflow:
            self._mlflow.end_run()

        logger.info(f"Ended run: {self.current_run.run_id} ({status})")
        self.current_run = None

    def _save_run(self, run: ExperimentRun) -> None:
        """Save run info to disk."""
        run_dir = self.tracking_dir / "runs" / run.run_id
        run_dir.mkdir(parents=True, exist_ok=True)

        with open(run_dir / "run_info.json", "w") as f:
            json.dump(run.to_dict(), f, indent=2)

    def load_run(self, run_id: str) -> ExperimentRun:
        """Load a run by ID."""
        run_dir = self.tracking_dir / "runs" / run_id
        with open(run_dir / "run_info.json") as f:
            data = json.load(f)

        return ExperimentRun(
            run_id=data["run_id"],
            experiment_name=data["experiment_name"],
            config=ExperimentConfig(**data["config"]),
            start_time=data["start_time"],
            end_time=data.get("end_time"),
            status=data.get("status", "completed"),
            git_sha=data.get("git_sha"),
            data_snapshot_id=data.get("data_snapshot_id"),
            metrics=data.get("metrics", {}),
            artifacts=data.get("artifacts", []),
            notes=data.get("notes", ""),
        )

    def load_model(self, run_id: str, model_name: str) -> Any:
        """Load a model from a run."""
        run_dir = self.tracking_dir / "runs" / run_id
        model_path = run_dir / "models" / f"{model_name}.pkl"

        with open(model_path, "rb") as f:
            return pickle.load(f)  # nosec B301  # noqa: S301 - Models are trusted internal artifacts

    def list_runs(
        self,
        experiment_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all runs, optionally filtered."""
        runs = self._registry.get("runs", [])

        if experiment_name:
            runs = [r for r in runs if r["experiment_name"] == experiment_name]

        if status:
            runs = [r for r in runs if r.get("status") == status]

        return sorted(runs, key=lambda x: x["start_time"], reverse=True)

    def compare_runs(
        self,
        run_ids: list[str],
        metrics: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        Compare multiple runs.

        Args:
            run_ids: List of run IDs to compare
            metrics: Optional list of metrics to include

        Returns:
            DataFrame with comparison
        """
        rows = []

        for run_id in run_ids:
            try:
                run = self.load_run(run_id)
                row = {
                    "run_id": run.run_id,
                    "experiment": run.experiment_name,
                    "status": run.status,
                    "start_time": run.start_time,
                }

                # Add metrics
                if metrics:
                    for m in metrics:
                        row[m] = run.metrics.get(m)
                else:
                    row.update(run.metrics)

                rows.append(row)
            except Exception as e:
                logger.warning(f"Could not load run {run_id}: {e}")

        return pd.DataFrame(rows)

    def get_best_run(
        self,
        experiment_name: str,
        metric: str = "sharpe",
        higher_is_better: bool = True,
    ) -> str | None:
        """
        Get the best run for an experiment by a metric.

        Args:
            experiment_name: Experiment name
            metric: Metric to optimize
            higher_is_better: Whether higher values are better

        Returns:
            Run ID of best run, or None
        """
        runs = self.list_runs(experiment_name=experiment_name, status="completed")

        if not runs:
            return None

        # Filter runs with the metric
        valid_runs = [r for r in runs if metric in r.get("metrics", {})]

        if not valid_runs:
            return None

        # Sort by metric
        sorted_runs = sorted(
            valid_runs,
            key=lambda x: x["metrics"].get(
                metric, float("-inf") if higher_is_better else float("inf")
            ),
            reverse=higher_is_better,
        )

        return sorted_runs[0]["run_id"]


class ModelRegistry:
    """
    Model registry for production deployment.

    Manages model versions, staging, and production deployments.
    """

    def __init__(self, registry_dir: str = "data/model_registry"):
        self.registry_dir = Path(registry_dir)
        self.registry_dir.mkdir(parents=True, exist_ok=True)
        self._registry_path = self.registry_dir / "registry.json"
        self._registry = self._load_registry()

    def _load_registry(self) -> dict[str, Any]:
        if self._registry_path.exists():
            with open(self._registry_path) as f:
                return json.load(f)
        return {"models": {}}

    def _save_registry(self) -> None:
        with open(self._registry_path, "w") as f:
            json.dump(self._registry, f, indent=2)

    def register_model(
        self,
        model_name: str,
        run_id: str,
        model_path: str,
        metrics: dict[str, float],
        stage: str = "staging",
    ) -> str:
        """
        Register a model version.

        Args:
            model_name: Model name
            run_id: Source experiment run ID
            model_path: Path to model file
            metrics: Model performance metrics
            stage: Deployment stage (staging, production, archived)

        Returns:
            Model version string
        """
        if model_name not in self._registry["models"]:
            self._registry["models"][model_name] = {
                "versions": [],
                "production_version": None,
            }

        # Generate version
        versions = self._registry["models"][model_name]["versions"]
        version_num = len(versions) + 1
        version = f"v{version_num}"

        # Copy model to registry
        src = Path(model_path)
        dst_dir = self.registry_dir / model_name / version
        dst_dir.mkdir(parents=True, exist_ok=True)
        dst = dst_dir / src.name

        import shutil

        shutil.copy2(src, dst)

        # Record version
        version_info = {
            "version": version,
            "run_id": run_id,
            "model_path": str(dst),
            "metrics": metrics,
            "stage": stage,
            "registered_at": datetime.now().isoformat(),
        }
        versions.append(version_info)
        self._save_registry()

        logger.info(f"Registered model: {model_name} {version} ({stage})")
        return version

    def promote_to_production(self, model_name: str, version: str) -> None:
        """Promote a model version to production."""
        if model_name not in self._registry["models"]:
            raise ValueError(f"Model not found: {model_name}")

        versions = self._registry["models"][model_name]["versions"]
        for v in versions:
            if v["version"] == version:
                v["stage"] = "production"
                self._registry["models"][model_name]["production_version"] = version
                break
            elif v["stage"] == "production":
                v["stage"] = "archived"

        self._save_registry()
        logger.info(f"Promoted {model_name} {version} to production")

    def get_production_model(self, model_name: str) -> str | None:
        """Get path to production model."""
        if model_name not in self._registry["models"]:
            return None

        prod_version = self._registry["models"][model_name].get("production_version")
        if not prod_version:
            return None

        for v in self._registry["models"][model_name]["versions"]:
            if v["version"] == prod_version:
                return v["model_path"]

        return None

    def list_models(self) -> list[dict[str, Any]]:
        """List all registered models."""
        result = []
        for name, info in self._registry["models"].items():
            result.append(
                {
                    "name": name,
                    "version_count": len(info["versions"]),
                    "production_version": info.get("production_version"),
                }
            )
        return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("EXPERIMENT TRACKING DEMO")
    print("=" * 80)

    # Initialize tracker
    tracker = ExperimentTracker(tracking_dir="data/experiments_demo")

    # Create experiment config
    config = ExperimentConfig(
        name="momentum_lstm",
        description="LSTM model for momentum prediction",
        tags=["lstm", "momentum", "v1"],
        hyperparameters={
            "hidden_dim": 128,
            "num_layers": 2,
            "learning_rate": 0.001,
            "epochs": 50,
            "sequence_length": 60,
        },
        data_config={
            "symbol": "SPY",
            "start_date": "2020-01-01",
            "end_date": "2024-01-01",
        },
    )

    # Start run
    run = tracker.start_run("momentum_lstm", config)
    print(f"\nStarted run: {run.run_id}")

    # Log some metrics
    tracker.log_metrics(
        {
            "train_loss": 0.025,
            "val_loss": 0.028,
            "test_accuracy": 0.58,
            "sharpe": 1.45,
            "max_drawdown": 0.12,
            "win_rate": 0.55,
        }
    )

    # Add note
    tracker.add_note("Initial baseline model - promising results")

    # End run
    tracker.end_run("completed")

    # List runs
    print("\nAll runs:")
    for run_info in tracker.list_runs():
        print(f"  {run_info['run_id']}: {run_info['status']}")
        print(f"    Metrics: {run_info.get('metrics', {})}")

    print("\n" + "=" * 80)

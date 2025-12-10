"""
Experiment tracking for trading research.

Logs experiments with code version, data snapshot, hyperparameters, and metrics.
"""

import json
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ExperimentConfig:
    """Configuration for an experiment run."""

    name: str
    description: str = ""
    hyperparameters: dict[str, Any] = field(default_factory=dict)
    data_snapshot_id: str | None = None
    tags: list[str] = field(default_factory=list)


@dataclass
class ExperimentRun:
    """A single experiment run with all metadata."""

    run_id: str
    experiment_name: str
    config: ExperimentConfig
    git_sha: str
    started_at: str
    ended_at: str | None = None
    status: str = "running"
    metrics: dict[str, float] = field(default_factory=dict)
    artifacts: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "experiment_name": self.experiment_name,
            "config": {
                "name": self.config.name,
                "description": self.config.description,
                "hyperparameters": self.config.hyperparameters,
                "data_snapshot_id": self.config.data_snapshot_id,
                "tags": self.config.tags,
            },
            "git_sha": self.git_sha,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "status": self.status,
            "metrics": self.metrics,
            "artifacts": self.artifacts,
            "notes": self.notes,
        }


class ExperimentTracker:
    """
    Track experiments for reproducibility.

    Example:
        >>> tracker = ExperimentTracker()
        >>> config = ExperimentConfig(name="momentum_v1", hyperparameters={"lookback": 20})
        >>> run = tracker.start_run("momentum", config)
        >>> tracker.log_metric("sharpe_ratio", 1.5)
        >>> tracker.log_metric("max_drawdown", -0.15)
        >>> tracker.end_run()
    """

    def __init__(self, tracking_dir: str = "experiments"):
        self.tracking_dir = Path(tracking_dir)
        self.tracking_dir.mkdir(parents=True, exist_ok=True)
        self.current_run: ExperimentRun | None = None

    def start_run(
        self,
        experiment_name: str,
        config: ExperimentConfig,
    ) -> ExperimentRun:
        """Start a new experiment run."""
        run_id = f"{experiment_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        git_sha = self._get_git_sha()

        self.current_run = ExperimentRun(
            run_id=run_id,
            experiment_name=experiment_name,
            config=config,
            git_sha=git_sha,
            started_at=datetime.now().isoformat(),
        )

        return self.current_run

    def log_metric(self, name: str, value: float) -> None:
        """Log a metric for the current run."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")
        self.current_run.metrics[name] = value

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """Log multiple metrics at once."""
        for name, value in metrics.items():
            self.log_metric(name, value)

    def log_artifact(self, path: str) -> None:
        """Log an artifact path for the current run."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")
        self.current_run.artifacts.append(path)

    def add_note(self, note: str) -> None:
        """Add a note to the current run."""
        if self.current_run is None:
            raise RuntimeError("No active run. Call start_run() first.")
        self.current_run.notes += note + "\n"

    def end_run(self, status: str = "completed") -> ExperimentRun:
        """End the current run and save it."""
        if self.current_run is None:
            raise RuntimeError("No active run to end.")

        self.current_run.ended_at = datetime.now().isoformat()
        self.current_run.status = status

        self._save_run(self.current_run)

        run = self.current_run
        self.current_run = None
        return run

    def _save_run(self, run: ExperimentRun) -> None:
        """Save run to disk."""
        run_dir = self.tracking_dir / run.experiment_name
        run_dir.mkdir(parents=True, exist_ok=True)

        run_file = run_dir / f"{run.run_id}.json"
        with open(run_file, "w") as f:
            json.dump(run.to_dict(), f, indent=2)

    def list_runs(
        self,
        experiment_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """List all runs, optionally filtered by experiment name."""
        runs = []

        if experiment_name:
            search_dirs = [self.tracking_dir / experiment_name]
        else:
            search_dirs = [d for d in self.tracking_dir.iterdir() if d.is_dir()]

        for exp_dir in search_dirs:
            if not exp_dir.exists():
                continue
            for run_file in exp_dir.glob("*.json"):
                with open(run_file) as f:
                    runs.append(json.load(f))

        return sorted(runs, key=lambda x: x["started_at"], reverse=True)

    def get_best_run(
        self,
        experiment_name: str,
        metric: str,
        maximize: bool = True,
    ) -> dict[str, Any] | None:
        """Get the best run for an experiment based on a metric."""
        runs = self.list_runs(experiment_name)

        valid_runs = [r for r in runs if metric in r.get("metrics", {})]
        if not valid_runs:
            return None

        return max(valid_runs, key=lambda x: x["metrics"][metric] * (1 if maximize else -1))

    def _get_git_sha(self) -> str:
        """Get current git SHA."""
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()[:8]
        except Exception:
            return "unknown"

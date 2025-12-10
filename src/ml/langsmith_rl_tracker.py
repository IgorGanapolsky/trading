"""
LangSmith RL Experiment Tracker

Provides comprehensive experiment tracking for RL training using LangSmith.

Features:
- Track training runs with hyperparameters
- Log episode metrics (reward, loss, etc.)
- Record trading decisions with context
- Evaluate model performance over time
- Compare experiments across runs

Integrates with:
- RLFilter (Gate 2)
- TransformerRLPolicy
- Cloud RL training jobs
- Uncertainty tracking (introspection)

Usage:
    from src.ml.langsmith_rl_tracker import RLExperimentTracker

    tracker = RLExperimentTracker()
    with tracker.track_episode("SPY") as episode:
        episode.log_step(state, action, reward)
        episode.log_metrics({"loss": 0.05, "entropy": 0.1})
"""

import json
import logging
import os
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Generator, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)

# Check LangSmith availability
try:
    from langsmith import Client, traceable  # noqa: F401
    from langsmith.run_helpers import get_current_run_tree  # noqa: F401

    LANGSMITH_AVAILABLE = True
except ImportError:
    LANGSMITH_AVAILABLE = False
    logger.warning("LangSmith not installed. RL experiment tracking disabled.")


@dataclass
class EpisodeMetrics:
    """Metrics for a single RL episode."""

    episode_id: str
    symbol: str
    start_time: str
    end_time: Optional[str] = None

    # Cumulative metrics
    total_reward: float = 0.0
    total_steps: int = 0
    actions_taken: dict[str, int] = field(default_factory=lambda: {"BUY": 0, "SELL": 0, "HOLD": 0})

    # Performance metrics
    avg_reward: float = 0.0
    max_reward: float = float("-inf")
    min_reward: float = float("inf")

    # Training metrics
    avg_loss: float = 0.0
    avg_entropy: float = 0.0
    avg_confidence: float = 0.0

    # Trading outcomes
    pnl: float = 0.0
    win_rate: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "episode_id": self.episode_id,
            "symbol": self.symbol,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "total_reward": self.total_reward,
            "total_steps": self.total_steps,
            "actions_taken": self.actions_taken,
            "avg_reward": self.avg_reward,
            "max_reward": self.max_reward if self.max_reward != float("-inf") else 0,
            "min_reward": self.min_reward if self.min_reward != float("inf") else 0,
            "avg_loss": self.avg_loss,
            "avg_entropy": self.avg_entropy,
            "avg_confidence": self.avg_confidence,
            "pnl": self.pnl,
            "win_rate": self.win_rate,
        }


class EpisodeTracker:
    """Tracks a single RL episode with LangSmith integration."""

    def __init__(
        self,
        episode_id: str,
        symbol: str,
        langsmith_client: Optional[Any] = None,
        parent_run_id: Optional[str] = None,
    ):
        self.episode_id = episode_id
        self.symbol = symbol
        self.langsmith_client = langsmith_client
        self.parent_run_id = parent_run_id

        self.metrics = EpisodeMetrics(
            episode_id=episode_id,
            symbol=symbol,
            start_time=datetime.now().isoformat(),
        )

        # Step tracking
        self.steps: list[dict[str, Any]] = []
        self._losses: list[float] = []
        self._entropies: list[float] = []
        self._confidences: list[float] = []

        # LangSmith run
        self._run_id: Optional[str] = None

    def log_step(
        self,
        state: dict[str, Any],
        action: str,
        reward: float,
        next_state: Optional[dict[str, Any]] = None,
        info: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log a single RL step.

        Args:
            state: Current state features
            action: Action taken ("BUY", "SELL", "HOLD")
            reward: Reward received
            next_state: Next state (optional)
            info: Additional info (optional)
        """
        step_data = {
            "step": self.metrics.total_steps,
            "action": action,
            "reward": reward,
            "timestamp": datetime.now().isoformat(),
        }

        if info:
            step_data["info"] = info

        self.steps.append(step_data)

        # Update metrics
        self.metrics.total_steps += 1
        self.metrics.total_reward += reward
        self.metrics.max_reward = max(self.metrics.max_reward, reward)
        self.metrics.min_reward = min(self.metrics.min_reward, reward)

        if action in self.metrics.actions_taken:
            self.metrics.actions_taken[action] += 1

        # Log to LangSmith
        if self.langsmith_client and self._run_id:
            try:
                self.langsmith_client.update_run(
                    self._run_id,
                    outputs={"current_step": self.metrics.total_steps},
                    extra={
                        "metadata": {
                            "total_reward": self.metrics.total_reward,
                            "action": action,
                        }
                    },
                )
            except Exception as e:
                logger.debug(f"LangSmith step update failed: {e}")

    def log_metrics(self, metrics: dict[str, float]) -> None:
        """
        Log training metrics for current step.

        Args:
            metrics: Dictionary of metric name -> value
        """
        if "loss" in metrics:
            self._losses.append(metrics["loss"])
        if "entropy" in metrics:
            self._entropies.append(metrics["entropy"])
        if "confidence" in metrics:
            self._confidences.append(metrics["confidence"])

    def log_trade(
        self,
        action: str,
        price: float,
        quantity: float,
        pnl: Optional[float] = None,
    ) -> None:
        """
        Log a trade execution.

        Args:
            action: Trade action
            price: Execution price
            quantity: Trade quantity
            pnl: Realized P/L (if closing)
        """
        trade_data = {
            "action": action,
            "price": price,
            "quantity": quantity,
            "pnl": pnl,
            "timestamp": datetime.now().isoformat(),
        }

        if pnl is not None:
            self.metrics.pnl += pnl

        # Log to LangSmith as a separate event
        if self.langsmith_client:
            try:
                self.langsmith_client.create_run(
                    name=f"trade_{action.lower()}",
                    run_type="tool",
                    inputs={"symbol": self.symbol, "action": action},
                    outputs=trade_data,
                    parent_run_id=self._run_id,
                )
            except Exception as e:
                logger.debug(f"LangSmith trade logging failed: {e}")

    def finalize(self) -> EpisodeMetrics:
        """Finalize episode and compute final metrics."""
        self.metrics.end_time = datetime.now().isoformat()

        # Compute averages
        if self.metrics.total_steps > 0:
            self.metrics.avg_reward = self.metrics.total_reward / self.metrics.total_steps

        if self._losses:
            self.metrics.avg_loss = sum(self._losses) / len(self._losses)
        if self._entropies:
            self.metrics.avg_entropy = sum(self._entropies) / len(self._entropies)
        if self._confidences:
            self.metrics.avg_confidence = sum(self._confidences) / len(self._confidences)

        # End LangSmith run
        if self.langsmith_client and self._run_id:
            try:
                self.langsmith_client.update_run(
                    self._run_id,
                    end_time=datetime.now(),
                    outputs=self.metrics.to_dict(),
                )
            except Exception as e:
                logger.debug(f"LangSmith run finalization failed: {e}")

        return self.metrics


class RLExperimentTracker:
    """
    Comprehensive RL experiment tracking with LangSmith integration.

    Tracks:
    - Training runs and hyperparameters
    - Episode metrics and rewards
    - Trading decisions and outcomes
    - Model performance over time
    """

    PROJECT_NAME = "trading-rl-experiments"

    def __init__(
        self,
        experiment_name: Optional[str] = None,
        enable_langsmith: bool = True,
    ):
        """
        Initialize experiment tracker.

        Args:
            experiment_name: Name for this experiment
            enable_langsmith: Enable LangSmith integration
        """
        self.experiment_name = experiment_name or f"rl_exp_{int(time.time())}"
        self.enable_langsmith = enable_langsmith and LANGSMITH_AVAILABLE

        # Initialize LangSmith
        self._langsmith_client: Optional[Any] = None
        if self.enable_langsmith:
            try:
                from langsmith import Client

                self._langsmith_client = Client()
                # Set project
                os.environ.setdefault("LANGCHAIN_PROJECT", self.PROJECT_NAME)
                logger.info(f"LangSmith tracking enabled (project={self.PROJECT_NAME})")
            except Exception as e:
                logger.warning(f"LangSmith initialization failed: {e}")
                self._langsmith_client = None

        # Local storage
        self.experiments_dir = Path("data/rl_experiments")
        self.experiments_dir.mkdir(parents=True, exist_ok=True)

        # Current experiment tracking
        self.run_id: Optional[str] = None
        self.episodes: list[EpisodeMetrics] = []
        self.start_time = datetime.now().isoformat()

    def start_run(
        self,
        algorithm: str,
        hyperparameters: dict[str, Any],
        metadata: Optional[dict[str, Any]] = None,
    ) -> str:
        """
        Start a new training run.

        Args:
            algorithm: RL algorithm name
            hyperparameters: Training hyperparameters
            metadata: Additional metadata

        Returns:
            Run ID
        """
        self.run_id = f"{self.experiment_name}_{uuid4().hex[:8]}"

        run_data = {
            "run_id": self.run_id,
            "experiment_name": self.experiment_name,
            "algorithm": algorithm,
            "hyperparameters": hyperparameters,
            "metadata": metadata or {},
            "start_time": datetime.now().isoformat(),
        }

        # Log to LangSmith
        if self._langsmith_client:
            try:
                self._langsmith_client.create_run(
                    name=self.run_id,
                    run_type="chain",
                    inputs=run_data,
                    extra={"metadata": {"type": "rl_training_run", **(metadata or {})}},
                )
            except Exception as e:
                logger.debug(f"LangSmith run creation failed: {e}")

        # Save locally
        self._save_run(run_data)

        logger.info(f"Started RL experiment run: {self.run_id}")
        return self.run_id

    @contextmanager
    def track_episode(self, symbol: str) -> Generator[EpisodeTracker, None, None]:
        """
        Context manager for tracking an episode.

        Args:
            symbol: Trading symbol

        Yields:
            EpisodeTracker for logging steps

        Example:
            with tracker.track_episode("SPY") as episode:
                episode.log_step(state, action, reward)
        """
        episode_id = f"{self.run_id or 'local'}_{symbol}_{uuid4().hex[:8]}"
        tracker = EpisodeTracker(
            episode_id=episode_id,
            symbol=symbol,
            langsmith_client=self._langsmith_client,
            parent_run_id=self.run_id,
        )

        # Start LangSmith episode run
        if self._langsmith_client:
            try:
                result = self._langsmith_client.create_run(
                    name=f"episode_{symbol}",
                    run_type="chain",
                    inputs={"symbol": symbol, "episode_id": episode_id},
                    parent_run_id=self.run_id,
                )
                tracker._run_id = result.id if hasattr(result, "id") else None
            except Exception as e:
                logger.debug(f"LangSmith episode start failed: {e}")

        try:
            yield tracker
        finally:
            metrics = tracker.finalize()
            self.episodes.append(metrics)
            self._save_episode(metrics)

    def log_decision(
        self,
        symbol: str,
        action: str,
        state: dict[str, Any],
        confidence: float,
        reasoning: Optional[str] = None,
        introspection: Optional[dict[str, Any]] = None,
    ) -> None:
        """
        Log a trading decision with full context.

        Args:
            symbol: Trading symbol
            action: Decision action
            state: Market state at decision time
            confidence: Decision confidence
            reasoning: Decision reasoning
            introspection: Introspection results (from Gate 3.5)
        """
        decision_data = {
            "symbol": symbol,
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "timestamp": datetime.now().isoformat(),
        }

        if introspection:
            decision_data["introspection"] = introspection

        # Log to LangSmith
        if self._langsmith_client:
            try:
                self._langsmith_client.create_run(
                    name=f"decision_{symbol}_{action.lower()}",
                    run_type="llm",
                    inputs={"state": state},
                    outputs=decision_data,
                    parent_run_id=self.run_id,
                    extra={
                        "metadata": {
                            "type": "trading_decision",
                            "symbol": symbol,
                            "action": action,
                        }
                    },
                )
            except Exception as e:
                logger.debug(f"LangSmith decision logging failed: {e}")

    def log_model_update(
        self,
        metrics: dict[str, float],
        weights_path: Optional[str] = None,
    ) -> None:
        """
        Log a model weight update.

        Args:
            metrics: Training metrics at update time
            weights_path: Path to saved weights
        """
        update_data = {
            "metrics": metrics,
            "weights_path": weights_path,
            "timestamp": datetime.now().isoformat(),
        }

        if self._langsmith_client:
            try:
                self._langsmith_client.create_run(
                    name="model_update",
                    run_type="tool",
                    inputs={"update_type": "weights"},
                    outputs=update_data,
                    parent_run_id=self.run_id,
                )
            except Exception as e:
                logger.debug(f"LangSmith model update logging failed: {e}")

    def end_run(self, final_metrics: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        End the current training run.

        Args:
            final_metrics: Final metrics to log

        Returns:
            Run summary
        """
        # Aggregate episode metrics
        total_episodes = len(self.episodes)
        total_steps = sum(e.total_steps for e in self.episodes)
        total_reward = sum(e.total_reward for e in self.episodes)
        avg_reward = total_reward / max(1, total_episodes)

        summary = {
            "run_id": self.run_id,
            "experiment_name": self.experiment_name,
            "total_episodes": total_episodes,
            "total_steps": total_steps,
            "total_reward": total_reward,
            "avg_reward_per_episode": avg_reward,
            "start_time": self.start_time,
            "end_time": datetime.now().isoformat(),
            "final_metrics": final_metrics or {},
        }

        # End LangSmith run
        if self._langsmith_client and self.run_id:
            try:
                self._langsmith_client.update_run(
                    self.run_id,
                    end_time=datetime.now(),
                    outputs=summary,
                )
            except Exception as e:
                logger.debug(f"LangSmith run end failed: {e}")

        # Save summary
        self._save_summary(summary)

        logger.info(
            f"RL experiment completed: {total_episodes} episodes, "
            f"{total_steps} steps, avg reward {avg_reward:.4f}"
        )

        return summary

    def get_experiment_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get recent experiment runs."""
        runs = []
        for run_file in sorted(self.experiments_dir.glob("*_summary.json"), reverse=True)[:limit]:
            try:
                with open(run_file) as f:
                    runs.append(json.load(f))
            except Exception:
                continue
        return runs

    def _save_run(self, run_data: dict[str, Any]) -> None:
        """Save run data locally."""
        run_file = self.experiments_dir / f"{self.run_id}_run.json"
        with open(run_file, "w") as f:
            json.dump(run_data, f, indent=2)

    def _save_episode(self, metrics: EpisodeMetrics) -> None:
        """Save episode metrics locally."""
        episode_file = self.experiments_dir / f"{metrics.episode_id}_episode.json"
        with open(episode_file, "w") as f:
            json.dump(metrics.to_dict(), f, indent=2)

    def _save_summary(self, summary: dict[str, Any]) -> None:
        """Save run summary locally."""
        summary_file = self.experiments_dir / f"{self.run_id}_summary.json"
        with open(summary_file, "w") as f:
            json.dump(summary, f, indent=2)


# Decorator for tracking RL functions
def track_rl_decision(func):
    """
    Decorator to track RL decision functions with LangSmith.

    Usage:
        @track_rl_decision
        def make_decision(state):
            return {"action": "BUY", "confidence": 0.8}
    """
    if not LANGSMITH_AVAILABLE:
        return func

    from langsmith import traceable

    @traceable(name=func.__name__, run_type="chain")
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)

    return wrapper


# Convenience function
def get_experiment_tracker(
    experiment_name: Optional[str] = None,
) -> RLExperimentTracker:
    """Get configured experiment tracker."""
    return RLExperimentTracker(experiment_name=experiment_name)

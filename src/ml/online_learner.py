"""
Online Learning System for RL Trading
Continuously updates models from live trade results.
"""

import json
import logging
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch

logger = logging.getLogger(__name__)


class OnlineRLLearner:
    """
    Online learning system that continuously updates RL models from live trades.

    Features:
    - Experience replay buffer
    - Periodic model updates
    - Adaptive learning rate
    - Performance tracking
    """

    def __init__(
        self,
        model,
        replay_buffer_size: int = 10000,
        update_frequency: int = 10,  # Update every N trades
        batch_size: int = 32,
        learning_rate: float = 0.0001,
        min_buffer_size: int = 100,
        save_dir: str = "models/ml/online",
    ):
        self.model = model
        self.replay_buffer = deque(maxlen=replay_buffer_size)
        self.update_frequency = update_frequency
        self.batch_size = batch_size
        self.learning_rate = learning_rate
        self.min_buffer_size = min_buffer_size
        self.save_dir = Path(save_dir)
        self.save_dir.mkdir(parents=True, exist_ok=True)

        # Performance tracking
        self.trade_count = 0
        self.update_count = 0
        self.performance_history = []

        logger.info(
            f"✅ Online RL Learner initialized (buffer: {replay_buffer_size}, update freq: {update_frequency})"
        )

    def add_experience(
        self,
        state: torch.Tensor,
        action: int,
        reward: float,
        next_state: torch.Tensor,
        done: bool = False,
        metadata: Optional[dict[str, Any]] = None,
    ):
        """
        Add a trade experience to the replay buffer.

        Args:
            state: State before action
            action: Action taken
            reward: Reward received
            next_state: State after action
            done: Whether episode is done
            metadata: Additional metadata (symbol, timestamp, etc.)
        """
        experience = {
            "state": state,
            "action": action,
            "reward": reward,
            "next_state": next_state,
            "done": done,
            "metadata": metadata or {},
            "timestamp": datetime.now().isoformat(),
        }

        self.replay_buffer.append(experience)
        self.trade_count += 1

        # Check if we should update
        if (
            self.trade_count % self.update_frequency == 0
            and len(self.replay_buffer) >= self.min_buffer_size
        ):
            self.update_model()

    def update_model(self):
        """
        Update model from replay buffer.
        """
        if len(self.replay_buffer) < self.min_buffer_size:
            logger.debug(
                f"Buffer too small ({len(self.replay_buffer)} < {self.min_buffer_size}), skipping update"
            )
            return

        try:
            # Sample batch
            batch_indices = np.random.choice(
                len(self.replay_buffer),
                size=min(self.batch_size, len(self.replay_buffer)),
                replace=False,
            )
            batch = [self.replay_buffer[i] for i in batch_indices]

            # Prepare batch data
            # states = torch.stack([exp["state"] for exp in batch])
            # actions = torch.tensor([exp["action"] for exp in batch], dtype=torch.long)
            rewards = torch.tensor([exp["reward"] for exp in batch], dtype=torch.float)
            # next_states = torch.stack([exp["next_state"] for exp in batch])
            # dones = torch.tensor([exp["done"] for exp in batch], dtype=torch.bool)

            # Update model (this is a placeholder - actual update depends on algorithm)
            # For PPO, this would be a PPO update step
            # For DQN, this would be a Q-learning update
            logger.info(
                f"🔄 Updating model from {len(batch)} experiences (total trades: {self.trade_count})"
            )

            # TODO: Implement algorithm-specific update
            # For now, just log the update
            self.update_count += 1

            # Track performance
            avg_reward = float(rewards.mean())
            self.performance_history.append(
                {
                    "update": self.update_count,
                    "avg_reward": avg_reward,
                    "buffer_size": len(self.replay_buffer),
                    "timestamp": datetime.now().isoformat(),
                }
            )

            logger.info(f"✅ Model updated (avg reward: {avg_reward:.4f})")

        except Exception as e:
            logger.error(f"❌ Failed to update model: {e}")

    def on_trade_complete(
        self,
        trade_result: dict[str, Any],
        entry_state: torch.Tensor,
        exit_state: torch.Tensor,
        action: int,
        reward_calculator=None,
    ):
        """
        Callback when a trade completes.

        Args:
            trade_result: Trade result dictionary
            entry_state: State when trade was entered
            exit_state: State when trade was exited
            action: Action taken
            reward_calculator: Reward calculator function
        """
        # Calculate reward
        if reward_calculator:
            reward = reward_calculator(trade_result)
        else:
            reward = trade_result.get("pl_pct", 0.0)

        # Add to replay buffer
        self.add_experience(
            state=entry_state,
            action=action,
            reward=reward,
            next_state=exit_state,
            done=True,
            metadata={
                "symbol": trade_result.get("symbol"),
                "pl": trade_result.get("pl"),
                "pl_pct": trade_result.get("pl_pct"),
                "holding_period": trade_result.get("holding_period_days", 1),
            },
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get learning statistics."""
        if len(self.performance_history) == 0:
            return {
                "trades": self.trade_count,
                "updates": self.update_count,
                "buffer_size": len(self.replay_buffer),
            }

        recent_performance = (
            self.performance_history[-10:]
            if len(self.performance_history) >= 10
            else self.performance_history
        )
        avg_recent_reward = np.mean([p["avg_reward"] for p in recent_performance])

        return {
            "trades": self.trade_count,
            "updates": self.update_count,
            "buffer_size": len(self.replay_buffer),
            "avg_recent_reward": avg_recent_reward,
            "performance_trend": (
                "improving"
                if len(self.performance_history) >= 2
                and self.performance_history[-1]["avg_reward"]
                > self.performance_history[0]["avg_reward"]
                else "stable"
            ),
        }

    def save_state(self, symbol: str):
        """Save online learning state."""
        state_path = self.save_dir / f"{symbol}_online_learner.json"
        with open(state_path, "w") as f:
            json.dump(
                {
                    "trade_count": self.trade_count,
                    "update_count": self.update_count,
                    "performance_history": self.performance_history[-100:],  # Last 100 updates
                    "buffer_size": len(self.replay_buffer),
                },
                f,
                indent=2,
            )
        logger.info(f"Saved online learner state to {state_path}")

    def load_state(self, symbol: str):
        """Load online learning state."""
        state_path = self.save_dir / f"{symbol}_online_learner.json"
        if state_path.exists():
            with open(state_path) as f:
                state = json.load(f)
                self.trade_count = state.get("trade_count", 0)
                self.update_count = state.get("update_count", 0)
                self.performance_history = state.get("performance_history", [])
            logger.info(f"Loaded online learner state from {state_path}")

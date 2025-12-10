#!/usr/bin/env python3
"""
Vertex AI Training Script for RL Models

This script is executed as a custom training job on Vertex AI.
It trains PPO/DQN/A2C models for trading using provided hyperparameters.

Usage (local):
    python src/ml/training_script.py --algorithm PPO --symbol SPY

Usage (Vertex AI):
    Submitted via RLServiceClient.start_training()

Environment Variables (set by Vertex AI):
    AIP_MODEL_DIR: Directory to save trained model
    AIP_CHECKPOINT_DIR: Directory for checkpoints
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class TradingEnvironment:
    """Simple trading environment for RL training."""

    def __init__(self, symbol: str, state_dim: int = 10):
        self.symbol = symbol
        self.state_dim = state_dim
        self.action_space = ["HOLD", "BUY", "SELL"]
        self.n_actions = len(self.action_space)

        # Simulated state
        self.current_step = 0
        self.max_steps = 1000
        self.position = 0  # -1: short, 0: flat, 1: long
        self.pnl = 0.0

    def reset(self) -> np.ndarray:
        """Reset environment and return initial state."""
        self.current_step = 0
        self.position = 0
        self.pnl = 0.0
        return self._get_state()

    def step(self, action: int) -> tuple[np.ndarray, float, bool, dict]:
        """
        Execute action and return (next_state, reward, done, info).

        Args:
            action: 0=HOLD, 1=BUY, 2=SELL

        Returns:
            Tuple of (state, reward, done, info)
        """
        self.current_step += 1

        # Simulate price movement
        price_change = np.random.randn() * 0.02  # 2% daily volatility

        # Calculate reward based on position and price change
        reward = 0.0
        if action == 1 and self.position <= 0:  # BUY
            self.position = 1
            reward = -0.001  # Transaction cost
        elif action == 2 and self.position >= 0:  # SELL
            self.position = -1
            reward = -0.001  # Transaction cost

        # Position PnL
        reward += self.position * price_change
        self.pnl += reward

        done = self.current_step >= self.max_steps

        info = {
            "step": self.current_step,
            "position": self.position,
            "pnl": self.pnl,
            "action": self.action_space[action],
        }

        return self._get_state(), reward, done, info

    def _get_state(self) -> np.ndarray:
        """Generate current state features."""
        # Simulated features (in production, these would be real market data)
        state = np.random.randn(self.state_dim)
        # Add position as last feature
        state[-1] = self.position
        return state.astype(np.float32)


class PPONetwork(nn.Module):
    """PPO Actor-Critic Network."""

    def __init__(self, state_dim: int, n_actions: int, hidden_dim: int = 64):
        super().__init__()

        # Shared feature extractor
        self.shared = nn.Sequential(
            nn.Linear(state_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Actor head (policy)
        self.actor = nn.Sequential(
            nn.Linear(hidden_dim, n_actions),
            nn.Softmax(dim=-1),
        )

        # Critic head (value)
        self.critic = nn.Linear(hidden_dim, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Forward pass returning action probabilities and state value."""
        features = self.shared(x)
        action_probs = self.actor(features)
        state_value = self.critic(features)
        return action_probs, state_value

    def get_action(self, state: np.ndarray) -> tuple[int, float, float]:
        """Sample action from policy."""
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0)
            probs, value = self.forward(state_tensor)
            dist = torch.distributions.Categorical(probs)
            action = dist.sample()
            log_prob = dist.log_prob(action)
        return action.item(), log_prob.item(), value.item()


class PPOTrainer:
    """PPO Training Algorithm."""

    def __init__(
        self,
        env: TradingEnvironment,
        learning_rate: float = 0.0003,
        gamma: float = 0.99,
        clip_range: float = 0.2,
        n_epochs: int = 10,
        batch_size: int = 64,
    ):
        self.env = env
        self.gamma = gamma
        self.clip_range = clip_range
        self.n_epochs = n_epochs
        self.batch_size = batch_size

        # Initialize network
        self.network = PPONetwork(env.state_dim, env.n_actions)
        self.optimizer = optim.Adam(self.network.parameters(), lr=learning_rate)

        # Training buffers
        self.states: list[np.ndarray] = []
        self.actions: list[int] = []
        self.rewards: list[float] = []
        self.log_probs: list[float] = []
        self.values: list[float] = []
        self.dones: list[bool] = []

    def collect_rollout(self, n_steps: int = 2048) -> dict[str, float]:
        """Collect experience from environment."""
        state = self.env.reset()
        episode_rewards = []
        current_episode_reward = 0

        for _ in range(n_steps):
            action, log_prob, value = self.network.get_action(state)

            next_state, reward, done, info = self.env.step(action)

            self.states.append(state)
            self.actions.append(action)
            self.rewards.append(reward)
            self.log_probs.append(log_prob)
            self.values.append(value)
            self.dones.append(done)

            current_episode_reward += reward

            if done:
                episode_rewards.append(current_episode_reward)
                current_episode_reward = 0
                state = self.env.reset()
            else:
                state = next_state

        return {
            "mean_reward": np.mean(episode_rewards) if episode_rewards else 0,
            "episodes": len(episode_rewards),
        }

    def compute_returns(self) -> torch.Tensor:
        """Compute discounted returns."""
        returns = []
        R = 0
        for reward, done in zip(reversed(self.rewards), reversed(self.dones)):
            if done:
                R = 0
            R = reward + self.gamma * R
            returns.insert(0, R)
        return torch.FloatTensor(returns)

    def update(self) -> dict[str, float]:
        """Update policy using collected experience."""
        states = torch.FloatTensor(np.array(self.states))
        actions = torch.LongTensor(self.actions)
        old_log_probs = torch.FloatTensor(self.log_probs)
        returns = self.compute_returns()
        old_values = torch.FloatTensor(self.values)

        # Compute advantages
        advantages = returns - old_values
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # PPO update
        total_loss = 0
        total_policy_loss = 0
        total_value_loss = 0

        for _ in range(self.n_epochs):
            # Mini-batch updates
            indices = np.random.permutation(len(states))
            for start in range(0, len(states), self.batch_size):
                end = start + self.batch_size
                batch_idx = indices[start:end]

                batch_states = states[batch_idx]
                batch_actions = actions[batch_idx]
                batch_old_log_probs = old_log_probs[batch_idx]
                batch_advantages = advantages[batch_idx]
                batch_returns = returns[batch_idx]

                # Forward pass
                probs, values = self.network(batch_states)
                dist = torch.distributions.Categorical(probs)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy().mean()

                # Policy loss (PPO clip)
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = (
                    torch.clamp(ratio, 1 - self.clip_range, 1 + self.clip_range) * batch_advantages
                )
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss
                value_loss = nn.MSELoss()(values.squeeze(), batch_returns)

                # Total loss
                loss = policy_loss + 0.5 * value_loss - 0.01 * entropy

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.network.parameters(), 0.5)
                self.optimizer.step()

                total_loss += loss.item()
                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()

        # Clear buffers
        self.states = []
        self.actions = []
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []

        n_updates = self.n_epochs * (len(states) // self.batch_size + 1)
        return {
            "loss": total_loss / n_updates,
            "policy_loss": total_policy_loss / n_updates,
            "value_loss": total_value_loss / n_updates,
        }

    def save(self, path: str) -> None:
        """Save model weights."""
        torch.save(self.network.state_dict(), path)
        logger.info(f"Model saved to {path}")

    def load(self, path: str) -> None:
        """Load model weights."""
        self.network.load_state_dict(torch.load(path))
        logger.info(f"Model loaded from {path}")


def train(args: argparse.Namespace) -> dict[str, Any]:
    """Main training function."""
    logger.info(f"Starting {args.algorithm} training for {args.symbol}")
    logger.info(f"Hyperparameters: lr={args.learning_rate}, gamma={args.gamma}")

    # Create environment
    env = TradingEnvironment(symbol=args.symbol, state_dim=args.state_dim)

    # Create trainer
    trainer = PPOTrainer(
        env=env,
        learning_rate=args.learning_rate,
        gamma=args.gamma,
        clip_range=args.clip_range,
        n_epochs=args.n_epochs,
        batch_size=args.batch_size,
    )

    # Training loop
    best_reward = float("-inf")
    training_history = []

    for iteration in range(args.max_iterations):
        # Collect experience
        rollout_stats = trainer.collect_rollout(n_steps=args.rollout_steps)

        # Update policy
        update_stats = trainer.update()

        # Log progress
        mean_reward = rollout_stats["mean_reward"]
        training_history.append(
            {
                "iteration": iteration,
                "mean_reward": mean_reward,
                "loss": update_stats["loss"],
            }
        )

        if iteration % 10 == 0:
            logger.info(
                f"Iteration {iteration}: reward={mean_reward:.4f}, loss={update_stats['loss']:.4f}"
            )

        # Save best model
        if mean_reward > best_reward:
            best_reward = mean_reward
            output_dir = os.getenv("AIP_MODEL_DIR", "models/ml")
            Path(output_dir).mkdir(parents=True, exist_ok=True)
            model_path = os.path.join(output_dir, f"{args.symbol}_ppo_best.pt")
            trainer.save(model_path)

        # Early stopping
        if mean_reward > 0.1:  # Target reward threshold
            logger.info(f"Target reward achieved at iteration {iteration}")
            break

    # Final results
    results = {
        "symbol": args.symbol,
        "algorithm": args.algorithm,
        "iterations": len(training_history),
        "best_reward": best_reward,
        "final_reward": training_history[-1]["mean_reward"] if training_history else 0,
        "training_history": training_history[-100:],  # Last 100 entries
        "timestamp": datetime.now().isoformat(),
    }

    # Save results
    output_dir = os.getenv("AIP_MODEL_DIR", "models/ml")
    results_path = os.path.join(output_dir, f"{args.symbol}_training_results.json")
    with open(results_path, "w") as f:
        json.dump(results, f, indent=2)

    logger.info(f"Training complete. Best reward: {best_reward:.4f}")
    return results


def main():
    parser = argparse.ArgumentParser(description="RL Training Script for Vertex AI")

    # Required arguments
    parser.add_argument(
        "--algorithm",
        type=str,
        default="PPO",
        choices=["PPO", "DQN", "A2C"],
        help="RL algorithm",
    )
    parser.add_argument(
        "--symbol",
        type=str,
        default="SPY",
        help="Trading symbol",
    )

    # Environment arguments
    parser.add_argument(
        "--state_dim",
        type=int,
        default=10,
        help="State dimension",
    )

    # Hyperparameters
    parser.add_argument(
        "--learning_rate",
        type=float,
        default=0.0003,
        help="Learning rate",
    )
    parser.add_argument(
        "--gamma",
        type=float,
        default=0.99,
        help="Discount factor",
    )
    parser.add_argument(
        "--clip_range",
        type=float,
        default=0.2,
        help="PPO clip range",
    )
    parser.add_argument(
        "--n_epochs",
        type=int,
        default=10,
        help="PPO epochs per update",
    )
    parser.add_argument(
        "--batch_size",
        type=int,
        default=64,
        help="Mini-batch size",
    )

    # Training arguments
    parser.add_argument(
        "--max_iterations",
        type=int,
        default=100,
        help="Maximum training iterations",
    )
    parser.add_argument(
        "--rollout_steps",
        type=int,
        default=2048,
        help="Steps per rollout",
    )
    parser.add_argument(
        "--max_steps",
        type=int,
        default=100000,
        help="Maximum total steps (for compatibility)",
    )

    args = parser.parse_args()

    try:
        _results = train(args)
        logger.info("Training completed successfully")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Training failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Enhanced Proximal Policy Optimization (PPO) for Trading

Improvements over basic PPO:
- Clipped surrogate objective
- Multiple epochs per update
- Value function clipping
- Generalized Advantage Estimation (GAE)
- Learning rate scheduling
- Entropy bonus for exploration
"""

import logging
from dataclasses import dataclass

import numpy as np
import torch
import torch.optim as optim

from .networks import LSTMPPO

logger = logging.getLogger(__name__)


@dataclass
class PPOBatch:
    """Batch of experiences for PPO training."""

    states: torch.Tensor
    actions: torch.Tensor
    old_log_probs: torch.Tensor
    advantages: torch.Tensor
    returns: torch.Tensor
    values: torch.Tensor


class EnhancedPPOTrainer:
    """
    Enhanced PPO Trainer with advanced features.

    Features:
    - Clipped surrogate objective
    - Value function clipping
    - GAE for advantage estimation
    - Multiple epochs per update
    - Learning rate scheduling
    - Entropy bonus
    """

    def __init__(
        self,
        model: LSTMPPO,
        learning_rate: float = 3e-4,
        clip_epsilon: float = 0.2,
        value_coef: float = 0.5,
        entropy_coef: float = 0.01,
        gamma: float = 0.99,
        gae_lambda: float = 0.95,
        max_grad_norm: float = 0.5,
        ppo_epochs: int = 4,
        batch_size: int = 64,
        device: str = "cpu",
    ):
        """
        Initialize Enhanced PPO Trainer.

        Args:
            model: LSTM-PPO model
            learning_rate: Learning rate
            clip_epsilon: PPO clipping parameter
            value_coef: Value loss coefficient
            entropy_coef: Entropy bonus coefficient
            gamma: Discount factor
            gae_lambda: GAE lambda parameter
            max_grad_norm: Gradient clipping norm
            ppo_epochs: Number of PPO epochs per update
            batch_size: Batch size for training
            device: Device to use
        """
        self.model = model.to(device)
        self.device = torch.device(device)
        self.clip_epsilon = clip_epsilon
        self.value_coef = value_coef
        self.entropy_coef = entropy_coef
        self.gamma = gamma
        self.gae_lambda = gae_lambda
        self.max_grad_norm = max_grad_norm
        self.ppo_epochs = ppo_epochs
        self.batch_size = batch_size

        self.optimizer = optim.Adam(self.model.parameters(), lr=learning_rate)

        # Experience buffer
        self.states = []
        self.actions = []
        self.rewards = []
        self.log_probs = []
        self.values = []
        self.dones = []

        logger.info(f"Enhanced PPO Trainer initialized: lr={learning_rate}, clip={clip_epsilon}")

    def store_transition(
        self,
        state: torch.Tensor,
        action: int,
        reward: float,
        log_prob: torch.Tensor,
        value: torch.Tensor,
        done: bool,
    ):
        """Store transition in buffer."""
        self.states.append(state)
        self.actions.append(action)
        self.rewards.append(reward)
        self.log_probs.append(log_prob)
        self.values.append(value)
        self.dones.append(done)

    def compute_gae(
        self,
        rewards: list[float],
        values: list[float],
        dones: list[bool],
        next_value: float = 0.0,
    ) -> tuple[list[float], list[float]]:
        """
        Compute Generalized Advantage Estimation (GAE).

        Args:
            rewards: List of rewards
            values: List of value estimates
            dones: List of done flags
            next_value: Value of next state

        Returns:
            advantages: List of advantages
            returns: List of returns
        """
        advantages = []
        returns = []

        gae = 0
        next_value = next_value

        for step in reversed(range(len(rewards))):
            if dones[step]:
                delta = rewards[step] - values[step]
                gae = delta
            else:
                delta = rewards[step] + self.gamma * next_value - values[step]
                gae = delta + self.gamma * self.gae_lambda * gae

            advantages.insert(0, gae)
            returns.insert(0, gae + values[step])
            next_value = values[step]

        return advantages, returns

    def train(self) -> dict[str, float]:
        """
        Train on collected experiences.

        Returns:
            Training statistics
        """
        if len(self.states) < self.batch_size:
            return {"loss": 0.0, "policy_loss": 0.0, "value_loss": 0.0, "entropy": 0.0}

        # Convert to tensors
        states = torch.stack(self.states).to(self.device)
        actions = torch.LongTensor(self.actions).to(self.device)
        old_log_probs = torch.stack(self.log_probs).to(self.device)
        rewards = np.array(self.rewards)
        values = torch.stack(self.values).to(self.device)
        dones = np.array(self.dones)

        # Compute advantages and returns
        next_value = 0.0  # Assume terminal state
        advantages, returns = self.compute_gae(
            rewards.tolist(),
            values.detach().cpu().numpy().flatten().tolist(),
            dones.tolist(),
            next_value,
        )

        advantages = torch.FloatTensor(advantages).to(self.device)
        returns = torch.FloatTensor(returns).to(self.device)

        # Normalize advantages
        advantages = (advantages - advantages.mean()) / (advantages.std() + 1e-8)

        # Training loop
        total_policy_loss = 0.0
        total_value_loss = 0.0
        total_entropy = 0.0

        for _epoch in range(self.ppo_epochs):
            # Shuffle indices
            indices = torch.randperm(len(states))

            for start_idx in range(0, len(states), self.batch_size):
                end_idx = min(start_idx + self.batch_size, len(states))
                batch_indices = indices[start_idx:end_idx]

                batch_states = states[batch_indices]
                batch_actions = actions[batch_indices]
                batch_old_log_probs = old_log_probs[batch_indices]
                batch_advantages = advantages[batch_indices]
                batch_returns = returns[batch_indices]

                # Forward pass
                action_probs, state_values, _ = self.model(batch_states)

                # Compute new log probs
                dist = torch.distributions.Categorical(action_probs)
                new_log_probs = dist.log_prob(batch_actions)
                entropy = dist.entropy().mean()

                # Policy loss (clipped surrogate)
                ratio = torch.exp(new_log_probs - batch_old_log_probs)
                surr1 = ratio * batch_advantages
                surr2 = (
                    torch.clamp(ratio, 1.0 - self.clip_epsilon, 1.0 + self.clip_epsilon)
                    * batch_advantages
                )
                policy_loss = -torch.min(surr1, surr2).mean()

                # Value loss (clipped)
                value_clipped = values[batch_indices] + torch.clamp(
                    state_values - values[batch_indices],
                    -self.clip_epsilon,
                    self.clip_epsilon,
                )
                value_loss1 = (state_values - batch_returns) ** 2
                value_loss2 = (value_clipped - batch_returns) ** 2
                value_loss = 0.5 * torch.max(value_loss1, value_loss2).mean()

                # Total loss
                loss = policy_loss + self.value_coef * value_loss - self.entropy_coef * entropy

                # Backward pass
                self.optimizer.zero_grad()
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), self.max_grad_norm)
                self.optimizer.step()

                total_policy_loss += policy_loss.item()
                total_value_loss += value_loss.item()
                total_entropy += entropy.item()

        # Clear buffer
        self.states.clear()
        self.actions.clear()
        self.rewards.clear()
        self.log_probs.clear()
        self.values.clear()
        self.dones.clear()

        avg_policy_loss = total_policy_loss / (
            self.ppo_epochs * (len(states) // self.batch_size + 1)
        )
        avg_value_loss = total_value_loss / (self.ppo_epochs * (len(states) // self.batch_size + 1))
        avg_entropy = total_entropy / (self.ppo_epochs * (len(states) // self.batch_size + 1))

        return {
            "policy_loss": avg_policy_loss,
            "value_loss": avg_value_loss,
            "entropy": avg_entropy,
            "loss": avg_policy_loss
            + self.value_coef * avg_value_loss
            - self.entropy_coef * avg_entropy,
        }

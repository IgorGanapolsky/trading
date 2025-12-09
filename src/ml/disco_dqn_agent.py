"""
DiscoRL-Inspired DQN Agent for Trading.

Incorporates key innovations from DeepMind's DiscoRL (Nature 2025):
- Categorical value distribution (distributional RL)
- Moving average normalization for advantages/TD errors
- Auxiliary prediction tasks for representation learning
- Target network with soft updates

This is Option C from our integration analysis - adopting specific
innovations without full meta-learning.

References:
- DiscoRL: https://github.com/google-deepmind/disco_rl
- Nature paper: https://www.nature.com/articles/s41586-025-09761-x
"""

import logging
import random
from collections import deque
from pathlib import Path
from typing import Any, Optional

import numpy as np
import torch
import torch.optim as optim

from .dqn_networks import (
    CategoricalDQNNetwork,
    DiscoInspiredNetwork,
)
from .prioritized_replay import MovingAverage, PrioritizedReplayBuffer

logger = logging.getLogger(__name__)


class DiscoDQNAgent:
    """
    DiscoRL-Inspired DQN Agent for trading.

    Key Features (inspired by DiscoRL):
    1. Categorical Value Distribution: Models uncertainty in Q-values
    2. Moving Average Normalization: Stabilizes training with EMA for TD/advantages
    3. Auxiliary Predictions: Additional prediction tasks for better representations
    4. Soft Target Updates: Smooth target network updates (Polyak averaging)

    Trading-Specific Adaptations:
    - State space: Market features (RSI, MACD, volume, etc.)
    - Action space: BUY (1), SELL (2), HOLD (0)
    - Reward: Risk-adjusted returns (Sharpe-based)
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = 3,
        # DiscoRL-inspired hyperparameters
        num_bins: int = 51,  # C51 default, can use 601 like DiscoRL
        v_min: float = -10.0,  # Min Q-value (scaled for % returns)
        v_max: float = 10.0,  # Max Q-value (scaled for % returns)
        use_disco_network: bool = False,  # Use full DiscoRL-inspired network
        # Standard DQN hyperparameters
        learning_rate: float = 0.0003,  # DiscoRL uses 0.0003
        gamma: float = 0.997,  # DiscoRL uses 0.997
        tau: float = 0.005,  # Soft update coefficient
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        batch_size: int = 32,
        replay_buffer_size: int = 100000,
        # DiscoRL-inspired normalization
        use_advantage_normalization: bool = True,
        use_td_normalization: bool = True,
        ema_decay: float = 0.99,  # DiscoRL moving_average_decay
        # Auxiliary prediction
        aux_prediction_weight: float = 0.1,  # Weight for auxiliary loss
        # Training
        device: str = "cpu",
        model_dir: str = "models/ml",
    ):
        """
        Initialize DiscoRL-inspired DQN Agent.

        Args:
            state_dim: Dimension of state space
            action_dim: Number of actions (default 3: HOLD, BUY, SELL)
            num_bins: Number of bins for categorical distribution
            v_min: Minimum value for distribution support
            v_max: Maximum value for distribution support
            use_disco_network: Use full DiscoRL-inspired architecture
            learning_rate: Learning rate (DiscoRL uses 0.0003)
            gamma: Discount factor (DiscoRL uses 0.997)
            tau: Soft update coefficient for target network
            epsilon_start: Initial exploration rate
            epsilon_end: Final exploration rate
            epsilon_decay: Epsilon decay rate
            batch_size: Batch size for training
            replay_buffer_size: Size of replay buffer
            use_advantage_normalization: Normalize advantages with EMA
            use_td_normalization: Normalize TD errors with EMA
            ema_decay: EMA decay for normalization
            aux_prediction_weight: Weight for auxiliary prediction loss
            device: Device to use (cpu/cuda)
            model_dir: Directory to save models
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.num_bins = num_bins
        self.v_min = v_min
        self.v_max = v_max
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.tau = tau
        self.epsilon = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.aux_weight = aux_prediction_weight
        self.device = torch.device(device)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Build networks
        if use_disco_network:
            self.q_network = DiscoInspiredNetwork(
                input_dim=state_dim,
                num_actions=action_dim,
                num_bins=num_bins,
                v_min=v_min,
                v_max=v_max,
            ).to(self.device)
            self.target_network = DiscoInspiredNetwork(
                input_dim=state_dim,
                num_actions=action_dim,
                num_bins=num_bins,
                v_min=v_min,
                v_max=v_max,
            ).to(self.device)
        else:
            self.q_network = CategoricalDQNNetwork(
                input_dim=state_dim,
                num_actions=action_dim,
                num_bins=num_bins,
                v_min=v_min,
                v_max=v_max,
                use_dueling=True,
            ).to(self.device)
            self.target_network = CategoricalDQNNetwork(
                input_dim=state_dim,
                num_actions=action_dim,
                num_bins=num_bins,
                v_min=v_min,
                v_max=v_max,
                use_dueling=True,
            ).to(self.device)

        # Copy weights to target
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        # Optimizer (DiscoRL uses Adam with specific settings)
        self.optimizer = optim.Adam(
            self.q_network.parameters(),
            lr=learning_rate,
            eps=1e-8,
        )

        # Replay buffer with DiscoRL-inspired TD normalization
        self.replay_buffer = PrioritizedReplayBuffer(
            capacity=replay_buffer_size,
            use_td_normalization=use_td_normalization,
        )

        # DiscoRL-inspired EMA normalization
        self.use_adv_norm = use_advantage_normalization
        self.use_td_norm = use_td_normalization
        self.adv_ema = MovingAverage(decay=ema_decay) if use_advantage_normalization else None
        self.td_ema = MovingAverage(decay=ema_decay) if use_td_normalization else None

        # Support atoms for distributional RL
        self.support = torch.linspace(v_min, v_max, num_bins).to(self.device)
        self.delta_z = (v_max - v_min) / (num_bins - 1)

        # Training stats
        self.step_count = 0
        self.update_count = 0
        self.losses = deque(maxlen=1000)

        logger.info("DiscoDQNAgent initialized:")
        logger.info(f"  State dim: {state_dim}, Actions: {action_dim}")
        logger.info(f"  Categorical: {num_bins} bins, range [{v_min}, {v_max}]")
        logger.info(
            f"  EMA normalization: adv={use_advantage_normalization}, td={use_td_normalization}"
        )
        logger.info(f"  Gamma: {gamma}, LR: {learning_rate}, Tau: {tau}")

    def select_action(
        self,
        state: np.ndarray,
        training: bool = True,
    ) -> tuple[int, dict[str, Any]]:
        """
        Select action using epsilon-greedy with distributional Q-values.

        Args:
            state: Current state
            training: Whether in training mode

        Returns:
            (action, info_dict) where info contains Q-values and distribution
        """
        if training and random.random() < self.epsilon:
            action = random.randint(0, self.action_dim - 1)
            return action, {"source": "exploration", "epsilon": self.epsilon}

        self.q_network.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)

            if hasattr(self.q_network, "get_distribution"):
                dist = self.q_network.get_distribution(state_tensor)
                dist_info = {"distribution": dist.cpu().numpy()}
            else:
                dist_info = {}

            action = q_values.argmax(dim=-1).item()
            q_values_np = q_values.cpu().numpy().flatten()

        info = {
            "source": "exploitation",
            "q_values": q_values_np,
            "epsilon": self.epsilon,
            **dist_info,
        }
        return action, info

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        """Store transition in replay buffer."""
        self.replay_buffer.add(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
        )

    def train_step(self) -> Optional[dict[str, float]]:
        """
        Perform one training step with distributional Bellman update.

        Returns:
            Dictionary of losses if training occurred, None otherwise
        """
        if len(self.replay_buffer) < self.batch_size:
            return None

        # Sample batch with importance weights
        batch, indices, weights = self.replay_buffer.sample(self.batch_size)

        # Extract batch components
        states = torch.FloatTensor(np.array([e.state for e in batch])).to(self.device)
        actions = torch.LongTensor(np.array([e.action for e in batch])).to(self.device)
        rewards = torch.FloatTensor(np.array([e.reward for e in batch])).to(self.device)
        next_states = torch.FloatTensor(np.array([e.next_state for e in batch])).to(self.device)
        dones = torch.BoolTensor(np.array([e.done for e in batch])).to(self.device)
        weights = torch.FloatTensor(weights).to(self.device)

        # Compute distributional loss
        loss, td_errors, loss_dict = self._compute_distributional_loss(
            states, actions, rewards, next_states, dones, weights
        )

        # Backward pass
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping (DiscoRL uses max_abs_update=1.0)
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 1.0)
        self.optimizer.step()

        # Update priorities
        self.replay_buffer.update_priorities(indices, td_errors.detach().cpu().numpy())

        # Soft update target network
        self._soft_update_target()

        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        self.step_count += 1
        self.losses.append(loss.item())

        return loss_dict

    def _compute_distributional_loss(
        self,
        states: torch.Tensor,
        actions: torch.Tensor,
        rewards: torch.Tensor,
        next_states: torch.Tensor,
        dones: torch.Tensor,
        weights: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, float]]:
        """
        Compute categorical distributional loss (C51-style).

        This is the core of distributional RL, as used in DiscoRL.
        """
        _batch_size = states.shape[0]  # Used implicitly in tensor operations

        # Current distributions
        current_dist = self.q_network.get_distribution(states)  # [B, A, num_bins]
        actions_expanded = actions.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, self.num_bins)
        current_dist_a = current_dist.gather(1, actions_expanded).squeeze(1)  # [B, num_bins]

        with torch.no_grad():
            # Double DQN: use online network to select action
            next_q = self.q_network(next_states)
            next_actions = next_q.argmax(dim=-1)

            # Use target network for distribution
            target_dist = self.target_network.get_distribution(next_states)
            next_actions_expanded = (
                next_actions.unsqueeze(-1).unsqueeze(-1).expand(-1, -1, self.num_bins)
            )
            next_dist = target_dist.gather(1, next_actions_expanded).squeeze(1)  # [B, num_bins]

            # Project distribution (Bellman update)
            projected_dist = self._project_distribution(next_dist, rewards, dones, self.gamma)

        # Cross-entropy loss between projected and current distributions
        # Add small epsilon for numerical stability
        log_current = torch.log(current_dist_a + 1e-8)
        loss_per_sample = -(projected_dist * log_current).sum(dim=-1)

        # Compute TD errors for priority update
        current_q = (current_dist_a * self.support).sum(dim=-1)
        target_q = (projected_dist * self.support).sum(dim=-1)
        td_errors = target_q - current_q

        # Apply EMA normalization if enabled (DiscoRL-style)
        if self.td_ema is not None:
            td_np = td_errors.detach().cpu().numpy()
            self.td_ema.update(td_np)

        # Weighted loss with importance sampling
        loss = (loss_per_sample * weights).mean()

        loss_dict = {
            "total_loss": loss.item(),
            "td_mean": td_errors.mean().item(),
            "td_std": td_errors.std().item(),
            "q_mean": current_q.mean().item(),
        }

        return loss, td_errors, loss_dict

    def _project_distribution(
        self,
        next_dist: torch.Tensor,
        rewards: torch.Tensor,
        dones: torch.Tensor,
        gamma: float,
    ) -> torch.Tensor:
        """
        Project the next distribution onto the support.

        Implements: Tz = r + γ * z (clamped to [v_min, v_max])
        """
        batch_size = rewards.shape[0]

        # Compute projected support
        rewards = rewards.unsqueeze(-1)  # [B, 1]
        dones = dones.unsqueeze(-1).float()  # [B, 1]
        support = self.support.unsqueeze(0)  # [1, num_bins]

        tz = rewards + (1 - dones) * gamma * support
        tz = tz.clamp(self.v_min, self.v_max)

        # Compute projection indices
        b = (tz - self.v_min) / self.delta_z
        lower_idx = b.floor().long()
        upper_idx = b.ceil().long()

        # Handle edge cases
        lower_idx = lower_idx.clamp(0, self.num_bins - 1)
        upper_idx = upper_idx.clamp(0, self.num_bins - 1)

        # Distribute probability mass
        projected = torch.zeros(batch_size, self.num_bins, device=self.device)

        # Vectorized distribution
        for i in range(batch_size):
            for j in range(self.num_bins):
                # Lower bound contribution
                projected[i, lower_idx[i, j]] += next_dist[i, j] * (
                    upper_idx[i, j].float() - b[i, j]
                )
                # Upper bound contribution
                projected[i, upper_idx[i, j]] += next_dist[i, j] * (
                    b[i, j] - lower_idx[i, j].float()
                )

        return projected

    def _soft_update_target(self):
        """Soft update target network (Polyak averaging)."""
        for target_param, param in zip(
            self.target_network.parameters(), self.q_network.parameters()
        ):
            target_param.data.copy_(self.tau * param.data + (1 - self.tau) * target_param.data)
        self.update_count += 1

    def calculate_reward(
        self,
        trade_result: dict[str, Any],
        market_state: Optional[dict[str, Any]] = None,
    ) -> float:
        """
        Calculate reward from trade result.

        Uses risk-adjusted reward similar to DiscoRL's signed log transform.
        """
        try:
            from src.ml.reward_functions import calculate_risk_adjusted_reward

            return calculate_risk_adjusted_reward(trade_result, market_state)
        except ImportError:
            # Fallback to simple reward
            pl_pct = trade_result.get("pl_pct", 0)
            # Signed log transform (DiscoRL-style)
            sign = np.sign(pl_pct)
            reward = sign * np.log1p(np.abs(pl_pct * 100))  # Scale up
            return np.clip(reward, -2.0, 2.0)

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for a state."""
        self.q_network.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
        return q_values.cpu().numpy().flatten()

    def get_value_distribution(self, state: np.ndarray) -> np.ndarray:
        """Get full value distribution for visualization."""
        self.q_network.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            dist = self.q_network.get_distribution(state_tensor)
        return dist.cpu().numpy()

    def save(self, filepath: str):
        """Save model and state."""
        save_dict = {
            "q_network_state_dict": self.q_network.state_dict(),
            "target_network_state_dict": self.target_network.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "step_count": self.step_count,
            "update_count": self.update_count,
            "config": {
                "state_dim": self.state_dim,
                "action_dim": self.action_dim,
                "num_bins": self.num_bins,
                "v_min": self.v_min,
                "v_max": self.v_max,
                "gamma": self.gamma,
                "tau": self.tau,
            },
        }
        if self.adv_ema is not None:
            save_dict["adv_ema"] = self.adv_ema.get_state()
        if self.td_ema is not None:
            save_dict["td_ema"] = self.td_ema.get_state()

        torch.save(save_dict, filepath)
        logger.info(f"DiscoDQNAgent saved to {filepath}")

    def load(self, filepath: str):
        """Load model and state."""
        if not Path(filepath).exists():
            logger.warning(f"Model file not found: {filepath}")
            return

        checkpoint = torch.load(filepath, map_location=self.device)
        self.q_network.load_state_dict(checkpoint["q_network_state_dict"])
        self.target_network.load_state_dict(checkpoint["target_network_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.epsilon = checkpoint.get("epsilon", self.epsilon)
        self.step_count = checkpoint.get("step_count", 0)
        self.update_count = checkpoint.get("update_count", 0)

        if "adv_ema" in checkpoint and self.adv_ema is not None:
            self.adv_ema.load_state(checkpoint["adv_ema"])
        if "td_ema" in checkpoint and self.td_ema is not None:
            self.td_ema.load_state(checkpoint["td_ema"])

        logger.info(f"DiscoDQNAgent loaded from {filepath}")

    def get_stats(self) -> dict[str, Any]:
        """Get training statistics."""
        avg_loss = np.mean(self.losses) if self.losses else 0.0
        stats = {
            "epsilon": self.epsilon,
            "step_count": self.step_count,
            "update_count": self.update_count,
            "avg_loss": avg_loss,
            "replay_buffer_size": len(self.replay_buffer),
            "num_bins": self.num_bins,
            "value_range": [self.v_min, self.v_max],
        }
        if self.adv_ema is not None:
            stats["adv_ema_mean"] = self.adv_ema.mean
            stats["adv_ema_var"] = self.adv_ema.var
        if self.td_ema is not None:
            stats["td_ema_mean"] = self.td_ema.mean
            stats["td_ema_var"] = self.td_ema.var
        return stats

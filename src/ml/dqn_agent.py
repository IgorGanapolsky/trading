"""
Deep Q-Network Agent for Trading

Implements state-of-the-art DQN algorithms:
- Vanilla DQN
- Double DQN
- Dueling DQN
- Prioritized Experience Replay
- Multi-step learning

Replaces tabular Q-learning with deep neural networks for better
generalization and handling of continuous state spaces.
"""

import logging
import random
from collections import deque
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.optim as optim

from .dqn_networks import DQNNetwork, DuelingDQNNetwork, LSTMDQNNetwork
from .prioritized_replay import PrioritizedReplayBuffer

logger = logging.getLogger(__name__)


class DQNAgent:
    """
    Deep Q-Network Agent for trading.

    Features:
    - Deep neural network for Q-value approximation
    - Experience replay for stable learning
    - Target network for stable Q-learning
    - Epsilon-greedy exploration
    - Double DQN to reduce overestimation
    """

    def __init__(
        self,
        state_dim: int,
        action_dim: int = 3,  # BUY, SELL, HOLD
        use_dueling: bool = True,
        use_lstm: bool = False,
        use_double: bool = True,
        use_prioritized_replay: bool = True,
        learning_rate: float = 0.001,
        gamma: float = 0.95,
        epsilon_start: float = 1.0,
        epsilon_end: float = 0.01,
        epsilon_decay: float = 0.995,
        batch_size: int = 32,
        replay_buffer_size: int = 10000,
        target_update_freq: int = 100,
        device: str = "cpu",
        model_dir: str = "models/ml",
    ):
        """
        Initialize DQN Agent.

        Args:
            state_dim: Dimension of state space
            action_dim: Number of actions
            use_dueling: Use dueling architecture
            use_lstm: Use LSTM for sequential data
            use_double: Use Double DQN
            use_prioritized_replay: Use prioritized experience replay
            learning_rate: Learning rate
            gamma: Discount factor
            epsilon_start: Initial exploration rate
            epsilon_end: Final exploration rate
            epsilon_decay: Epsilon decay rate
            batch_size: Batch size for training
            replay_buffer_size: Size of replay buffer
            target_update_freq: Frequency to update target network
            device: Device to use (cpu/cuda)
            model_dir: Directory to save models
        """
        self.state_dim = state_dim
        self.action_dim = action_dim
        self.use_double = use_double
        self.use_prioritized_replay = use_prioritized_replay
        self.learning_rate = learning_rate
        self.gamma = gamma
        self.epsilon = epsilon_start
        self.epsilon_start = epsilon_start
        self.epsilon_end = epsilon_end
        self.epsilon_decay = epsilon_decay
        self.batch_size = batch_size
        self.target_update_freq = target_update_freq
        self.device = torch.device(device)
        self.model_dir = Path(model_dir)
        self.model_dir.mkdir(parents=True, exist_ok=True)

        # Build networks
        if use_lstm:
            self.q_network = LSTMDQNNetwork(input_dim=state_dim, num_actions=action_dim).to(
                self.device
            )
            self.target_network = LSTMDQNNetwork(input_dim=state_dim, num_actions=action_dim).to(
                self.device
            )
        elif use_dueling:
            self.q_network = DuelingDQNNetwork(input_dim=state_dim, num_actions=action_dim).to(
                self.device
            )
            self.target_network = DuelingDQNNetwork(input_dim=state_dim, num_actions=action_dim).to(
                self.device
            )
        else:
            self.q_network = DQNNetwork(input_dim=state_dim, num_actions=action_dim).to(self.device)
            self.target_network = DQNNetwork(input_dim=state_dim, num_actions=action_dim).to(
                self.device
            )

        # Copy weights to target network
        self.target_network.load_state_dict(self.q_network.state_dict())
        self.target_network.eval()

        # Optimizer
        self.optimizer = optim.Adam(self.q_network.parameters(), lr=learning_rate)

        # Replay buffer
        if use_prioritized_replay:
            self.replay_buffer = PrioritizedReplayBuffer(capacity=replay_buffer_size)
        else:
            self.replay_buffer = deque(maxlen=replay_buffer_size)

        # Training stats
        self.step_count = 0
        self.update_count = 0
        self.losses = deque(maxlen=1000)

        logger.info(f"DQN Agent initialized: state_dim={state_dim}, actions={action_dim}")
        logger.info(f"  Dueling: {use_dueling}, LSTM: {use_lstm}, Double: {use_double}")
        logger.info(f"  Prioritized Replay: {use_prioritized_replay}")

    def select_action(
        self,
        state: np.ndarray,
        agent_recommendation: str | None = None,
        training: bool = True,
    ) -> int:
        """
        Select action using epsilon-greedy policy.

        Args:
            state: Current state
            agent_recommendation: Optional recommendation from other agents
            training: Whether in training mode

        Returns:
            Action index (0=HOLD, 1=BUY, 2=SELL)
        """
        if training and random.random() < self.epsilon:
            # Explore: random or use agent recommendation
            if agent_recommendation:
                action_map = {"HOLD": 0, "BUY": 1, "SELL": 2}
                return action_map.get(agent_recommendation, random.randint(0, self.action_dim - 1))
            return random.randint(0, self.action_dim - 1)

        # Exploit: use Q-network
        self.q_network.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
            action = q_values.argmax().item()

        return action

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: float | None = None,
    ):
        """Store transition in replay buffer."""
        if self.use_prioritized_replay:
            self.replay_buffer.add(
                state=state,
                action=action,
                reward=reward,
                next_state=next_state,
                done=done,
                td_error=td_error,
            )
        else:
            self.replay_buffer.append((state, action, reward, next_state, done))

    def train_step(self) -> float | None:
        """
        Perform one training step.

        Returns:
            Loss value if training occurred, None otherwise
        """
        # Check if we have enough samples
        if self.use_prioritized_replay:
            if len(self.replay_buffer) < self.batch_size:
                return None
        else:
            if len(self.replay_buffer) < self.batch_size:
                return None

        # Sample batch
        if self.use_prioritized_replay:
            batch, indices, weights = self.replay_buffer.sample(self.batch_size)
            states = torch.FloatTensor(np.array([e.state for e in batch])).to(self.device)
            actions = torch.LongTensor(np.array([e.action for e in batch])).to(self.device)
            rewards = torch.FloatTensor(np.array([e.reward for e in batch])).to(self.device)
            next_states = torch.FloatTensor(np.array([e.next_state for e in batch])).to(self.device)
            dones = torch.BoolTensor(np.array([e.done for e in batch])).to(self.device)
            weights = torch.FloatTensor(weights).to(self.device)
        else:
            batch = random.sample(self.replay_buffer, self.batch_size)
            states = torch.FloatTensor(np.array([e[0] for e in batch])).to(self.device)
            actions = torch.LongTensor(np.array([e[1] for e in batch])).to(self.device)
            rewards = torch.FloatTensor(np.array([e[2] for e in batch])).to(self.device)
            next_states = torch.FloatTensor(np.array([e[3] for e in batch])).to(self.device)
            dones = torch.BoolTensor(np.array([e[4] for e in batch])).to(self.device)
            weights = None

        # Current Q-values
        current_q_values = self.q_network(states).gather(1, actions.unsqueeze(1))

        # Next Q-values
        with torch.no_grad():
            if self.use_double:
                # Double DQN: use main network to select action, target to evaluate
                next_actions = self.q_network(next_states).argmax(1, keepdim=True)
                next_q_values = self.target_network(next_states).gather(1, next_actions)
            else:
                # Vanilla DQN: use target network for both
                next_q_values = self.target_network(next_states).max(1, keepdim=True)[0]

            # Target Q-values
            target_q_values = rewards.unsqueeze(1) + (
                self.gamma * next_q_values * (~dones).unsqueeze(1)
            )

        # Compute loss
        td_errors = target_q_values - current_q_values
        loss = td_errors**2

        if weights is not None:
            loss = loss * weights.unsqueeze(1)

        loss = loss.mean()

        # Update network
        self.optimizer.zero_grad()
        loss.backward()
        # Gradient clipping
        torch.nn.utils.clip_grad_norm_(self.q_network.parameters(), 10.0)
        self.optimizer.step()

        # Update priorities if using prioritized replay
        if self.use_prioritized_replay:
            td_errors_np = td_errors.detach().cpu().numpy().flatten()
            self.replay_buffer.update_priorities(indices, td_errors_np)

        # Update target network
        self.update_count += 1
        if self.update_count % self.target_update_freq == 0:
            self.target_network.load_state_dict(self.q_network.state_dict())
            logger.debug(f"Target network updated at step {self.update_count}")

        # Decay epsilon
        self.epsilon = max(self.epsilon_end, self.epsilon * self.epsilon_decay)

        self.losses.append(loss.item())
        self.step_count += 1

        return loss.item()

    def calculate_reward(
        self,
        trade_result: dict[str, Any],
        market_state: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate reward from trade result using multi-objective risk-adjusted reward.

        Dec 4, 2025: Updated to use RiskAdjustedReward class for production-grade
        reward calculation with components for:
        - Annualized return (35% weight)
        - Downside risk penalty (25% weight)
        - Sharpe ratio (20% weight)
        - Drawdown penalty (15% weight)
        - Transaction cost penalty (5% weight)

        Args:
            trade_result: Trade result dictionary with pl_pct, holding_period_days, etc.
            market_state: Optional market state with volatility, sharpe_ratio, etc.

        Returns:
            Risk-adjusted reward value normalized to [-1, 1]
        """
        try:
            from src.ml.reward_functions import calculate_risk_adjusted_reward

            return calculate_risk_adjusted_reward(trade_result, market_state)
        except ImportError:
            # Fallback to simple reward if import fails
            logger.warning("RiskAdjustedReward not available, using simple reward")
            pl_pct = trade_result.get("pl_pct", 0)

            if market_state:
                volatility = market_state.get("volatility", 0.2)
                sharpe_adjustment = pl_pct / max(volatility, 0.01)
                reward = np.clip(sharpe_adjustment / 5.0, -1.0, 1.0)
            else:
                reward = np.clip(pl_pct / 0.05, -1.0, 1.0)

            return reward

    def get_q_values(self, state: np.ndarray) -> np.ndarray:
        """Get Q-values for a state."""
        self.q_network.eval()
        with torch.no_grad():
            state_tensor = torch.FloatTensor(state).unsqueeze(0).to(self.device)
            q_values = self.q_network(state_tensor)
        return q_values.cpu().numpy().flatten()

    def save(self, filepath: str):
        """Save model and state."""
        save_dict = {
            "q_network_state_dict": self.q_network.state_dict(),
            "target_network_state_dict": self.target_network.state_dict(),
            "optimizer_state_dict": self.optimizer.state_dict(),
            "epsilon": self.epsilon,
            "step_count": self.step_count,
            "update_count": self.update_count,
        }
        torch.save(save_dict, filepath)
        logger.info(f"Model saved to {filepath}")

    def load(self, filepath: str):
        """Load model and state."""
        if not Path(filepath).exists():
            logger.warning(f"Model file not found: {filepath}")
            return

        checkpoint = torch.load(filepath, map_location=self.device)
        self.q_network.load_state_dict(checkpoint["q_network_state_dict"])
        self.target_network.load_state_dict(checkpoint["target_network_state_dict"])
        self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        self.epsilon = checkpoint.get("epsilon", self.epsilon_start)
        self.step_count = checkpoint.get("step_count", 0)
        self.update_count = checkpoint.get("update_count", 0)
        logger.info(f"Model loaded from {filepath}")

    def get_stats(self) -> dict[str, Any]:
        """Get training statistics."""
        avg_loss = np.mean(self.losses) if self.losses else 0.0
        return {
            "epsilon": self.epsilon,
            "step_count": self.step_count,
            "update_count": self.update_count,
            "avg_loss": avg_loss,
            "replay_buffer_size": len(self.replay_buffer),
            "target_updates": self.update_count // self.target_update_freq,
        }

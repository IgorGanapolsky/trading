"""
Deep Q-Network (DQN) Architectures for Trading

Implements state-of-the-art DQN variants from Deep Learning Specialization:
- Vanilla DQN
- Double DQN
- Dueling DQN
- Prioritized Experience Replay

Inspired by:
- DeepMind's DQN (2015)
- Double DQN (2016)
- Dueling DQN (2016)
- Prioritized Experience Replay (2016)
"""

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F


class DQNNetwork(nn.Module):
    """
    Vanilla Deep Q-Network for trading.

    Architecture:
    - Input: Market state features (flattened)
    - Hidden layers: Fully connected with ReLU
    - Output: Q-values for each action (BUY, SELL, HOLD)
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dims: list = None,
        num_actions: int = 3,
        dropout: float = 0.1,
    ):
        if hidden_dims is None:
            hidden_dims = [128, 128, 64]
        super().__init__()

        layers = []
        prev_dim = input_dim

        for hidden_dim in hidden_dims:
            layers.append(nn.Linear(prev_dim, hidden_dim))
            layers.append(nn.ReLU())
            layers.append(nn.Dropout(dropout))
            prev_dim = hidden_dim

        # Output layer
        layers.append(nn.Linear(prev_dim, num_actions))

        self.network = nn.Sequential(*layers)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            state: Input state tensor (batch_size, input_dim)

        Returns:
            Q-values for each action (batch_size, num_actions)
        """
        return self.network(state)


class DuelingDQNNetwork(nn.Module):
    """
    Dueling DQN Architecture.

    Separates value function V(s) and advantage function A(s,a):
    Q(s,a) = V(s) + (A(s,a) - mean(A(s,a)))

    This allows the network to learn:
    - Which states are valuable (V)
    - Which actions are better relative to others (A)
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_actions: int = 3,
        dropout: float = 0.1,
    ):
        super().__init__()

        # Shared feature extractor
        self.feature_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Value stream: V(s)
        self.value_stream = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))

        # Advantage stream: A(s,a)
        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, num_actions)
        )

        self.num_actions = num_actions

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass with dueling architecture.

        Args:
            state: Input state tensor (batch_size, input_dim)

        Returns:
            Q-values for each action (batch_size, num_actions)
        """
        features = self.feature_layer(state)

        # Value: scalar for state
        value = self.value_stream(features)

        # Advantage: vector for each action
        advantage = self.advantage_stream(features)

        # Combine: Q(s,a) = V(s) + (A(s,a) - mean(A(s,a)))
        # This ensures that advantage has zero mean
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))

        return q_values


class LSTMDQNNetwork(nn.Module):
    """
    LSTM-based DQN for sequential market data.

    Architecture:
    - LSTM encoder for time-series features
    - Dueling DQN head for action values
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        num_actions: int = 3,
        dropout: float = 0.2,
    ):
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # LSTM encoder
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=dropout if num_layers > 1 else 0,
        )

        # Dueling head
        self.value_stream = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))

        self.advantage_stream = nn.Sequential(
            nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, num_actions)
        )

        self.num_actions = num_actions

    def forward(
        self,
        state: torch.Tensor,
        hidden: Optional[tuple[torch.Tensor, torch.Tensor]] = None,
    ) -> tuple[torch.Tensor, tuple[torch.Tensor, torch.Tensor]]:
        """
        Forward pass with LSTM.

        Args:
            state: Input sequence (batch_size, seq_len, input_dim)
            hidden: Optional LSTM hidden state

        Returns:
            Q-values and updated hidden state
        """
        # LSTM encoding
        lstm_out, next_hidden = self.lstm(state, hidden)

        # Use last timestep
        last_hidden = lstm_out[:, -1, :]

        # Value and advantage
        value = self.value_stream(last_hidden)
        advantage = self.advantage_stream(last_hidden)

        # Combine
        q_values = value + (advantage - advantage.mean(dim=1, keepdim=True))

        return q_values, next_hidden


class DistributionalDQNNetwork(nn.Module):
    """
    Distributional DQN (C51) - predicts distribution of returns.

    Instead of predicting expected Q-value, predicts distribution
    over possible returns. More expressive and stable.
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_actions: int = 3,
        num_atoms: int = 51,  # C51 uses 51 atoms
        v_min: float = -10.0,
        v_max: float = 10.0,
    ):
        super().__init__()

        self.num_actions = num_actions
        self.num_atoms = num_atoms
        self.v_min = v_min
        self.v_max = v_max

        # Support: atoms for distribution
        self.register_buffer("support", torch.linspace(v_min, v_max, num_atoms))

        # Network
        self.feature_layer = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, hidden_dim),
            nn.ReLU(),
        )

        # Output: probability distribution over atoms for each action
        self.output = nn.Linear(hidden_dim, num_actions * num_atoms)

    def forward(self, state: torch.Tensor) -> torch.Tensor:
        """
        Forward pass.

        Args:
            state: Input state tensor (batch_size, input_dim)

        Returns:
            Probability distributions (batch_size, num_actions, num_atoms)
        """
        features = self.feature_layer(state)
        logits = self.output(features)

        # Reshape to (batch_size, num_actions, num_atoms)
        logits = logits.view(-1, self.num_actions, self.num_atoms)

        # Softmax to get probabilities
        probs = F.softmax(logits, dim=2)

        return probs

    def get_q_values(self, probs: torch.Tensor) -> torch.Tensor:
        """
        Convert distribution to expected Q-values.

        Args:
            probs: Probability distributions (batch_size, num_actions, num_atoms)

        Returns:
            Expected Q-values (batch_size, num_actions)
        """
        # Expected value: sum(prob * atom_value)
        q_values = torch.sum(probs * self.support.unsqueeze(0).unsqueeze(0), dim=2)
        return q_values

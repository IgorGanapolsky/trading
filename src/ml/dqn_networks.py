"""
DQN Network Architectures with DiscoRL-Inspired Enhancements.

Includes:
- Standard DQN network
- Dueling DQN architecture
- LSTM DQN for temporal patterns
- Categorical (Distributional) DQN inspired by DiscoRL

DiscoRL Integration (Dec 2025):
- Categorical value distribution (601 bins like Disco103)
- Signed hyperbolic transform for value compression
"""

import logging

import torch
import torch.nn as nn
import torch.nn.functional as F

logger = logging.getLogger(__name__)


class DQNNetwork(nn.Module):
    """Standard DQN network."""

    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (256, 128, 64),
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_actions = num_actions

        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(prev_dim, hidden_dim),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_dim),
                ]
            )
            prev_dim = hidden_dim

        self.feature_extractor = nn.Sequential(*layers)
        self.q_head = nn.Linear(prev_dim, num_actions)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.0)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.feature_extractor(x)
        return self.q_head(features)


class DuelingDQNNetwork(nn.Module):
    """
    Dueling DQN architecture.

    Separates value and advantage streams for better learning.
    Q(s,a) = V(s) + A(s,a) - mean(A(s,a))
    """

    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (256, 128),
        value_hidden: int = 64,
        advantage_hidden: int = 64,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_actions = num_actions

        # Shared feature extractor
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(prev_dim, hidden_dim),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_dim),
                ]
            )
            prev_dim = hidden_dim

        self.feature_extractor = nn.Sequential(*layers)

        # Value stream
        self.value_stream = nn.Sequential(
            nn.Linear(prev_dim, value_hidden),
            nn.ReLU(),
            nn.Linear(value_hidden, 1),
        )

        # Advantage stream
        self.advantage_stream = nn.Sequential(
            nn.Linear(prev_dim, advantage_hidden),
            nn.ReLU(),
            nn.Linear(advantage_hidden, num_actions),
        )

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=1.0)
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        features = self.feature_extractor(x)
        value = self.value_stream(features)
        advantage = self.advantage_stream(features)
        # Combine using dueling formula
        q_values = value + advantage - advantage.mean(dim=-1, keepdim=True)
        return q_values


class LSTMDQNNetwork(nn.Module):
    """
    LSTM-based DQN for temporal pattern recognition.

    Processes sequences of market states to capture temporal dynamics.
    """

    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        hidden_dim: int = 128,
        lstm_hidden: int = 128,
        num_lstm_layers: int = 2,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_actions = num_actions
        self.lstm_hidden = lstm_hidden
        self.num_lstm_layers = num_lstm_layers

        # Input projection
        self.input_proj = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.LayerNorm(hidden_dim),
        )

        # LSTM
        self.lstm = nn.LSTM(
            input_size=hidden_dim,
            hidden_size=lstm_hidden,
            num_layers=num_lstm_layers,
            batch_first=True,
            dropout=0.1 if num_lstm_layers > 1 else 0,
        )

        # Q-value head
        self.q_head = nn.Sequential(
            nn.Linear(lstm_hidden, 64),
            nn.ReLU(),
            nn.Linear(64, num_actions),
        )

        self._init_weights()

    def _init_weights(self):
        for name, param in self.lstm.named_parameters():
            if "weight_ih" in name or "weight_hh" in name:
                nn.init.orthogonal_(param)
            elif "bias" in name:
                nn.init.constant_(param, 0)

    def forward(
        self, x: torch.Tensor, hidden: tuple[torch.Tensor, torch.Tensor] | None = None
    ) -> torch.Tensor:
        # Handle both single states and sequences
        if x.dim() == 2:
            x = x.unsqueeze(1)  # Add sequence dimension

        batch_size, seq_len, _ = x.shape

        # Project input
        x = self.input_proj(x)

        # Initialize hidden state if not provided
        if hidden is None:
            h0 = torch.zeros(self.num_lstm_layers, batch_size, self.lstm_hidden, device=x.device)
            c0 = torch.zeros(self.num_lstm_layers, batch_size, self.lstm_hidden, device=x.device)
            hidden = (h0, c0)

        # LSTM forward
        lstm_out, _ = self.lstm(x, hidden)

        # Use last output for Q-values
        q_values = self.q_head(lstm_out[:, -1, :])
        return q_values


class CategoricalDQNNetwork(nn.Module):
    """
    Categorical (Distributional) DQN inspired by DiscoRL.

    Instead of predicting a single Q-value, predicts a probability distribution
    over possible values using categorical representation (C51/DiscoRL style).

    Key DiscoRL innovations:
    - 601 bins for value distribution (like Disco103)
    - Max absolute value of 300 (scaled for trading)
    - Signed hyperbolic transform option
    """

    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (256, 128),
        num_bins: int = 51,  # C51 default, can use 601 like DiscoRL
        v_min: float = -10.0,  # Min value (scaled for % returns)
        v_max: float = 10.0,  # Max value (scaled for % returns)
        use_dueling: bool = True,
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_actions = num_actions
        self.num_bins = num_bins
        self.v_min = v_min
        self.v_max = v_max
        self.use_dueling = use_dueling

        # Support atoms
        self.register_buffer("support", torch.linspace(v_min, v_max, num_bins))
        self.delta_z = (v_max - v_min) / (num_bins - 1)

        # Shared feature extractor
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(prev_dim, hidden_dim),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_dim),
                ]
            )
            prev_dim = hidden_dim

        self.feature_extractor = nn.Sequential(*layers)

        if use_dueling:
            # Value distribution stream
            self.value_stream = nn.Sequential(
                nn.Linear(prev_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_bins),
            )
            # Advantage distribution stream
            self.advantage_stream = nn.Sequential(
                nn.Linear(prev_dim, 64),
                nn.ReLU(),
                nn.Linear(64, num_actions * num_bins),
            )
        else:
            # Standard distribution head
            self.dist_head = nn.Linear(prev_dim, num_actions * num_bins)

        self._init_weights()

    def _init_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.01)  # Small init like DiscoRL
                nn.init.constant_(m.bias, 0)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """
        Returns Q-values (expected values from distributions).

        For training, use get_distribution() to get full distributions.
        """
        dist = self.get_distribution(x)
        q_values = (dist * self.support).sum(dim=-1)
        return q_values

    def get_distribution(self, x: torch.Tensor) -> torch.Tensor:
        """
        Get value distributions for all actions.

        Returns:
            Tensor of shape [batch, num_actions, num_bins] with probabilities
        """
        batch_size = x.shape[0]
        features = self.feature_extractor(x)

        if self.use_dueling:
            # Value distribution
            value_dist = self.value_stream(features)  # [B, num_bins]
            value_dist = F.softmax(value_dist, dim=-1)

            # Advantage distribution
            adv_dist = self.advantage_stream(features)  # [B, A*num_bins]
            adv_dist = adv_dist.view(batch_size, self.num_actions, self.num_bins)
            adv_dist = F.softmax(adv_dist, dim=-1)

            # Combine (approximate)
            # In distributional setting, we work with log-space for stability
            value_dist = value_dist.unsqueeze(1)  # [B, 1, num_bins]
            dist = value_dist + adv_dist - adv_dist.mean(dim=1, keepdim=True)
            dist = F.softmax(dist, dim=-1)
        else:
            logits = self.dist_head(features)
            logits = logits.view(batch_size, self.num_actions, self.num_bins)
            dist = F.softmax(logits, dim=-1)

        return dist

    def project_distribution(
        self,
        next_dist: torch.Tensor,
        rewards: torch.Tensor,
        dones: torch.Tensor,
        gamma: float = 0.99,
    ) -> torch.Tensor:
        """
        Project the target distribution onto the support.

        Implements the Bellman projection for distributional RL.
        """
        batch_size = rewards.shape[0]

        # Compute projected support
        # Tz = r + γ * z (clamped to [v_min, v_max])
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
        projected = torch.zeros(batch_size, self.num_bins, device=rewards.device)
        offset = (
            torch.linspace(0, (batch_size - 1) * self.num_bins, batch_size, device=rewards.device)
            .long()
            .unsqueeze(-1)
        )

        # Lower bound contribution
        projected.view(-1).index_add_(
            0, (lower_idx + offset).view(-1), (next_dist * (upper_idx.float() - b)).view(-1)
        )
        # Upper bound contribution
        projected.view(-1).index_add_(
            0, (upper_idx + offset).view(-1), (next_dist * (b - lower_idx.float())).view(-1)
        )

        return projected


class DiscoInspiredNetwork(nn.Module):
    """
    Network architecture inspired by DiscoRL's Disco103.

    Combines:
    - Categorical value distribution (like C51/DiscoRL)
    - Auxiliary prediction heads (like DiscoRL's y, z predictions)
    - Layer normalization throughout
    """

    def __init__(
        self,
        input_dim: int,
        num_actions: int = 3,
        hidden_dims: tuple[int, ...] = (512, 512),
        num_bins: int = 601,  # DiscoRL uses 601 bins
        v_min: float = -300.0,  # DiscoRL max_abs_value = 300
        v_max: float = 300.0,
        prediction_size: int = 128,  # Auxiliary prediction dimension
    ):
        super().__init__()
        self.input_dim = input_dim
        self.num_actions = num_actions
        self.num_bins = num_bins
        self.v_min = v_min
        self.v_max = v_max
        self.prediction_size = prediction_size

        # Support atoms
        self.register_buffer("support", torch.linspace(v_min, v_max, num_bins))
        self.delta_z = (v_max - v_min) / (num_bins - 1)

        # Feature extractor (like DiscoRL's agent network)
        layers = []
        prev_dim = input_dim
        for hidden_dim in hidden_dims:
            layers.extend(
                [
                    nn.Linear(prev_dim, hidden_dim),
                    nn.ReLU(),
                    nn.LayerNorm(hidden_dim),
                ]
            )
            prev_dim = hidden_dim

        self.feature_extractor = nn.Sequential(*layers)

        # LSTM for temporal context (like DiscoRL's model_kwargs lstm_size=128)
        self.lstm = nn.LSTM(
            input_size=prev_dim,
            hidden_size=128,
            num_layers=1,
            batch_first=True,
        )

        # Q-value distribution head
        self.q_head = nn.Linear(128, num_actions * num_bins)

        # Policy logits head
        self.policy_head = nn.Linear(128, num_actions)

        # Auxiliary prediction head (like DiscoRL's y prediction)
        self.aux_head = nn.Linear(128, prediction_size)

        self._init_weights()

    def _init_weights(self):
        # Small initialization like DiscoRL (head_w_init_std=1e-2)
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.orthogonal_(m.weight, gain=0.01)
                nn.init.constant_(m.bias, 0)

    def forward(
        self,
        x: torch.Tensor,
        hidden: tuple[torch.Tensor, torch.Tensor] | None = None,
    ) -> dict:
        """
        Forward pass returning Q-values and auxiliary outputs.

        Returns:
            dict with keys: q_values, policy_logits, aux_prediction, distribution
        """
        batch_size = x.shape[0]

        # Feature extraction
        features = self.feature_extractor(x)

        # Handle sequence dimension for LSTM
        if features.dim() == 2:
            features = features.unsqueeze(1)

        # LSTM
        if hidden is None:
            h0 = torch.zeros(1, batch_size, 128, device=x.device)
            c0 = torch.zeros(1, batch_size, 128, device=x.device)
            hidden = (h0, c0)

        lstm_out, new_hidden = self.lstm(features, hidden)
        lstm_out = lstm_out[:, -1, :]  # Take last output

        # Q-value distribution
        q_logits = self.q_head(lstm_out)
        q_logits = q_logits.view(batch_size, self.num_actions, self.num_bins)
        q_dist = F.softmax(q_logits, dim=-1)
        q_values = (q_dist * self.support).sum(dim=-1)

        # Policy logits
        policy_logits = self.policy_head(lstm_out)

        # Auxiliary prediction
        aux_pred = self.aux_head(lstm_out)

        return {
            "q_values": q_values,
            "q_distribution": q_dist,
            "q_logits": q_logits,
            "policy_logits": policy_logits,
            "aux_prediction": aux_pred,
            "hidden": new_hidden,
        }

    def get_q_values(self, x: torch.Tensor) -> torch.Tensor:
        """Simple interface for Q-value retrieval."""
        return self.forward(x)["q_values"]

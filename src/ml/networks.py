import torch
import torch.nn as nn


class LSTMPPO(nn.Module):
    """
    Hybrid LSTM-PPO Network for Trading.

    Architecture:
    1. LSTM Encoder: Processes time-series market data (OHLCV + indicators)
    2. Actor Head: Outputs action probabilities (Buy, Sell, Hold)
    3. Critic Head: Outputs value estimate for the state
    """

    def __init__(
        self,
        input_dim: int,
        hidden_dim: int = 128,
        num_layers: int = 2,
        action_dim: int = 3,
    ):
        """
        Args:
            input_dim: Number of input features (e.g., Open, High, Low, Close, Vol, RSI, MACD...)
            hidden_dim: Hidden dimension of LSTM and dense layers
            num_layers: Number of LSTM layers
            action_dim: Number of actions (default 3: Hold, Buy, Sell)
        """
        super().__init__()

        self.hidden_dim = hidden_dim
        self.num_layers = num_layers

        # 1. Feature Extractor (LSTM)
        # batch_first=True expects input shape: (batch, seq_len, features)
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2 if num_layers > 1 else 0,
        )

        # 2. Actor Head (Policy)
        self.actor = nn.Sequential(
            nn.Linear(hidden_dim, 64),
            nn.ReLU(),
            nn.Linear(64, action_dim),
            nn.Softmax(dim=-1),
        )

        # 3. Critic Head (Value)
        self.critic = nn.Sequential(nn.Linear(hidden_dim, 64), nn.ReLU(), nn.Linear(64, 1))

    def forward(self, x: torch.Tensor, hidden: tuple[torch.Tensor, torch.Tensor] = None):
        """
        Forward pass.

        Args:
            x: Input tensor of shape (batch, seq_len, input_dim)
            hidden: Optional hidden state for LSTM

        Returns:
            action_probs: Probability distribution over actions
            state_value: Estimated value of the current state
            next_hidden: Updated hidden state
        """
        # LSTM encoding
        # out shape: (batch, seq_len, hidden_dim)
        # h_n, c_n shape: (num_layers, batch, hidden_dim)
        lstm_out, next_hidden = self.lstm(x, hidden)

        # We only care about the last time step for the decision
        # last_step_out shape: (batch, hidden_dim)
        last_step_out = lstm_out[:, -1, :]

        # Actor: Action probabilities
        action_probs = self.actor(last_step_out)

        # Critic: State Value
        state_value = self.critic(last_step_out)

        return action_probs, state_value, next_hidden

    def get_action(
        self,
        x: torch.Tensor,
        hidden: tuple[torch.Tensor, torch.Tensor] = None,
        deterministic: bool = False,
    ):
        """
        Select an action given the state.

        Args:
            x: Input state
            hidden: LSTM hidden state
            deterministic: If True, return the argmax action. If False, sample from distribution.

        Returns:
            action: Selected action index
            log_prob: Log probability of the selected action
            value: State value estimate
            hidden: Updated hidden state
        """
        action_probs, value, next_hidden = self.forward(x, hidden)

        if deterministic:
            action = torch.argmax(action_probs, dim=-1)
            log_prob = torch.log(action_probs.gather(1, action.unsqueeze(1)))
        else:
            dist = torch.distributions.Categorical(action_probs)
            action = dist.sample()
            log_prob = dist.log_prob(action)

        return action.item(), log_prob, value, next_hidden

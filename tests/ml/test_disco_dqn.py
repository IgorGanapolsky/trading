"""
Tests for DiscoRL-Inspired DQN Components.

Tests the key innovations adopted from DiscoRL:
- Categorical value distribution networks
- Moving average normalization
- Prioritized replay with TD normalization
- DiscoDQN agent integration
"""

import numpy as np
import pytest
import torch


class TestCategoricalDQNNetwork:
    """Test categorical (distributional) DQN network."""

    def test_network_initialization(self):
        from src.ml.dqn_networks import CategoricalDQNNetwork

        net = CategoricalDQNNetwork(
            input_dim=10,
            num_actions=3,
            num_bins=51,
            v_min=-10.0,
            v_max=10.0,
        )
        assert net.num_bins == 51
        assert net.num_actions == 3
        assert len(net.support) == 51

    def test_forward_pass(self):
        from src.ml.dqn_networks import CategoricalDQNNetwork

        net = CategoricalDQNNetwork(input_dim=10, num_actions=3, num_bins=51)
        state = torch.randn(4, 10)  # Batch of 4
        q_values = net(state)

        assert q_values.shape == (4, 3)  # [batch, actions]

    def test_distribution_output(self):
        from src.ml.dqn_networks import CategoricalDQNNetwork

        net = CategoricalDQNNetwork(input_dim=10, num_actions=3, num_bins=51)
        state = torch.randn(4, 10)
        dist = net.get_distribution(state)

        assert dist.shape == (4, 3, 51)  # [batch, actions, bins]
        # Distribution should sum to 1 for each action
        assert torch.allclose(dist.sum(dim=-1), torch.ones(4, 3), atol=1e-5)


class TestDiscoInspiredNetwork:
    """Test full DiscoRL-inspired network."""

    def test_network_initialization(self):
        from src.ml.dqn_networks import DiscoInspiredNetwork

        net = DiscoInspiredNetwork(
            input_dim=10,
            num_actions=3,
            num_bins=601,  # DiscoRL uses 601
            v_min=-300.0,
            v_max=300.0,
        )
        assert net.num_bins == 601
        assert net.prediction_size == 128  # Auxiliary prediction

    def test_forward_returns_dict(self):
        from src.ml.dqn_networks import DiscoInspiredNetwork

        net = DiscoInspiredNetwork(input_dim=10, num_actions=3)
        state = torch.randn(4, 10)
        output = net(state)

        assert "q_values" in output
        assert "q_distribution" in output
        assert "policy_logits" in output
        assert "aux_prediction" in output
        assert output["q_values"].shape == (4, 3)


class TestMovingAverage:
    """Test EMA normalization (DiscoRL-style)."""

    def test_initialization(self):
        from src.ml.prioritized_replay import MovingAverage

        ema = MovingAverage(decay=0.99, eps=1e-6)
        assert ema.decay == 0.99
        assert ema.mean == 0.0
        assert ema.var == 1.0

    def test_update(self):
        from src.ml.prioritized_replay import MovingAverage

        ema = MovingAverage(decay=0.99)
        values = np.array([1.0, 2.0, 3.0, 4.0, 5.0])
        ema.update(values)

        # First update should set mean directly
        assert ema.mean == pytest.approx(np.mean(values), rel=0.1)

    def test_normalize(self):
        from src.ml.prioritized_replay import MovingAverage

        ema = MovingAverage(decay=0.99)
        ema.mean = 5.0
        ema.var = 4.0

        values = np.array([3.0, 5.0, 7.0])
        normalized = ema.normalize(values)

        # (3-5)/2 = -1, (5-5)/2 = 0, (7-5)/2 = 1
        assert normalized[1] == pytest.approx(0.0, abs=0.1)


class TestPrioritizedReplayBuffer:
    """Test prioritized replay with TD normalization."""

    def test_add_and_sample(self):
        from src.ml.prioritized_replay import PrioritizedReplayBuffer

        buffer = PrioritizedReplayBuffer(capacity=100)

        # Add experiences
        for i in range(50):
            buffer.add(
                state=np.random.randn(10),
                action=np.random.randint(0, 3),
                reward=np.random.randn(),
                next_state=np.random.randn(10),
                done=False,
            )

        assert len(buffer) == 50

        # Sample batch
        batch, indices, weights = buffer.sample(16)
        assert len(batch) == 16
        assert len(indices) == 16
        assert len(weights) == 16

    def test_priority_update(self):
        from src.ml.prioritized_replay import PrioritizedReplayBuffer

        buffer = PrioritizedReplayBuffer(capacity=100, use_td_normalization=True)

        for i in range(50):
            buffer.add(
                state=np.random.randn(10),
                action=0,
                reward=0.0,
                next_state=np.random.randn(10),
                done=False,
            )

        _, indices, _ = buffer.sample(16)
        td_errors = np.random.randn(16)
        buffer.update_priorities(indices, td_errors)

        # Check that TD EMA was updated
        assert buffer.td_ema is not None
        assert buffer.td_ema.count > 0


class TestDiscoDQNAgent:
    """Test full DiscoDQN agent."""

    def test_agent_initialization(self):
        from src.ml.disco_dqn_agent import DiscoDQNAgent

        agent = DiscoDQNAgent(
            state_dim=10,
            action_dim=3,
            num_bins=51,
            v_min=-10.0,
            v_max=10.0,
        )
        assert agent.num_bins == 51
        assert agent.action_dim == 3

    def test_action_selection(self):
        from src.ml.disco_dqn_agent import DiscoDQNAgent

        agent = DiscoDQNAgent(state_dim=10, action_dim=3)
        state = np.random.randn(10)

        # Exploration
        agent.epsilon = 1.0
        action, info = agent.select_action(state, training=True)
        assert action in [0, 1, 2]
        assert info["source"] == "exploration"

        # Exploitation
        agent.epsilon = 0.0
        action, info = agent.select_action(state, training=True)
        assert action in [0, 1, 2]
        assert info["source"] == "exploitation"
        assert "q_values" in info

    def test_store_and_train(self):
        from src.ml.disco_dqn_agent import DiscoDQNAgent

        agent = DiscoDQNAgent(state_dim=10, action_dim=3, batch_size=8)

        # Store transitions
        for _ in range(20):
            agent.store_transition(
                state=np.random.randn(10),
                action=np.random.randint(0, 3),
                reward=np.random.randn(),
                next_state=np.random.randn(10),
                done=False,
            )

        # Train
        loss_dict = agent.train_step()
        assert loss_dict is not None
        assert "total_loss" in loss_dict

    def test_save_and_load(self, tmp_path):
        from src.ml.disco_dqn_agent import DiscoDQNAgent

        agent = DiscoDQNAgent(state_dim=10, action_dim=3)
        agent.step_count = 100
        agent.epsilon = 0.5

        filepath = str(tmp_path / "disco_dqn.pt")
        agent.save(filepath)

        # Load into new agent
        agent2 = DiscoDQNAgent(state_dim=10, action_dim=3)
        agent2.load(filepath)

        assert agent2.step_count == 100
        assert agent2.epsilon == 0.5


class TestDQNNetworks:
    """Test standard DQN network architectures."""

    def test_standard_dqn(self):
        from src.ml.dqn_networks import DQNNetwork

        net = DQNNetwork(input_dim=10, num_actions=3)
        state = torch.randn(4, 10)
        q_values = net(state)
        assert q_values.shape == (4, 3)

    def test_dueling_dqn(self):
        from src.ml.dqn_networks import DuelingDQNNetwork

        net = DuelingDQNNetwork(input_dim=10, num_actions=3)
        state = torch.randn(4, 10)
        q_values = net(state)
        assert q_values.shape == (4, 3)

    def test_lstm_dqn(self):
        from src.ml.dqn_networks import LSTMDQNNetwork

        net = LSTMDQNNetwork(input_dim=10, num_actions=3)
        state = torch.randn(4, 10)
        q_values = net(state)
        assert q_values.shape == (4, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

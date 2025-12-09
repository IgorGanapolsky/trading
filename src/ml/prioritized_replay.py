"""
Prioritized Experience Replay Buffer with DiscoRL-Inspired Enhancements.

Implements:
- Proportional prioritization (Schaul et al., 2015)
- Importance sampling weights
- Sum-tree for O(log n) sampling

DiscoRL Integration (Dec 2025):
- Moving average normalization for TD errors (like DiscoRL's EMA)
- Support for auxiliary predictions in experience
"""

import logging
from dataclasses import dataclass
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """Single experience tuple with optional auxiliary data."""

    state: np.ndarray
    action: int
    reward: float
    next_state: np.ndarray
    done: bool
    td_error: float | None = None
    aux_prediction: np.ndarray | None = None  # DiscoRL-style auxiliary


class SumTree:
    """
    Sum tree for efficient prioritized sampling.

    Tree structure where parent = sum of children.
    Enables O(log n) sampling based on priorities.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)
        self.data = [None] * capacity
        self.write_idx = 0
        self.size = 0

    def _propagate(self, idx: int, change: float):
        """Propagate priority change up the tree."""
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx: int, s: float) -> int:
        """Find leaf node for given cumulative sum."""
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):
            return idx

        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self) -> float:
        """Total priority sum."""
        return self.tree[0]

    def add(self, priority: float, data: Any):
        """Add experience with priority."""
        idx = self.write_idx + self.capacity - 1
        self.data[self.write_idx] = data
        self.update(idx, priority)
        self.write_idx = (self.write_idx + 1) % self.capacity
        self.size = min(self.size + 1, self.capacity)

    def update(self, idx: int, priority: float):
        """Update priority at index."""
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)

    def get(self, s: float) -> tuple[int, float, Any]:
        """Sample based on cumulative sum."""
        idx = self._retrieve(0, s)
        data_idx = idx - self.capacity + 1
        return idx, self.tree[idx], self.data[data_idx]


class MovingAverage:
    """
    Exponential moving average for normalization.

    Directly inspired by DiscoRL's utils.MovingAverage.
    Used for normalizing advantages and TD errors.
    """

    def __init__(self, decay: float = 0.99, eps: float = 1e-6):
        """
        Args:
            decay: EMA decay factor (0.99 means slow adaptation)
            eps: Small constant for numerical stability
        """
        self.decay = decay
        self.eps = eps
        self.mean = 0.0
        self.var = 1.0
        self.count = 0

    def update(self, values: np.ndarray) -> "MovingAverage":
        """Update running statistics."""
        batch_mean = np.mean(values)
        batch_var = np.var(values)
        batch_count = len(values)

        if self.count == 0:
            self.mean = batch_mean
            self.var = batch_var
        else:
            # EMA update
            self.mean = self.decay * self.mean + (1 - self.decay) * batch_mean
            self.var = self.decay * self.var + (1 - self.decay) * batch_var

        self.count += batch_count
        return self

    def normalize(self, values: np.ndarray, subtract_mean: bool = True) -> np.ndarray:
        """Normalize values using running statistics."""
        std = np.sqrt(self.var + self.eps)
        if subtract_mean:
            return (values - self.mean) / std
        else:
            return values / std

    def get_state(self) -> dict:
        """Get state for serialization."""
        return {
            "mean": self.mean,
            "var": self.var,
            "count": self.count,
        }

    def load_state(self, state: dict):
        """Load state from dict."""
        self.mean = state["mean"]
        self.var = state["var"]
        self.count = state["count"]


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay with DiscoRL-inspired enhancements.

    Features:
    - Sum-tree for O(log n) sampling
    - Importance sampling weights
    - EMA normalization for TD errors
    - Support for auxiliary predictions
    """

    def __init__(
        self,
        capacity: int = 100000,
        alpha: float = 0.6,  # Priority exponent
        beta: float = 0.4,  # IS weight exponent (annealed to 1.0)
        beta_increment: float = 0.001,
        min_priority: float = 1e-6,
        use_td_normalization: bool = True,  # DiscoRL-inspired
    ):
        """
        Args:
            capacity: Maximum buffer size
            alpha: Priority exponent (0 = uniform, 1 = full prioritization)
            beta: Importance sampling weight exponent
            beta_increment: Per-sample beta increment
            min_priority: Minimum priority to prevent zero probabilities
            use_td_normalization: Use EMA for TD error normalization
        """
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        self.min_priority = min_priority
        self.use_td_normalization = use_td_normalization

        self.tree = SumTree(capacity)
        self.max_priority = 1.0

        # DiscoRL-inspired TD normalization
        self.td_ema = MovingAverage(decay=0.99) if use_td_normalization else None

        logger.info(
            f"PrioritizedReplayBuffer initialized: capacity={capacity}, "
            f"alpha={alpha}, beta={beta}, td_norm={use_td_normalization}"
        )

    def __len__(self) -> int:
        return self.tree.size

    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: float | None = None,
        aux_prediction: np.ndarray | None = None,
    ):
        """Add experience with optional TD error priority."""
        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            td_error=td_error,
            aux_prediction=aux_prediction,
        )

        # Use max priority for new experiences (will be updated after first use)
        priority = self.max_priority**self.alpha
        self.tree.add(priority, experience)

    def sample(self, batch_size: int) -> tuple[list[Experience], np.ndarray, np.ndarray]:
        """
        Sample batch with importance sampling weights.

        Returns:
            (experiences, tree_indices, IS_weights)
        """
        batch = []
        indices = np.empty(batch_size, dtype=np.int32)
        weights = np.empty(batch_size, dtype=np.float32)

        # Segment the total priority range
        total = self.tree.total()
        segment = total / batch_size

        # Anneal beta towards 1.0
        self.beta = min(1.0, self.beta + self.beta_increment)

        # Min probability for IS weights
        min_prob = self.min_priority / total if total > 0 else self.min_priority

        for i in range(batch_size):
            # Sample from segment
            low = segment * i
            high = segment * (i + 1)
            s = np.random.uniform(low, high)

            idx, priority, experience = self.tree.get(s)
            indices[i] = idx
            batch.append(experience)

            # Importance sampling weight
            prob = priority / total if total > 0 else 1.0
            prob = max(prob, min_prob)
            weights[i] = (self.tree.size * prob) ** (-self.beta)

        # Normalize weights
        weights = weights / weights.max()

        return batch, indices, weights

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """Update priorities based on TD errors."""
        # Optionally normalize TD errors using EMA (DiscoRL-style)
        if self.td_ema is not None:
            self.td_ema.update(td_errors)
            normalized_errors = self.td_ema.normalize(td_errors, subtract_mean=False)
        else:
            normalized_errors = td_errors

        for idx, error in zip(indices, normalized_errors):
            # Priority = |TD error| + epsilon
            priority = (np.abs(error) + self.min_priority) ** self.alpha
            self.tree.update(idx, priority)
            self.max_priority = max(self.max_priority, priority)

    def get_stats(self) -> dict:
        """Get buffer statistics."""
        stats = {
            "size": len(self),
            "capacity": self.capacity,
            "beta": self.beta,
            "max_priority": self.max_priority,
        }
        if self.td_ema is not None:
            stats["td_ema"] = self.td_ema.get_state()
        return stats


class UniformReplayBuffer:
    """Simple uniform replay buffer for comparison."""

    def __init__(self, capacity: int = 100000):
        self.capacity = capacity
        self.buffer: list[Experience] = []
        self.position = 0

    def __len__(self) -> int:
        return len(self.buffer)

    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        **kwargs,  # Ignore extra args for compatibility
    ):
        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
        )
        if len(self.buffer) < self.capacity:
            self.buffer.append(experience)
        else:
            self.buffer[self.position] = experience
        self.position = (self.position + 1) % self.capacity

    def sample(self, batch_size: int) -> list[Experience]:
        indices = np.random.choice(len(self.buffer), batch_size, replace=False)
        return [self.buffer[i] for i in indices]

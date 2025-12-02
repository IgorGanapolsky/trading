"""
Prioritized Experience Replay Buffer

Implements prioritized experience replay from Deep Learning Specialization:
- TD-error based prioritization
- Importance sampling weights
- Efficient sampling using sum-tree

Improves sample efficiency by replaying important transitions more frequently.
"""

import random
from collections import namedtuple
from typing import Any, Optional

import numpy as np

Experience = namedtuple(
    "Experience", ["state", "action", "reward", "next_state", "done", "td_error"]
)


class SumTree:
    """
    Sum Tree for efficient prioritized sampling.

    Binary tree where parent nodes contain sum of children.
    Allows O(log n) sampling and update.
    """

    def __init__(self, capacity: int):
        self.capacity = capacity
        self.tree = np.zeros(2 * capacity - 1)
        self.data = np.zeros(capacity, dtype=object)
        self.write = 0
        self.n_entries = 0

    def _propagate(self, idx: int, change: float):
        """Update parent nodes."""
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx: int, s: float) -> int:
        """Find sample index."""
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):
            return idx

        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self) -> float:
        """Get total priority."""
        return self.tree[0]

    def add(self, priority: float, data: Any):
        """Add experience with priority."""
        idx = self.write + self.capacity - 1

        self.data[self.write] = data
        self.update(idx, priority)

        self.write += 1
        if self.write >= self.capacity:
            self.write = 0

        if self.n_entries < self.capacity:
            self.n_entries += 1

    def update(self, idx: int, priority: float):
        """Update priority."""
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)

    def get(self, s: float) -> tuple[int, Any, float]:
        """Sample experience."""
        idx = self._retrieve(0, s)
        data_idx = idx - self.capacity + 1
        return idx, self.data[data_idx], self.tree[idx]


class PrioritizedReplayBuffer:
    """
    Prioritized Experience Replay Buffer.

    Samples transitions with probability proportional to TD-error.
    Uses importance sampling to correct for bias.
    """

    def __init__(
        self,
        capacity: int = 10000,
        alpha: float = 0.6,  # Prioritization exponent (0 = uniform, 1 = full prioritization)
        beta: float = 0.4,  # Importance sampling exponent
        beta_increment: float = 0.001,  # Beta annealing
        epsilon: float = 1e-6,  # Small constant to avoid zero priority
    ):
        self.capacity = capacity
        self.alpha = alpha
        self.beta = beta
        self.beta_increment = beta_increment
        self.epsilon = epsilon

        self.tree = SumTree(capacity)
        self.max_priority = 1.0

    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
        td_error: Optional[float] = None,
    ):
        """
        Add experience to buffer.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode ended
            td_error: TD-error (if None, uses max priority)
        """
        if td_error is None:
            priority = self.max_priority
        else:
            priority = (abs(td_error) + self.epsilon) ** self.alpha

        experience = Experience(
            state=state,
            action=action,
            reward=reward,
            next_state=next_state,
            done=done,
            td_error=td_error or 0.0,
        )

        self.tree.add(priority, experience)

    def sample(self, batch_size: int) -> tuple[list[Experience], np.ndarray, np.ndarray]:
        """
        Sample batch of experiences.

        Args:
            batch_size: Number of samples

        Returns:
            Experiences, indices, importance sampling weights
        """
        batch = []
        indices = []
        priorities = []

        segment = self.tree.total() / batch_size

        # Anneal beta
        self.beta = min(1.0, self.beta + self.beta_increment)

        for i in range(batch_size):
            a = segment * i
            b = segment * (i + 1)
            s = random.uniform(a, b)

            idx, experience, priority = self.tree.get(s)

            batch.append(experience)
            indices.append(idx)
            priorities.append(priority)

        # Calculate importance sampling weights
        priorities = np.array(priorities)
        probabilities = priorities / self.tree.total()
        weights = (self.tree.n_entries * probabilities) ** (-self.beta)
        weights = weights / weights.max()  # Normalize

        return batch, np.array(indices), weights

    def update_priorities(self, indices: np.ndarray, td_errors: np.ndarray):
        """
        Update priorities for sampled experiences.

        Args:
            indices: Indices of experiences
            td_errors: New TD-errors
        """
        priorities = (np.abs(td_errors) + self.epsilon) ** self.alpha

        for idx, priority in zip(indices, priorities):
            self.tree.update(idx, priority)
            self.max_priority = max(self.max_priority, priority)

    def __len__(self) -> int:
        """Get current buffer size."""
        return self.tree.n_entries

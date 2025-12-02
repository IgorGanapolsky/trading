"""
Multi-Step Learning for RL

Implements n-step returns for faster learning:
- n-step Q-learning
- n-step advantage estimation
- Eligibility traces (optional)

Benefits:
- Faster learning by propagating rewards further
- Better credit assignment
- Reduced variance compared to 1-step
"""

from collections import deque
from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass
class NStepTransition:
    """N-step transition."""

    state: np.ndarray
    action: int
    rewards: list[float]  # n rewards
    next_state: np.ndarray
    done: bool
    n: int  # Number of steps


class NStepBuffer:
    """
    Buffer for n-step learning.

    Stores transitions and computes n-step returns when ready.
    """

    def __init__(self, n: int = 3, gamma: float = 0.99):
        """
        Initialize n-step buffer.

        Args:
            n: Number of steps
            gamma: Discount factor
        """
        self.n = n
        self.gamma = gamma
        self.buffer: deque[tuple] = deque(maxlen=n)

    def add(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ) -> Optional[NStepTransition]:
        """
        Add transition and return n-step transition if ready.

        Args:
            state: Current state
            action: Action taken
            reward: Reward received
            next_state: Next state
            done: Whether episode ended

        Returns:
            N-step transition if ready, None otherwise
        """
        self.buffer.append((state, action, reward, next_state, done))

        if len(self.buffer) == self.n or done:
            # Compute n-step return
            initial_state, initial_action, _, _, _ = self.buffer[0]
            rewards = [r for _, _, r, _, _ in self.buffer]
            final_next_state, _, _, _, final_done = self.buffer[-1]

            # Compute n-step return (unused here, computed later)
            # n_step_return = self._compute_n_step_return(rewards, final_done)

            transition = NStepTransition(
                state=initial_state,
                action=initial_action,
                rewards=rewards,
                next_state=final_next_state,
                done=final_done,
                n=len(self.buffer),
            )

            # Clear buffer if done
            if done:
                self.buffer.clear()
            else:
                # Keep last transition for next n-step
                self.buffer = deque([self.buffer[-1]], maxlen=self.n)

            return transition

        return None

    def _compute_n_step_return(self, rewards: list[float], done: bool) -> float:
        """Compute n-step return."""
        return sum(r * (self.gamma**i) for i, r in enumerate(rewards))

    def flush(self) -> Optional[NStepTransition]:
        """Flush remaining transitions."""
        if len(self.buffer) > 1:
            initial_state, initial_action, _, _, _ = self.buffer[0]
            rewards = [r for _, _, r, _, _ in self.buffer]
            final_next_state, _, _, _, final_done = self.buffer[-1]

            transition = NStepTransition(
                state=initial_state,
                action=initial_action,
                rewards=rewards,
                next_state=final_next_state,
                done=final_done,
                n=len(self.buffer),
            )

            self.buffer.clear()
            return transition

        return None


class NStepDQNAgent:
    """
    DQN Agent with n-step learning.

    Uses n-step returns instead of 1-step for faster learning.
    """

    def __init__(self, base_agent, n: int = 3):
        """
        Initialize n-step DQN agent.

        Args:
            base_agent: Base DQN agent
            n: Number of steps
        """
        self.base_agent = base_agent
        self.n = n
        self.n_step_buffer = NStepBuffer(n=n, gamma=base_agent.gamma)

    def store_transition(
        self,
        state: np.ndarray,
        action: int,
        reward: float,
        next_state: np.ndarray,
        done: bool,
    ):
        """Store transition and train on n-step returns."""
        # Add to n-step buffer
        n_step_transition = self.n_step_buffer.add(state, action, reward, next_state, done)

        if n_step_transition:
            # Compute n-step return
            n_step_return = sum(
                r * (self.base_agent.gamma**i) for i, r in enumerate(n_step_transition.rewards)
            )

            # Store with n-step return as reward
            self.base_agent.store_transition(
                state=n_step_transition.state,
                action=n_step_transition.action,
                reward=n_step_return,  # Use n-step return
                next_state=n_step_transition.next_state,
                done=n_step_transition.done,
            )

    def select_action(self, state: np.ndarray, **kwargs):
        """Select action using base agent."""
        return self.base_agent.select_action(state, **kwargs)

    def train_step(self):
        """Train base agent."""
        return self.base_agent.train_step()

    def get_stats(self):
        """Get statistics."""
        return self.base_agent.get_stats()

"""
Reinforcement Learning Layer - Adaptive policy learning

Inspired by AlphaQuanter framework:
- Learn optimal policies from experience
- Adapt to market conditions
- Improve decision-making over time

Simple RL implementation using Q-learning
"""

import json
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

import numpy as np

logger = logging.getLogger(__name__)


class RLPolicyLearner:
    """
    Reinforcement Learning policy learner for trading decisions.

    Uses Q-learning to learn optimal actions in different market states.
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        exploration_rate: float = 0.2,
        state_file: str = "data/rl_policy_state.json",
    ):
        self.learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = exploration_rate
        self.state_file = Path(state_file)

        # Q-table: state -> action -> Q-value
        self.q_table: dict[str, dict[str, float]] = defaultdict(
            lambda: {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        )

        # Load existing Q-table if available
        self._load_state()

        logger.info(
            f"RL Policy Learner initialized (α={learning_rate}, γ={discount_factor}, ε={exploration_rate})"
        )

    def get_state_key(self, market_state: dict[str, Any]) -> str:
        """
        Convert market state to discrete state key for Q-table.

        Args:
            market_state: Dict with market indicators

        Returns:
            State key string
        """
        # Discretize continuous states
        regime = market_state.get("market_regime", "UNKNOWN")

        # Discretize RSI
        rsi = market_state.get("rsi", 50)
        rsi_bin = "LOW" if rsi < 30 else "HIGH" if rsi > 70 else "MID"

        # Discretize MACD
        macd_hist = market_state.get("macd_histogram", 0)
        macd_bin = "BULL" if macd_hist > 0 else "BEAR"

        # Discretize trend
        trend = market_state.get("trend", "SIDEWAYS")

        return f"{regime}_{rsi_bin}_{macd_bin}_{trend}"

    def select_action(self, market_state: dict[str, Any], agent_recommendation: str) -> str:
        """
        Select action using epsilon-greedy policy.

        Args:
            market_state: Current market state
            agent_recommendation: Recommendation from agent consensus

        Returns:
            Selected action (BUY/SELL/HOLD)
        """
        state_key = self.get_state_key(market_state)

        # Epsilon-greedy: explore vs exploit
        if np.random.random() < self.exploration_rate:
            # Explore: Use agent recommendation (learning phase)
            action = agent_recommendation
            logger.debug(f"RL: EXPLORE - using agent rec: {action}")
        else:
            # Exploit: Use learned Q-values
            q_values = self.q_table[state_key]
            action = max(q_values, key=q_values.get)
            logger.debug(f"RL: EXPLOIT - Q-values: {q_values}, selected: {action}")

        return action

    def update_policy(
        self,
        prev_state: dict[str, Any],
        action: str,
        reward: float,
        new_state: dict[str, Any],
        done: bool = False,
    ) -> None:
        """
        Update Q-values based on observed reward.

        Args:
            prev_state: Previous market state
            action: Action taken
            reward: Reward received (profit/loss)
            new_state: New market state
            done: Whether episode is done
        """
        prev_key = self.get_state_key(prev_state)
        new_key = self.get_state_key(new_state)

        # Current Q-value
        current_q = self.q_table[prev_key][action]

        # Max Q-value for next state
        max_next_q = 0 if done else max(self.q_table[new_key].values())

        # Q-learning update: Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]
        new_q = current_q + self.learning_rate * (
            reward + self.discount_factor * max_next_q - current_q
        )

        self.q_table[prev_key][action] = new_q

        logger.info(
            f"RL UPDATE: State={prev_key}, Action={action}, Reward={reward:.4f}, Q: {current_q:.4f} -> {new_q:.4f}"
        )

        # Save updated state
        self._save_state()

    def calculate_reward(
        self,
        trade_result: dict[str, Any],
        market_state: Optional[dict[str, Any]] = None,
    ) -> float:
        """
        Calculate reward from trade result using world-class risk-adjusted reward function.

        Args:
            trade_result: Dict with P/L, win/loss, etc.
            market_state: Optional market state for risk adjustment

        Returns:
            Reward value (normalized)
        """
        # Use world-class risk-adjusted reward function if available
        try:
            from src.ml.reward_functions import RiskAdjustedReward

            reward_calculator = RiskAdjustedReward()
            return reward_calculator.calculate_from_trade_result(trade_result, market_state)
        except ImportError:
            # Fallback to simple reward
            logger.debug("Using simple reward function (reward_functions module not available)")

        # Fallback: Simple P/L-based reward
        pl_pct = trade_result.get("pl_pct", 0)
        reward = np.clip(pl_pct / 0.05, -1.0, 1.0)

        return reward

    def _save_state(self) -> None:
        """Save Q-table to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert defaultdict to regular dict for JSON serialization
            q_table_dict = {k: dict(v) for k, v in self.q_table.items()}

            state = {
                "q_table": q_table_dict,
                "learning_rate": self.learning_rate,
                "discount_factor": self.discount_factor,
                "exploration_rate": self.exploration_rate,
            }

            with open(self.state_file, "w") as f:
                json.dump(state, f, indent=2)

            logger.debug(f"RL state saved to {self.state_file}")

        except Exception as e:
            logger.error(f"Error saving RL state: {e}")

    def _load_state(self) -> None:
        """Load Q-table from disk."""
        if not self.state_file.exists():
            logger.info("No existing RL state found - starting fresh")
            return

        try:
            with open(self.state_file) as f:
                state = json.load(f)

            # Load Q-table
            loaded_q_table = state.get("q_table", {})
            for state_key, actions in loaded_q_table.items():
                self.q_table[state_key] = actions

            logger.info(f"RL state loaded: {len(self.q_table)} states learned")

        except Exception as e:
            logger.error(f"Error loading RL state: {e}")

    def get_policy_stats(self) -> dict[str, Any]:
        """Get statistics about learned policy."""
        total_states = len(self.q_table)

        # Count preferred actions
        action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for state_actions in self.q_table.values():
            best_action = max(state_actions, key=state_actions.get)
            action_counts[best_action] += 1

        return {
            "total_states_learned": total_states,
            "action_distribution": action_counts,
            "exploration_rate": self.exploration_rate,
        }

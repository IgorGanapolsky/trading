"""
Optimized Reinforcement Learning Layer - Enhanced Q-learning

Improvements over base RLPolicyLearner:
- Better state representation with more features
- Risk-adjusted reward function
- Experience replay buffer for better learning
- Epsilon decay for exploration/exploitation balance
- State-action value tracking and statistics
- Adaptive learning rate
- Better handling of market regime changes
- Multi-timescale memory integration (nested learning)

Inspired by:
- AlphaQuanter framework
- Pro Trader RL patterns
- Risk-aware RL research (2024)
- Google Nested Learning paradigm
"""

import json
import logging
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    """Experience tuple for replay buffer."""

    state: dict[str, Any]
    action: str
    reward: float
    next_state: dict[str, Any]
    done: bool
    timestamp: float


@dataclass
class StateActionStats:
    """Statistics for state-action pairs."""

    count: int = 0
    total_reward: float = 0.0
    avg_reward: float = 0.0
    last_updated: float = 0.0


class OptimizedRLPolicyLearner:
    """
    Enhanced RL policy learner with advanced features.

    Improvements:
    - Richer state representation
    - Risk-adjusted rewards
    - Experience replay
    - Adaptive exploration
    - Better market regime handling
    """

    def __init__(
        self,
        learning_rate: float = 0.1,
        discount_factor: float = 0.95,
        initial_exploration_rate: float = 0.3,
        min_exploration_rate: float = 0.05,
        exploration_decay: float = 0.995,
        state_file: str = "data/rl_policy_state_optimized.json",
        enable_replay: bool = True,
        replay_buffer_size: int = 10000,
        replay_batch_size: int = 32,
        enable_adaptive_lr: bool = True,
        use_multi_timescale: bool = True,
        context_engine=None,
    ):
        """
        Initialize optimized RL policy learner.

        Args:
            learning_rate: Initial learning rate
            discount_factor: Discount factor (gamma)
            initial_exploration_rate: Starting epsilon
            min_exploration_rate: Minimum epsilon
            exploration_decay: Epsilon decay per update
            state_file: Path to save state
            enable_replay: Enable experience replay
            replay_buffer_size: Size of replay buffer
            replay_batch_size: Batch size for replay
            enable_adaptive_lr: Enable adaptive learning rate
            use_multi_timescale: Use multi-timescale memory context
            context_engine: ContextEngine instance (None = auto-get)
        """
        self.learning_rate = learning_rate
        self.base_learning_rate = learning_rate
        self.discount_factor = discount_factor
        self.exploration_rate = initial_exploration_rate
        self.initial_exploration_rate = initial_exploration_rate
        self.min_exploration_rate = min_exploration_rate
        self.exploration_decay = exploration_decay
        self.state_file = Path(state_file)
        self.enable_replay = enable_replay
        self.replay_buffer_size = replay_buffer_size
        self.replay_batch_size = replay_batch_size
        self.enable_adaptive_lr = enable_adaptive_lr
        self.use_multi_timescale = use_multi_timescale

        # Multi-timescale memory support
        if use_multi_timescale and context_engine is None:
            try:
                from src.agent_framework.context_engine import get_context_engine

                self.context_engine = get_context_engine()
            except ImportError:
                self.context_engine = None
                self.use_multi_timescale = False
                logger.warning("ContextEngine not available, disabling multi-timescale")
        else:
            self.context_engine = context_engine

        # Q-table: state -> action -> Q-value
        self.q_table: dict[str, dict[str, float]] = defaultdict(
            lambda: {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        )

        # Experience replay buffer
        self.replay_buffer: deque = deque(maxlen=replay_buffer_size)

        # State-action statistics
        self.state_action_stats: dict[str, dict[str, StateActionStats]] = defaultdict(
            lambda: {
                "BUY": StateActionStats(),
                "SELL": StateActionStats(),
                "HOLD": StateActionStats(),
            }
        )

        # Performance tracking
        self.update_count = 0
        self.total_rewards = 0.0
        self.episode_rewards: list[float] = []

        # Load existing state
        self._load_state()

        logger.info(
            f"OptimizedRLPolicyLearner initialized (α={learning_rate}, "
            f"γ={discount_factor}, ε={initial_exploration_rate}, replay={enable_replay})"
        )

    def get_state_key(self, market_state: dict[str, Any]) -> str:
        """
        Convert market state to discrete state key with richer features.

        Args:
            market_state: Dict with market indicators

        Returns:
            State key string
        """
        # Extract features
        regime = market_state.get("market_regime", "UNKNOWN")

        # RSI bins (more granular)
        rsi = market_state.get("rsi", 50)
        if rsi < 25:
            rsi_bin = "VERY_LOW"
        elif rsi < 40:
            rsi_bin = "LOW"
        elif rsi < 60:
            rsi_bin = "MID"
        elif rsi < 75:
            rsi_bin = "HIGH"
        else:
            rsi_bin = "VERY_HIGH"

        # MACD histogram bins
        macd_hist = market_state.get("macd_histogram", 0)
        if macd_hist > 0.5:
            macd_bin = "STRONG_BULL"
        elif macd_hist > 0:
            macd_bin = "BULL"
        elif macd_hist > -0.5:
            macd_bin = "BEAR"
        else:
            macd_bin = "STRONG_BEAR"

        # Trend strength
        trend = market_state.get("trend", "SIDEWAYS")
        trend_strength = market_state.get("trend_strength", 0.5)
        if trend_strength > 0.7:
            trend_modifier = "STRONG"
        elif trend_strength > 0.4:
            trend_modifier = "MODERATE"
        else:
            trend_modifier = "WEAK"

        # Volatility bin
        volatility = market_state.get("volatility", 0.2)
        if volatility < 0.15:
            vol_bin = "LOW_VOL"
        elif volatility < 0.30:
            vol_bin = "MED_VOL"
        else:
            vol_bin = "HIGH_VOL"

        return f"{regime}_{rsi_bin}_{macd_bin}_{trend}_{trend_modifier}_{vol_bin}"

    def select_action(
        self,
        market_state: dict[str, Any],
        agent_recommendation: str,
        agent_id: str | None = None,
    ) -> str:
        """
        Select action using epsilon-greedy policy with adaptive exploration.

        Enhanced with multi-timescale memory context for nested learning.

        Args:
            market_state: Current market state
            agent_recommendation: Recommendation from agent consensus
            agent_id: Agent ID for multi-timescale memory lookup

        Returns:
            Selected action (BUY/SELL/HOLD)
        """
        state_key = self.get_state_key(market_state)

        # Get multi-timescale context if available
        historical_bias = None
        if self.use_multi_timescale and self.context_engine and agent_id:
            historical_bias = self._get_historical_action_bias(market_state, agent_id)
            if historical_bias:
                logger.debug(
                    f"RL: Multi-timescale context bias: {historical_bias} for state {state_key}"
                )

        # Epsilon-greedy: explore vs exploit
        if np.random.random() < self.exploration_rate:
            # Explore: Use agent recommendation (learning phase)
            action = agent_recommendation
            logger.debug(f"RL: EXPLORE (ε={self.exploration_rate:.3f}) - using agent rec: {action}")
        else:
            # Exploit: Use learned Q-values with historical bias
            q_values = self.q_table[state_key].copy()

            # Apply historical bias from multi-timescale memory
            if historical_bias:
                for action_name, bias in historical_bias.items():
                    if action_name in q_values:
                        q_values[action_name] += bias * 0.1  # Small bias weight

            action = max(q_values, key=q_values.get)
            logger.debug(
                f"RL: EXPLOIT (ε={self.exploration_rate:.3f}) - Q-values: {q_values}, "
                f"selected: {action}"
            )

        return action

    def _get_historical_action_bias(
        self, market_state: dict[str, Any], agent_id: str
    ) -> dict[str, float] | None:
        """
        Get action bias from multi-timescale historical memories.

        Analyzes past outcomes in similar market states across different timescales
        to inform current action selection.

        Args:
            market_state: Current market state
            agent_id: Agent identifier

        Returns:
            Dict mapping actions to bias values, or None
        """
        try:
            from src.agent_framework.context_engine import MemoryTimescale

            # Retrieve memories from all timescales
            memories = self.context_engine.retrieve_memories(
                agent_id=agent_id,
                limit=20,
                min_importance=0.3,  # Only use important memories
                use_multi_timescale=True,
            )

            if not memories:
                return None

            # Analyze outcomes by action
            action_outcomes: dict[str, list[float]] = {
                "BUY": [],
                "SELL": [],
                "HOLD": [],
            }

            market_state.get("market_regime", "UNKNOWN")

            for memory in memories:
                content = memory.content
                outcome = content.get("outcome", {})
                decision = content.get("decision", {})
                action = decision.get("action", "HOLD")
                pl = memory.outcome_pl or outcome.get("pl", 0.0)

                # Weight by importance and timescale
                # Episodic memories have higher weight
                if memory.timescale == MemoryTimescale.EPISODIC:
                    weight = 2.0
                elif memory.timescale == MemoryTimescale.MONTHLY:
                    weight = 1.5
                elif memory.timescale == MemoryTimescale.WEEKLY:
                    weight = 1.2
                else:
                    weight = 1.0

                # Apply importance score
                weight *= memory.importance_score

                if action in action_outcomes:
                    action_outcomes[action].append(pl * weight)

            # Calculate average P/L per action (bias)
            bias: dict[str, float] = {}
            for action, outcomes in action_outcomes.items():
                if outcomes:
                    avg_pl = np.mean(outcomes)
                    # Normalize to [-1, 1] range
                    bias[action] = np.clip(avg_pl / 100.0, -1.0, 1.0)
                else:
                    bias[action] = 0.0

            return bias if any(abs(v) > 0.01 for v in bias.values()) else None

        except Exception as e:
            logger.warning(f"Failed to get historical action bias: {e}")
            return None

    def calculate_reward_risk_adjusted(
        self, trade_result: dict[str, Any], market_state: dict[str, Any]
    ) -> float:
        """
        Calculate risk-adjusted reward from trade result using world-class reward function.

        Args:
            trade_result: Dict with P/L, win/loss, etc.
            market_state: Market state for risk context

        Returns:
            Risk-adjusted reward value
        """
        # Use world-class risk-adjusted reward function
        try:
            from src.ml.reward_functions import RiskAdjustedReward

            reward_calculator = RiskAdjustedReward()
            return reward_calculator.calculate_from_trade_result(trade_result, market_state)
        except ImportError:
            # Fallback to original implementation
            logger.warning("⚠️  Using fallback reward function (install reward_functions module)")

        # Fallback: Original implementation
        trade_result.get("pl", 0)
        pl_pct = trade_result.get("pl_pct", 0)
        holding_period = trade_result.get("holding_period_days", 1)
        volatility = market_state.get("volatility", 0.2)
        max_drawdown = trade_result.get("max_drawdown", 0.0)

        # Base reward from P/L
        base_reward = pl_pct

        # Risk adjustment: penalize high volatility trades
        volatility_penalty = -abs(pl_pct) * volatility * 0.5

        # Time adjustment: prefer faster wins
        time_bonus = pl_pct * (1.0 / max(1, holding_period)) * 0.1

        # Drawdown penalty
        drawdown_penalty = -max_drawdown * 2.0

        # Sharpe-like adjustment: reward consistency
        win_rate = trade_result.get("win_rate", 0.5)
        consistency_bonus = (win_rate - 0.5) * 0.2

        # Composite reward
        reward = (
            base_reward + volatility_penalty + time_bonus + drawdown_penalty + consistency_bonus
        )

        # Normalize to [-1, 1] range
        reward = np.clip(reward / 0.1, -1.0, 1.0)

        return reward

    def update_policy(
        self,
        prev_state: dict[str, Any],
        action: str,
        reward: float,
        new_state: dict[str, Any],
        done: bool = False,
        use_replay: bool = True,
    ) -> None:
        """
        Update Q-values with optional experience replay.

        Args:
            prev_state: Previous market state
            action: Action taken
            reward: Reward received
            new_state: New market state
            done: Whether episode is done
            use_replay: Whether to use experience replay
        """
        prev_key = self.get_state_key(prev_state)
        new_key = self.get_state_key(new_state)

        # Store experience in replay buffer
        if self.enable_replay and use_replay:
            experience = Experience(
                state=prev_state,
                action=action,
                reward=reward,
                next_state=new_state,
                done=done,
                timestamp=time.time(),
            )
            self.replay_buffer.append(experience)

        # Q-learning update
        current_q = self.q_table[prev_key][action]

        # Max Q-value for next state
        max_next_q = 0 if done else max(self.q_table[new_key].values())

        # Adaptive learning rate
        if self.enable_adaptive_lr:
            # Decay learning rate as we learn more
            lr_decay = 1.0 / (1.0 + self.update_count * 0.0001)
            adaptive_lr = self.base_learning_rate * lr_decay
        else:
            adaptive_lr = self.learning_rate

        # Q-learning update: Q(s,a) = Q(s,a) + α * [r + γ * max(Q(s',a')) - Q(s,a)]
        new_q = current_q + adaptive_lr * (reward + self.discount_factor * max_next_q - current_q)

        self.q_table[prev_key][action] = new_q

        # Update statistics
        self.update_count += 1
        self.total_rewards += reward

        # Update state-action statistics
        stats = self.state_action_stats[prev_key][action]
        stats.count += 1
        stats.total_reward += reward
        stats.avg_reward = stats.total_reward / stats.count
        stats.last_updated = time.time()

        # Decay exploration rate
        self.exploration_rate = max(
            self.min_exploration_rate,
            self.exploration_rate * self.exploration_decay,
        )

        logger.debug(
            f"RL UPDATE #{self.update_count}: State={prev_key}, Action={action}, "
            f"Reward={reward:.4f}, Q: {current_q:.4f} -> {new_q:.4f}, "
            f"ε={self.exploration_rate:.3f}, α={adaptive_lr:.4f}"
        )

        # Periodic replay training
        if (
            self.enable_replay
            and use_replay
            and len(self.replay_buffer) >= self.replay_batch_size
            and self.update_count % 10 == 0
        ):
            self._train_from_replay()

        # Save state periodically
        if self.update_count % 50 == 0:
            self._save_state()

    def _train_from_replay(self) -> None:
        """Train from experience replay buffer."""
        if len(self.replay_buffer) < self.replay_batch_size:
            return

        # Sample random batch
        batch_indices = np.random.choice(
            len(self.replay_buffer), size=self.replay_batch_size, replace=False
        )
        batch = [self.replay_buffer[i] for i in batch_indices]

        # Update Q-values from batch
        for experience in batch:
            prev_key = self.get_state_key(experience.state)
            new_key = self.get_state_key(experience.next_state)

            current_q = self.q_table[prev_key][experience.action]

            max_next_q = 0 if experience.done else max(self.q_table[new_key].values())

            # Smaller learning rate for replay (more stable)
            replay_lr = self.base_learning_rate * 0.1

            new_q = current_q + replay_lr * (
                experience.reward + self.discount_factor * max_next_q - current_q
            )

            self.q_table[prev_key][experience.action] = new_q

        logger.debug(f"Replay training: updated {len(batch)} Q-values from buffer")

    def calculate_reward(
        self,
        trade_result: dict[str, Any],
        market_state: dict[str, Any] | None = None,
    ) -> float:
        """
        Calculate reward from trade result (with risk adjustment if state provided).

        Args:
            trade_result: Dict with P/L, win/loss, etc.
            market_state: Optional market state for risk adjustment

        Returns:
            Reward value
        """
        if market_state is not None:
            return self.calculate_reward_risk_adjusted(trade_result, market_state)

        # Fallback to simple reward
        pl_pct = trade_result.get("pl_pct", 0)
        return np.clip(pl_pct / 0.05, -1.0, 1.0)

    def get_policy_stats(self) -> dict[str, Any]:
        """Get comprehensive statistics about learned policy."""
        total_states = len(self.q_table)

        # Count preferred actions
        action_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}
        for state_actions in self.q_table.values():
            best_action = max(state_actions, key=state_actions.get)
            action_counts[best_action] += 1

        # Calculate average Q-values
        avg_q_values = {"BUY": 0.0, "SELL": 0.0, "HOLD": 0.0}
        q_counts = {"BUY": 0, "SELL": 0, "HOLD": 0}

        for state_actions in self.q_table.values():
            for action, q_value in state_actions.items():
                avg_q_values[action] += q_value
                q_counts[action] += 1

        for action in avg_q_values:
            if q_counts[action] > 0:
                avg_q_values[action] /= q_counts[action]

        return {
            "total_states_learned": total_states,
            "action_distribution": action_counts,
            "exploration_rate": self.exploration_rate,
            "update_count": self.update_count,
            "total_rewards": self.total_rewards,
            "avg_reward": self.total_rewards / max(1, self.update_count),
            "avg_q_values": avg_q_values,
            "replay_buffer_size": len(self.replay_buffer),
            "learning_rate": self.learning_rate,
        }

    def _save_state(self) -> None:
        """Save Q-table and state to disk."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            q_table_dict = {k: dict(v) for k, v in self.q_table.items()}

            state = {
                "q_table": q_table_dict,
                "learning_rate": self.learning_rate,
                "base_learning_rate": self.base_learning_rate,
                "discount_factor": self.discount_factor,
                "exploration_rate": self.exploration_rate,
                "update_count": self.update_count,
                "total_rewards": self.total_rewards,
                "timestamp": time.time(),
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

            loaded_q_table = state.get("q_table", {})
            for state_key, actions in loaded_q_table.items():
                self.q_table[state_key] = actions

            self.exploration_rate = state.get("exploration_rate", self.initial_exploration_rate)
            self.update_count = state.get("update_count", 0)
            self.total_rewards = state.get("total_rewards", 0.0)

            logger.info(
                f"RL state loaded: {len(self.q_table)} states learned, "
                f"ε={self.exploration_rate:.3f}, updates={self.update_count}"
            )

        except Exception as e:
            logger.error(f"Error loading RL state: {e}")

    def reset_exploration(self, new_rate: float | None = None) -> None:
        """
        Reset exploration rate (useful for new market regimes).

        Args:
            new_rate: New exploration rate (defaults to initial rate)
        """
        self.exploration_rate = new_rate or self.initial_exploration_rate
        logger.info(f"Exploration rate reset to {self.exploration_rate:.3f}")

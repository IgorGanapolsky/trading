"""
LanceDB Storage for RLHF Trajectories.

Stores state → action → reward sequences with versioning support.
LanceDB advantages over ChromaDB for RLHF:
- Native time-series/versioning support
- Zero-copy reads for fast training
- Built for sequential trajectory data
- Multi-modal (states can include images/charts)
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)

# LanceDB import with fallback
try:
    import lancedb
    import pyarrow as pa

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    lancedb = None
    pa = None


class RLHFStorage:
    """
    LanceDB-backed storage for RLHF trajectories.

    Stores:
    - State vectors (market features)
    - Actions taken (BUY/SELL/HOLD)
    - Rewards received (P/L, user feedback)
    - Episode metadata (timestamps, policy version)
    """

    TRAJECTORY_SCHEMA = {
        "trajectory_id": str,
        "episode_id": str,
        "step": int,
        "timestamp": str,
        "policy_version": str,
        # State features (10-dim from RLFilter.STATE_FEATURES)
        "state_vector": list,  # Will be stored as fixed-size list
        # Action and reward
        "action": int,  # 0=HOLD, 1=BUY, 2=SELL
        "reward": float,
        "cumulative_reward": float,
        # Context
        "symbol": str,
        "market_regime": str,
        "done": bool,
        # User feedback
        "user_feedback": int,  # -1=thumbs_down, 0=none, 1=thumbs_up
        "feedback_timestamp": str,
        # Metadata
        "metadata": str,  # JSON string
    }

    def __init__(
        self,
        db_path: str | Path = "data/rlhf_trajectories",
        table_name: str = "trajectories",
    ):
        """
        Initialize LanceDB connection.

        Args:
            db_path: Path to LanceDB database directory
            table_name: Name of the trajectories table
        """
        self.db_path = Path(db_path)
        self.table_name = table_name
        self.db = None
        self.table = None

        if not LANCEDB_AVAILABLE:
            logger.warning("LanceDB not available - RLHF storage disabled")
            return

        try:
            self.db_path.mkdir(parents=True, exist_ok=True)
            self.db = lancedb.connect(str(self.db_path))
            self._init_table()
            logger.info("RLHF storage initialized at %s", self.db_path)
        except Exception as exc:
            logger.error("Failed to initialize RLHF storage: %s", exc)

    def _init_table(self) -> None:
        """Initialize or open the trajectories table."""
        if self.db is None:
            return

        try:
            # Check if table exists
            existing_tables = self.db.table_names()
            if self.table_name in existing_tables:
                self.table = self.db.open_table(self.table_name)
                logger.info(
                    "Opened existing RLHF table: %d trajectories",
                    self.table.count_rows() if self.table else 0,
                )
            else:
                # Create empty table with schema
                self.table = self.db.create_table(
                    self.table_name,
                    data=[self._empty_trajectory()],
                    mode="overwrite",
                )
                logger.info("Created new RLHF trajectories table")
        except Exception as exc:
            logger.error("Failed to init table: %s", exc)

    def _empty_trajectory(self) -> dict[str, Any]:
        """Return an empty trajectory record for schema initialization."""
        return {
            "trajectory_id": "_init_",
            "episode_id": "_init_",
            "step": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "policy_version": "0.0.0",
            "state_vector": [0.0] * 10,
            "action": 0,
            "reward": 0.0,
            "cumulative_reward": 0.0,
            "symbol": "INIT",
            "market_regime": "unknown",
            "done": True,
            "user_feedback": 0,
            "feedback_timestamp": "",
            "metadata": "{}",
        }

    def store_trajectory(
        self,
        episode_id: str,
        step: int,
        state_vector: list[float] | np.ndarray,
        action: int,
        reward: float,
        cumulative_reward: float,
        symbol: str,
        policy_version: str = "1.0.0",
        market_regime: str = "unknown",
        done: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Store a single trajectory step.

        Args:
            episode_id: Unique identifier for the trading episode
            step: Step number within episode
            state_vector: 10-dim state from RLFilter
            action: 0=HOLD, 1=BUY, 2=SELL
            reward: Immediate reward
            cumulative_reward: Total reward so far in episode
            symbol: Trading symbol
            policy_version: Version of policy that generated action
            market_regime: Current market regime
            done: Whether episode is complete
            metadata: Additional metadata

        Returns:
            trajectory_id if successful, None otherwise
        """
        if self.table is None:
            logger.warning("RLHF storage not initialized")
            return None

        try:
            trajectory_id = (
                f"{episode_id}_{step}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
            )

            # Ensure state_vector is a list of floats
            if isinstance(state_vector, np.ndarray):
                state_vector = state_vector.tolist()
            state_vector = [float(x) for x in state_vector[:10]]
            # Pad if needed
            while len(state_vector) < 10:
                state_vector.append(0.0)

            record = {
                "trajectory_id": trajectory_id,
                "episode_id": episode_id,
                "step": step,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "policy_version": policy_version,
                "state_vector": state_vector,
                "action": action,
                "reward": float(reward),
                "cumulative_reward": float(cumulative_reward),
                "symbol": symbol.upper(),
                "market_regime": market_regime,
                "done": done,
                "user_feedback": 0,
                "feedback_timestamp": "",
                "metadata": json.dumps(metadata or {}),
            }

            self.table.add([record])
            logger.debug("Stored trajectory: %s (step %d)", trajectory_id, step)
            return trajectory_id

        except Exception as exc:
            logger.error("Failed to store trajectory: %s", exc)
            return None

    def store_episode(
        self,
        states: list[np.ndarray | list],
        actions: list[int],
        rewards: list[float],
        symbol: str,
        policy_version: str = "1.0.0",
        market_regime: str = "unknown",
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        """
        Store a complete episode (sequence of state-action-reward tuples).

        Args:
            states: List of state vectors
            actions: List of actions taken
            rewards: List of rewards received
            symbol: Trading symbol
            policy_version: Policy version
            market_regime: Market regime
            metadata: Episode metadata

        Returns:
            episode_id if successful
        """
        if len(states) != len(actions) or len(states) != len(rewards):
            logger.error(
                "Mismatched lengths: states=%d, actions=%d, rewards=%d",
                len(states),
                len(actions),
                len(rewards),
            )
            return None

        episode_id = f"{symbol}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}"
        cumulative = 0.0

        for step, (state, action, reward) in enumerate(zip(states, actions, rewards)):
            cumulative += reward
            done = step == len(states) - 1

            result = self.store_trajectory(
                episode_id=episode_id,
                step=step,
                state_vector=state,
                action=action,
                reward=reward,
                cumulative_reward=cumulative,
                symbol=symbol,
                policy_version=policy_version,
                market_regime=market_regime,
                done=done,
                metadata=metadata if done else None,
            )
            if result is None:
                logger.error("Failed to store episode at step %d", step)
                return None

        logger.info(
            "Stored episode %s: %d steps, cumulative_reward=%.4f",
            episode_id,
            len(states),
            cumulative,
        )
        return episode_id

    def add_user_feedback(
        self,
        episode_id: str,
        thumbs_up: bool,
    ) -> bool:
        """
        Add user feedback to an episode.

        Args:
            episode_id: Episode to add feedback to
            thumbs_up: True for positive, False for negative

        Returns:
            True if successful
        """
        if self.table is None:
            return False

        try:
            feedback_value = 1 if thumbs_up else -1
            feedback_ts = datetime.now(timezone.utc).isoformat()

            # Update all steps in the episode
            # LanceDB uses SQL-like syntax
            self.table.update(
                where=f"episode_id = '{episode_id}'",
                values={
                    "user_feedback": feedback_value,
                    "feedback_timestamp": feedback_ts,
                },
            )
            logger.info("Added feedback %s to episode %s", "👍" if thumbs_up else "👎", episode_id)
            return True

        except Exception as exc:
            logger.error("Failed to add feedback: %s", exc)
            return False

    def get_episode(self, episode_id: str) -> list[dict[str, Any]]:
        """
        Retrieve all steps from an episode.

        Args:
            episode_id: Episode to retrieve

        Returns:
            List of trajectory steps sorted by step number
        """
        if self.table is None:
            return []

        try:
            results = (
                self.table.search()
                .where(f"episode_id = '{episode_id}'", prefilter=True)
                .limit(1000)
                .to_list()
            )
            return sorted(results, key=lambda x: x.get("step", 0))
        except Exception as exc:
            logger.error("Failed to get episode: %s", exc)
            return []

    def get_training_batch(
        self,
        batch_size: int = 64,
        policy_version: str | None = None,
        symbol: str | None = None,
        only_with_feedback: bool = False,
    ) -> list[dict[str, Any]]:
        """
        Get a batch of trajectories for training.

        Args:
            batch_size: Number of trajectories to return
            policy_version: Filter by policy version
            symbol: Filter by symbol
            only_with_feedback: Only return trajectories with user feedback

        Returns:
            List of trajectory records
        """
        if self.table is None:
            return []

        try:
            query = self.table.search()

            # Build where clause
            conditions = ["trajectory_id != '_init_'"]
            if policy_version:
                conditions.append(f"policy_version = '{policy_version}'")
            if symbol:
                conditions.append(f"symbol = '{symbol.upper()}'")
            if only_with_feedback:
                conditions.append("user_feedback != 0")

            where_clause = " AND ".join(conditions)
            results = query.where(where_clause, prefilter=True).limit(batch_size).to_list()

            logger.debug("Retrieved %d trajectories for training", len(results))
            return results

        except Exception as exc:
            logger.error("Failed to get training batch: %s", exc)
            return []

    def get_stats(self) -> dict[str, Any]:
        """Get storage statistics."""
        if self.table is None:
            return {"enabled": False, "error": "Not initialized"}

        try:
            total = self.table.count_rows()
            # Get unique episodes
            all_data = self.table.search().limit(10000).to_list()
            episodes = set(
                r.get("episode_id", "") for r in all_data if r.get("episode_id") != "_init_"
            )
            with_feedback = sum(1 for r in all_data if r.get("user_feedback", 0) != 0)

            return {
                "enabled": True,
                "total_trajectories": total,
                "unique_episodes": len(episodes),
                "with_feedback": with_feedback,
                "db_path": str(self.db_path),
            }
        except Exception as exc:
            return {"enabled": True, "error": str(exc)}


# Singleton instance
_rlhf_storage: RLHFStorage | None = None


def get_rlhf_storage() -> RLHFStorage:
    """Get or create the singleton RLHF storage instance."""
    global _rlhf_storage
    if _rlhf_storage is None:
        _rlhf_storage = RLHFStorage()
    return _rlhf_storage


def store_trade_trajectory(
    episode_id: str,
    entry_state: dict[str, Any],
    action: int,
    exit_state: dict[str, Any],
    reward: float,
    symbol: str,
    policy_version: str = "1.0.0",
    metadata: dict[str, Any] | None = None,
) -> str | None:
    """
    Convenience function to store a trade as a 2-step trajectory.

    Args:
        episode_id: Trade/episode identifier
        entry_state: Market state at entry
        action: Action taken
        exit_state: Market state at exit
        reward: Trade P/L
        symbol: Trading symbol
        policy_version: Policy version
        metadata: Additional metadata

    Returns:
        episode_id if successful
    """
    from src.agents.rl_agent import RLFilter

    storage = get_rlhf_storage()

    # Convert market states to vectors using RLFilter's method
    rl = RLFilter(enable_transformer=False, enable_disco_dqn=False)
    entry_vec = rl._market_state_to_vector(entry_state)
    exit_vec = rl._market_state_to_vector(exit_state)

    return storage.store_episode(
        states=[entry_vec, exit_vec],
        actions=[action, 0],  # Action at entry, HOLD at exit
        rewards=[0.0, reward],  # No immediate reward, P/L at exit
        symbol=symbol,
        policy_version=policy_version,
        market_regime=entry_state.get("regime", "unknown"),
        metadata=metadata,
    )

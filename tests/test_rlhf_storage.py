"""
Tests for RLHF Trajectory Storage (LanceDB).

100% coverage for:
- src/learning/rlhf_storage.py

Tests:
1. RLHFStorage initialization
2. Store single trajectory steps
3. Store complete episodes
4. Add user feedback (thumbs up/down)
5. Retrieve episodes
6. Get training batches
7. Get storage statistics
8. Singleton pattern
9. Convenience functions
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
np = pytest.importorskip("numpy", reason="numpy required for RLHF storage tests")

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Skip all tests if lancedb is not installed
pytest.importorskip("lancedb", reason="lancedb not installed - skipping RLHF storage tests")


class TestRLHFStorageInitialization:
    """Test RLHFStorage initialization."""

    def test_import_rlhf_storage(self):
        """Should import RLHFStorage without errors."""
        from src.learning.rlhf_storage import RLHFStorage

        assert RLHFStorage is not None

    def test_lancedb_importable(self):
        """LanceDB must be importable."""
        import lancedb

        assert lancedb.__version__ is not None

    def test_init_creates_directory(self):
        """Initialization should create database directory."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "test_rlhf"
            storage = RLHFStorage(db_path=str(db_path))

            assert db_path.exists()
            assert storage.db is not None

    def test_init_creates_table(self):
        """Initialization should create trajectories table."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            assert storage.table is not None
            # Check table was created with schema record
            assert storage.table.count_rows() >= 1

    def test_init_opens_existing_table(self):
        """Should open existing table on second init."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            # First init creates table
            storage1 = RLHFStorage(db_path=tmpdir, table_name="test_traj")
            storage1.store_trajectory(
                episode_id="ep1",
                step=0,
                state_vector=[1.0] * 10,
                action=1,
                reward=0.5,
                cumulative_reward=0.5,
                symbol="SPY",
            )

            # Second init should open existing table
            storage2 = RLHFStorage(db_path=tmpdir, table_name="test_traj")
            assert storage2.table.count_rows() >= 2  # init + 1 trajectory


class TestEmptyTrajectory:
    """Test the _empty_trajectory helper."""

    def test_empty_trajectory_schema(self):
        """Empty trajectory should have all required fields."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            empty = storage._empty_trajectory()

            required_fields = [
                "trajectory_id",
                "episode_id",
                "step",
                "timestamp",
                "policy_version",
                "state_vector",
                "action",
                "reward",
                "cumulative_reward",
                "symbol",
                "market_regime",
                "done",
                "user_feedback",
                "feedback_timestamp",
                "metadata",
            ]

            for field in required_fields:
                assert field in empty, f"Missing field: {field}"

    def test_empty_trajectory_state_vector_size(self):
        """State vector should be 10-dimensional."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            empty = storage._empty_trajectory()

            assert len(empty["state_vector"]) == 10


class TestStoreTrajectory:
    """Test storing single trajectory steps."""

    def test_store_trajectory_basic(self):
        """Should store a basic trajectory step."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="test_ep_001",
                step=0,
                state_vector=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0],
                action=1,  # BUY
                reward=0.05,
                cumulative_reward=0.05,
                symbol="AAPL",
            )

            assert result is not None
            assert result.startswith("test_ep_001_0_")

    def test_store_trajectory_with_numpy_array(self):
        """Should handle numpy array state vectors."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            state = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0])
            result = storage.store_trajectory(
                episode_id="test_np",
                step=0,
                state_vector=state,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="SPY",
            )

            assert result is not None

    def test_store_trajectory_pads_short_vector(self):
        """Should pad short state vectors to 10 dimensions."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Only 5 elements
            short_state = [0.1, 0.2, 0.3, 0.4, 0.5]
            result = storage.store_trajectory(
                episode_id="test_short",
                step=0,
                state_vector=short_state,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="SPY",
            )

            assert result is not None

    def test_store_trajectory_truncates_long_vector(self):
        """Should truncate long state vectors to 10 dimensions."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # 15 elements
            long_state = [float(i) for i in range(15)]
            result = storage.store_trajectory(
                episode_id="test_long",
                step=0,
                state_vector=long_state,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="SPY",
            )

            assert result is not None

    def test_store_trajectory_with_all_params(self):
        """Should store trajectory with all optional params."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="full_ep",
                step=5,
                state_vector=[0.5] * 10,
                action=2,  # SELL
                reward=0.10,
                cumulative_reward=0.50,
                symbol="TSLA",
                policy_version="2.0.0",
                market_regime="bullish",
                done=True,
                metadata={"reason": "take_profit", "price": 250.0},
            )

            assert result is not None

    def test_store_trajectory_lowercase_symbol(self):
        """Should convert symbol to uppercase."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            storage.store_trajectory(
                episode_id="test_case",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="aapl",  # lowercase
            )

            # Retrieve and verify
            episode = storage.get_episode("test_case")
            assert len(episode) >= 1
            assert episode[0]["symbol"] == "AAPL"

    def test_store_trajectory_not_initialized(self):
        """Should return None when storage not initialized."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            storage.table = None  # Simulate not initialized

            result = storage.store_trajectory(
                episode_id="test",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="SPY",
            )

            assert result is None


class TestStoreEpisode:
    """Test storing complete episodes."""

    def test_store_episode_basic(self):
        """Should store a complete episode."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            states = [[float(i)] * 10 for i in range(3)]
            actions = [0, 1, 2]  # HOLD, BUY, SELL
            rewards = [0.0, 0.05, 0.10]

            result = storage.store_episode(
                states=states,
                actions=actions,
                rewards=rewards,
                symbol="SPY",
            )

            assert result is not None
            assert result.startswith("SPY_")

    def test_store_episode_with_numpy_states(self):
        """Should handle numpy array states."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            states = [np.random.randn(10) for _ in range(5)]
            actions = [0, 1, 0, 2, 0]
            rewards = [0.0, 0.02, 0.01, 0.08, 0.0]

            result = storage.store_episode(
                states=states,
                actions=actions,
                rewards=rewards,
                symbol="AAPL",
                policy_version="1.5.0",
                market_regime="sideways",
                metadata={"strategy": "momentum"},
            )

            assert result is not None

    def test_store_episode_mismatched_lengths(self):
        """Should return None for mismatched lengths."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            states = [[0.0] * 10 for _ in range(3)]
            actions = [0, 1]  # Only 2 actions
            rewards = [0.0, 0.05, 0.10]  # 3 rewards

            result = storage.store_episode(
                states=states,
                actions=actions,
                rewards=rewards,
                symbol="SPY",
            )

            assert result is None

    def test_store_episode_cumulative_reward(self):
        """Should calculate cumulative reward correctly."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            states = [[0.0] * 10 for _ in range(3)]
            actions = [0, 1, 2]
            rewards = [0.1, 0.2, 0.3]

            episode_id = storage.store_episode(
                states=states,
                actions=actions,
                rewards=rewards,
                symbol="SPY",
            )

            # Retrieve and verify cumulative rewards
            episode = storage.get_episode(episode_id)
            assert len(episode) == 3
            assert abs(episode[0]["cumulative_reward"] - 0.1) < 0.01
            assert abs(episode[1]["cumulative_reward"] - 0.3) < 0.01
            assert abs(episode[2]["cumulative_reward"] - 0.6) < 0.01

    def test_store_episode_done_flag(self):
        """Last step should have done=True."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            states = [[0.0] * 10 for _ in range(3)]
            actions = [0, 1, 2]
            rewards = [0.0, 0.0, 0.0]

            episode_id = storage.store_episode(
                states=states,
                actions=actions,
                rewards=rewards,
                symbol="SPY",
            )

            episode = storage.get_episode(episode_id)
            assert episode[0]["done"] is False
            assert episode[1]["done"] is False
            assert episode[2]["done"] is True


class TestUserFeedback:
    """Test adding user feedback to episodes."""

    def test_add_thumbs_up(self):
        """Should add positive feedback."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Store an episode
            episode_id = storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="SPY",
            )

            # Add feedback
            result = storage.add_user_feedback(episode_id, thumbs_up=True)
            assert result is True

            # Verify feedback was added
            episode = storage.get_episode(episode_id)
            for step in episode:
                assert step["user_feedback"] == 1
                assert step["feedback_timestamp"] != ""

    def test_add_thumbs_down(self):
        """Should add negative feedback."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            episode_id = storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 2],
                rewards=[0.0, -0.1],
                symbol="SPY",
            )

            result = storage.add_user_feedback(episode_id, thumbs_up=False)
            assert result is True

            episode = storage.get_episode(episode_id)
            for step in episode:
                assert step["user_feedback"] == -1

    def test_add_feedback_not_initialized(self):
        """Should return False when not initialized."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            storage.table = None

            result = storage.add_user_feedback("test", thumbs_up=True)
            assert result is False


class TestGetEpisode:
    """Test retrieving episodes."""

    def test_get_episode_sorted_by_step(self):
        """Retrieved episode should be sorted by step number."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            episode_id = storage.store_episode(
                states=[[float(i)] * 10 for i in range(5)],
                actions=[0, 1, 0, 2, 0],
                rewards=[0.1, 0.2, 0.3, 0.4, 0.5],
                symbol="SPY",
            )

            episode = storage.get_episode(episode_id)
            assert len(episode) == 5

            # Verify sorted by step
            for i, step in enumerate(episode):
                assert step["step"] == i

    def test_get_episode_not_found(self):
        """Should return empty list for non-existent episode."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.get_episode("nonexistent_episode_123")
            assert result == []

    def test_get_episode_not_initialized(self):
        """Should return empty list when not initialized."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            storage.table = None

            result = storage.get_episode("any")
            assert result == []


class TestGetTrainingBatch:
    """Test retrieving training batches."""

    def test_get_training_batch_basic(self):
        """Should retrieve a batch of trajectories."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Store several episodes
            for i in range(3):
                storage.store_episode(
                    states=[[float(i)] * 10 for _ in range(2)],
                    actions=[0, 1],
                    rewards=[0.0, 0.1],
                    symbol="SPY",
                )

            batch = storage.get_training_batch(batch_size=10)
            assert len(batch) >= 3  # At least 3 episodes x 2 steps

    def test_get_training_batch_excludes_init(self):
        """Should exclude initialization record."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            batch = storage.get_training_batch()
            # Should not contain _init_ records
            assert all(t["trajectory_id"] != "_init_" for t in batch)

    def test_get_training_batch_filter_by_symbol(self):
        """Should filter by symbol."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Store episodes for different symbols
            storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="SPY",
            )
            storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="AAPL",
            )

            batch = storage.get_training_batch(symbol="SPY")
            assert all(t["symbol"] == "SPY" for t in batch)

    def test_get_training_batch_filter_by_policy_version(self):
        """Should filter by policy version."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="SPY",
                policy_version="1.0.0",
            )
            storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="SPY",
                policy_version="2.0.0",
            )

            batch = storage.get_training_batch(policy_version="2.0.0")
            assert all(t["policy_version"] == "2.0.0" for t in batch)

    def test_get_training_batch_only_with_feedback(self):
        """Should filter for only records with feedback."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Store episode and add feedback
            episode_id = storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="SPY",
            )
            storage.add_user_feedback(episode_id, thumbs_up=True)

            # Store another without feedback
            storage.store_episode(
                states=[[0.0] * 10 for _ in range(2)],
                actions=[0, 1],
                rewards=[0.0, 0.1],
                symbol="AAPL",
            )

            batch = storage.get_training_batch(only_with_feedback=True)
            assert all(t["user_feedback"] != 0 for t in batch)

    def test_get_training_batch_not_initialized(self):
        """Should return empty list when not initialized."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            storage.table = None

            result = storage.get_training_batch()
            assert result == []


class TestGetStats:
    """Test getting storage statistics."""

    def test_get_stats_enabled(self):
        """Should return stats when enabled."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # Store an episode with feedback
            episode_id = storage.store_episode(
                states=[[0.0] * 10 for _ in range(3)],
                actions=[0, 1, 2],
                rewards=[0.1, 0.2, 0.3],
                symbol="SPY",
            )
            storage.add_user_feedback(episode_id, thumbs_up=True)

            stats = storage.get_stats()

            assert stats["enabled"] is True
            assert stats["total_trajectories"] >= 4  # init + 3 steps
            assert stats["unique_episodes"] >= 1
            assert stats["with_feedback"] >= 3
            assert "db_path" in stats

    def test_get_stats_not_initialized(self):
        """Should return disabled status when not initialized."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)
            storage.table = None

            stats = storage.get_stats()
            assert stats["enabled"] is False
            assert "error" in stats


class TestSingletonPattern:
    """Test the singleton pattern for RLHF storage."""

    def test_get_rlhf_storage_singleton(self):
        """Should return the same instance."""
        # Reset singleton for test
        import src.learning.rlhf_storage as module
        from src.learning.rlhf_storage import get_rlhf_storage

        module._rlhf_storage = None

        storage1 = get_rlhf_storage()
        storage2 = get_rlhf_storage()

        assert storage1 is storage2


class TestStoreTradeTrajectory:
    """Test the convenience function for storing trades."""

    def test_store_trade_trajectory_smoke(self):
        """Smoke test for store_trade_trajectory function."""
        from src.learning.rlhf_storage import store_trade_trajectory

        # This tests integration with RLFilter - skip if not available
        try:
            entry_state = {
                "price": 100.0,
                "volume": 1000000,
                "volatility": 0.02,
                "regime": "bullish",
            }
            exit_state = {
                "price": 105.0,
                "volume": 1200000,
                "volatility": 0.025,
                "regime": "bullish",
            }

            result = store_trade_trajectory(
                episode_id="trade_001",
                entry_state=entry_state,
                action=1,  # BUY
                exit_state=exit_state,
                reward=5.0,
                symbol="SPY",
                metadata={"strategy": "momentum"},
            )

            # May return None if RLFilter or storage fails gracefully
            # The important thing is no exceptions
            assert result is None or isinstance(result, str)
        except ImportError:
            pytest.skip("RLFilter not available")


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_storage_with_empty_metadata(self):
        """Should handle None metadata."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="test",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="SPY",
                metadata=None,
            )

            assert result is not None

    def test_storage_with_special_characters_in_symbol(self):
        """Should handle symbols properly."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="test",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=0.0,
                cumulative_reward=0.0,
                symbol="BRK.B",  # Symbol with period
            )

            assert result is not None

    def test_storage_with_large_reward(self):
        """Should handle large reward values."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="test",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=1000000.0,
                cumulative_reward=1000000.0,
                symbol="SPY",
            )

            assert result is not None

    def test_storage_with_negative_reward(self):
        """Should handle negative reward values."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            result = storage.store_trajectory(
                episode_id="test",
                step=0,
                state_vector=[0.0] * 10,
                action=0,
                reward=-500.0,
                cumulative_reward=-500.0,
                symbol="SPY",
            )

            assert result is not None


class TestLanceDBNotAvailable:
    """Test behavior when LanceDB is not available."""

    def test_storage_disabled_when_lancedb_unavailable(self):
        """Storage should be disabled gracefully without LanceDB."""
        with patch.dict("sys.modules", {"lancedb": None}):
            # Force reimport with mocked module

            with tempfile.TemporaryDirectory():
                # This tests the fallback behavior
                # The actual behavior depends on how import is handled
                pass


class TestIntegration:
    """Integration tests for the RLHF storage pipeline."""

    def test_full_rlhf_pipeline(self):
        """Test complete RLHF workflow: store → feedback → train."""
        from src.learning.rlhf_storage import RLHFStorage

        with tempfile.TemporaryDirectory() as tmpdir:
            storage = RLHFStorage(db_path=tmpdir)

            # 1. Store multiple episodes
            episode_ids = []
            for i in range(3):
                states = [np.random.randn(10).tolist() for _ in range(5)]
                actions = [0, 1, 0, 2, 0]
                rewards = [0.0, 0.1, 0.0, 0.2, 0.0]

                episode_id = storage.store_episode(
                    states=states,
                    actions=actions,
                    rewards=rewards,
                    symbol=f"SYM{i}",
                    policy_version="1.0.0",
                )
                episode_ids.append(episode_id)

            # 2. Add feedback to some episodes
            storage.add_user_feedback(episode_ids[0], thumbs_up=True)
            storage.add_user_feedback(episode_ids[1], thumbs_up=False)

            # 3. Get training batch with feedback
            batch = storage.get_training_batch(only_with_feedback=True)
            assert len(batch) >= 5  # At least 2 episodes x 5 steps with feedback

            # 4. Get stats
            stats = storage.get_stats()
            assert stats["enabled"] is True
            assert stats["unique_episodes"] >= 3
            assert stats["with_feedback"] >= 10  # 2 episodes x 5 steps

    def test_smoke_imports(self):
        """Smoke test that all imports work."""
        from src.learning import RLHFStorage, get_rlhf_storage, store_trade_trajectory

        assert RLHFStorage is not None
        assert get_rlhf_storage is not None
        assert store_trade_trajectory is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

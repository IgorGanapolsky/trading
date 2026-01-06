"""
Tests for RL Feedback Loop (Microsoft Agent Lightning-style).

100% coverage for:
- src/rag/rl_feedback.py

Tests:
1. RLFeedbackLoop initialization and state persistence
2. Episode management (start, record actions, end)
3. Thompson Sampling parameter updates
4. Action recommendations using Thompson Sampling
5. Feedback category tracking and analysis
6. Integration with existing feedback stats
7. Action-type statistics and success rates
8. Reward calculation
9. Singleton pattern
10. Edge cases and error handling
"""

import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.rag.rl_feedback import (
    ActionOutcome,
    ActionType,
    FeedbackCategory,
    RLFeedbackLoop,
    ThompsonSamplingParams,
    get_rl_feedback_loop,
)


class TestThompsonSamplingParams:
    """Test Thompson Sampling parameter class."""

    def test_initialization(self):
        """Should initialize with action type and priors."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=1.0,
            beta=1.0,
        )

        assert params.action_type == ActionType.RAG_QUERY
        assert params.alpha == 1.0
        assert params.beta == 1.0

    def test_posterior_mean(self):
        """Should calculate posterior mean correctly."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=10.0,
            beta=5.0,
        )

        # Mean = alpha / (alpha + beta)
        expected = 10.0 / 15.0
        assert abs(params.posterior_mean - expected) < 0.001

    def test_posterior_std(self):
        """Should calculate posterior standard deviation."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=10.0,
            beta=5.0,
        )

        # Should be positive and decrease with more samples
        assert params.posterior_std > 0

        # More samples should reduce uncertainty
        params2 = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=100.0,
            beta=50.0,
        )
        assert params2.posterior_std < params.posterior_std

    def test_sample_probability(self):
        """Should sample from Beta distribution."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=10.0,
            beta=5.0,
        )

        # Sample multiple times
        samples = [params.sample_probability() for _ in range(100)]

        # All samples should be in [0, 1]
        assert all(0 <= s <= 1 for s in samples)

        # Mean of samples should approximate posterior mean
        mean_sample = sum(samples) / len(samples)
        assert abs(mean_sample - params.posterior_mean) < 0.15

    def test_update_success(self):
        """Should increment alpha on success."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=5.0,
            beta=3.0,
        )

        params.update(success=True)

        assert params.alpha == 6.0
        assert params.beta == 3.0

    def test_update_failure(self):
        """Should increment beta on failure."""
        params = ThompsonSamplingParams(
            action_type=ActionType.RAG_QUERY,
            alpha=5.0,
            beta=3.0,
        )

        params.update(success=False)

        assert params.alpha == 5.0
        assert params.beta == 4.0


class TestRLFeedbackLoopInitialization:
    """Test RLFeedbackLoop initialization."""

    def test_initialization_default(self):
        """Should initialize with default parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"
            loop = RLFeedbackLoop(state_file=state_file)

            assert loop.state_file == state_file
            assert loop.alpha_prior == 1.0
            assert loop.beta_prior == 1.0
            assert len(loop.action_params) == 0
            assert len(loop.episodes) == 0
            assert len(loop.current_episode) == 0

    def test_initialization_custom_priors(self):
        """Should initialize with custom priors."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(
                state_file=Path(tmpdir) / "rl_state.json",
                alpha_prior=2.0,
                beta_prior=3.0,
            )

            assert loop.alpha_prior == 2.0
            assert loop.beta_prior == 3.0

    def test_state_persistence(self):
        """Should persist and load state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"

            # Create loop and record action
            loop1 = RLFeedbackLoop(state_file=state_file)
            loop1.start_episode()
            loop1.record_action(ActionType.RAG_QUERY, success=True)
            loop1.end_episode()

            # Create new loop and verify state loaded
            loop2 = RLFeedbackLoop(state_file=state_file)
            assert len(loop2.action_params) == 1
            assert ActionType.RAG_QUERY in loop2.action_params

            # Check parameters were restored
            params = loop2.action_params[ActionType.RAG_QUERY]
            assert params.alpha == 2.0  # Prior + 1 success
            assert params.beta == 1.0  # Prior only


class TestEpisodeManagement:
    """Test episode lifecycle management."""

    def test_start_episode_default_id(self):
        """Should start episode with auto-generated ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            episode_id = loop.start_episode()

            assert episode_id.startswith("episode_")
            assert loop.current_episode_id == episode_id
            assert len(loop.current_episode) == 0

    def test_start_episode_custom_id(self):
        """Should start episode with custom ID."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            episode_id = loop.start_episode(episode_id="custom_episode_123")

            assert episode_id == "custom_episode_123"
            assert loop.current_episode_id == "custom_episode_123"

    def test_start_episode_without_ending_previous(self):
        """Should auto-end previous episode when starting new one."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode("ep1")
            loop.record_action(ActionType.RAG_QUERY, success=True)

            # Start new episode without ending first
            loop.start_episode("ep2")

            # First episode should be saved
            assert len(loop.episodes) == 1
            assert loop.episodes[0][0].episode_id == "ep1"

    def test_record_action_basic(self):
        """Should record action outcome."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            outcome = loop.record_action(
                action_type=ActionType.RAG_QUERY,
                success=True,
            )

            assert isinstance(outcome, ActionOutcome)
            assert outcome.action_type == ActionType.RAG_QUERY
            assert outcome.success is True
            assert len(loop.current_episode) == 1

    def test_record_action_with_feedback_categories(self):
        """Should record action with feedback categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            outcome = loop.record_action(
                action_type=ActionType.RAG_QUERY,
                success=True,
                feedback_categories={
                    FeedbackCategory.RAG_CONSULTED.value: True,
                    FeedbackCategory.EVIDENCE_PROVIDED.value: True,
                },
            )

            assert len(outcome.feedback_categories) == 2
            assert outcome.feedback_categories[FeedbackCategory.RAG_CONSULTED.value] is True

    def test_record_action_with_context(self):
        """Should record action with context."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            outcome = loop.record_action(
                action_type=ActionType.CREATE_PR,
                success=True,
                context={"pr_number": 123, "files_changed": 5},
            )

            assert outcome.context["pr_number"] == 123
            assert outcome.context["files_changed"] == 5

    def test_record_action_with_explicit_reward(self):
        """Should use explicit reward if provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            outcome = loop.record_action(
                action_type=ActionType.RAG_QUERY,
                success=True,
                reward=0.75,
            )

            assert outcome.reward == 0.75

    def test_record_action_auto_reward(self):
        """Should auto-calculate reward if not provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            outcome = loop.record_action(
                action_type=ActionType.RAG_QUERY,
                success=True,
            )

            # Success should give positive reward
            assert outcome.reward == 1.0

    def test_record_action_updates_thompson_params(self):
        """Should update Thompson Sampling parameters."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()

            # Record successful action
            loop.record_action(ActionType.RAG_QUERY, success=True)

            # Check parameters updated
            params = loop.action_params[ActionType.RAG_QUERY]
            assert params.alpha == 2.0  # Prior + 1 success
            assert params.beta == 1.0  # Prior only

    def test_end_episode_basic(self):
        """Should end episode and return statistics."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True, reward=1.0)
            loop.record_action(ActionType.FOLLOW_RAG_ADVICE, success=True, reward=0.8)

            stats = loop.end_episode()

            assert stats["actions"] == 2
            assert stats["total_reward"] == 1.8
            assert abs(stats["avg_reward"] - 0.9) < 0.01
            assert len(loop.episodes) == 1
            assert len(loop.current_episode) == 0  # Reset

    def test_end_episode_auto_success(self):
        """Should auto-calculate episode success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.record_action(ActionType.FOLLOW_RAG_ADVICE, success=True)

            stats = loop.end_episode()

            assert stats["success"] is True

    def test_end_episode_explicit_success(self):
        """Should use explicit success if provided."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)

            stats = loop.end_episode(success=False)  # Override

            assert stats["success"] is False

    def test_end_episode_empty(self):
        """Should handle ending episode with no actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            stats = loop.end_episode()

            assert stats["actions"] == 0


class TestThompsonSamplingRecommendations:
    """Test Thompson Sampling action recommendations."""

    def test_recommend_action_basic(self):
        """Should recommend action using Thompson Sampling."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            action, prob = loop.recommend_action()

            assert isinstance(action, ActionType)
            assert 0 <= prob <= 1

    def test_recommend_action_from_candidates(self):
        """Should recommend from candidate list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            candidates = [ActionType.RAG_QUERY, ActionType.FOLLOW_RAG_ADVICE]
            action, prob = loop.recommend_action(candidate_actions=candidates)

            assert action in candidates
            assert 0 <= prob <= 1

    def test_recommend_action_prefers_successful_actions(self):
        """Should prefer actions with high success rates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            # Record many successes for RAG_QUERY
            loop.start_episode()
            for _ in range(20):
                loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.end_episode()

            # Record many failures for SKIP_RAG
            loop.start_episode()
            for _ in range(20):
                loop.record_action(ActionType.SKIP_RAG, success=False)
            loop.end_episode()

            # Should prefer RAG_QUERY most of the time
            recommendations = []
            for _ in range(50):
                action, _ = loop.recommend_action(
                    candidate_actions=[ActionType.RAG_QUERY, ActionType.SKIP_RAG]
                )
                recommendations.append(action)

            rag_query_count = sum(1 for a in recommendations if a == ActionType.RAG_QUERY)
            # Should recommend RAG_QUERY more often (but not always due to exploration)
            assert rag_query_count > 30


class TestActionStatistics:
    """Test action-type statistics."""

    def test_get_action_stats_basic(self):
        """Should return statistics for action type."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            # Record some actions
            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.record_action(ActionType.RAG_QUERY, success=False)
            loop.end_episode()

            stats = loop.get_action_stats(ActionType.RAG_QUERY)

            assert stats["action_type"] == ActionType.RAG_QUERY.value
            assert stats["total_samples"] == 3
            assert stats["successes"] == 2
            assert stats["failures"] == 1
            assert abs(stats["empirical_success_rate"] - 2 / 3) < 0.01

    def test_get_action_stats_confidence_interval(self):
        """Should calculate confidence interval."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            for _ in range(10):
                loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.end_episode()

            stats = loop.get_action_stats(ActionType.RAG_QUERY)

            ci_low, ci_high = stats["confidence_interval_95"]
            assert 0 <= ci_low <= ci_high <= 1
            assert ci_low < stats["posterior_mean"] < ci_high

    def test_get_action_stats_no_samples(self):
        """Should handle action type with no samples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            stats = loop.get_action_stats(ActionType.RAG_QUERY)

            assert stats["total_samples"] == 0
            assert stats["empirical_success_rate"] == 0.0
            # Should still have prior-based posterior
            assert stats["posterior_mean"] == 0.5  # Uniform prior

    def test_get_all_action_stats(self):
        """Should return statistics for all action types."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.record_action(ActionType.FOLLOW_RAG_ADVICE, success=False)
            loop.end_episode()

            all_stats = loop.get_all_action_stats()

            assert ActionType.RAG_QUERY.value in all_stats
            assert ActionType.FOLLOW_RAG_ADVICE.value in all_stats
            assert len(all_stats) == 2


class TestFeedbackPatternAnalysis:
    """Test feedback pattern analysis."""

    def test_analyze_feedback_patterns_basic(self):
        """Should analyze feedback patterns."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(
                ActionType.RAG_QUERY,
                success=True,
                feedback_categories={
                    FeedbackCategory.RAG_CONSULTED.value: True,
                    FeedbackCategory.EVIDENCE_PROVIDED.value: True,
                },
            )
            loop.end_episode()

            analysis = loop.analyze_feedback_patterns()

            assert "feedback_patterns" in analysis
            assert "total_episodes" in analysis
            assert "total_actions" in analysis
            assert analysis["total_episodes"] == 1
            assert analysis["total_actions"] == 1

    def test_analyze_feedback_patterns_success_rates(self):
        """Should calculate feedback category success rates."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            # RAG_QUERY with mixed feedback
            loop.record_action(
                ActionType.RAG_QUERY,
                success=True,
                feedback_categories={FeedbackCategory.RAG_CONSULTED.value: True},
            )
            loop.record_action(
                ActionType.RAG_QUERY,
                success=True,
                feedback_categories={FeedbackCategory.RAG_CONSULTED.value: False},
            )
            loop.end_episode()

            analysis = loop.analyze_feedback_patterns()

            patterns = analysis["feedback_patterns"]
            assert ActionType.RAG_QUERY.value in patterns
            # 50% success rate for RAG_CONSULTED category
            assert abs(patterns[ActionType.RAG_QUERY.value][FeedbackCategory.RAG_CONSULTED.value] - 0.5) < 0.01

    def test_analyze_feedback_patterns_empty(self):
        """Should handle no episodes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            analysis = loop.analyze_feedback_patterns()

            assert analysis["total_episodes"] == 0
            assert analysis["total_actions"] == 0


class TestRewardCalculation:
    """Test reward calculation logic."""

    def test_calculate_reward_success(self):
        """Should give positive reward for success."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            reward = loop._calculate_reward(success=True, feedback_categories={})

            assert reward == 1.0

    def test_calculate_reward_failure(self):
        """Should give negative reward for failure."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            reward = loop._calculate_reward(success=False, feedback_categories={})

            assert reward == -1.0

    def test_calculate_reward_with_positive_feedback(self):
        """Should add bonus for positive feedback categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            reward = loop._calculate_reward(
                success=True,
                feedback_categories={
                    "category1": True,
                    "category2": True,
                },
            )

            # Base +1.0 + 2 * 0.2 = 1.4, but clipped to 1.0
            assert reward == 1.0

    def test_calculate_reward_with_negative_feedback(self):
        """Should subtract for negative feedback categories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            reward = loop._calculate_reward(
                success=True,
                feedback_categories={
                    "category1": False,
                    "category2": False,
                },
            )

            # Base +1.0 - 2 * 0.2 = 0.6
            assert abs(reward - 0.6) < 0.01

    def test_calculate_reward_clipping(self):
        """Should clip reward to [-1, +1]."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            # Try to exceed 1.0
            reward1 = loop._calculate_reward(
                success=True,
                feedback_categories={f"cat{i}": True for i in range(10)},
            )
            assert reward1 == 1.0

            # Try to go below -1.0
            reward2 = loop._calculate_reward(
                success=False,
                feedback_categories={f"cat{i}": False for i in range(10)},
            )
            assert reward2 == -1.0


class TestFeedbackStatsIntegration:
    """Test integration with data/feedback/stats.json."""

    def test_update_feedback_stats_success(self):
        """Should update stats file on successful episode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats_file.write_text(
                json.dumps(
                    {
                        "total": 5,
                        "positive": 4,
                        "negative": 1,
                        "satisfaction_rate": 80.0,
                        "last_updated": "2025-01-01 00:00:00",
                    }
                )
            )

            loop = RLFeedbackLoop(
                state_file=Path(tmpdir) / "rl_state.json",
                stats_file=stats_file,
            )

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            loop.end_episode(success=True)

            # Check stats updated
            stats = json.loads(stats_file.read_text())
            assert stats["total"] == 6
            assert stats["positive"] == 5
            assert stats["negative"] == 1
            assert abs(stats["satisfaction_rate"] - 83.33) < 0.01

    def test_update_feedback_stats_failure(self):
        """Should update stats file on failed episode."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats_file.write_text(
                json.dumps(
                    {
                        "total": 5,
                        "positive": 4,
                        "negative": 1,
                        "satisfaction_rate": 80.0,
                        "last_updated": "2025-01-01 00:00:00",
                    }
                )
            )

            loop = RLFeedbackLoop(
                state_file=Path(tmpdir) / "rl_state.json",
                stats_file=stats_file,
            )

            loop.start_episode()
            loop.record_action(ActionType.SKIP_RAG, success=False)
            loop.end_episode(success=False)

            stats = json.loads(stats_file.read_text())
            assert stats["total"] == 6
            assert stats["positive"] == 4
            assert stats["negative"] == 2

    def test_update_feedback_stats_missing_file(self):
        """Should handle missing stats file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(
                state_file=Path(tmpdir) / "rl_state.json",
                stats_file=Path(tmpdir) / "nonexistent.json",
            )

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            # Should not raise exception
            loop.end_episode(success=True)


class TestSingletonPattern:
    """Test singleton pattern for RL feedback loop."""

    def test_get_rl_feedback_loop_singleton(self):
        """Should return same instance."""
        # Reset singleton
        import src.rag.rl_feedback as module

        module._rl_feedback_loop = None

        loop1 = get_rl_feedback_loop()
        loop2 = get_rl_feedback_loop()

        assert loop1 is loop2


class TestActionAndFeedbackEnums:
    """Test enum definitions."""

    def test_feedback_category_values(self):
        """Should have expected feedback categories."""
        categories = [
            FeedbackCategory.RAG_CONSULTED,
            FeedbackCategory.ADVICE_FOLLOWED,
            FeedbackCategory.OUTCOME,
            FeedbackCategory.CEO_FEEDBACK,
            FeedbackCategory.VERIFICATION,
            FeedbackCategory.EVIDENCE_PROVIDED,
        ]

        assert len(categories) == 6
        assert all(isinstance(c, FeedbackCategory) for c in categories)

    def test_action_type_values(self):
        """Should have expected action types."""
        actions = [
            ActionType.RAG_QUERY,
            ActionType.FOLLOW_RAG_ADVICE,
            ActionType.VERIFY_CLAIM,
            ActionType.SHOW_EVIDENCE,
            ActionType.CREATE_PR,
            ActionType.RUN_TESTS,
            ActionType.COMMIT_CODE,
            ActionType.DEPLOY,
            ActionType.SKIP_RAG,
            ActionType.MAKE_UNVERIFIED_CLAIM,
        ]

        assert len(actions) == 10
        assert all(isinstance(a, ActionType) for a in actions)


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_episode_with_zero_reward(self):
        """Should handle episode with zero total reward."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True, reward=0.5)
            loop.record_action(ActionType.SKIP_RAG, success=False, reward=-0.5)

            stats = loop.end_episode()

            assert abs(stats["total_reward"]) < 0.01
            assert abs(stats["avg_reward"]) < 0.01

    def test_load_corrupted_state_file(self):
        """Should handle corrupted state file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"
            state_file.write_text("not valid json {{{")

            # Should not raise exception
            loop = RLFeedbackLoop(state_file=state_file)
            assert len(loop.action_params) == 0

    def test_load_state_with_invalid_action_type(self):
        """Should skip invalid action types when loading state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"
            state_file.write_text(
                json.dumps(
                    {
                        "version": "1.0.0",
                        "action_params": {
                            "invalid_action_type": {"alpha": 5.0, "beta": 3.0},
                            "rag_query": {"alpha": 10.0, "beta": 2.0},
                        },
                    }
                )
            )

            loop = RLFeedbackLoop(state_file=state_file)

            # Should have loaded valid action, skipped invalid
            assert ActionType.RAG_QUERY in loop.action_params
            assert len(loop.action_params) == 1

    def test_update_feedback_stats_with_corrupted_file(self):
        """Should handle corrupted feedback stats file gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            stats_file = Path(tmpdir) / "stats.json"
            stats_file.write_text("not valid json {{{")

            loop = RLFeedbackLoop(
                state_file=Path(tmpdir) / "rl_state.json",
                stats_file=stats_file,
            )

            loop.start_episode()
            loop.record_action(ActionType.RAG_QUERY, success=True)
            # Should not raise exception
            loop.end_episode(success=True)

    def test_many_actions_in_episode(self):
        """Should handle episode with many actions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            loop = RLFeedbackLoop(state_file=Path(tmpdir) / "rl_state.json")

            loop.start_episode()
            for i in range(100):
                loop.record_action(
                    ActionType.RAG_QUERY,
                    success=(i % 2 == 0),  # Alternate success/failure
                )

            stats = loop.end_episode()

            assert stats["actions"] == 100
            assert len(loop.current_episode) == 0


class TestIntegration:
    """Integration tests for complete workflows."""

    def test_full_rl_workflow(self):
        """Test complete RL feedback workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"
            loop = RLFeedbackLoop(state_file=state_file)

            # Episode 1: Successful RAG consultation
            loop.start_episode("ep1")
            loop.record_action(
                ActionType.RAG_QUERY,
                success=True,
                feedback_categories={FeedbackCategory.RAG_CONSULTED.value: True},
            )
            loop.record_action(
                ActionType.FOLLOW_RAG_ADVICE,
                success=True,
                feedback_categories={FeedbackCategory.ADVICE_FOLLOWED.value: True},
            )
            loop.record_action(
                ActionType.VERIFY_CLAIM,
                success=True,
                feedback_categories={FeedbackCategory.VERIFICATION.value: True},
            )
            stats1 = loop.end_episode(success=True)

            assert stats1["success"] is True
            assert stats1["actions"] == 3

            # Episode 2: Skipped RAG and failed
            loop.start_episode("ep2")
            loop.record_action(ActionType.SKIP_RAG, success=False)
            loop.record_action(ActionType.MAKE_UNVERIFIED_CLAIM, success=False)
            stats2 = loop.end_episode(success=False)

            assert stats2["success"] is False

            # Analyze patterns
            analysis = loop.analyze_feedback_patterns()
            assert analysis["total_episodes"] == 2
            assert analysis["total_actions"] == 5

            # Get recommendations
            action, prob = loop.recommend_action()
            # Should prefer successful action types
            assert isinstance(action, ActionType)

            # Check action stats
            rag_stats = loop.get_action_stats(ActionType.RAG_QUERY)
            assert rag_stats["successes"] == 1
            assert rag_stats["failures"] == 0

            skip_stats = loop.get_action_stats(ActionType.SKIP_RAG)
            assert skip_stats["successes"] == 0
            assert skip_stats["failures"] == 1

    def test_persistence_across_sessions(self):
        """Test state persists across multiple loop instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / "rl_state.json"

            # Session 1
            loop1 = RLFeedbackLoop(state_file=state_file)
            loop1.start_episode()
            for _ in range(5):
                loop1.record_action(ActionType.RAG_QUERY, success=True)
            loop1.end_episode()

            # Session 2 (new instance)
            loop2 = RLFeedbackLoop(state_file=state_file)

            # Should have loaded Thompson Sampling parameters (these ARE persisted)
            assert ActionType.RAG_QUERY in loop2.action_params
            params = loop2.action_params[ActionType.RAG_QUERY]
            assert params.alpha == 6.0  # Prior (1) + 5 successes
            assert params.beta == 1.0  # Prior only (no failures)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

#!/usr/bin/env python3
"""
Tests for ReasonRAG-style process-level rewards system.

Tests all three stages: query generation, evidence extraction, answer generation.
Validates reward scoring, persistence, cumulative tracking.
"""

import json
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from src.rag.process_rewards import (
    ActionStage,
    ProcessReward,
    ProcessRewardTracker,
    RewardScore,
    get_tracker,
    record_evidence_reward,
    record_outcome_reward,
    record_query_reward,
)


@pytest.fixture
def temp_data_dir(tmp_path):
    """Create temporary data directory."""
    with patch("src.rag.process_rewards.DATA_DIR", tmp_path):
        with patch("src.rag.process_rewards.PROCESS_REWARDS_FILE", tmp_path / "process_rewards.json"):
            yield tmp_path


@pytest.fixture
def tracker(temp_data_dir):
    """Create fresh tracker instance for each test."""
    # Reset singleton
    import src.rag.process_rewards as pr_module
    pr_module._tracker = None

    tracker = ProcessRewardTracker()
    yield tracker

    # Cleanup
    pr_module._tracker = None


class TestProcessReward:
    """Test ProcessReward dataclass."""

    def test_process_reward_creation(self):
        """Test creating a ProcessReward."""
        reward = ProcessReward(
            timestamp="2026-01-06T10:00:00Z",
            action_type="EXECUTE_TRADE",
            stage=ActionStage.QUERY_GENERATION.value,
            reward=1.0,
            query_quality=0.8,
            notes="Test reward",
        )

        assert reward.action_type == "EXECUTE_TRADE"
        assert reward.stage == ActionStage.QUERY_GENERATION.value
        assert reward.reward == 1.0
        assert reward.query_quality == 0.8

    def test_process_reward_to_dict(self):
        """Test converting ProcessReward to dict."""
        reward = ProcessReward(
            timestamp="2026-01-06T10:00:00Z",
            action_type="EXECUTE_TRADE",
            stage=ActionStage.QUERY_GENERATION.value,
            reward=1.0,
        )

        d = reward.to_dict()
        assert d["action_type"] == "EXECUTE_TRADE"
        assert d["stage"] == ActionStage.QUERY_GENERATION.value
        assert d["reward"] == 1.0


class TestRewardScoring:
    """Test reward scoring system."""

    def test_reward_score_values(self):
        """Test that reward scores match specification."""
        assert RewardScore.CONSULTED_RAG.value == 1.0
        assert RewardScore.FOLLOWED_ADVICE.value == 0.5
        assert RewardScore.IGNORED_ADVICE.value == -0.5
        assert RewardScore.FAILURE_AFTER_IGNORE.value == -1.0

    def test_action_stage_values(self):
        """Test that action stages are defined."""
        assert ActionStage.QUERY_GENERATION.value == "query_generation"
        assert ActionStage.EVIDENCE_EXTRACTION.value == "evidence_extraction"
        assert ActionStage.ANSWER_GENERATION.value == "answer_generation"


class TestQueryGenerationRewards:
    """Test query generation reward tracking."""

    def test_record_query_high_relevance(self, tracker):
        """Test recording query with high relevance."""
        reward = tracker.record_query_generation(
            action_type="EXECUTE_TRADE",
            lessons_found=5,
            query_relevance=0.9,  # High relevance
        )

        # Base reward (1.0) + bonus (0.2) = 1.2
        assert reward == 1.2
        assert len(tracker.rewards) == 1
        assert tracker.rewards[0].query_quality == 0.9

    def test_record_query_medium_relevance(self, tracker):
        """Test recording query with medium relevance."""
        reward = tracker.record_query_generation(
            action_type="EXECUTE_TRADE",
            lessons_found=3,
            query_relevance=0.5,  # Medium relevance
        )

        # Base reward only = 1.0
        assert reward == 1.0
        assert len(tracker.rewards) == 1

    def test_record_query_low_relevance(self, tracker):
        """Test recording query with low relevance."""
        reward = tracker.record_query_generation(
            action_type="EXECUTE_TRADE",
            lessons_found=1,
            query_relevance=0.3,  # Low relevance
        )

        # Base reward (1.0) - penalty (0.2) = 0.8
        assert reward == 0.8
        assert len(tracker.rewards) == 1

    def test_query_cumulative_score(self, tracker):
        """Test cumulative score for query generation."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker.record_query_generation("EXECUTE_TRADE", 3, 0.5)

        total = tracker.get_cumulative_score("EXECUTE_TRADE")
        assert total == 1.2 + 1.0  # 2.2


class TestEvidenceExtractionRewards:
    """Test evidence extraction reward tracking."""

    def test_record_evidence_used_high_quality(self, tracker):
        """Test recording evidence extraction with high quality."""
        reward = tracker.record_evidence_extraction(
            action_type="EXECUTE_TRADE",
            evidence_used=True,
            evidence_quality=0.9,
        )

        # 0.9 * 0.5 = 0.45
        assert reward == 0.45
        assert len(tracker.rewards) == 1

    def test_record_evidence_used_low_quality(self, tracker):
        """Test recording evidence extraction with low quality."""
        reward = tracker.record_evidence_extraction(
            action_type="EXECUTE_TRADE",
            evidence_used=True,
            evidence_quality=0.3,
        )

        # 0.3 * 0.5 = 0.15
        assert reward == 0.15

    def test_record_evidence_not_used(self, tracker):
        """Test recording when evidence not extracted."""
        reward = tracker.record_evidence_extraction(
            action_type="EXECUTE_TRADE",
            evidence_used=False,
            evidence_quality=0.0,
        )

        assert reward == 0.0  # Neutral
        assert len(tracker.rewards) == 1


class TestAnswerGenerationRewards:
    """Test answer/action generation reward tracking."""

    def test_followed_advice_success(self, tracker):
        """Test following advice with successful outcome."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=True,
            outcome="success",
        )

        # Followed advice reward = 0.5
        assert reward == 0.5
        assert tracker.rewards[0].outcome_quality == 1.0

    def test_followed_advice_partial(self, tracker):
        """Test following advice with partial outcome."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=True,
            outcome="partial",
        )

        # Followed advice * 0.5 = 0.25
        assert reward == 0.25
        assert tracker.rewards[0].outcome_quality == 0.5

    def test_followed_advice_failure(self, tracker):
        """Test following advice with failure outcome."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=True,
            outcome="failure",
        )

        # Neutral - followed advice but failed
        assert reward == 0.0
        assert tracker.rewards[0].outcome_quality == 0.0

    def test_ignored_advice_success(self, tracker):
        """Test ignoring advice but getting lucky."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=False,
            outcome="success",
        )

        # Ignored advice but succeeded = -0.25
        assert reward == -0.25

    def test_ignored_advice_failure(self, tracker):
        """Test ignoring advice with failure outcome."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=False,
            outcome="failure",
        )

        # Worst case = -1.0
        assert reward == -1.0

    def test_custom_outcome_quality(self, tracker):
        """Test providing custom outcome quality score."""
        reward = tracker.record_answer_generation(
            action_type="EXECUTE_TRADE",
            followed_advice=True,
            outcome="success",
            outcome_quality=0.75,  # Custom quality
        )

        assert tracker.rewards[0].outcome_quality == 0.75


class TestCumulativeScoring:
    """Test cumulative score tracking."""

    def test_cumulative_score_single_action(self, tracker):
        """Test cumulative score for single action type."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_evidence_extraction("EXECUTE_TRADE", True, 0.8)  # +0.4
        tracker.record_answer_generation("EXECUTE_TRADE", True, "success")  # +0.5

        total = tracker.get_cumulative_score("EXECUTE_TRADE")
        assert total == pytest.approx(2.1, 0.01)

    def test_cumulative_score_multiple_actions(self, tracker):
        """Test cumulative scores for multiple action types."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_query_generation("CREATE_DATA", 3, 0.5)  # +1.0

        assert tracker.get_cumulative_score("EXECUTE_TRADE") == 1.2
        assert tracker.get_cumulative_score("CREATE_DATA") == 1.0
        assert tracker.get_cumulative_score() == 2.2  # Total

    def test_cumulative_score_with_penalties(self, tracker):
        """Test cumulative score with negative rewards."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_answer_generation(
            "EXECUTE_TRADE", False, "failure"
        )  # -1.0

        total = tracker.get_cumulative_score("EXECUTE_TRADE")
        assert total == pytest.approx(0.2, 0.01)


class TestStageScores:
    """Test stage-specific score tracking."""

    def test_get_stage_scores(self, tracker):
        """Test retrieving stage-specific scores."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_evidence_extraction("EXECUTE_TRADE", True, 0.8)  # +0.4
        tracker.record_answer_generation("EXECUTE_TRADE", True, "success")  # +0.5

        stage_scores = tracker.get_stage_scores("EXECUTE_TRADE")

        assert stage_scores["query_generation"] == pytest.approx(1.2, 0.01)
        assert stage_scores["evidence_extraction"] == pytest.approx(0.4, 0.01)
        assert stage_scores["answer_generation"] == pytest.approx(0.5, 0.01)

    def test_stage_scores_multiple_events(self, tracker):
        """Test stage scores with multiple events per stage."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_query_generation("EXECUTE_TRADE", 3, 0.5)  # +1.0

        stage_scores = tracker.get_stage_scores("EXECUTE_TRADE")
        assert stage_scores["query_generation"] == pytest.approx(2.2, 0.01)


class TestActionSummary:
    """Test action summary statistics."""

    def test_get_action_summary_full(self, tracker):
        """Test getting summary for action with all stages."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker.record_evidence_extraction("EXECUTE_TRADE", True, 0.8)
        tracker.record_answer_generation("EXECUTE_TRADE", True, "success")

        summary = tracker.get_action_summary("EXECUTE_TRADE")

        assert summary["action_type"] == "EXECUTE_TRADE"
        assert summary["total_events"] == 3
        assert summary["total_score"] == pytest.approx(2.1, 0.01)
        assert summary["avg_query_quality"] == 0.9
        assert summary["avg_evidence_quality"] == 0.8
        assert summary["avg_outcome_quality"] == 1.0

    def test_get_action_summary_empty(self, tracker):
        """Test getting summary for action with no events."""
        summary = tracker.get_action_summary("NONEXISTENT_ACTION")

        assert summary["action_type"] == "NONEXISTENT_ACTION"
        assert summary["total_events"] == 0
        assert summary["total_score"] == 0.0
        assert summary["avg_query_quality"] is None

    def test_get_action_summary_partial_stages(self, tracker):
        """Test summary when not all stages have data."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        # No evidence or answer stages

        summary = tracker.get_action_summary("EXECUTE_TRADE")

        assert summary["total_events"] == 1
        assert summary["avg_query_quality"] == 0.9
        assert summary["avg_evidence_quality"] is None
        assert summary["avg_outcome_quality"] is None


class TestOverallStats:
    """Test overall statistics."""

    def test_get_overall_stats_empty(self, tracker):
        """Test stats when no rewards recorded."""
        stats = tracker.get_overall_stats()

        assert stats["total_rewards"] == 0
        assert stats["total_score"] == 0.0
        assert stats["avg_reward"] == 0.0

    def test_get_overall_stats_with_data(self, tracker):
        """Test stats with recorded rewards."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)  # +1.2
        tracker.record_evidence_extraction("EXECUTE_TRADE", True, 0.8)  # +0.4
        tracker.record_answer_generation("EXECUTE_TRADE", False, "failure")  # -1.0

        stats = tracker.get_overall_stats()

        assert stats["total_rewards"] == 3
        assert stats["total_score"] == pytest.approx(0.6, 0.01)
        assert stats["avg_reward"] == pytest.approx(0.2, 0.01)
        assert stats["positive_rewards"] == 2
        assert stats["negative_rewards"] == 1
        assert stats["neutral_rewards"] == 0

    def test_get_overall_stats_multiple_actions(self, tracker):
        """Test stats across multiple action types."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker.record_query_generation("CREATE_DATA", 3, 0.5)
        tracker.record_answer_generation("SYNC_DATA", True, "success")

        stats = tracker.get_overall_stats()

        assert stats["total_rewards"] == 3
        assert stats["action_types"] == 3  # Three different action types


class TestPersistence:
    """Test saving and loading rewards."""

    def test_save_and_load_rewards(self, temp_data_dir):
        """Test that rewards persist across tracker instances."""
        # Create tracker and add rewards
        tracker1 = ProcessRewardTracker()
        tracker1.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker1.record_evidence_extraction("EXECUTE_TRADE", True, 0.8)

        # Create new tracker - should load from disk
        tracker2 = ProcessRewardTracker()

        assert len(tracker2.rewards) == 2
        assert tracker2.get_cumulative_score("EXECUTE_TRADE") == pytest.approx(1.6, 0.01)

    def test_persistence_file_format(self, temp_data_dir):
        """Test that persistence file has correct format."""
        tracker = ProcessRewardTracker()
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)

        file_path = temp_data_dir / "process_rewards.json"
        assert file_path.exists()

        with open(file_path) as f:
            data = json.load(f)

        assert "last_updated" in data
        assert "total_rewards" in data
        assert "rewards" in data
        assert "cumulative_scores" in data
        assert "stage_scores" in data
        assert len(data["rewards"]) == 1

    def test_load_corrupted_file(self, temp_data_dir):
        """Test handling of corrupted persistence file."""
        file_path = temp_data_dir / "process_rewards.json"
        with open(file_path, "w") as f:
            f.write("invalid json{")

        # Should initialize empty instead of crashing
        tracker = ProcessRewardTracker()
        assert len(tracker.rewards) == 0


class TestRecentRewards:
    """Test retrieving recent rewards."""

    def test_get_recent_rewards(self, tracker):
        """Test getting recent reward events."""
        for i in range(5):
            tracker.record_query_generation(f"ACTION_{i}", 5, 0.9)

        recent = tracker.get_recent_rewards(limit=3)
        assert len(recent) == 3
        assert recent[-1]["action_type"] == "ACTION_4"  # Most recent

    def test_get_recent_rewards_less_than_limit(self, tracker):
        """Test getting recent rewards when fewer than limit."""
        tracker.record_query_generation("ACTION_1", 5, 0.9)

        recent = tracker.get_recent_rewards(limit=10)
        assert len(recent) == 1


class TestClearRewards:
    """Test clearing rewards."""

    def test_clear_specific_action(self, tracker):
        """Test clearing rewards for specific action type."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker.record_query_generation("CREATE_DATA", 3, 0.5)

        tracker.clear_rewards("EXECUTE_TRADE")

        assert len(tracker.rewards) == 1
        assert tracker.rewards[0].action_type == "CREATE_DATA"
        assert tracker.get_cumulative_score("EXECUTE_TRADE") == 0.0

    def test_clear_all_rewards(self, tracker):
        """Test clearing all rewards."""
        tracker.record_query_generation("EXECUTE_TRADE", 5, 0.9)
        tracker.record_query_generation("CREATE_DATA", 3, 0.5)

        tracker.clear_rewards()

        assert len(tracker.rewards) == 0
        assert tracker.get_cumulative_score() == 0.0


class TestConvenienceFunctions:
    """Test convenience functions."""

    def test_record_query_reward(self, temp_data_dir):
        """Test convenience function for query reward."""
        # Reset singleton
        import src.rag.process_rewards as pr_module
        pr_module._tracker = None

        reward = record_query_reward("EXECUTE_TRADE", 5, 0.9)
        assert reward == 1.2

        tracker = get_tracker()
        assert len(tracker.rewards) == 1

    def test_record_evidence_reward(self, temp_data_dir):
        """Test convenience function for evidence reward."""
        import src.rag.process_rewards as pr_module
        pr_module._tracker = None

        reward = record_evidence_reward("EXECUTE_TRADE", True, 0.8)
        assert reward == 0.4

        tracker = get_tracker()
        assert len(tracker.rewards) == 1

    def test_record_outcome_reward(self, temp_data_dir):
        """Test convenience function for outcome reward."""
        import src.rag.process_rewards as pr_module
        pr_module._tracker = None

        reward = record_outcome_reward("EXECUTE_TRADE", True, "success")
        assert reward == 0.5

        tracker = get_tracker()
        assert len(tracker.rewards) == 1


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def test_full_rag_workflow_success(self, tracker):
        """Test complete RAG workflow with successful outcome."""
        # Query stage
        query_reward = tracker.record_query_generation(
            "EXECUTE_TRADE", lessons_found=5, query_relevance=0.9
        )
        assert query_reward == 1.2

        # Evidence stage
        evidence_reward = tracker.record_evidence_extraction(
            "EXECUTE_TRADE", evidence_used=True, evidence_quality=0.8
        )
        assert evidence_reward == 0.4

        # Answer stage
        answer_reward = tracker.record_answer_generation(
            "EXECUTE_TRADE", followed_advice=True, outcome="success"
        )
        assert answer_reward == 0.5

        # Verify total
        total = tracker.get_cumulative_score("EXECUTE_TRADE")
        assert total == pytest.approx(2.1, 0.01)

    def test_full_rag_workflow_ignored_failure(self, tracker):
        """Test RAG workflow where advice ignored and action failed."""
        # Query stage
        tracker.record_query_generation("EXECUTE_TRADE", lessons_found=5, query_relevance=0.9)

        # Evidence stage - low quality evidence
        tracker.record_evidence_extraction("EXECUTE_TRADE", evidence_used=True, evidence_quality=0.3)

        # Answer stage - ignored advice and failed
        tracker.record_answer_generation("EXECUTE_TRADE", followed_advice=False, outcome="failure")

        # Verify total is low due to failure
        total = tracker.get_cumulative_score("EXECUTE_TRADE")
        assert total < 1.0  # Should be negative overall


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

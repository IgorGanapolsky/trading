"""Tests for RAG Enforcement System."""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestRAGEnforcer:
    """Tests for RAGEnforcer class."""

    @pytest.fixture
    def enforcer(self):
        """Create enforcer with mocked ChromaDB."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.rag.enforcer.DATA_DIR", Path(tmpdir)):
                with patch("src.rag.enforcer.ENFORCEMENT_LOG", Path(tmpdir) / "log.json"):
                    with patch("src.rag.enforcer.VECTOR_DB_PATH", Path(tmpdir) / "vector_db"):
                        # Mock ChromaDB
                        with patch("src.rag.enforcer.chromadb") as mock_chroma:
                            mock_collection = MagicMock()
                            mock_collection.count.return_value = 100
                            mock_collection.query.return_value = {
                                "documents": [["Test lesson about verification"]],
                                "metadatas": [[{"source": "test", "severity": "MEDIUM"}]],
                            }
                            mock_client = MagicMock()
                            mock_client.get_collection.return_value = mock_collection
                            mock_chroma.PersistentClient.return_value = mock_client

                            from src.rag.enforcer import RAGEnforcer

                            yield RAGEnforcer()

    def test_query_before_action_returns_lessons(self, enforcer):
        """Should return relevant lessons for action."""
        result = enforcer.query_before_action(
            action_type="CREATE_DATA",
            action_description="Creating trades file",
        )

        assert "lessons" in result
        assert "recommendation" in result
        assert len(result["lessons"]) > 0

    def test_query_before_action_detects_blocking(self, enforcer):
        """Should detect blocking CRITICAL lessons."""
        # Mock a CRITICAL lesson
        enforcer._collection.query.return_value = {
            "documents": [["CRITICAL: Never create data without verification"]],
            "metadatas": [[{"source": "ll_086", "severity": "CRITICAL"}]],
        }

        result = enforcer.query_before_action(
            action_type="CREATE_DATA",
            action_description="Creating data file",
        )

        assert result["blocking"] is True
        assert result["recommendation"] == "BLOCK"

    def test_query_logs_to_enforcement_log(self, enforcer):
        """Should log queries to enforcement log."""
        enforcer.query_before_action(
            action_type="TEST_ACTION",
            action_description="Test description",
        )

        assert len(enforcer._enforcement_log["queries"]) > 0
        assert enforcer._enforcement_log["stats"]["total_queries"] > 0

    def test_record_outcome_tracks_followed(self, enforcer):
        """Should track when advice is followed."""
        enforcer.record_outcome(
            action_type="CREATE_DATA",
            followed_advice=True,
            outcome="success",
        )

        assert enforcer._enforcement_log["stats"]["lessons_followed"] == 1

    def test_record_outcome_tracks_ignored(self, enforcer):
        """Should track when advice is ignored."""
        enforcer.record_outcome(
            action_type="CREATE_DATA",
            followed_advice=False,
            outcome="failure",
            notes="Ignored RAG and created fake data",
        )

        assert enforcer._enforcement_log["stats"]["lessons_ignored"] == 1

    def test_get_stats_calculates_follow_rate(self, enforcer):
        """Should calculate follow rate correctly."""
        enforcer.record_outcome("TEST", followed_advice=True, outcome="success")
        enforcer.record_outcome("TEST", followed_advice=True, outcome="success")
        enforcer.record_outcome("TEST", followed_advice=False, outcome="failure")

        stats = enforcer.get_stats()

        assert stats["follow_rate"] == pytest.approx(66.67, rel=0.1)

    def test_evidence_gap_detection(self, enforcer):
        """Should detect evidence gaps."""
        # Query with no matching lessons
        enforcer._collection.query.return_value = {
            "documents": [["Unrelated lesson about something else"]],
            "metadatas": [[{"source": "unrelated"}]],
        }

        result = enforcer.query_before_action(
            action_type="CREATE_DATA",
            action_description="Creating important data",
        )

        assert result["evidence_gap"] is not None


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_query_before_action_function(self):
        """Should work via convenience function."""
        with patch("src.rag.enforcer._enforcer", None):
            with patch("src.rag.enforcer.RAGEnforcer") as MockEnforcer:
                mock_instance = MagicMock()
                mock_instance.query_before_action.return_value = {
                    "lessons": [],
                    "blocking": False,
                    "recommendation": "PROCEED",
                }
                MockEnforcer.return_value = mock_instance

                from src.rag.enforcer import query_before_action

                result = query_before_action("TEST", "test action")

                assert result["recommendation"] == "PROCEED"

    def test_record_outcome_function(self):
        """Should work via convenience function."""
        with patch("src.rag.enforcer._enforcer", None):
            with patch("src.rag.enforcer.RAGEnforcer") as MockEnforcer:
                mock_instance = MagicMock()
                MockEnforcer.return_value = mock_instance

                from src.rag.enforcer import record_outcome

                record_outcome("TEST", True, "success")

                mock_instance.record_outcome.assert_called_once()


class TestRecommendationLogic:
    """Tests for recommendation logic."""

    @pytest.fixture
    def enforcer_with_mocks(self):
        """Create enforcer with controlled mocks."""
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch("src.rag.enforcer.DATA_DIR", Path(tmpdir)):
                with patch("src.rag.enforcer.ENFORCEMENT_LOG", Path(tmpdir) / "log.json"):
                    with patch("src.rag.enforcer.chromadb") as mock_chroma:
                        mock_collection = MagicMock()
                        mock_collection.count.return_value = 100
                        mock_client = MagicMock()
                        mock_client.get_collection.return_value = mock_collection
                        mock_chroma.PersistentClient.return_value = mock_client

                        from src.rag.enforcer import RAGEnforcer

                        enforcer = RAGEnforcer()
                        enforcer._collection = mock_collection
                        yield enforcer, mock_collection

    def test_proceed_when_no_blocking_lessons(self, enforcer_with_mocks):
        """Should recommend PROCEED when no blocking lessons."""
        enforcer, mock_collection = enforcer_with_mocks
        mock_collection.query.return_value = {
            "documents": [["Normal lesson"]],
            "metadatas": [[{"severity": "LOW"}]],
        }

        result = enforcer.query_before_action("TEST", "test")

        assert result["recommendation"] == "PROCEED"

    def test_block_when_critical_matching_lesson(self, enforcer_with_mocks):
        """Should recommend BLOCK when CRITICAL lesson matches action."""
        enforcer, mock_collection = enforcer_with_mocks
        mock_collection.query.return_value = {
            "documents": [["CRITICAL: Never create_data without verification"]],
            "metadatas": [[{"severity": "CRITICAL"}]],
        }

        result = enforcer.query_before_action("CREATE_DATA", "creating data")

        assert result["recommendation"] == "BLOCK"

    def test_no_precedent_when_no_lessons(self, enforcer_with_mocks):
        """Should indicate no precedent when no lessons found."""
        enforcer, mock_collection = enforcer_with_mocks
        mock_collection.query.return_value = {
            "documents": [[]],
            "metadatas": [[]],
        }

        result = enforcer.query_before_action("NOVEL_ACTION", "something new")

        assert result["recommendation"] == "PROCEED_NO_PRECEDENT"

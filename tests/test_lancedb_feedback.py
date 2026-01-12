"""
Tests for LanceDB RLHF feedback storage.

Verifies:
1. LanceDB installation and import
2. Feedback storage with embeddings
3. Semantic search over feedback
4. Time-travel queries
5. Integration with FeedbackTrainer

Note: These tests are skipped in CI when LanceDB is not installed.
"""

import tempfile
from pathlib import Path

import pytest

# Check if LanceDB is available - skip all dependent tests if not
try:
    import fastembed
    import lancedb

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    lancedb = None
    fastembed = None


@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not installed")
class TestLanceDBInstallation:
    """Verify LanceDB is installed and functional."""

    def test_lancedb_importable(self):
        """LanceDB must be importable."""
        assert lancedb.__version__ is not None

    def test_fastembed_importable(self):
        """FastEmbed must be importable for embeddings."""
        assert fastembed.__version__ is not None

    def test_lancedb_connection(self):
        """LanceDB connection must work."""
        with tempfile.TemporaryDirectory() as tmpdir:
            db = lancedb.connect(tmpdir)
            assert db is not None


@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not installed")
class TestLanceDBFeedbackStore:
    """Test LanceDB feedback storage module."""

    def test_store_initialization(self):
        """Store should initialize without errors."""
        from src.learning.lancedb_feedback_store import LanceDBFeedbackStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LanceDBFeedbackStore(db_path=tmpdir)
            assert store is not None
            assert store.db is not None

    def test_add_feedback(self):
        """Should store feedback with embeddings."""
        from src.learning.lancedb_feedback_store import LanceDBFeedbackStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LanceDBFeedbackStore(db_path=tmpdir)

            context = {
                "decision_type": "entry_signal",
                "ticker": "AAPL",
                "strategy": "momentum",
                "signal_strength": 0.8,
            }

            record = store.add_feedback(
                feedback_id="test_001",
                is_positive=True,
                context=context,
                reward=2.0,
                model_checkpoint={"alpha": 5.0, "beta": 2.0, "feature_weights": {}},
            )

            assert record["feedback_id"] == "test_001"
            assert record["is_positive"] is True
            assert record["reward"] == 2.0
            assert "vector" in record

    def test_semantic_search(self):
        """Should find similar feedback using semantic search."""
        from src.learning.lancedb_feedback_store import LanceDBFeedbackStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LanceDBFeedbackStore(db_path=tmpdir)

            # Add multiple feedback records
            contexts = [
                {"decision_type": "entry", "ticker": "AAPL", "strategy": "momentum"},
                {"decision_type": "exit", "ticker": "AAPL", "strategy": "momentum"},
                {"decision_type": "entry", "ticker": "TSLA", "strategy": "mean_reversion"},
            ]

            for i, ctx in enumerate(contexts):
                store.add_feedback(
                    feedback_id=f"test_{i:03d}",
                    is_positive=i % 2 == 0,
                    context=ctx,
                    reward=1.0 if i % 2 == 0 else -1.0,
                    model_checkpoint={"alpha": 1.0, "beta": 1.0, "feature_weights": {}},
                )

            # Search for similar to first context
            query_context = {"decision_type": "entry", "ticker": "AAPL", "strategy": "momentum"}
            results = store.search_similar_contexts(query_context, limit=2)

            assert len(results) >= 1
            # Should find the AAPL momentum entry first
            assert "test_000" in results[0]["feedback_id"]

    def test_time_travel_query(self):
        """Should retrieve feedback from specific model checkpoints."""
        from src.learning.lancedb_feedback_store import LanceDBFeedbackStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LanceDBFeedbackStore(db_path=tmpdir)

            # Add feedback at different model checkpoints
            for i in range(5):
                store.add_feedback(
                    feedback_id=f"test_{i:03d}",
                    is_positive=True,
                    context={"iteration": i},
                    reward=1.0,
                    model_checkpoint={"alpha": 1.0 + i, "beta": 1.0, "feature_weights": {}},
                )

            # Query for checkpoint at alpha=3
            results = store.get_feedback_at_checkpoint(alpha=3.0, beta=1.0, tolerance=0.5)

            assert len(results) >= 1
            # Should find feedback near alpha=3
            assert any(2.5 <= r["model_alpha"] <= 3.5 for r in results)

    def test_get_statistics(self):
        """Should return accurate statistics."""
        from src.learning.lancedb_feedback_store import LanceDBFeedbackStore

        with tempfile.TemporaryDirectory() as tmpdir:
            store = LanceDBFeedbackStore(db_path=tmpdir)

            # Add 3 positive, 1 negative
            for i in range(4):
                store.add_feedback(
                    feedback_id=f"test_{i:03d}",
                    is_positive=i < 3,
                    context={"test": i},
                    reward=1.0 if i < 3 else -1.0,
                    model_checkpoint={"alpha": 1.0, "beta": 1.0, "feature_weights": {}},
                )

            stats = store.get_statistics()

            assert stats["total_feedback"] == 4
            assert stats["positive"] == 3
            assert stats["negative"] == 1
            assert stats["satisfaction_rate"] == 75.0


@pytest.mark.skipif(not LANCEDB_AVAILABLE, reason="LanceDB not installed")
class TestFeedbackTrainerIntegration:
    """Test FeedbackTrainer with LanceDB."""

    def test_trainer_with_lancedb_enabled(self):
        """Trainer should initialize with LanceDB enabled."""
        from src.learning.feedback_trainer import FeedbackTrainer

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = FeedbackTrainer(
                feedback_dir=tmpdir,
                model_path=str(Path(tmpdir) / "model.json"),
                use_lancedb=True,
            )

            # Should have lancedb_store initialized
            assert trainer.use_lancedb is True
            assert trainer.lancedb_store is not None

    def test_record_feedback_stores_in_lancedb(self):
        """Recording feedback should store in LanceDB."""
        from src.learning.feedback_trainer import FeedbackTrainer

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = FeedbackTrainer(
                feedback_dir=tmpdir,
                model_path=str(Path(tmpdir) / "model.json"),
                use_lancedb=True,
            )

            context = {"decision_type": "entry", "ticker": "AAPL"}

            result = trainer.record_feedback(is_positive=True, context=context)

            assert result["recorded"] is True
            assert result["is_positive"] is True

            # Verify stored in LanceDB
            stats = trainer.lancedb_store.get_statistics()
            assert stats["total_feedback"] >= 1

    def test_semantic_search_through_trainer(self):
        """Trainer should expose semantic search."""
        from src.learning.feedback_trainer import FeedbackTrainer

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = FeedbackTrainer(
                feedback_dir=tmpdir,
                model_path=str(Path(tmpdir) / "model.json"),
                use_lancedb=True,
            )

            # Record some feedback
            trainer.record_feedback(
                is_positive=True, context={"decision_type": "entry", "ticker": "AAPL"}
            )
            trainer.record_feedback(
                is_positive=False, context={"decision_type": "exit", "ticker": "AAPL"}
            )

            # Search for similar
            results = trainer.search_similar_feedback(
                context={"decision_type": "entry", "ticker": "AAPL"}, limit=5
            )

            assert len(results) >= 1

    def test_model_stats_includes_lancedb(self):
        """Model stats should include LanceDB statistics."""
        from src.learning.feedback_trainer import FeedbackTrainer

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = FeedbackTrainer(
                feedback_dir=tmpdir,
                model_path=str(Path(tmpdir) / "model.json"),
                use_lancedb=True,
            )

            trainer.record_feedback(is_positive=True, context={"test": "data"})

            stats = trainer.get_model_stats()

            assert "lancedb" in stats
            assert stats["lancedb"]["total_feedback"] >= 1


class TestBackwardCompatibility:
    """Test that LanceDB is optional and backward compatible."""

    def test_trainer_without_lancedb(self):
        """Trainer should work without LanceDB (fallback mode)."""
        pytest.importorskip("src.learning.feedback_trainer", reason="feedback_trainer not available")
        from src.learning.feedback_trainer import FeedbackTrainer

        with tempfile.TemporaryDirectory() as tmpdir:
            trainer = FeedbackTrainer(
                feedback_dir=tmpdir,
                model_path=str(Path(tmpdir) / "model.json"),
                use_lancedb=False,
            )

            assert trainer.use_lancedb is False
            assert trainer.lancedb_store is None

            # Should still record feedback (JSON fallback)
            result = trainer.record_feedback(is_positive=True)
            assert result["recorded"] is True

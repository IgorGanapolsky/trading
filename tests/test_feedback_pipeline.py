"""
Tests for Feedback Training Pipeline.

100% coverage for:
- src/learning/reward_shaper.py
- src/learning/feedback_trainer.py
"""

import sys
import tempfile
from pathlib import Path

import pytest

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.learning.feedback_trainer import FeedbackTrainer
from src.learning.reward_shaper import BinaryRewardShaper


class TestBinaryRewardShaper:
    """Tests for BinaryRewardShaper class."""

    def test_init_defaults(self):
        """Test default initialization."""
        shaper = BinaryRewardShaper()
        assert shaper.base_reward == 1.0
        assert shaper.risk_penalty_weight == 0.3
        assert shaper.feedback_weight == 2.0
        assert shaper.pattern_bonus == 0.5

    def test_init_custom_values(self):
        """Test custom initialization."""
        shaper = BinaryRewardShaper(
            base_reward=2.0,
            risk_penalty_weight=0.5,
            feedback_weight=3.0,
            pattern_bonus=1.0,
        )
        assert shaper.base_reward == 2.0
        assert shaper.risk_penalty_weight == 0.5
        assert shaper.feedback_weight == 3.0
        assert shaper.pattern_bonus == 1.0

    def test_shape_trade_outcome_profitable(self):
        """Test shaping profitable trade outcome."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=100.0)

        assert result["binary_reward"] == 1.0
        assert result["shaped_reward"] > 0
        assert "Profitable trade" in result["explanation"]

    def test_shape_trade_outcome_loss(self):
        """Test shaping losing trade outcome."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=-50.0)

        assert result["binary_reward"] == -1.0
        assert result["shaped_reward"] < 0
        assert "Losing trade" in result["explanation"]

    def test_shape_trade_outcome_quick_win_bonus(self):
        """Test quick win bonus for short holding period."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=100.0, holding_period_days=2)

        assert result["holding_bonus"] == 0.2
        assert "Quick win bonus" in result["explanation"]

    def test_shape_trade_outcome_slow_trade_penalty(self):
        """Test penalty for slow trade."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=100.0, holding_period_days=15)

        assert result["holding_bonus"] == -0.1
        assert "Slow trade penalty" in result["explanation"]

    def test_shape_trade_outcome_high_drawdown_penalty(self):
        """Test risk penalty for high drawdown."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=100.0, max_drawdown=0.10)

        assert result["risk_penalty"] < 0
        assert "High drawdown penalty" in result["explanation"]

    def test_shape_trade_outcome_high_volatility_penalty(self):
        """Test volatility adjustment."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_trade_outcome(pnl=100.0, volatility=0.05)

        assert result["vol_adjustment"] == -0.2
        assert "High volatility penalty" in result["explanation"]

    def test_shape_trade_outcome_winning_pattern_bonus(self):
        """Test pattern bonus for winning patterns."""
        shaper = BinaryRewardShaper()
        pattern_history = {"found": True, "win_rate": 0.8}
        result = shaper.shape_trade_outcome(pnl=100.0, pattern_history=pattern_history)

        assert result["pattern_adjustment"] == 0.5
        assert "Winning pattern bonus" in result["explanation"]

    def test_shape_trade_outcome_losing_pattern_penalty(self):
        """Test pattern penalty for losing patterns."""
        shaper = BinaryRewardShaper()
        pattern_history = {"found": True, "win_rate": 0.2}
        result = shaper.shape_trade_outcome(pnl=100.0, pattern_history=pattern_history)

        assert result["pattern_adjustment"] == -0.5
        assert "Losing pattern penalty" in result["explanation"]

    def test_shape_user_feedback_thumbs_up(self):
        """Test shaping thumbs up feedback."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_user_feedback(thumbs_up=True)

        assert result["shaped_reward"] == 2.0
        assert result["binary_feedback"] == 2.0
        assert "Positive feedback" in result["explanation"]

    def test_shape_user_feedback_thumbs_down(self):
        """Test shaping thumbs down feedback."""
        shaper = BinaryRewardShaper()
        result = shaper.shape_user_feedback(thumbs_up=False)

        assert result["shaped_reward"] == -2.0
        assert result["binary_feedback"] == -2.0
        assert "Negative feedback" in result["explanation"]

    def test_shape_user_feedback_strategic_context(self):
        """Test context bonus for strategic decisions."""
        shaper = BinaryRewardShaper()
        context = {"decision_type": "risk_exceeded"}
        result = shaper.shape_user_feedback(thumbs_up=True, context=context)

        assert result["context_bonus"] == 0.5
        assert result["shaped_reward"] == 2.5

    def test_shape_user_feedback_tactical_context(self):
        """Test context bonus for tactical decisions."""
        shaper = BinaryRewardShaper()
        context = {"decision_type": "entry_signal"}
        result = shaper.shape_user_feedback(thumbs_up=True, context=context)

        assert result["context_bonus"] == 0.3
        assert result["shaped_reward"] == 2.3


class TestFeedbackTrainer:
    """Tests for FeedbackTrainer class."""

    @pytest.fixture
    def temp_feedback_dir(self):
        """Create temporary feedback directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_dir = Path(tmpdir) / "feedback"
            feedback_dir.mkdir()
            model_path = Path(tmpdir) / "model.json"
            yield feedback_dir, model_path

    def test_init_defaults(self, temp_feedback_dir):
        """Test default initialization."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        assert trainer.alpha == 1.0
        assert trainer.beta == 1.0
        assert trainer.min_samples == 5

    def test_record_positive_feedback(self, temp_feedback_dir):
        """Test recording positive feedback."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        result = trainer.record_feedback(is_positive=True)

        assert result["recorded"] is True
        assert result["is_positive"] is True
        assert trainer.alpha == 2.0
        assert trainer.beta == 1.0
        assert result["posterior_mean"] == 2/3

    def test_record_negative_feedback(self, temp_feedback_dir):
        """Test recording negative feedback."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        result = trainer.record_feedback(is_positive=False)

        assert result["recorded"] is True
        assert result["is_positive"] is False
        assert trainer.alpha == 1.0
        assert trainer.beta == 2.0
        assert result["posterior_mean"] == 1/3

    def test_get_model_stats(self, temp_feedback_dir):
        """Test getting model statistics."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        # Record some feedback
        trainer.record_feedback(is_positive=True)
        trainer.record_feedback(is_positive=True)
        trainer.record_feedback(is_positive=False)

        stats = trainer.get_model_stats()

        assert stats["alpha"] == 3.0
        assert stats["beta"] == 2.0
        assert stats["total_samples"] == 3
        assert stats["posterior_mean"] == 0.6
        assert 0 <= stats["confidence_interval_95"][0] <= stats["confidence_interval_95"][1] <= 1

    def test_get_feedback_reward(self, temp_feedback_dir):
        """Test getting feedback reward."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        # Record positive feedback to skew posterior
        for _ in range(5):
            trainer.record_feedback(is_positive=True)

        # Get reward multiple times (Thompson sampling is stochastic)
        rewards = [trainer.get_feedback_reward() for _ in range(10)]

        # Should mostly be positive given strong positive posterior
        assert sum(1 for r in rewards if r > 0) >= 5

    def test_save_and_load_model(self, temp_feedback_dir):
        """Test saving and loading model."""
        feedback_dir, model_path = temp_feedback_dir

        # Create and train model
        trainer1 = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )
        trainer1.record_feedback(is_positive=True)
        trainer1.record_feedback(is_positive=True)
        trainer1.record_feedback(is_positive=False)

        # Load in new instance
        trainer2 = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        assert trainer2.alpha == trainer1.alpha
        assert trainer2.beta == trainer1.beta

    def test_process_feedback_logs_insufficient(self, temp_feedback_dir):
        """Test processing with insufficient samples."""
        feedback_dir, model_path = temp_feedback_dir

        # Create feedback file with only 2 samples
        feedback_file = feedback_dir / "feedback_2026-01-01.jsonl"
        feedback_file.write_text(
            '{"type": "positive", "score": 1}\n'
            '{"type": "negative", "score": -1}\n'
        )

        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
            min_samples=5,
        )

        result = trainer.process_feedback_logs()

        assert result["trained"] is False
        assert result["reason"] == "insufficient_samples"

    def test_process_feedback_logs_success(self, temp_feedback_dir):
        """Test successful batch processing."""
        feedback_dir, model_path = temp_feedback_dir

        # Create feedback file with enough samples
        lines = []
        for i in range(10):
            feedback_type = "positive" if i % 3 != 0 else "negative"
            lines.append(f'{{"type": "{feedback_type}", "score": {1 if feedback_type == "positive" else -1}}}')

        feedback_file = feedback_dir / "feedback_2026-01-01.jsonl"
        feedback_file.write_text("\n".join(lines))

        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
            min_samples=5,
        )

        result = trainer.process_feedback_logs()

        assert result["trained"] is True
        assert result["samples"] == 10

    def test_feature_extraction(self, temp_feedback_dir):
        """Test feature extraction from context."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        context = "CI test failed, momentum trade entry"
        features = trainer._extract_features_from_context(context)

        assert "ci" in features
        assert "test" in features
        assert "momentum" in features
        assert "trade" in features
        assert "entry" in features

    def test_context_adjustment(self, temp_feedback_dir):
        """Test context-based reward adjustment."""
        feedback_dir, model_path = temp_feedback_dir
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        # Record feedback with context to build feature weights
        trainer.record_feedback(
            is_positive=True,
            context={"raw_context": "profit trade momentum"}
        )
        trainer.record_feedback(
            is_positive=False,
            context={"raw_context": "loss trade risk"}
        )

        # Check feature weights were updated
        assert len(trainer.feature_weights) > 0


class TestIntegration:
    """Integration tests for the full pipeline."""

    @pytest.fixture
    def temp_env(self):
        """Create temporary environment."""
        with tempfile.TemporaryDirectory() as tmpdir:
            feedback_dir = Path(tmpdir) / "feedback"
            feedback_dir.mkdir()
            model_path = Path(tmpdir) / "model.json"
            yield feedback_dir, model_path

    def test_full_pipeline(self, temp_env):
        """Test full feedback → training → prediction pipeline."""
        feedback_dir, model_path = temp_env

        # 1. Initialize components
        shaper = BinaryRewardShaper()
        trainer = FeedbackTrainer(
            feedback_dir=str(feedback_dir),
            model_path=str(model_path),
        )

        # 2. Simulate trade outcomes
        trades = [
            {"pnl": 100, "holding_period_days": 2},  # Quick win
            {"pnl": -50, "holding_period_days": 5},   # Loss
            {"pnl": 200, "holding_period_days": 1},   # Quick win
            {"pnl": 75, "holding_period_days": 3},    # Win
        ]

        total_shaped_reward = 0
        for trade in trades:
            result = shaper.shape_trade_outcome(**trade)
            total_shaped_reward += result["shaped_reward"]

        # 3. Record user feedback
        trainer.record_feedback(is_positive=True)  # 👍
        trainer.record_feedback(is_positive=True)  # 👍
        trainer.record_feedback(is_positive=False) # 👎

        # 4. Get prediction
        stats = trainer.get_model_stats()

        # 5. Verify results
        assert total_shaped_reward > 0  # Net positive from trades
        assert stats["posterior_mean"] > 0.5  # More positive feedback
        assert stats["total_samples"] == 3

    def test_smoke_test_imports(self):
        """Smoke test that all imports work."""
        from src.learning import BinaryRewardShaper, FeedbackTrainer, TradeMemory

        assert TradeMemory is not None
        assert BinaryRewardShaper is not None
        assert FeedbackTrainer is not None

    def test_smoke_test_cli_script(self, temp_env):
        """Smoke test the CLI script."""
        feedback_dir, model_path = temp_env

        # Import the script functions directly
        from scripts.train_from_feedback import (
            record_immediate_feedback,
            show_model_stats,
            train_from_logs,
        )

        # These should not raise
        assert callable(train_from_logs)
        assert callable(record_immediate_feedback)
        assert callable(show_model_stats)


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

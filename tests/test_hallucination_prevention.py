"""
Tests for Hallucination Prevention Pipeline.

Tests the multi-stage verification including:
- Pre-trade RAG queries
- Real-time claim validation
- Post-trade prediction verification
- Pattern learning
"""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from src.verification.hallucination_prevention import (
    HallucinationPattern,
    HallucinationPreventionPipeline,
    Prediction,
)


class TestPreTradeCheck:
    """Test Stage 1: Pre-trade verification."""

    @pytest.fixture
    def pipeline(self):
        pipeline = HallucinationPreventionPipeline()
        pipeline.patterns = []  # Clear for clean tests
        pipeline.predictions = {}
        return pipeline

    def test_pre_trade_check_no_warnings(self, pipeline):
        """Test pre-trade check with no issues."""
        result = pipeline.pre_trade_check(
            symbol="SPY",
            action="BUY",
            model="google/gemini-3-pro-preview",
            confidence=0.6,
            reasoning="Strong momentum signal",
        )

        assert result["approved"] is True
        assert result["risk_score"] < 0.6
        assert len(result["warnings"]) == 0

    def test_pre_trade_check_high_confidence_warning(self, pipeline):
        """Test that high confidence triggers warning."""
        # Add factuality monitor
        mock_monitor = Mock()
        mock_monitor.get_facts_score.return_value = 0.688
        pipeline.factuality_monitor = mock_monitor

        result = pipeline.pre_trade_check(
            symbol="SPY",
            action="BUY",
            model="google/gemini-3-pro-preview",
            confidence=0.95,  # Way too high
            reasoning="Very confident",
        )

        assert any("FACTS ceiling" in w for w in result["warnings"])
        assert result["risk_score"] > 0

    def test_pre_trade_check_pattern_match(self, pipeline):
        """Test pattern matching detection."""
        pipeline.patterns = [
            HallucinationPattern(
                pattern_id="test_pattern",
                description="Test pattern for guaranteed claims",
                trigger_conditions={"keywords": ["guaranteed", "certain"]},
                frequency=5,
                models_affected=["all"],
                severity="high",
                mitigation="Don't trust guarantees",
            )
        ]

        result = pipeline.pre_trade_check(
            symbol="SPY",
            action="BUY",
            model="test/model",
            confidence=0.7,
            reasoning="This trade is guaranteed to work",
        )

        assert len(result["pattern_matches"]) > 0
        assert any("pattern" in w.lower() for w in result["warnings"])

    def test_pre_trade_check_with_rag(self, pipeline):
        """Test RAG integration for similar past mistakes."""
        mock_rag = Mock()
        mock_lesson = Mock()
        mock_lesson.id = "lesson_1"
        mock_lesson.title = "Past SPY mistake"
        mock_lesson.description = "Lost money on similar trade"
        mock_lesson.prevention = "Be more careful"
        mock_lesson.severity = "high"

        mock_rag.search.return_value = [(mock_lesson, 0.85)]
        pipeline.rag_system = mock_rag

        result = pipeline.pre_trade_check(
            symbol="SPY",
            action="BUY",
            model="test/model",
            confidence=0.6,
            reasoning="Similar to past trade",
        )

        assert len(result["similar_mistakes"]) > 0
        assert result["similar_mistakes"][0]["relevance"] == 0.85


class TestRealTimeMonitoring:
    """Test Stage 2: Real-time monitoring."""

    @pytest.fixture
    def pipeline(self):
        pipeline = HallucinationPreventionPipeline()
        pipeline.patterns = []
        pipeline.predictions = {}
        return pipeline

    def test_record_prediction(self, pipeline):
        """Test recording a prediction."""
        pred_id = pipeline.record_prediction(
            model="google/gemini-3-pro-preview",
            symbol="SPY",
            predicted_action="BUY",
            predicted_direction="UP",
            confidence=0.65,
            reasoning="Technical indicators bullish",
        )

        assert pred_id in pipeline.predictions
        pred = pipeline.predictions[pred_id]
        assert pred.model == "google/gemini-3-pro-preview"
        assert pred.symbol == "SPY"
        assert pred.predicted_direction == "UP"

    def test_validate_claim_correct(self, pipeline):
        """Test validating a correct claim."""
        result = pipeline.validate_claim(
            claim_type="price",
            claimed_value=100.0,
            actual_value=100.5,  # Within 1% tolerance
            model="test/model",
        )

        assert result["valid"] is True
        assert result["deviation"] < 0.01

    def test_validate_claim_hallucination(self, pipeline):
        """Test detecting a hallucinated claim."""
        result = pipeline.validate_claim(
            claim_type="price",
            claimed_value=100.0,
            actual_value=120.0,  # 20% off - clearly wrong
            model="test/model",
        )

        assert result["valid"] is False
        assert result["deviation"] > 0.1

    def test_validate_claim_position_mismatch(self, pipeline):
        """Test detecting position hallucination."""
        result = pipeline.validate_claim(
            claim_type="position",
            claimed_value=100,
            actual_value=0,  # No position exists
            model="test/model",
        )

        assert result["valid"] is False


class TestPostTradeVerification:
    """Test Stage 3: Post-trade verification."""

    @pytest.fixture
    def pipeline(self):
        pipeline = HallucinationPreventionPipeline()
        pipeline.patterns = []
        pipeline.predictions = {}
        return pipeline

    def test_verify_correct_prediction(self, pipeline):
        """Test verifying a correct prediction."""
        # Record prediction
        pred_id = pipeline.record_prediction(
            model="test/model",
            symbol="SPY",
            predicted_action="BUY",
            predicted_direction="UP",
            confidence=0.65,
            reasoning="Test",
        )

        # Verify it was correct
        result = pipeline.verify_prediction(
            prediction_id=pred_id,
            actual_direction="UP",
            actual_pnl=5.0,
        )

        assert result["was_correct"] is True
        assert result["pnl"] == 5.0

    def test_verify_wrong_prediction(self, pipeline):
        """Test verifying a wrong prediction."""
        pred_id = pipeline.record_prediction(
            model="test/model",
            symbol="SPY",
            predicted_action="BUY",
            predicted_direction="UP",
            confidence=0.65,
            reasoning="Test",
        )

        result = pipeline.verify_prediction(
            prediction_id=pred_id,
            actual_direction="DOWN",
            actual_pnl=-10.0,
        )

        assert result["was_correct"] is False
        assert result["pnl"] == -10.0

    def test_model_accuracy_report(self, pipeline):
        """Test accuracy report generation."""
        # Add some predictions
        for i in range(5):
            pred_id = pipeline.record_prediction(
                model="test/model",
                symbol="SPY",
                predicted_action="BUY",
                predicted_direction="UP" if i < 3 else "DOWN",
                confidence=0.6,
                reasoning="Test",
            )
            pipeline.verify_prediction(
                prediction_id=pred_id,
                actual_direction="UP",
                actual_pnl=5.0 if i < 3 else -5.0,
            )

        report = pipeline.get_model_accuracy_report()

        assert "test/model" in report["models"]
        assert report["models"]["test/model"]["total_predictions"] == 5
        assert report["models"]["test/model"]["correct_predictions"] == 3
        assert report["models"]["test/model"]["accuracy"] == 0.6


class TestPatternLearning:
    """Test pattern learning from hallucinations."""

    @pytest.fixture
    def pipeline(self):
        pipeline = HallucinationPreventionPipeline()
        pipeline.patterns = []
        pipeline.predictions = {}
        return pipeline

    def test_learn_from_hallucination(self, pipeline):
        """Test that patterns are learned from hallucinations."""
        initial_patterns = len(pipeline.patterns)

        # Record multiple hallucinations of same type
        for i in range(3):
            pipeline._learn_from_hallucination(
                model="test/model",
                claim_type="price",
                claimed=100.0 + i,
                actual=120.0 + i,
                context={"test": True},
            )

        # Should have created a pattern
        assert len(pipeline.patterns) > initial_patterns

        # Find the pattern
        pattern = next((p for p in pipeline.patterns if "test/model" in p.pattern_id), None)
        assert pattern is not None
        assert pattern.frequency == 3

    def test_default_patterns_initialized(self, pipeline):
        """Test that default patterns are created."""
        pipeline._init_default_patterns()

        assert any(p.pattern_id == "overconfidence" for p in pipeline.patterns)
        assert any(p.pattern_id == "price_fabrication" for p in pipeline.patterns)
        assert any(p.pattern_id == "false_certainty" for p in pipeline.patterns)


class TestPatternMatching:
    """Test hallucination pattern matching."""

    @pytest.fixture
    def pipeline(self):
        return HallucinationPreventionPipeline()

    def test_matches_keyword_pattern(self, pipeline):
        """Test keyword-based pattern matching."""
        pattern = HallucinationPattern(
            pattern_id="test",
            description="Test",
            trigger_conditions={"keywords": ["guaranteed", "certain"]},
            frequency=0,
            models_affected=[],
            severity="high",
            mitigation="Test",
        )

        # Should match
        assert pipeline._matches_pattern(
            pattern, "SPY", "BUY", "model", "This is guaranteed to work"
        )

        # Should not match
        assert not pipeline._matches_pattern(pattern, "SPY", "BUY", "model", "This might work")

    def test_matches_model_pattern(self, pipeline):
        """Test model-specific pattern matching."""
        pattern = HallucinationPattern(
            pattern_id="test",
            description="Test",
            trigger_conditions={"model": "bad/model"},
            frequency=0,
            models_affected=["bad/model"],
            severity="high",
            mitigation="Test",
        )

        # Should match specific model
        assert pipeline._matches_pattern(pattern, "SPY", "BUY", "bad/model", "Some reasoning")

        # Should not match other models
        assert not pipeline._matches_pattern(pattern, "SPY", "BUY", "good/model", "Some reasoning")


class TestAccuracyCalculation:
    """Test accuracy calculations."""

    @pytest.fixture
    def pipeline(self):
        pipeline = HallucinationPreventionPipeline()
        pipeline.predictions = {}
        return pipeline

    def test_calculate_model_accuracy(self, pipeline):
        """Test model accuracy calculation."""
        # Add verified predictions
        for i in range(10):
            pred = Prediction(
                prediction_id=f"pred_{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                model="test/model",
                symbol="SPY",
                predicted_action="BUY",
                predicted_direction="UP",
                confidence=0.6,
                reasoning="Test",
                context={},
                actual_direction="UP" if i < 7 else "DOWN",
                was_correct=i < 7,  # 70% correct
            )
            pipeline.predictions[pred.prediction_id] = pred

        accuracy = pipeline._calculate_model_accuracy("test/model")
        assert accuracy == 0.7

    def test_get_model_symbol_accuracy(self, pipeline):
        """Test per-symbol accuracy calculation."""
        # Add predictions for SPY
        for i in range(10):
            pred = Prediction(
                prediction_id=f"pred_{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                model="test/model",
                symbol="SPY",
                predicted_action="BUY",
                predicted_direction="UP",
                confidence=0.6,
                reasoning="Test",
                context={},
                actual_direction="UP" if i < 8 else "DOWN",
                was_correct=i < 8,  # 80% correct on SPY
            )
            pipeline.predictions[pred.prediction_id] = pred

        accuracy = pipeline._get_model_symbol_accuracy("test/model", "SPY")
        assert accuracy == 0.8

    def test_accuracy_returns_none_insufficient_data(self, pipeline):
        """Test that accuracy returns None with insufficient data."""
        # Only 3 predictions (need at least 5)
        for i in range(3):
            pred = Prediction(
                prediction_id=f"pred_{i}",
                timestamp=datetime.now(timezone.utc).isoformat(),
                model="test/model",
                symbol="SPY",
                predicted_action="BUY",
                predicted_direction="UP",
                confidence=0.6,
                reasoning="Test",
                context={},
                was_correct=True,
            )
            pipeline.predictions[pred.prediction_id] = pred

        accuracy = pipeline._get_model_symbol_accuracy("test/model", "SPY")
        assert accuracy is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

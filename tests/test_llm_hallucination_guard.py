"""
Tests for LLM Hallucination RAG Guard

Comprehensive test coverage for all validation stages:
1. Type safety (NaN, null, infinity)
2. Format validation (regex)
3. Range validation (bounds checking)
4. Business logic (position sizing)
5. Pattern matching
6. RAG integration

Author: Trading System
Created: 2025-12-11
"""

from unittest.mock import MagicMock, Mock, patch

import pytest
from src.verification.llm_hallucination_rag_guard import (
    LLMHallucinationGuard,
    create_hallucination_guard,
)


class TestTypeValidation:
    """Test type safety checks."""

    def test_valid_types(self):
        """Valid types should pass."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "action": "BUY",
            "amount": 10.0,
            "confidence": 0.65,
            "sentiment": 0.3,
        }

        result = guard.validate_output(output)
        assert result["valid"] is True
        assert len(result["violations"]) == 0

    def test_none_values(self):
        """None values should be rejected."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": None,
            "action": "BUY",
        }

        result = guard.validate_output(output)
        assert result["valid"] is False
        assert any(v["field"] == "symbol" for v in result["violations"])
        assert any("None/null" in v["message"] for v in result["violations"])

    def test_nan_values(self):
        """NaN values should be rejected."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "amount": float("nan"),
            "confidence": 0.5,
        }

        result = guard.validate_output(output)
        assert result["valid"] is False
        assert any(v["field"] == "amount" for v in result["violations"])
        assert any("NaN" in v["message"] for v in result["violations"])

    def test_infinity_values(self):
        """Infinity values should be rejected."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "amount": float("inf"),
            "confidence": 0.5,
        }

        result = guard.validate_output(output)
        assert result["valid"] is False
        assert any(v["field"] == "amount" for v in result["violations"])
        assert any("infinity" in v["message"] for v in result["violations"])

    def test_invalid_string_values(self):
        """Invalid string literals should be rejected."""
        guard = LLMHallucinationGuard()

        for invalid_str in ["nan", "null", "undefined", "N/A", "unknown"]:
            output = {
                "symbol": invalid_str,
                "action": "BUY",
            }

            result = guard.validate_output(output)
            assert result["valid"] is False
            violation_found = any(
                v["field"] == "symbol" and "invalid string" in v["message"]
                for v in result["violations"]
            )
            assert violation_found, f"Should reject '{invalid_str}'"


class TestFormatValidation:
    """Test regex-based format validation."""

    def test_valid_ticker_format(self):
        """Valid ticker formats should pass."""
        guard = LLMHallucinationGuard()

        valid_tickers = ["A", "SPY", "AAPL", "NVDA", "GOOGL"]

        for ticker in valid_tickers:
            output = {"symbol": ticker, "action": "BUY"}
            result = guard.validate_output(output)
            # Should not have critical ticker violations
            ticker_critical = [
                v
                for v in result["violations"]
                if v["field"] == "symbol" and v["severity"] == "critical"
            ]
            assert len(ticker_critical) == 0, f"Ticker '{ticker}' should be valid"

    def test_invalid_ticker_format(self):
        """Invalid ticker formats should be rejected."""
        guard = LLMHallucinationGuard()

        invalid_tickers = [
            "APPL1",  # Number
            "sp500",  # Lowercase
            "TOOLONG",  # >5 chars
            "",  # Empty
            "AAP-L",  # Dash
        ]

        for ticker in invalid_tickers:
            output = {"symbol": ticker, "action": "BUY"}
            result = guard.validate_output(output)
            assert result["valid"] is False, f"Should reject '{ticker}'"
            assert any(
                v["field"] == "symbol" and v["severity"] == "critical" for v in result["violations"]
            ), f"Should have critical violation for '{ticker}'"

    def test_ticker_whitelist(self):
        """Tickers not in whitelist should trigger warning."""
        guard = LLMHallucinationGuard(valid_tickers=["SPY", "QQQ"])

        # Valid format but not in whitelist
        output = {"symbol": "AAPL", "action": "BUY"}
        result = guard.validate_output(output)

        # Should pass (no critical violation) but have warning
        assert result["valid"] is True  # No critical violations
        assert any(
            v["field"] == "symbol" and v["severity"] == "warning" for v in result["violations"]
        )

    def test_valid_action_formats(self):
        """Valid action/side formats should pass."""
        guard = LLMHallucinationGuard()

        valid_actions = ["BUY", "SELL", "HOLD", "buy", "sell", "hold"]
        valid_sides = ["long", "short", "neutral", "LONG", "SHORT"]

        for action in valid_actions:
            output = {"symbol": "SPY", "action": action}
            result = guard.validate_output(output)
            action_violations = [
                v
                for v in result["violations"]
                if v["field"] == "action" and v["severity"] == "critical"
            ]
            assert len(action_violations) == 0, f"Action '{action}' should be valid"

        for side in valid_sides:
            output = {"symbol": "SPY", "side": side}
            result = guard.validate_output(output)
            side_violations = [
                v
                for v in result["violations"]
                if v["field"] == "side" and v["severity"] == "critical"
            ]
            assert len(side_violations) == 0, f"Side '{side}' should be valid"

    def test_invalid_action_formats(self):
        """Invalid action/side formats should be rejected."""
        guard = LLMHallucinationGuard()

        invalid_actions = ["MAYBE", "UNCERTAIN", "WAIT", "123"]

        for action in invalid_actions:
            output = {"symbol": "SPY", "action": action}
            result = guard.validate_output(output)
            assert result["valid"] is False
            assert any(
                v["field"] == "action" and v["severity"] == "critical" for v in result["violations"]
            ), f"Should reject action '{action}'"


class TestRangeValidation:
    """Test numeric range validation."""

    def test_valid_sentiment_range(self):
        """Sentiment in [-1, 1] should pass."""
        guard = LLMHallucinationGuard()

        for sentiment in [-1.0, -0.5, 0.0, 0.5, 1.0]:
            output = {"symbol": "SPY", "sentiment": sentiment}
            result = guard.validate_output(output)
            sentiment_violations = [
                v
                for v in result["violations"]
                if v["field"] == "sentiment" and v["severity"] == "critical"
            ]
            assert len(sentiment_violations) == 0, f"Sentiment {sentiment} should be valid"

    def test_invalid_sentiment_range(self):
        """Sentiment outside [-1, 1] should be rejected."""
        guard = LLMHallucinationGuard()

        for sentiment in [-2.0, -1.5, 1.5, 2.0, 5.0]:
            output = {"symbol": "SPY", "sentiment": sentiment}
            result = guard.validate_output(output)
            assert result["valid"] is False
            assert any(
                v["field"] == "sentiment" and "out of range" in v["message"]
                for v in result["violations"]
            ), f"Should reject sentiment {sentiment}"

    def test_valid_confidence_range(self):
        """Confidence in [0, 1] should pass."""
        guard = LLMHallucinationGuard()

        for confidence in [0.0, 0.25, 0.5, 0.68, 1.0]:
            output = {"symbol": "SPY", "confidence": confidence}
            result = guard.validate_output(output)
            confidence_critical = [
                v
                for v in result["violations"]
                if v["field"] == "confidence" and v["severity"] == "critical"
            ]
            assert len(confidence_critical) == 0, f"Confidence {confidence} should be valid"

    def test_confidence_exceeds_facts_ceiling(self):
        """Confidence >0.70 should trigger warning (FACTS benchmark)."""
        guard = LLMHallucinationGuard()

        output = {"symbol": "SPY", "confidence": 0.85}
        result = guard.validate_output(output)

        # Should be valid (warning, not critical)
        assert result["valid"] is True

        # Should have warning about FACTS ceiling
        assert any(
            v["field"] == "confidence" and v["severity"] == "warning" and "FACTS" in v["message"]
            for v in result["violations"]
        )

    def test_invalid_confidence_range(self):
        """Confidence outside [0, 1] should be rejected."""
        guard = LLMHallucinationGuard()

        for confidence in [-0.5, 1.5, 2.0]:
            output = {"symbol": "SPY", "confidence": confidence}
            result = guard.validate_output(output)
            assert result["valid"] is False
            assert any(
                v["field"] == "confidence" and v["severity"] == "critical"
                for v in result["violations"]
            ), f"Should reject confidence {confidence}"

    def test_positive_amount(self):
        """Positive amounts should pass."""
        guard = LLMHallucinationGuard()

        for amount in [0.01, 1.0, 10.0, 100.0]:
            output = {"symbol": "SPY", "amount": amount}
            result = guard.validate_output(output)
            amount_critical = [
                v
                for v in result["violations"]
                if v["field"] == "amount" and v["severity"] == "critical"
            ]
            assert len(amount_critical) == 0, f"Amount {amount} should be valid"

    def test_negative_amount(self):
        """Negative amounts should be rejected."""
        guard = LLMHallucinationGuard()

        for amount in [-1.0, -10.0, -100.0]:
            output = {"symbol": "SPY", "amount": amount}
            result = guard.validate_output(output)
            assert result["valid"] is False
            assert any(
                v["field"] == "amount" and "Negative" in v["message"] for v in result["violations"]
            ), f"Should reject negative amount {amount}"

    def test_zero_amount_warning(self):
        """Zero amount should trigger warning."""
        guard = LLMHallucinationGuard()

        output = {"symbol": "SPY", "amount": 0.0}
        result = guard.validate_output(output)

        # Valid but with warning
        assert result["valid"] is True
        assert any(
            v["field"] == "amount" and v["severity"] == "warning" for v in result["violations"]
        )


class TestBusinessLogic:
    """Test business logic validation."""

    def test_position_size_within_limit(self):
        """Position size within limit should pass."""
        guard = LLMHallucinationGuard(max_position_pct=0.10)

        output = {
            "symbol": "SPY",
            "amount": 5000.0,  # 5% of portfolio
            "portfolio_value": 100000.0,
        }

        result = guard.validate_output(output)
        position_violations = [
            v
            for v in result["violations"]
            if v["field"] == "amount" and "exceeds max" in v["message"]
        ]
        assert len(position_violations) == 0

    def test_position_size_exceeds_limit(self):
        """Position size exceeding limit should be rejected."""
        guard = LLMHallucinationGuard(max_position_pct=0.10)

        output = {
            "symbol": "SPY",
            "amount": 15000.0,  # 15% of portfolio
            "portfolio_value": 100000.0,
        }

        result = guard.validate_output(output)
        assert result["valid"] is False
        assert any(
            v["field"] == "amount" and "exceeds max" in v["message"] for v in result["violations"]
        )

    def test_empty_reasoning(self):
        """Empty or short reasoning should trigger warning."""
        guard = LLMHallucinationGuard()

        for reasoning in ["", "Buy", "Good"]:
            output = {"symbol": "SPY", "reasoning": reasoning}
            result = guard.validate_output(output)

            # Should have warning about short reasoning
            assert any(
                v["field"] == "reasoning" and v["severity"] == "warning"
                for v in result["violations"]
            ), f"Should warn about short reasoning: '{reasoning}'"

    def test_valid_reasoning(self):
        """Valid reasoning should pass."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "reasoning": "Strong uptrend with MACD crossover and volume confirmation",
        }

        result = guard.validate_output(output)
        reasoning_violations = [v for v in result["violations"] if v["field"] == "reasoning"]
        assert len(reasoning_violations) == 0


class TestPatternMatching:
    """Test hallucination pattern detection."""

    def test_check_hallucination_patterns(self):
        """Should identify matching hallucination patterns."""
        guard = LLMHallucinationGuard()

        # Output with high confidence (matches overconfidence pattern)
        output = {
            "symbol": "SPY",
            "confidence": 0.95,
        }

        patterns = guard.check_hallucination_patterns(output)

        # Should match confidence-related pattern
        assert len(patterns) > 0

    def test_get_pattern_summary(self):
        """Should return summary of known patterns."""
        guard = LLMHallucinationGuard()

        summary = guard.get_pattern_summary()

        assert "total_patterns" in summary
        assert summary["total_patterns"] > 0
        assert "patterns" in summary
        assert isinstance(summary["patterns"], list)

        # Check pattern structure
        for pattern in summary["patterns"]:
            assert "type_id" in pattern
            assert "description" in pattern
            assert "frequency" in pattern


class TestRAGIntegration:
    """Test RAG system integration."""

    def test_rag_integration_with_violations(self):
        """RAG should be queried when violations exist."""
        # Setup mock RAG
        mock_rag = MagicMock()
        mock_lesson = Mock()
        mock_lesson.id = "ll_001"
        mock_lesson.title = "Invalid ticker hallucination"
        mock_lesson.description = "LLM generated invalid ticker"
        mock_lesson.prevention = "Always validate tickers with regex"
        mock_lesson.severity = "high"

        mock_rag.search.return_value = [(mock_lesson, 0.85)]

        guard = LLMHallucinationGuard(rag_system=mock_rag)

        # Output with invalid ticker
        output = {
            "symbol": "INVALID123",
            "action": "BUY",
        }

        result = guard.validate_output(output)

        # Should have called RAG search
        assert mock_rag.search.called

        # Should return similar hallucinations
        assert len(result["similar_hallucinations"]) > 0
        assert result["similar_hallucinations"][0]["id"] == "ll_001"

        # Should have prevention steps
        assert len(result["prevention_steps"]) > 0

    def test_rag_not_called_when_valid(self):
        """RAG should not be queried when output is valid."""
        mock_rag = MagicMock()
        guard = LLMHallucinationGuard(rag_system=mock_rag)

        # Valid output
        output = {
            "symbol": "SPY",
            "action": "BUY",
            "amount": 10.0,
            "confidence": 0.65,
        }

        result = guard.validate_output(output)

        # Should be valid
        assert result["valid"] is True

        # RAG should not be called (no violations)
        assert not mock_rag.search.called


class TestRiskScoring:
    """Test risk score calculation."""

    def test_risk_score_no_violations(self):
        """No violations = risk score 0."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "action": "BUY",
            "amount": 10.0,
        }

        result = guard.validate_output(output)
        assert result["risk_score"] == 0.0

    def test_risk_score_with_critical_violations(self):
        """Critical violations should increase risk score."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": None,  # Critical
            "amount": float("nan"),  # Critical
        }

        result = guard.validate_output(output)
        assert result["risk_score"] > 0.5  # Multiple critical = high risk

    def test_risk_score_with_warnings(self):
        """Warnings should have lower risk impact than critical."""
        guard = LLMHallucinationGuard()

        output = {
            "symbol": "SPY",
            "reasoning": "Buy",  # Warning (too short)
            "confidence": 0.75,  # Warning (exceeds FACTS)
        }

        result = guard.validate_output(output)
        assert 0.0 < result["risk_score"] < 0.5  # Lower risk than critical

    def test_risk_score_capped_at_one(self):
        """Risk score should be capped at 1.0."""
        guard = LLMHallucinationGuard()

        # Many critical violations
        output = {
            "symbol": None,
            "amount": float("nan"),
            "confidence": 5.0,
            "sentiment": 10.0,
        }

        result = guard.validate_output(output)
        assert result["risk_score"] <= 1.0


class TestFactoryFunction:
    """Test factory function."""

    @patch("src.rag.lessons_learned_rag.LessonsLearnedRAG")
    def test_create_hallucination_guard(self, mock_rag_class):
        """Factory should create guard with RAG integration."""
        mock_rag = MagicMock()
        mock_rag_class.return_value = mock_rag

        guard = create_hallucination_guard(valid_tickers=["SPY", "QQQ"], max_position_pct=0.15)

        assert guard is not None
        assert guard.valid_tickers == {"SPY", "QQQ"}
        assert guard.max_position_pct == 0.15

    def test_create_hallucination_guard_without_rag(self):
        """Factory should work even if RAG fails to load."""
        with patch("src.rag.lessons_learned_rag.LessonsLearnedRAG") as mock_rag:
            mock_rag.side_effect = Exception("RAG not available")

            guard = create_hallucination_guard()

            # Should still create guard (without RAG)
            assert guard is not None
            assert guard.rag_system is None


class TestComplexScenarios:
    """Test complex real-world scenarios."""

    def test_multiple_violations_scenario(self):
        """Test output with multiple violations."""
        guard = LLMHallucinationGuard(valid_tickers=["SPY", "QQQ"], max_position_pct=0.10)

        output = {
            "symbol": "APPL",  # Typo (critical)
            "action": "MAYBE",  # Invalid (critical)
            "amount": -5.0,  # Negative (critical)
            "confidence": 0.95,  # Exceeds FACTS (warning)
            "sentiment": 2.5,  # Out of range (critical)
            "reasoning": "Buy",  # Too short (warning)
            "portfolio_value": 100000.0,
        }

        result = guard.validate_output(output)

        # Should be invalid
        assert result["valid"] is False

        # Should have multiple violations
        assert len(result["violations"]) >= 5

        # Should have high risk score
        assert result["risk_score"] > 0.7

    def test_edge_case_boundary_values(self):
        """Test boundary values at limits."""
        guard = LLMHallucinationGuard()

        # Exactly at boundaries
        output = {
            "symbol": "SPY",
            "sentiment": -1.0,  # Min
            "confidence": 1.0,  # Max
            "amount": 0.01,  # Min positive
        }

        result = guard.validate_output(output)

        # Sentiment and amount should be valid
        sentiment_critical = [
            v
            for v in result["violations"]
            if v["field"] == "sentiment" and v["severity"] == "critical"
        ]
        amount_critical = [
            v
            for v in result["violations"]
            if v["field"] == "amount" and v["severity"] == "critical"
        ]

        assert len(sentiment_critical) == 0
        assert len(amount_critical) == 0

    def test_real_world_signal_output(self):
        """Test with realistic signal agent output."""
        guard = LLMHallucinationGuard(valid_tickers=["SPY"])

        output = {
            "symbol": "SPY",
            "action": "BUY",
            "strength": 8,
            "direction": "BULLISH",
            "entry_quality": 7,
            "confidence": 0.68,
            "sentiment": 0.45,
            "amount": 8.50,
            "reasoning": "MACD histogram positive crossover, RSI recovering from 28, volume 1.8x confirms breakout",
            "portfolio_value": 100000.0,
            "indicators": {"macd_histogram": 0.0234, "rsi": 32.5, "volume_ratio": 1.8},
        }

        result = guard.validate_output(output)

        # Should pass all validations
        assert result["valid"] is True
        assert result["risk_score"] == 0.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

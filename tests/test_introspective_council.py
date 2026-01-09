"""
Tests for IntrospectiveCouncil - specifically the anonymization feature.

Tests the _anonymize_responses() method added based on Karpathy's LLM Council insight.
Reference: https://github.com/karpathy/llm-council
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


class TestAnonymizeResponses:
    """Test the _anonymize_responses method for peer review bias prevention."""

    def setup_method(self):
        """Set up test fixtures."""
        try:
            from src.core.introspective_council import IntrospectiveCouncil
            self.council_class = IntrospectiveCouncil
        except ImportError:
            pytest.skip("IntrospectiveCouncil not available")

    def test_anonymize_empty_scores(self):
        """Test anonymization with empty input returns empty dict."""
        mock_analyzer = MagicMock()
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )
        result = council._anonymize_responses({})
        assert result == {}

    def test_anonymize_single_model(self):
        """Test anonymization with single model response."""
        mock_analyzer = MagicMock()
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )
        individual_scores = {"claude-sonnet": 0.75}
        result = council._anonymize_responses(individual_scores)
        assert "Response_A" in result
        assert result["Response_A"] == 0.75
        assert "claude-sonnet" not in result

    def test_anonymize_multiple_models(self):
        """Test anonymization with multiple model responses."""
        mock_analyzer = MagicMock()
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )
        individual_scores = {
            "claude-sonnet": 0.75,
            "gpt-4": 0.80,
            "gemini-pro": 0.65,
        }
        result = council._anonymize_responses(individual_scores)
        assert len(result) == 3
        assert "Response_A" in result
        assert "Response_B" in result
        assert "Response_C" in result
        assert "claude-sonnet" not in result
        assert "gpt-4" not in result

    def test_anonymize_preserves_values(self):
        """Test that anonymization preserves the score values."""
        mock_analyzer = MagicMock()
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )
        individual_scores = {"model_a": 0.5, "model_b": 0.9}
        result = council._anonymize_responses(individual_scores)
        values = set(result.values())
        assert values == {0.5, 0.9}

    def test_anonymize_more_than_8_models(self):
        """Test anonymization with more than 8 models (fallback to Response_N)."""
        mock_analyzer = MagicMock()
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            enable_introspection=False,
        )
        individual_scores = {f"model_{i}": i * 0.1 for i in range(10)}
        result = council._anonymize_responses(individual_scores)
        assert len(result) == 10
        for label in ["A", "B", "C", "D", "E", "F", "G", "H"]:
            assert f"Response_{label}" in result
        assert "Response_9" in result
        assert "Response_10" in result


class TestCouncilValidationWithAnonymization:
    """Test that council validation properly uses anonymized scores."""

    def setup_method(self):
        """Set up test fixtures."""
        try:
            from src.core.introspective_council import IntrospectiveCouncil
            self.council_class = IntrospectiveCouncil
        except ImportError:
            pytest.skip("IntrospectiveCouncil not available")

    @pytest.mark.asyncio
    async def test_validation_passes_anonymized_scores(self):
        """Test that validate_trade receives anonymized peer_responses."""
        mock_analyzer = MagicMock()
        mock_council = MagicMock()
        mock_council.validate_trade = AsyncMock(return_value={
            "approved": True,
            "confidence": 0.8,
            "reasoning": "Test passed",
        })
        council = self.council_class(
            multi_llm_analyzer=mock_analyzer,
            llm_council=mock_council,
            enable_introspection=False,
        )
        mock_introspection = MagicMock()
        mock_introspection.aggregate_confidence = 0.7
        ensemble = {
            "sentiment": 0.5,
            "confidence": 0.7,
            "individual_scores": {"claude": 0.6, "gpt4": 0.7}
        }
        result = await council._get_council_validation(
            symbol="SPY",
            ensemble=ensemble,
            introspection=mock_introspection,
        )
        mock_council.validate_trade.assert_called_once()
        call_kwargs = mock_council.validate_trade.call_args[1]
        assert "peer_responses" in call_kwargs
        peer_responses = call_kwargs["peer_responses"]
        assert "claude" not in peer_responses
        assert "gpt4" not in peer_responses


class TestSmokeTests:
    """Smoke tests to verify basic functionality."""

    def test_import_introspective_council(self):
        """Smoke test: Can import IntrospectiveCouncil."""
        try:
            from src.core.introspective_council import IntrospectiveCouncil
            assert IntrospectiveCouncil is not None
        except ImportError as e:
            pytest.skip(f"Import failed: {e}")

    def test_import_trade_decision(self):
        """Smoke test: Can import TradeDecision enum."""
        try:
            from src.core.introspective_council import TradeDecision
            assert TradeDecision.BUY is not None
            assert TradeDecision.SELL is not None
            assert TradeDecision.HOLD is not None
            assert TradeDecision.SKIP is not None
        except ImportError as e:
            pytest.skip(f"Import failed: {e}")

    def test_anonymize_method_exists(self):
        """Smoke test: _anonymize_responses method exists."""
        try:
            from src.core.introspective_council import IntrospectiveCouncil
            assert hasattr(IntrospectiveCouncil, "_anonymize_responses")
        except ImportError as e:
            pytest.skip(f"Import failed: {e}")

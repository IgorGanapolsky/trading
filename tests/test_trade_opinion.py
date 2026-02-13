"""
Tests for Pre-Trade Research Agent (DeepSeek-R1 powered IC entry opinion).

Verifies:
- TradeOpinion Pydantic model validation
- get_trade_opinion() graceful fallbacks
- Prompt construction with various context combinations
- Model routing via BATS framework (R1 for pre_trade_research)
- Advisory-only behavior (never overrides hard risk limits)
"""

import json
import os
import sys
from unittest.mock import MagicMock, patch

import pytest

from src.llm.trade_opinion import (
    TradeOpinion,
    _build_prompt,
    _system_prompt,
    get_trade_opinion,
)


# =============================================================================
# TradeOpinion MODEL TESTS
# =============================================================================


class TestTradeOpinionModel:
    """Test TradeOpinion Pydantic schema validation."""

    def test_valid_trade_opinion(self):
        """Valid opinion parses correctly."""
        opinion = TradeOpinion(
            should_trade=True,
            confidence=0.85,
            regime="calm",
            suggested_short_delta=0.15,
            suggested_dte=35,
            reasoning="VIX in optimal range, no catalysts.",
            risk_flags=[],
        )
        assert opinion.should_trade is True
        assert opinion.confidence == 0.85
        assert opinion.regime == "calm"
        assert opinion.suggested_short_delta == 0.15
        assert opinion.suggested_dte == 35

    def test_skip_trade_opinion(self):
        """Skip opinion with risk flags."""
        opinion = TradeOpinion(
            should_trade=False,
            confidence=0.92,
            regime="volatile",
            suggested_short_delta=0.10,
            suggested_dte=45,
            reasoning="FOMC meeting tomorrow, avoid entry.",
            risk_flags=["FOMC", "high_vix"],
        )
        assert opinion.should_trade is False
        assert opinion.confidence == 0.92
        assert len(opinion.risk_flags) == 2

    def test_confidence_bounds(self):
        """Confidence must be 0.0-1.0."""
        with pytest.raises(ValueError):
            TradeOpinion(
                should_trade=True,
                confidence=1.5,
                regime="calm",
                reasoning="test",
            )
        with pytest.raises(ValueError):
            TradeOpinion(
                should_trade=True,
                confidence=-0.1,
                regime="calm",
                reasoning="test",
            )

    def test_delta_bounds(self):
        """Suggested delta must be 0.05-0.30."""
        with pytest.raises(ValueError):
            TradeOpinion(
                should_trade=True,
                confidence=0.5,
                regime="calm",
                suggested_short_delta=0.50,
                reasoning="test",
            )

    def test_dte_bounds(self):
        """Suggested DTE must be 14-60."""
        with pytest.raises(ValueError):
            TradeOpinion(
                should_trade=True,
                confidence=0.5,
                regime="calm",
                suggested_dte=5,
                reasoning="test",
            )

    def test_default_values(self):
        """Default delta and DTE are set."""
        opinion = TradeOpinion(
            should_trade=True,
            confidence=0.5,
            regime="calm",
            reasoning="test",
        )
        assert opinion.suggested_short_delta == 0.15
        assert opinion.suggested_dte == 35
        assert opinion.risk_flags == []

    def test_model_dump(self):
        """model_dump produces serializable dict."""
        opinion = TradeOpinion(
            should_trade=True,
            confidence=0.75,
            regime="calm",
            reasoning="Good conditions.",
        )
        data = opinion.model_dump()
        assert isinstance(data, dict)
        assert data["should_trade"] is True
        assert data["confidence"] == 0.75
        # Ensure JSON-serializable
        json.dumps(data)

    def test_model_validate_from_json(self):
        """model_validate parses dict correctly (simulates LLM JSON response)."""
        raw = {
            "should_trade": False,
            "confidence": 0.88,
            "regime": "spike",
            "suggested_short_delta": 0.10,
            "suggested_dte": 45,
            "reasoning": "VIX spike, wait for mean reversion.",
            "risk_flags": ["vix_spike", "earnings_season"],
        }
        opinion = TradeOpinion.model_validate(raw)
        assert opinion.should_trade is False
        assert opinion.regime == "spike"
        assert "vix_spike" in opinion.risk_flags


# =============================================================================
# PROMPT CONSTRUCTION TESTS
# =============================================================================


class TestPromptConstruction:
    """Test _build_prompt and _system_prompt."""

    def test_system_prompt_contains_rules(self):
        """System prompt includes Phil Town and IC rules."""
        prompt = _system_prompt()
        assert "Phil Town" in prompt
        assert "iron condor" in prompt.lower()
        assert "VIX" in prompt
        assert "JSON" in prompt

    def test_build_prompt_minimal(self):
        """Prompt builds with no context."""
        prompt = _build_prompt(None, None, None, None)
        assert "SPY iron condor" in prompt
        assert "JSON" in prompt

    def test_build_prompt_with_vix(self):
        """VIX data appears in prompt."""
        prompt = _build_prompt(
            vix_current=18.5, thompson_stats=None, regime=None, recent_lessons=None
        )
        assert "18.50" in prompt
        assert "VIX" in prompt

    def test_build_prompt_with_thompson(self):
        """Thompson stats appear in prompt."""
        stats = {"wins": 10, "losses": 2, "posterior_mean": 0.833, "recommendation": "ENTER"}
        prompt = _build_prompt(None, stats, None, None)
        assert "10W/2L" in prompt
        assert "0.833" in prompt
        assert "ENTER" in prompt

    def test_build_prompt_with_regime(self):
        """Market regime appears in prompt."""
        prompt = _build_prompt(None, None, "LOW_VOL_RANGE", None)
        assert "LOW_VOL_RANGE" in prompt

    def test_build_prompt_with_lessons(self):
        """RAG lessons appear in prompt (capped at 5)."""
        lessons = [f"Lesson {i}" for i in range(10)]
        prompt = _build_prompt(None, None, None, lessons)
        assert "Lesson 0" in prompt
        assert "Lesson 4" in prompt
        # Cap at 5
        assert "Lesson 5" not in prompt

    def test_build_prompt_lessons_truncated(self):
        """Long lessons are truncated to 200 chars."""
        long_lesson = "x" * 500
        prompt = _build_prompt(None, None, None, [long_lesson])
        # Each lesson is capped at 200 chars
        assert "x" * 200 in prompt
        assert "x" * 201 not in prompt

    def test_build_prompt_full_context(self):
        """All context fields appear when provided."""
        prompt = _build_prompt(
            vix_current=22.0,
            thompson_stats={
                "wins": 5,
                "losses": 1,
                "posterior_mean": 0.75,
                "recommendation": "ENTER",
            },
            regime="TRENDING_UP",
            recent_lessons=["Avoid FOMC weeks"],
        )
        assert "22.00" in prompt
        assert "5W/1L" in prompt
        assert "TRENDING_UP" in prompt
        assert "Avoid FOMC weeks" in prompt


# =============================================================================
# get_trade_opinion() FALLBACK TESTS
# =============================================================================


def _ensure_openai_mock():
    """Ensure openai module is available (mocked if not installed)."""
    if "openai" not in sys.modules:
        mock_openai = MagicMock()
        mock_openai.OpenAI = MagicMock
        sys.modules["openai"] = mock_openai
    return sys.modules["openai"]


class TestGetTradeOpinionFallbacks:
    """Test get_trade_opinion() graceful degradation."""

    def test_no_api_key_returns_none(self):
        """Returns None when OPENROUTER_API_KEY is not set."""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("OPENROUTER_API_KEY", None)
            result = get_trade_opinion()
            assert result is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_non_openrouter_provider_returns_none(self):
        """Returns None when selected model is not OpenRouter."""
        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "claude-opus-4-5-20251101"
            mock_selector.get_model_provider.return_value = "anthropic"
            mock_sel.return_value = mock_selector

            result = get_trade_opinion()
            assert result is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_import_error_returns_none(self):
        """Returns None when openai package is not installed."""
        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            # Force ImportError on openai
            with patch.dict(sys.modules, {"openai": None}):
                result = get_trade_opinion()
                assert result is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_json_decode_error_returns_none(self):
        """Returns None when LLM returns invalid JSON."""
        _ensure_openai_mock()

        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            with patch("openai.OpenAI") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_choice = MagicMock()
                mock_choice.message.content = "not valid json!!!"
                mock_response.choices = [mock_choice]
                mock_response.usage = None
                mock_client.chat.completions.create.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = get_trade_opinion()
                assert result is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_empty_response_returns_none(self):
        """Returns None when LLM returns empty content."""
        _ensure_openai_mock()

        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            with patch("openai.OpenAI") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_response.choices = []
                mock_response.usage = None
                mock_client.chat.completions.create.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = get_trade_opinion()
                assert result is None

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_api_exception_returns_none(self):
        """Returns None when API call raises an exception."""
        _ensure_openai_mock()

        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            with patch("openai.OpenAI") as mock_client_cls:
                mock_client = MagicMock()
                mock_client.chat.completions.create.side_effect = RuntimeError("API timeout")
                mock_client_cls.return_value = mock_client

                result = get_trade_opinion()
                assert result is None


# =============================================================================
# get_trade_opinion() SUCCESS PATH
# =============================================================================


class TestGetTradeOpinionSuccess:
    """Test get_trade_opinion() successful LLM call."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_successful_trade_opinion(self):
        """Successful LLM call returns TradeOpinion."""
        _ensure_openai_mock()

        valid_response = json.dumps(
            {
                "should_trade": True,
                "confidence": 0.82,
                "regime": "calm",
                "suggested_short_delta": 0.15,
                "suggested_dte": 35,
                "reasoning": "VIX at 18, no catalysts.",
                "risk_flags": [],
            }
        )

        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            with patch("openai.OpenAI") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_choice = MagicMock()
                mock_choice.message.content = valid_response
                mock_response.choices = [mock_choice]
                mock_response.usage = MagicMock(prompt_tokens=500, completion_tokens=200)
                mock_client.chat.completions.create.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = get_trade_opinion(vix_current=18.0)

                assert result is not None
                assert isinstance(result, TradeOpinion)
                assert result.should_trade is True
                assert result.confidence == 0.82
                assert result.regime == "calm"

                # Verify usage was logged
                mock_selector.log_usage.assert_called_once_with(
                    "deepseek/deepseek-r1",
                    500,
                    200,
                )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_skip_opinion_with_risk_flags(self):
        """LLM advises to skip with risk flags."""
        _ensure_openai_mock()

        skip_response = json.dumps(
            {
                "should_trade": False,
                "confidence": 0.91,
                "regime": "volatile",
                "suggested_short_delta": 0.10,
                "suggested_dte": 45,
                "reasoning": "FOMC meeting tomorrow.",
                "risk_flags": ["FOMC", "earnings"],
            }
        )

        with patch("src.llm.trade_opinion.get_model_selector") as mock_sel:
            mock_selector = MagicMock()
            mock_selector.select_model.return_value = "deepseek/deepseek-r1"
            mock_selector.get_model_provider.return_value = "openrouter"
            mock_sel.return_value = mock_selector

            with patch("openai.OpenAI") as mock_client_cls:
                mock_client = MagicMock()
                mock_response = MagicMock()
                mock_choice = MagicMock()
                mock_choice.message.content = skip_response
                mock_response.choices = [mock_choice]
                mock_response.usage = None
                mock_client.chat.completions.create.return_value = mock_response
                mock_client_cls.return_value = mock_client

                result = get_trade_opinion()

                assert result is not None
                assert result.should_trade is False
                assert result.confidence == 0.91
                assert "FOMC" in result.risk_flags


# =============================================================================
# MODEL ROUTING TESTS
# =============================================================================


class TestModelRouting:
    """Verify pre_trade_research routes to DeepSeek-R1 via BATS."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_pre_trade_research_selects_r1(self):
        """pre_trade_research task selects DeepSeek-R1."""
        from src.utils.model_selector import MODEL_REGISTRY, ModelSelector, ModelTier

        selector = ModelSelector()
        model_id = selector.select_model("pre_trade_research")
        assert model_id == MODEL_REGISTRY[ModelTier.DEEPSEEK_R1].model_id

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"})
    def test_r1_is_openrouter_provider(self):
        """DeepSeek-R1 routes through OpenRouter."""
        from src.utils.model_selector import MODEL_REGISTRY, ModelSelector, ModelTier

        selector = ModelSelector()
        model_id = selector.select_model("pre_trade_research")
        provider = selector.get_model_provider(model_id)
        assert provider == "openrouter"
        assert MODEL_REGISTRY[ModelTier.DEEPSEEK_R1].supports_extended_thinking is True

    def test_pre_trade_research_is_complex(self):
        """pre_trade_research is mapped to COMPLEX complexity."""
        from src.utils.model_selector import TASK_COMPLEXITY_MAP, TaskComplexity

        assert TASK_COMPLEXITY_MAP["pre_trade_research"] == TaskComplexity.COMPLEX

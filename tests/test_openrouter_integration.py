"""
Tests for OpenRouter Integration Wiring

These tests verify that the OpenRouter integration is properly wired up
in the trading pipeline. They catch dead-code failures like:
- model_selector returning OpenRouter model IDs that never reach OpenRouter
- base_agent sending OpenRouter models to Anthropic API
- mirascope_client having zero callers in the pipeline

Run in CI to prevent integration wiring regressions.
"""

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.utils.model_selector import (
    MODEL_REGISTRY,
    ModelSelector,
)


def _ensure_openai_mock():
    """Ensure openai module is available (mocked if not installed)."""
    if "openai" not in sys.modules:
        mock_openai = MagicMock()
        mock_openai.OpenAI = MagicMock
        sys.modules["openai"] = mock_openai
    return sys.modules["openai"]


# =============================================================================
# TEST 1: Import Chain Completeness (Dead Code Detection)
# =============================================================================


class TestImportChainCompleteness:
    """Verify that key LLM modules are imported by at least one non-test module."""

    @staticmethod
    def _get_project_root() -> Path:
        """Get project root directory."""
        return Path(__file__).parent.parent

    def _find_importers(self, module_path: str, exclude_tests: bool = True) -> list[str]:
        """Find Python files in src/ and scripts/ that import from the given module path."""
        root = self._get_project_root()
        importers = []

        # Only scan src/ and scripts/ directories for production code
        search_dirs = [root / "src", root / "scripts"]

        for search_dir in search_dirs:
            if not search_dir.exists():
                continue
            for py_file in search_dir.rglob("*.py"):
                if "__pycache__" in str(py_file):
                    continue
                if exclude_tests and "test" in py_file.name.lower():
                    continue

                try:
                    source = py_file.read_text(encoding="utf-8")
                except (UnicodeDecodeError, OSError):
                    continue

                # Simple string search (faster than AST parsing)
                if f"from {module_path}" in source or f"import {module_path}" in source:
                    importers.append(str(py_file.relative_to(root)))

        return importers

    def test_model_selector_has_callers(self):
        """model_selector.py must be imported by at least one non-test module."""
        importers = self._find_importers("src.utils.model_selector")
        assert len(importers) > 0, (
            "DEAD CODE: src.utils.model_selector has zero non-test importers. "
            "The BATS model selection framework is not wired into the pipeline."
        )

    def test_mirascope_client_has_callers(self):
        """mirascope_client.py must be imported by at least one non-test module.

        This test catches the exact failure from Feb 13, 2026:
        mirascope_client.py had full OpenRouter support but zero callers.
        """
        importers = self._find_importers("src.llm")
        assert len(importers) > 0, (
            "DEAD CODE: src.llm (mirascope_client) has zero non-test importers. "
            "The OpenRouter/multi-provider LLM client is not wired into the pipeline."
        )

    def test_base_agent_has_callers(self):
        """base_agent.py must be used by at least one agent in the pipeline."""
        importers = self._find_importers("src.agents")
        assert len(importers) > 0, (
            "DEAD CODE: src.agents has zero non-test importers. "
            "The agent framework is not wired into the pipeline."
        )


# =============================================================================
# TEST 2: Provider Routing Correctness
# =============================================================================


class TestProviderRouting:
    """Verify that model_selector routes to correct providers."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    def test_simple_task_routes_to_openrouter(self):
        """SIMPLE tasks should route to OpenRouter (DeepSeek) when key is available."""
        selector = ModelSelector()
        model_id = selector.select_model("sentiment_classification")
        provider = selector.get_model_provider(model_id)
        assert provider == "openrouter", (
            f"SIMPLE task selected model {model_id} with provider '{provider}'. "
            f"Expected OpenRouter provider for cost optimization."
        )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    def test_medium_task_routes_to_openrouter(self):
        """MEDIUM tasks should route to OpenRouter (Mistral) when key is available."""
        selector = ModelSelector()
        model_id = selector.select_model("technical_analysis")
        provider = selector.get_model_provider(model_id)
        assert provider == "openrouter", (
            f"MEDIUM task selected model {model_id} with provider '{provider}'. "
            f"Expected OpenRouter provider for cost optimization."
        )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    def test_complex_task_routes_to_openrouter(self):
        """COMPLEX tasks should route to OpenRouter (Kimi K2) when key is available."""
        selector = ModelSelector()
        model_id = selector.select_model("risk_assessment")
        provider = selector.get_model_provider(model_id)
        assert provider == "openrouter", (
            f"COMPLEX task selected model {model_id} with provider '{provider}'. "
            f"Expected OpenRouter provider (Kimi K2 = StockBench #1)."
        )

    def test_critical_task_always_anthropic(self):
        """CRITICAL tasks must ALWAYS route to Anthropic (Opus)."""
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"}):
            selector = ModelSelector()
            model_id = selector.select_model("trade_execution")
            provider = selector.get_model_provider(model_id)
            assert provider == "anthropic", (
                f"CRITICAL task selected model {model_id} with provider '{provider}'. "
                f"Trade execution MUST use Anthropic Opus. Phil Town Rule #1."
            )

    @patch.dict(os.environ, {}, clear=True)
    def test_falls_back_to_anthropic_without_key(self):
        """Without OPENROUTER_API_KEY, all tasks should use Anthropic models."""
        os.environ.pop("OPENROUTER_API_KEY", None)
        selector = ModelSelector()

        for task_type in ["sentiment_classification", "technical_analysis", "risk_assessment"]:
            model_id = selector.select_model(task_type)
            provider = selector.get_model_provider(model_id)
            assert provider == "anthropic", (
                f"Task '{task_type}' selected provider '{provider}' without OPENROUTER_API_KEY. "
                f"Expected fallback to Anthropic."
            )


# =============================================================================
# TEST 3: Base Agent Provider Wiring
# =============================================================================


class TestBaseAgentProviderWiring:
    """Verify base_agent correctly routes to OpenRouter or Anthropic."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_notification_agent_uses_openrouter(self, mock_api_key, mock_context, mock_anthropic):
        """NotificationAgent (SIMPLE task) should use OpenRouter provider."""
        _ensure_openai_mock()
        mock_context.return_value = MagicMock()

        from src.agents.base_agent import BaseAgent

        # Create a concrete subclass for testing
        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        agent = TestAgent(name="NotificationAgent", role="test")

        assert agent._provider == "openrouter", (
            f"NotificationAgent should use OpenRouter but got provider '{agent._provider}'. "
            f"Model: {agent.model}"
        )
        assert agent._openrouter_client is not None

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_agent_falls_back_to_anthropic(self, mock_api_key, mock_context, mock_anthropic):
        """Without OPENROUTER_API_KEY, agents should use Anthropic."""
        os.environ.pop("OPENROUTER_API_KEY", None)
        mock_context.return_value = MagicMock()
        mock_anthropic.return_value = MagicMock()

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        agent = TestAgent(name="NotificationAgent", role="test")
        assert agent._provider == "anthropic"
        assert agent.client is not None
        assert agent._openrouter_client is None

    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_execution_agent_always_anthropic(self, mock_api_key, mock_context, mock_anthropic):
        """ExecutionAgent (CRITICAL) must always use Anthropic Opus."""
        mock_context.return_value = MagicMock()
        mock_anthropic.return_value = MagicMock()

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"}):
            agent = TestAgent(name="ExecutionAgent", role="test")
            assert agent._provider == "anthropic", (
                "ExecutionAgent MUST use Anthropic (Opus). "
                "Trade execution cannot use cost-optimized models."
            )

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_openrouter_model_not_sent_to_anthropic(
        self, mock_api_key, mock_context, mock_anthropic
    ):
        """OpenRouter model IDs must NEVER be sent to Anthropic API.

        This catches the exact bug from Feb 13, 2026: model_selector returned
        'deepseek/deepseek-chat' but base_agent sent it to Anthropic() which fails.
        """
        _ensure_openai_mock()
        mock_context.return_value = MagicMock()

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        agent = TestAgent(name="NotificationAgent", role="test")

        if agent._provider == "openrouter":
            # Anthropic client should NOT be initialized for OpenRouter agents
            assert agent.client is None, (
                "OpenRouter agent has an Anthropic client initialized. "
                "This means OpenRouter model IDs could be sent to Anthropic API."
            )


# =============================================================================
# TEST 4: OpenRouter Client Initialization
# =============================================================================


class TestOpenRouterClientInit:
    """Verify OpenRouter client can be properly initialized."""

    def test_mirascope_client_supports_openrouter(self):
        """MirascopeTradingClient must support OpenRouter provider."""
        from src.llm.mirascope_client import LLMProvider

        assert hasattr(LLMProvider, "OPENROUTER")
        assert LLMProvider.OPENROUTER.value == "openrouter"

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    def test_mirascope_client_openrouter_init(self):
        """MirascopeTradingClient initializes with OpenRouter provider."""
        from src.llm.mirascope_client import LLMProvider, MirascopeTradingClient

        client = MirascopeTradingClient(provider=LLMProvider.OPENROUTER)
        assert client.provider == LLMProvider.OPENROUTER

    def test_mirascope_client_has_convenience_functions(self):
        """Convenience functions for market analysis exist and are callable."""
        from src.llm.mirascope_client import (
            analyze_market,
            get_mirascope_client,
            get_trade_decision,
            stream_analysis,
        )

        assert callable(get_mirascope_client)
        assert callable(stream_analysis)
        assert callable(get_trade_decision)
        assert callable(analyze_market)

    def test_model_selector_openrouter_models_valid(self):
        """All OpenRouter model IDs must follow the 'org/model' format."""
        for tier, config in MODEL_REGISTRY.items():
            if config.provider == "openrouter":
                assert "/" in config.model_id, (
                    f"OpenRouter model {tier.value} has invalid model_id '{config.model_id}'. "
                    f"OpenRouter requires 'org/model' format."
                )


# =============================================================================
# TEST 5: Reason With LLM Provider Routing
# =============================================================================


class TestReasonWithLLMRouting:
    """Verify reason_with_llm routes to the correct API based on provider."""

    @patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key-123"})
    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_openrouter_agent_calls_openrouter_api(
        self, mock_api_key, mock_context, mock_anthropic
    ):
        """OpenRouter agents must call OpenRouter API, not Anthropic."""
        mock_openai_mod = _ensure_openai_mock()
        mock_context.return_value = MagicMock()

        # Set up mock OpenAI client that will be returned by OpenAI()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "test response"
        mock_response.choices[0].message.tool_calls = None
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_mod.OpenAI = MagicMock(return_value=mock_client)

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        agent = TestAgent(name="SignalAgent", role="test")

        if agent._provider == "openrouter":
            result = agent.reason_with_llm("Analyze SPY conditions")
            mock_client.chat.completions.create.assert_called_once()
            assert result["reasoning"] == "test response"

    @patch.dict(os.environ, {}, clear=True)
    @patch("src.agents.base_agent.Anthropic")
    @patch("src.agents.base_agent.get_context_engine")
    @patch("src.agents.base_agent.get_anthropic_api_key", return_value="test-key")
    def test_anthropic_agent_calls_anthropic_api(
        self, mock_api_key, mock_context, mock_anthropic_cls
    ):
        """Anthropic agents must call Anthropic API."""
        os.environ.pop("OPENROUTER_API_KEY", None)
        mock_context.return_value = MagicMock()

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="anthropic response")]
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        mock_client.messages.create.return_value = mock_response
        mock_anthropic_cls.return_value = mock_client

        from src.agents.base_agent import BaseAgent

        class TestAgent(BaseAgent):
            def analyze(self, data):
                return data

        agent = TestAgent(name="ExecutionAgent", role="test")
        result = agent.reason_with_llm("Execute trade")

        mock_client.messages.create.assert_called_once()
        assert result["reasoning"] == "anthropic response"


# =============================================================================
# TEST 6: Provider Consistency Invariants
# =============================================================================


class TestProviderConsistencyInvariants:
    """Architectural invariants that must always hold."""

    def test_all_openrouter_models_have_valid_provider(self):
        """Every model with provider='openrouter' must have an OpenRouter-formatted model_id."""
        for tier, config in MODEL_REGISTRY.items():
            if config.provider == "openrouter":
                parts = config.model_id.split("/")
                assert len(parts) == 2, (
                    f"Model {tier.value}: OpenRouter model_id '{config.model_id}' "
                    f"must be in 'org/model' format."
                )

    def test_critical_tasks_never_use_openrouter(self):
        """CRITICAL tasks must never route to OpenRouter models."""
        from src.utils.model_selector import TASK_COMPLEXITY_MAP, TaskComplexity

        critical_tasks = [k for k, v in TASK_COMPLEXITY_MAP.items() if v == TaskComplexity.CRITICAL]

        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "test-key"}):
            selector = ModelSelector()
            for task in critical_tasks:
                model_id = selector.select_model(task)
                provider = selector.get_model_provider(model_id)
                assert provider == "anthropic", (
                    f"CRITICAL task '{task}' routed to provider '{provider}' "
                    f"(model: {model_id}). Trade execution MUST use Anthropic Opus."
                )

    def test_openrouter_key_env_var_name(self):
        """Verify the correct env var name is used for OpenRouter."""
        import src.utils.model_selector as ms

        source = Path(ms.__file__).read_text()
        assert "OPENROUTER_API_KEY" in source, (
            "model_selector.py does not reference OPENROUTER_API_KEY env var. "
            "OpenRouter integration cannot detect available credentials."
        )

    def test_base_agent_has_provider_attribute(self):
        """BaseAgent must have _provider attribute for routing."""
        import inspect

        from src.agents.base_agent import BaseAgent

        source = inspect.getsource(BaseAgent.__init__)
        assert "_provider" in source, (
            "BaseAgent.__init__ does not set _provider attribute. "
            "LLM calls cannot be routed to the correct provider."
        )

    def test_base_agent_has_openrouter_method(self):
        """BaseAgent must have _reason_with_openrouter method."""
        from src.agents.base_agent import BaseAgent

        assert hasattr(BaseAgent, "_reason_with_openrouter"), (
            "BaseAgent missing _reason_with_openrouter method. "
            "OpenRouter models selected by model_selector will not be callable."
        )

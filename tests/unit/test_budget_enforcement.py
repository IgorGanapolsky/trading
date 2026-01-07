"""
Tests for budget enforcement in ModelSelector.

Technical Debt Fix - Jan 2026
Verifies runtime budget enforcement prevents overspending.
"""

import pytest

from src.utils.model_selector import (
    MODEL_REGISTRY,
    ModelSelector,
    ModelTier,
)


class TestBudgetEnforcement:
    """Tests for runtime budget enforcement."""

    def test_can_afford_model_within_budget(self):
        """Test that affordable models return True."""
        selector = ModelSelector(daily_budget=10.0)
        selector.daily_spend = 0.0

        # HAIKU is cheap, should be affordable
        assert selector.can_afford_model(ModelTier.HAIKU, estimated_tokens=1000)

    def test_can_afford_model_exceeds_budget(self):
        """Test that expensive models return False when budget is low."""
        selector = ModelSelector(daily_budget=0.01)
        selector.daily_spend = 0.0

        # OPUS is expensive, should not be affordable with $0.01 budget
        assert not selector.can_afford_model(ModelTier.OPUS, estimated_tokens=10000)

    def test_enforce_budget_allows_within_limit(self):
        """Test that enforce_budget allows calls within daily limit."""
        selector = ModelSelector(daily_budget=10.0)
        selector.daily_spend = 0.0

        haiku_config = MODEL_REGISTRY[ModelTier.HAIKU]
        allowed, reason = selector.enforce_budget(haiku_config.model_id)

        assert allowed is True
        assert reason == "within_budget"

    def test_enforce_budget_blocks_over_limit(self):
        """Test that enforce_budget blocks calls that would exceed limit."""
        selector = ModelSelector(daily_budget=0.001)
        selector.daily_spend = 0.0

        # Sonnet is too expensive for $0.001 budget
        sonnet_config = MODEL_REGISTRY[ModelTier.SONNET]
        allowed, reason = selector.enforce_budget(
            sonnet_config.model_id, estimated_tokens=10000
        )

        assert allowed is False
        assert "budget_exceeded" in reason

    def test_critical_tasks_never_blocked(self):
        """Test that CRITICAL (Opus) tasks are never blocked by budget."""
        selector = ModelSelector(daily_budget=0.0001)  # Tiny budget
        selector.daily_spend = 0.0

        opus_config = MODEL_REGISTRY[ModelTier.OPUS]
        allowed, reason = selector.enforce_budget(opus_config.model_id)

        assert allowed is True
        assert reason == "critical_always_allowed"

    def test_select_model_downgrades_when_over_budget(self):
        """Test that select_model downgrades when budget would be exceeded."""
        selector = ModelSelector(daily_budget=0.001)
        selector.daily_spend = 0.0

        # Request a complex task that would normally use expensive model
        # With tiny budget, should downgrade
        model_id = selector.select_model("technical_analysis", enforce_budget=True)

        # Should get a cheaper model due to budget constraints
        config = selector.get_model_config(model_id)
        assert config is not None
        # Verify it's not an expensive model (OPUS, SONNET)
        assert config.tier in (ModelTier.HAIKU, ModelTier.DEEPSEEK, ModelTier.MISTRAL)

    def test_select_model_no_downgrade_when_within_budget(self):
        """Test that select_model uses appropriate tier when budget allows."""
        selector = ModelSelector(daily_budget=100.0)  # Large budget
        selector.daily_spend = 0.0

        # For complex task with large budget, should get appropriate model
        model_id = selector.select_model("risk_assessment", enforce_budget=True)

        config = selector.get_model_config(model_id)
        assert config is not None
        # Should get a capable model for complex tasks
        assert config.tier in (ModelTier.KIMI, ModelTier.OPUS, ModelTier.SONNET)

    def test_critical_task_always_opus(self):
        """Test that CRITICAL tasks always use Opus regardless of budget."""
        selector = ModelSelector(daily_budget=0.0001)  # Tiny budget
        selector.daily_spend = 0.0

        model_id = selector.select_model("trade_execution")

        opus_config = MODEL_REGISTRY[ModelTier.OPUS]
        assert model_id == opus_config.model_id

    def test_log_usage_updates_spend(self):
        """Test that log_usage correctly updates daily_spend."""
        selector = ModelSelector(daily_budget=10.0)
        selector.daily_spend = 0.0

        haiku_config = MODEL_REGISTRY[ModelTier.HAIKU]
        cost = selector.log_usage(
            haiku_config.model_id, input_tokens=1000, output_tokens=500
        )

        assert cost > 0
        assert selector.daily_spend == cost

    def test_budget_status_reporting(self):
        """Test that get_budget_status returns correct info."""
        selector = ModelSelector(daily_budget=10.0, monthly_budget=300.0)
        selector.daily_spend = 2.5
        selector.monthly_spend = 75.0

        status = selector.get_budget_status()

        assert status["daily_spent"] == 2.5
        assert status["daily_budget"] == 10.0
        assert status["daily_remaining"] == 7.5
        assert status["daily_pct_used"] == 25.0
        assert status["monthly_spent"] == 75.0


class TestToolDefinitions:
    """Tests for unified tool definitions."""

    def test_tool_definition_to_claude(self):
        """Test conversion to Claude format."""
        from src.utils.tool_definitions import ToolDefinition, ToolParameter

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type="string",
                    description="First parameter",
                    required=True,
                ),
                ToolParameter(
                    name="param2",
                    type="number",
                    description="Second parameter",
                    required=False,
                ),
            ],
        )

        claude_format = tool.to_claude()

        assert claude_format["name"] == "test_tool"
        assert claude_format["description"] == "A test tool"
        assert "input_schema" in claude_format
        assert claude_format["input_schema"]["type"] == "object"
        assert "param1" in claude_format["input_schema"]["properties"]
        assert claude_format["input_schema"]["required"] == ["param1"]

    def test_tool_definition_to_gemini(self):
        """Test conversion to Gemini format."""
        from src.utils.tool_definitions import ToolDefinition, ToolParameter

        tool = ToolDefinition(
            name="test_tool",
            description="A test tool",
            parameters=[
                ToolParameter(
                    name="param1",
                    type="string",
                    description="First parameter",
                ),
            ],
        )

        gemini_format = tool.to_gemini()

        assert gemini_format["name"] == "test_tool"
        assert gemini_format["description"] == "A test tool"
        assert "parameters" in gemini_format
        assert gemini_format["parameters"]["type"] == "OBJECT"

    def test_tool_registry(self):
        """Test tool registry operations."""
        from src.utils.tool_definitions import ToolDefinition, ToolRegistry

        registry = ToolRegistry()
        tool = ToolDefinition(name="my_tool", description="Test")

        registry.register(tool)

        assert registry.get("my_tool") is not None
        assert registry.get("nonexistent") is None

        claude_tools = registry.to_claude()
        assert len(claude_tools) == 1

    def test_trading_registry_preloaded(self):
        """Test that trading registry has expected tools."""
        from src.utils.tool_definitions import get_trading_registry

        registry = get_trading_registry()

        assert registry.get("calculate_position_size") is not None
        assert registry.get("get_quote") is not None
        assert registry.get("place_order") is not None
        assert registry.get("assess_trade_risk") is not None
        assert registry.get("query_lessons_learned") is not None


class TestUnifiedMCPClient:
    """Tests for unified MCP client."""

    def test_mcp_tool_result_success(self):
        """Test MCPToolResult for successful calls."""
        from mcp.client import MCPToolResult, MCPTransport

        result = MCPToolResult(
            success=True,
            data={"key": "value"},
            transport=MCPTransport.DIRECT,
            latency_ms=10.5,
        )

        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.error is None

        # Should not raise
        result.raise_on_error()

    def test_mcp_tool_result_failure(self):
        """Test MCPToolResult for failed calls."""
        from mcp.client import MCPError, MCPToolResult

        result = MCPToolResult(
            success=False,
            error="Connection failed",
            latency_ms=5.0,
        )

        assert result.success is False
        assert result.error == "Connection failed"

        with pytest.raises(MCPError):
            result.raise_on_error()

    def test_unified_client_singleton(self):
        """Test that get_unified_client returns singleton."""
        from mcp.client import get_unified_client

        client1 = get_unified_client()
        client2 = get_unified_client()

        assert client1 is client2

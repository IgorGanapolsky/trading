"""
Unified Tool Definition Format for Claude and Gemini APIs.

Technical Debt Fix - Jan 2026

This module provides a standardized way to define tools that work with both:
- Anthropic Claude API (tools parameter in messages.create)
- Google Gemini API (tools parameter in generate_content)

The APIs use different formats:
- Claude: {"name": str, "description": str, "input_schema": JSONSchema}
- Gemini: {"function_declarations": [{"name": str, "description": str, "parameters": JSONSchema}]}

This module provides:
1. ToolDefinition dataclass - Provider-agnostic tool definition
2. ToolRegistry - Collection of tool definitions with conversion methods
3. Pre-defined trading tools ready for use
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ToolProvider(Enum):
    """Supported LLM providers for tool calling."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    OPENROUTER = "openrouter"


@dataclass
class ToolParameter:
    """A single parameter for a tool."""

    name: str
    type: str  # "string", "number", "integer", "boolean", "array", "object"
    description: str
    required: bool = True
    enum: list[str] | None = None
    default: Any = None
    items: dict[str, Any] | None = None  # For array types


@dataclass
class ToolDefinition:
    """
    Provider-agnostic tool definition.

    Can be converted to Claude or Gemini format.
    """

    name: str
    description: str
    parameters: list[ToolParameter] = field(default_factory=list)

    def to_claude(self) -> dict[str, Any]:
        """Convert to Anthropic Claude tool format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def to_gemini(self) -> dict[str, Any]:
        """Convert to Google Gemini function declaration format."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type.upper(),  # Gemini uses uppercase types
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "type": "OBJECT",
                "properties": properties,
                "required": required,
            },
        }

    def to_openrouter(self) -> dict[str, Any]:
        """Convert to OpenRouter format (OpenAI-compatible)."""
        properties = {}
        required = []

        for param in self.parameters:
            prop: dict[str, Any] = {
                "type": param.type,
                "description": param.description,
            }
            if param.enum:
                prop["enum"] = param.enum
            if param.items:
                prop["items"] = param.items

            properties[param.name] = prop

            if param.required:
                required.append(param.name)

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required,
                },
            },
        }


class ToolRegistry:
    """
    Registry of tool definitions with multi-provider support.

    Usage:
        registry = ToolRegistry()
        registry.register(my_tool)

        # Get tools for Claude
        claude_tools = registry.to_claude()

        # Get tools for Gemini
        gemini_tools = registry.to_gemini()
    """

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool
        logger.debug(f"Registered tool: {tool.name}")

    def get(self, name: str) -> ToolDefinition | None:
        """Get a tool by name."""
        return self._tools.get(name)

    def to_claude(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Convert all or selected tools to Claude format."""
        tools = self._tools.values()
        if tool_names:
            tools = [t for t in tools if t.name in tool_names]
        return [t.to_claude() for t in tools]

    def to_gemini(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Convert all or selected tools to Gemini function_declarations format."""
        tools = self._tools.values()
        if tool_names:
            tools = [t for t in tools if t.name in tool_names]
        return {"function_declarations": [t.to_gemini() for t in tools]}

    def to_openrouter(self, tool_names: list[str] | None = None) -> list[dict[str, Any]]:
        """Convert all or selected tools to OpenRouter format."""
        tools = self._tools.values()
        if tool_names:
            tools = [t for t in tools if t.name in tool_names]
        return [t.to_openrouter() for t in tools]

    def to_provider(
        self,
        provider: ToolProvider,
        tool_names: list[str] | None = None,
    ) -> list[dict[str, Any]] | dict[str, Any]:
        """Convert tools to the format for a specific provider."""
        if provider == ToolProvider.CLAUDE:
            return self.to_claude(tool_names)
        elif provider == ToolProvider.GEMINI:
            return self.to_gemini(tool_names)
        elif provider == ToolProvider.OPENROUTER:
            return self.to_openrouter(tool_names)
        else:
            raise ValueError(f"Unknown provider: {provider}")


# =============================================================================
# PRE-DEFINED TRADING TOOLS
# =============================================================================

# Position sizing tool
POSITION_SIZE_TOOL = ToolDefinition(
    name="calculate_position_size",
    description="Calculate the optimal position size for a trade based on risk management rules",
    parameters=[
        ToolParameter(
            name="symbol",
            type="string",
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
        ),
        ToolParameter(
            name="entry_price",
            type="number",
            description="Planned entry price for the position",
        ),
        ToolParameter(
            name="stop_loss_price",
            type="number",
            description="Stop loss price for risk calculation",
        ),
        ToolParameter(
            name="account_value",
            type="number",
            description="Total account value in dollars",
        ),
        ToolParameter(
            name="risk_percent",
            type="number",
            description="Maximum risk per trade as percentage (e.g., 1.0 for 1%)",
            required=False,
            default=1.0,
        ),
    ],
)

# Market data tool
GET_QUOTE_TOOL = ToolDefinition(
    name="get_quote",
    description="Get the current quote (bid/ask/last) for a stock symbol",
    parameters=[
        ToolParameter(
            name="symbol",
            type="string",
            description="Stock ticker symbol (e.g., 'AAPL', 'MSFT')",
        ),
    ],
)

# Order placement tool
PLACE_ORDER_TOOL = ToolDefinition(
    name="place_order",
    description="Place a stock order (buy or sell)",
    parameters=[
        ToolParameter(
            name="symbol",
            type="string",
            description="Stock ticker symbol",
        ),
        ToolParameter(
            name="side",
            type="string",
            description="Order side",
            enum=["buy", "sell"],
        ),
        ToolParameter(
            name="quantity",
            type="integer",
            description="Number of shares to trade",
        ),
        ToolParameter(
            name="order_type",
            type="string",
            description="Type of order",
            enum=["market", "limit", "stop", "stop_limit"],
            required=False,
            default="market",
        ),
        ToolParameter(
            name="limit_price",
            type="number",
            description="Limit price (required for limit and stop_limit orders)",
            required=False,
        ),
        ToolParameter(
            name="stop_price",
            type="number",
            description="Stop price (required for stop and stop_limit orders)",
            required=False,
        ),
    ],
)

# Risk assessment tool
ASSESS_RISK_TOOL = ToolDefinition(
    name="assess_trade_risk",
    description="Assess the risk level of a proposed trade",
    parameters=[
        ToolParameter(
            name="symbol",
            type="string",
            description="Stock ticker symbol",
        ),
        ToolParameter(
            name="position_size",
            type="number",
            description="Proposed position size in dollars",
        ),
        ToolParameter(
            name="portfolio_value",
            type="number",
            description="Total portfolio value",
        ),
        ToolParameter(
            name="existing_exposure",
            type="number",
            description="Current exposure to this sector/stock",
            required=False,
            default=0,
        ),
    ],
)

# RAG query tool
QUERY_LESSONS_TOOL = ToolDefinition(
    name="query_lessons_learned",
    description="Query the lessons learned database for relevant past trading experiences",
    parameters=[
        ToolParameter(
            name="query",
            type="string",
            description="Search query for lessons (e.g., 'AAPL earnings', 'stop loss triggered')",
        ),
        ToolParameter(
            name="severity",
            type="string",
            description="Filter by lesson severity",
            enum=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            required=False,
        ),
        ToolParameter(
            name="limit",
            type="integer",
            description="Maximum number of results to return",
            required=False,
            default=5,
        ),
    ],
)

# Sentiment analysis tool
ANALYZE_SENTIMENT_TOOL = ToolDefinition(
    name="analyze_sentiment",
    description="Analyze market sentiment for a stock from news and social media",
    parameters=[
        ToolParameter(
            name="symbol",
            type="string",
            description="Stock ticker symbol",
        ),
        ToolParameter(
            name="sources",
            type="array",
            description="Data sources to analyze",
            items={"type": "string", "enum": ["news", "twitter", "reddit", "sec_filings"]},
            required=False,
        ),
        ToolParameter(
            name="lookback_days",
            type="integer",
            description="Number of days to look back for sentiment data",
            required=False,
            default=7,
        ),
    ],
)


def get_trading_registry() -> ToolRegistry:
    """Get a registry pre-populated with trading tools."""
    registry = ToolRegistry()
    registry.register(POSITION_SIZE_TOOL)
    registry.register(GET_QUOTE_TOOL)
    registry.register(PLACE_ORDER_TOOL)
    registry.register(ASSESS_RISK_TOOL)
    registry.register(QUERY_LESSONS_TOOL)
    registry.register(ANALYZE_SENTIMENT_TOOL)
    return registry


# Singleton registry
_trading_registry: ToolRegistry | None = None


def get_default_registry() -> ToolRegistry:
    """Get the default trading tool registry (singleton)."""
    global _trading_registry
    if _trading_registry is None:
        _trading_registry = get_trading_registry()
    return _trading_registry

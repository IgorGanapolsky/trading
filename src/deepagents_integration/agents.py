"""
DeepAgents-based trading agents with planning and sub-agent capabilities.
"""

from __future__ import annotations

import logging

from langchain.chat_models import init_chat_model
from langchain_core.language_models.chat_models import BaseChatModel

from .mcp_tools import build_mcp_tools_for_deepagents
from .tools import build_trading_tools

logger = logging.getLogger(__name__)

try:
    from deepagents import create_deep_agent
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    create_deep_agent = None  # type: ignore
    DEEPAGENTS_IMPORT_ERROR = exc
else:
    DEEPAGENTS_IMPORT_ERROR = None


TRADING_RESEARCH_SYSTEM_PROMPT = """You are an expert trading research analyst specializing in comprehensive market analysis.

Your workflow:
1. **Planning**: Use write_todos to break down complex research tasks into manageable steps
2. **Data Gathering**: Use market data and sentiment tools to gather information
3. **Analysis**: Use read_file and write_file to store intermediate analysis results
4. **Delegation**: Use the task tool to delegate specialized analysis to sub-agents when needed
5. **Reporting**: Write comprehensive research reports using write_file

## Available Tools

### Market Data
- `get_market_data`: Fetch historical OHLCV data for symbols
- `analyze_technical_indicators`: Calculate technical indicators (RSI, MACD, etc.)

### Sentiment Analysis
- `query_sentiment`: Semantic search over historical sentiment data
- `get_sentiment_history`: Get recent sentiment snapshots for a ticker

### MCP Tools
- `call_mcp_tool`: Access trading APIs, order placement, account info
- `get_mcp_servers`: List available MCP servers

## Best Practices

1. **Always plan first**: Use write_todos before starting complex research
2. **Save intermediate results**: Use write_file to save analysis at each step
3. **Batch similar queries**: Group related data requests together
4. **Use sub-agents for deep dives**: Delegate specialized analysis to sub-agents
5. **Document your reasoning**: Include clear explanations in your reports

## Output Format

When completing research, provide:
- Executive summary
- Key findings with supporting data
- Risk factors
- Recommendations
- Data sources used
"""


MARKET_ANALYSIS_SYSTEM_PROMPT = """You are a market analysis agent specializing in real-time market assessment and trade signal generation.

Your responsibilities:
1. **Market Regime Detection**: Analyze current market conditions (bullish, bearish, range-bound)
2. **Signal Generation**: Identify trading opportunities based on technical and sentiment analysis
3. **Risk Assessment**: Evaluate position sizing and risk parameters
4. **Execution Planning**: Prepare detailed execution plans for approved trades

## Workflow

1. **Planning**: Use write_todos to structure your analysis
2. **Data Collection**: Gather market data, sentiment, and technical indicators
3. **Analysis**: Use filesystem tools to store analysis and compare with historical patterns
4. **Delegation**: Use task tool to delegate risk assessment to specialized sub-agents
5. **Reporting**: Generate structured trade recommendations

## Key Tools

- Market data: `get_market_data`, `analyze_technical_indicators`
- Sentiment: `query_sentiment`, `get_sentiment_history`
- Trading: `call_mcp_tool` (for order placement, account info)
- Filesystem: `read_file`, `write_file`, `ls`, `grep` (built-in)

## Output Requirements

Trade recommendations must include:
- Symbol and action (BUY/SELL/HOLD)
- Entry price and timing
- Stop loss and take profit levels
- Position size recommendation
- Conviction score (0-1)
- Risk assessment
- Supporting data and reasoning
"""


def create_trading_research_agent(
    model: str | BaseChatModel | None = None,
    include_mcp_tools: bool = True,
    temperature: float = 0.3,
) -> any:
    """
    Create a deepagent for trading research with planning and sub-agent capabilities.

    Args:
        model: Model name or instance (default: claude-sonnet-4-5-20250929)
        include_mcp_tools: Whether to include MCP trading tools
        temperature: Model temperature (default: 0.3)

    Returns:
        DeepAgent instance configured for trading research
    """
    if create_deep_agent is None:
        raise ImportError(
            "deepagents is not installed. Install optional extras with "
            '`python -m pip install ".[deepagents]"` and set DEEPAGENTS_ENABLED=true.'
        ) from DEEPAGENTS_IMPORT_ERROR

    if model is None:
        model = init_chat_model(
            model="anthropic:claude-sonnet-4-5-20250929",
            temperature=temperature,
        )
    elif isinstance(model, str):
        model = init_chat_model(model=model, temperature=temperature)

    tools = build_trading_tools()

    if include_mcp_tools:
        tools.extend(build_mcp_tools_for_deepagents())

    logger.info(f"Creating trading research agent with {len(tools)} tools")

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=TRADING_RESEARCH_SYSTEM_PROMPT,
    )

    return agent


def create_market_analysis_agent(
    model: str | BaseChatModel | None = None,
    include_mcp_tools: bool = True,
    temperature: float = 0.2,
    subagents: list | None = None,
) -> any:
    """
    Create a deepagent for market analysis with sub-agent delegation.

    Args:
        model: Model name or instance (default: claude-sonnet-4-5-20250929)
        include_mcp_tools: Whether to include MCP trading tools
        temperature: Model temperature (default: 0.2 for more deterministic analysis)
        subagents: Optional list of sub-agent configurations

    Returns:
        DeepAgent instance configured for market analysis
    """
    if create_deep_agent is None:
        raise ImportError(
            "deepagents is not installed. Install optional extras with "
            '`python -m pip install ".[deepagents]"` and set DEEPAGENTS_ENABLED=true.'
        ) from DEEPAGENTS_IMPORT_ERROR

    if model is None:
        model = init_chat_model(
            model="anthropic:claude-sonnet-4-5-20250929",
            temperature=temperature,
        )
    elif isinstance(model, str):
        model = init_chat_model(model=model, temperature=temperature)

    tools = build_trading_tools()

    if include_mcp_tools:
        tools.extend(build_mcp_tools_for_deepagents())

    logger.info(f"Creating market analysis agent with {len(tools)} tools")

    agent = create_deep_agent(
        model=model,
        tools=tools,
        system_prompt=MARKET_ANALYSIS_SYSTEM_PROMPT,
        subagents=subagents,
    )

    return agent

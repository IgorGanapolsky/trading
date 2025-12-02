from __future__ import annotations

import logging
import os
from collections.abc import Iterable

try:  # LangChain 0.x
    from langchain.agents import AgentExecutor, AgentType, initialize_agent
except ImportError:  # LangChain 1.x fallback
    AgentExecutor = None
    AgentType = None
    initialize_agent = None
from langchain_community.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from .toolkit import build_mcp_tool, build_sentiment_tools

logger = logging.getLogger(__name__)


def _get_anthropic_api_key() -> str | None:
    """
    Get Anthropic API key with fallback to CLAUDE_API_KEY.

    This ensures backward compatibility and allows using either
    ANTHROPIC_API_KEY or CLAUDE_API_KEY environment variables.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    # Backfill ANTHROPIC_API_KEY for downstream libs if only CLAUDE_API_KEY is set
    if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("CLAUDE_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("CLAUDE_API_KEY") or ""
    return api_key


def get_default_llm() -> BaseChatModel:
    """
    Instantiate the default chat model for LangChain agents.

    Uses Anthropic (Claude) by default because it performs well with tool calling.
    Override via `LANGCHAIN_MODEL` or by passing a custom LLM to build_* helpers.

    Supports both ANTHROPIC_API_KEY and CLAUDE_API_KEY for backward compatibility.
    """
    model = os.environ.get("LANGCHAIN_MODEL", "claude-3-5-sonnet-20241022")
    temperature = float(os.environ.get("LANGCHAIN_TEMPERATURE", "0.3"))

    # Get API key with fallback
    api_key = _get_anthropic_api_key()

    logger.info("Initializing LangChain ChatAnthropic model: %s", model)
    return ChatAnthropic(model=model, temperature=temperature, anthropic_api_key=api_key)


class _SimpleLLMExecutor:
    """Fallback executor if the LangChain Agent API is unavailable."""

    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    def invoke(self, payload: dict) -> dict:
        prompt = payload.get("input") if isinstance(payload, dict) else str(payload)
        response = self._llm.invoke(prompt)
        text = getattr(response, "content", str(response))
        return {"output": text}


class _SimpleLLMExecutor:
    """Fallback executor if the LangChain Agent API is unavailable."""

    def __init__(self, llm: BaseChatModel):
        self._llm = llm

    def invoke(self, payload: dict) -> dict:
        prompt = payload.get("input") if isinstance(payload, dict) else str(payload)
        response = self._llm.invoke(prompt)
        text = getattr(response, "content", str(response))
        return {"output": text}


def build_price_action_agent(
    llm: BaseChatModel | None = None,
    extra_tools: Iterable[BaseTool] | None = None,
):
    """
    Construct a LangChain agent tuned for price-action/technical analysis.

    The agent has access to:
        * Sentiment RAG queries/histories
        * Optional MCP tool bridge (for brokerage or additional data sources)
    """
    llm = llm or get_default_llm()

    tools: list[BaseTool] = []
    tools.extend(build_sentiment_tools())

    # MCP tool access can be toggled via env flag
    if os.environ.get("LANGCHAIN_ENABLE_MCP", "true").lower() == "true":
        tools.append(build_mcp_tool())

    if extra_tools:
        tools.extend(extra_tools)

    if initialize_agent is None or AgentType is None:
        logger.warning("LangChain agent interfaces unavailable; using simple LLM executor instead.")
        return _SimpleLLMExecutor(llm)

    logger.info("Initializing price action agent with %d tools.", len(tools))

    executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )
    return executor

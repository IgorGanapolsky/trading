from __future__ import annotations

import logging
import os
from typing import Iterable, Optional

try:  # LangChain 0.x
    from langchain.agents import AgentExecutor, AgentType, initialize_agent
except ImportError:  # LangChain 1.x fallback
    AgentExecutor = None
    AgentType = None
    initialize_agent = None
from langchain_community.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.tools import BaseTool

from .toolkit import build_sentiment_tools, build_mcp_tool

logger = logging.getLogger(__name__)


def get_default_llm() -> BaseChatModel:
    """
    Instantiate the default chat model for LangChain agents.

    Uses Anthropic (Claude) by default because it performs well with tool calling.
    Override via `LANGCHAIN_MODEL` or by passing a custom LLM to build_* helpers.
    """
    model = os.environ.get("LANGCHAIN_MODEL", "claude-3-5-sonnet-20241022")
    temperature = float(os.environ.get("LANGCHAIN_TEMPERATURE", "0.3"))

    logger.info("Initializing LangChain ChatAnthropic model: %s", model)
    return ChatAnthropic(model=model, temperature=temperature)


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
    llm: Optional[BaseChatModel] = None,
    extra_tools: Optional[Iterable[BaseTool]] = None,
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
        logger.warning(
            "LangChain agent interfaces unavailable; using simple LLM executor instead."
        )
        return _SimpleLLMExecutor(llm)

    logger.info("Initializing price action agent with %d tools.", len(tools))

    executor = initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )
    return executor


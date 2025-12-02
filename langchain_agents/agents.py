from __future__ import annotations

import json
import logging
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Annotated, Any, TypedDict

import yaml
from langchain_community.chat_models import ChatAnthropic
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

try:
    from langchain.agents import AgentExecutor, AgentType, initialize_agent
except ImportError:  # The legacy agent executor API is optional
    AgentExecutor = None
    AgentType = None
    initialize_agent = None

try:
    from langgraph.graph import StateGraph, add_messages
    from langgraph.prebuilt import ToolNode, tools_condition

    LANGGRAPH_AVAILABLE = True
except ImportError:  # pragma: no cover - LangGraph is part of our default toolchain
    StateGraph = None  # type: ignore[assignment]
    ToolNode = None  # type: ignore[assignment]
    tools_condition = None  # type: ignore[assignment]
    LANGGRAPH_AVAILABLE = False

    def add_messages(*args, **kwargs):  # type: ignore[override]
        raise RuntimeError("LangGraph is required for the langgraph executor path.")

from .langsmith_support import LangSmithAgentBridge
from .toolkit import (
    build_filesystem_tools,
    build_mcp_tool,
    build_sentiment_tools,
)

logger = logging.getLogger(__name__)

_CONFIG_PATH = Path(__file__).with_name("config").joinpath("price_action_agent.yaml")
_DEFAULT_PROMPT = """You are a price-action analyst preparing a concise morning brief for the trading desk.
Summarize technical outlook, highlight key support/resistance, volume context, and sentiment anomalies surfaced by internal tools.
When sentiment data is missing, call it out explicitly. Keep answers focused, data-backed, and under 300 words."""


if LANGGRAPH_AVAILABLE:

    class AgentState(TypedDict):
        messages: Annotated[list[BaseMessage], add_messages]

else:

    class AgentState(TypedDict):
        messages: list[BaseMessage]


def _load_price_action_config() -> dict[str, Any]:
    if not _CONFIG_PATH.exists():
        return {
            "name": "price-action-agent",
            "system_prompt": _DEFAULT_PROMPT,
            "description": "Price-action briefing agent with sentiment + MCP tools.",
        }
    try:
        data = yaml.safe_load(_CONFIG_PATH.read_text())
        if not data:
            raise ValueError("empty config")
        return data
    except Exception as exc:  # pragma: no cover
        logger.warning("Failed to parse %s: %s", _CONFIG_PATH, exc)
        return {
            "name": "price-action-agent",
            "system_prompt": _DEFAULT_PROMPT,
            "description": "Price-action briefing agent with sentiment + MCP tools.",
        }


def _get_anthropic_api_key() -> str | None:
    api_key = os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    if not os.getenv("ANTHROPIC_API_KEY") and os.getenv("CLAUDE_API_KEY"):
        os.environ["ANTHROPIC_API_KEY"] = os.getenv("CLAUDE_API_KEY") or ""
    return api_key


def get_default_llm() -> BaseChatModel:
    model = os.environ.get("LANGCHAIN_MODEL", "claude-3-5-sonnet-20241022")
    temperature = float(os.environ.get("LANGCHAIN_TEMPERATURE", "0.3"))
    api_key = _get_anthropic_api_key()
    logger.info("Initializing LangChain ChatAnthropic model: %s", model)
    return ChatAnthropic(model=model, temperature=temperature, anthropic_api_key=api_key)


class _SimpleLLMExecutor:
    """Fallback executor if LangGraph and the Agent API are unavailable."""

    def __init__(self, llm: BaseChatModel, system_prompt: str):
        self._llm = llm
        self._system_prompt = system_prompt

    def invoke(self, payload: dict | str) -> dict[str, str]:
        user_prompt = (
            payload.get("input") if isinstance(payload, dict) else str(payload)
        )
        prompt = f"{self._system_prompt}\n\n{user_prompt}"
        response = self._llm.invoke(prompt)
        text = getattr(response, "content", str(response))
        return {"output": text}


class PriceActionAgentExecutor:
    """LangGraph powered executor with LangSmith instrumentation hooks."""

    def __init__(
        self,
        graph,
        *,
        system_prompt: str,
        bridge: LangSmithAgentBridge | None = None,
    ) -> None:
        self._graph = graph
        self._system_prompt = system_prompt
        self.langsmith_bridge = bridge

    def _build_messages(self, payload: dict | str | None) -> list[BaseMessage]:
        if payload is None:
            text = ""
        elif isinstance(payload, dict):
            text = (
                payload.get("input")
                or payload.get("prompt")
                or payload.get("question")
                or ""
            )
        else:
            text = str(payload)
        if not text:
            raise ValueError("Agent invocation requires non-empty input text.")
        return [SystemMessage(content=self._system_prompt), HumanMessage(content=text)]

    def invoke(self, payload: dict | str | None, config: dict | None = None) -> dict:
        messages = self._build_messages(payload)
        state = self._graph.invoke({"messages": messages}, config=config or {})
        final_message: BaseMessage = state["messages"][-1]
        output = (
            final_message.content
            if hasattr(final_message, "content")
            else json.dumps(final_message, default=str)
        )
        if self.langsmith_bridge:
            self.langsmith_bridge.record_run(
                prompt=messages[-1].content,
                response=output,
                metadata={"engine": "langgraph"},
            )
        return {"output": output, "messages": state["messages"]}

    async def ainvoke(
        self, payload: dict | str | None, config: dict | None = None
    ) -> dict:
        messages = self._build_messages(payload)
        state = await self._graph.ainvoke({"messages": messages}, config=config or {})
        final_message: BaseMessage = state["messages"][-1]
        output = (
            final_message.content
            if hasattr(final_message, "content")
            else json.dumps(final_message, default=str)
        )
        if self.langsmith_bridge:
            self.langsmith_bridge.record_run(
                prompt=messages[-1].content,
                response=output,
                metadata={"engine": "langgraph", "async": True},
            )
        return {"output": output, "messages": state["messages"]}


def _build_langgraph_executor(llm: BaseChatModel, tools: list[BaseTool]):
    if not LANGGRAPH_AVAILABLE:  # pragma: no cover - guarded upstream
        raise RuntimeError("LangGraph is not installed.")
    tool_node = ToolNode(tools)
    bound_llm = llm.bind_tools(tools)

    def agent_node(state: AgentState):
        response = bound_llm.invoke(state["messages"])
        if isinstance(response, str):
            response = AIMessage(content=response)
        return {"messages": [response]}

    graph = StateGraph(AgentState)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_edge("__start__", "agent")
    graph.add_conditional_edges(
        "agent", tools_condition, {"tools": "tools", "__end__": "__end__"}
    )
    graph.add_edge("tools", "agent")
    return graph.compile()


def _build_legacy_executor(
    llm: BaseChatModel, tools: list[BaseTool], system_prompt: str
) -> Any:
    if initialize_agent is None or AgentType is None:
        logger.warning(
            "LangChain initialize_agent unavailable; falling back to simple executor."
        )
        return _SimpleLLMExecutor(llm, system_prompt=system_prompt)
    logger.info("Using legacy LangChain AgentType executor with %d tools.", len(tools))
    return initialize_agent(
        tools=tools,
        llm=llm,
        agent=AgentType.STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION,
        verbose=True,
    )


def build_price_action_agent(
    llm: BaseChatModel | None = None,
    extra_tools: Iterable[BaseTool] | None = None,
):
    """
    Construct the price-action LangGraph agent with LangSmith instrumentation.
    """

    config = _load_price_action_config()
    system_prompt = config.get("system_prompt", _DEFAULT_PROMPT)

    llm = llm or get_default_llm()

    tools: list[BaseTool] = []
    tools.extend(build_sentiment_tools())

    if os.environ.get("LANGCHAIN_ENABLE_MCP", "true").lower() == "true":
        tools.append(build_mcp_tool())

    if os.environ.get("LANGCHAIN_ENABLE_FS_TOOLS", "true").lower() == "true":
        tools.extend(build_filesystem_tools())

    if extra_tools:
        tools.extend(extra_tools)

    engine = os.environ.get("LANGCHAIN_AGENT_ENGINE", "langgraph").lower()

    bridge = LangSmithAgentBridge(agent_name=config.get("name", "price-action-agent"))

    spec = {
        "name": config.get("name", "price-action-agent"),
        "engine": engine,
        "model": getattr(llm, "model", getattr(llm, "model_name", llm.__class__.__name__)),
        "tool_names": [getattr(tool, "name", repr(tool)) for tool in tools],
        "system_prompt": system_prompt.strip(),
    }
    bridge.record_version(spec)

    if engine == "legacy" or not LANGGRAPH_AVAILABLE:
        logger.info("Initializing legacy agent executor (engine=%s).", engine)
        return _build_legacy_executor(llm, tools, system_prompt=system_prompt)

    logger.info(
        "Initializing LangGraph price action agent with %d tools (engine=%s).",
        len(tools),
        engine,
    )
    graph = _build_langgraph_executor(llm, tools)
    executor = PriceActionAgentExecutor(graph, system_prompt=system_prompt, bridge=bridge)
    return executor

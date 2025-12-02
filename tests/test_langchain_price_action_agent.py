from __future__ import annotations

import pytest
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel

from langchain_agents import agents
from langchain_agents.agents import PriceActionAgentExecutor
from langchain_agents.toolkit import build_filesystem_tools


class StubChatModel(FakeMessagesListChatModel):
    def bind_tools(self, tools):
        return self


def _stub_tool(name: str):
    def _impl() -> str:
        """stub tool"""
        return name

    return StructuredTool.from_function(
        func=_impl,
        name=name,
        description=f"{name} tool",
    )


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch):
    monkeypatch.delenv("LANGSMITH_AGENT_REGISTRY_DATASET", raising=False)
    monkeypatch.delenv("LANGSMITH_AGENT_EVAL_DATASET", raising=False)
    monkeypatch.delenv("LANGSMITH_AGENT_RUN_DATASET", raising=False)
    monkeypatch.setenv("LANGCHAIN_ENABLE_MCP", "false")
    monkeypatch.setenv("LANGCHAIN_ENABLE_FS_TOOLS", "false")
    monkeypatch.setenv("LANGCHAIN_AGENT_ENGINE", "langgraph")


@pytest.fixture
def _patched_tools(monkeypatch):
    monkeypatch.setattr(
        agents,
        "build_sentiment_tools",
        lambda: [_stub_tool("sentiment_query")],
    )
    monkeypatch.setattr(
        agents,
        "build_mcp_tool",
        lambda: _stub_tool("mcp"),
    )
    monkeypatch.setattr(
        agents,
        "build_filesystem_tools",
        lambda: [_stub_tool("workspace_read")],
    )


def test_price_action_agent_uses_langgraph(monkeypatch, _patched_tools):
    fake_llm = StubChatModel(responses=[AIMessage(content="stub output")])
    agent = agents.build_price_action_agent(llm=fake_llm)
    assert isinstance(agent, PriceActionAgentExecutor)

    payload = {"input": "Give me a brief"}
    result = agent.invoke(payload)
    assert result["output"] == "stub output"
    assert "messages" in result


def test_legacy_executor_path(monkeypatch, _patched_tools):
    fake_llm = StubChatModel(responses=[AIMessage(content="legacy response")])
    monkeypatch.setenv("LANGCHAIN_AGENT_ENGINE", "legacy")

    sentinel = object()

    def _fake_initialize(**kwargs):
        return sentinel

    monkeypatch.setattr(agents, "initialize_agent", _fake_initialize)
    monkeypatch.setattr(
        agents,
        "AgentType",
        type("AgentType", (), {"STRUCTURED_CHAT_ZERO_SHOT_REACT_DESCRIPTION": "react"}),
    )
    agent = agents.build_price_action_agent(llm=fake_llm)
    assert agent is sentinel


def test_filesystem_tools_root(tmp_path, monkeypatch):
    root = tmp_path / "fs-root"
    monkeypatch.setenv("LANGCHAIN_AGENT_FS_ROOT", str(root))
    tools = build_filesystem_tools()
    assert root.exists()
    assert {tool.name for tool in tools} == {"list_directory", "read_file", "write_file"}

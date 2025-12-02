from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from langchain_core.tools import BaseTool, StructuredTool
from langchain_community.tools.file_management import (
    ListDirectoryTool,
    ReadFileTool,
    WriteFileTool,
)
from pydantic import BaseModel, Field
from src.rag.sentiment_store import SentimentRAGStore
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover
    from mcp import MCPClient
else:
    MCPClient = Any  # type: ignore[assignment]

logger = logging.getLogger(__name__)


class SentimentQueryInput(BaseModel):
    query: str = Field(..., description="Natural language sentiment query.")
    ticker: str | None = Field(
        default=None,
        description="Optional ticker symbol (e.g., SPY, NVDA) to filter results.",
    )
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of sentiment snapshots to return.",
    )


class SentimentHistoryInput(BaseModel):
    ticker: str = Field(..., description="Ticker symbol (e.g., SPY)")
    limit: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of recent snapshots to return.",
    )


class MCPCallInput(BaseModel):
    server: str = Field(..., description="MCP server identifier.")
    tool: str = Field(..., description="Tool ID on the MCP server.")
    payload: dict = Field(default_factory=dict, description="Tool payload.")


def _format_results(raw_results):
    if not raw_results:
        return "No matching sentiment entries."

    formatted = []
    for entry in raw_results:
        metadata = entry.get("metadata", {})
        formatted.append(
            {
                "id": entry.get("id"),
                "score": entry.get("score"),
                "snapshot_date": metadata.get("snapshot_date"),
                "ticker": metadata.get("ticker"),
                "sentiment_score": metadata.get("sentiment_score"),
                "confidence": metadata.get("confidence"),
                "market_regime": metadata.get("market_regime"),
                "sources": metadata.get("source_list"),
            }
        )

    return json.dumps(formatted, indent=2)


def build_sentiment_tools(
    store: SentimentRAGStore | None = None,
) -> list[StructuredTool]:
    """
    Create LangChain tools that expose the sentiment RAG store.

    Args:
        store: Optional pre-configured SentimentRAGStore (useful for tests)
    """
    sentiment_store = store or SentimentRAGStore()

    def query_sentiment(query: str, ticker: str | None = None, limit: int = 5):
        logger.info("LangChain sentiment query: %s (ticker=%s)", query, ticker)
        results = sentiment_store.query(query=query, ticker=ticker, top_k=limit)
        return _format_results(results)

    def get_history(ticker: str, limit: int = 5):
        logger.info("LangChain sentiment history request: %s, limit=%s", ticker, limit)
        results = sentiment_store.get_ticker_history(ticker=ticker, limit=limit)
        return _format_results(results)

    query_tool = StructuredTool.from_function(
        name="query_sentiment_context",
        description=(
            "Search historical sentiment snapshots (Reddit, news, etc.) using "
            "semantic search. Ideal for qualitative market briefs."
        ),
        func=query_sentiment,
        args_schema=SentimentQueryInput,
    )

    history_tool = StructuredTool.from_function(
        name="get_recent_sentiment_history",
        description=(
            "Fetch the most recent sentiment entries for a ticker. Returns dates, "
            "scores, confidence, and market regime."
        ),
        func=get_history,
        args_schema=SentimentHistoryInput,
    )

    return [query_tool, history_tool]


def build_filesystem_tools(
    root_path: str | os.PathLike[str] | None = None,
    *,
    include_write_tool: bool = True,
) -> list[BaseTool]:
    """
    Provide LangChain file-management tools scoped to an agent workspace.

    The new LangChain "context engineering" patterns rely on agents persisting
    scratch work (notes, intermediate calculations, mini-datasets) to disk.  We
    expose the standard file-management helpers but sandbox them inside a
    configurable directory so the agent cannot wander across the repo.
    """

    base_dir = Path(
        root_path
        or os.environ.get("LANGCHAIN_AGENT_FS_ROOT", ".agent_workspace")
    ).expanduser()
    base_dir.mkdir(parents=True, exist_ok=True)

    tools: list[BaseTool] = [
        ListDirectoryTool(root_dir=str(base_dir)),
        ReadFileTool(root_dir=str(base_dir)),
    ]

    if include_write_tool:
        tools.append(WriteFileTool(root_dir=str(base_dir)))

    return tools


def build_mcp_tool(client: MCPClient | None = None) -> StructuredTool:
    """
    Wrap the MCP client so LangChain agents can call any registered MCP server.

    Args:
        client: Optional MCPClient instance (defaults to shared singleton).
    """
    from mcp import default_client  # local import to avoid heavy deps at import time

    resolved_client = client or default_client()

    def call_mcp(server: str, tool: str, payload: dict) -> str:
        logger.info("LangChain MCP call: %s.%s", server, tool)
        response = resolved_client.call_tool(server=server, tool=tool, payload=payload)
        return json.dumps(response, indent=2)

    return StructuredTool.from_function(
        name="mcp_tool_call",
        description=(
            "Invoke a Model Context Protocol (MCP) tool by specifying the server, "
            "tool name, and JSON payload."
        ),
        func=call_mcp,
        args_schema=MCPCallInput,
    )

"""
MCP (Model Context Protocol) tools integration for deepagents.

Wraps existing MCP client functionality into deepagents-compatible tools.
"""

from __future__ import annotations

import json
import logging

from langchain_core.tools import tool
from mcp import default_client

logger = logging.getLogger(__name__)


@tool
def call_mcp_tool(
    server: str,
    tool_name: str,
    payload: dict,
) -> str:
    """
    Call a tool from an MCP server.

    Args:
        server: MCP server identifier (e.g., 'alpaca-trading', 'trade-agent')
        tool_name: Name of the tool to call on the server
        payload: Dictionary of parameters for the tool

    Returns:
        JSON string with the tool's response
    """
    try:
        mcp_client = default_client()
        response = mcp_client.call_tool(server=server, tool=tool_name, payload=payload)
        return json.dumps(response, indent=2)
    except Exception as e:
        logger.exception(f"Error calling MCP tool {server}.{tool_name}")
        return json.dumps({"error": str(e)})


@tool
def get_mcp_servers() -> str:
    """
    List all available MCP servers and their tools.

    Returns:
        JSON string listing all registered MCP servers and their available tools
    """
    try:
        from mcp.registry import load_registry

        registry = load_registry()
        servers_info = []

        for server_config in registry.servers:
            servers_info.append(
                {
                    "id": server_config["id"],
                    "display_name": server_config.get("display_name", server_config["id"]),
                    "tools": list(server_config.get("tools", {}).keys()),
                }
            )

        return json.dumps({"servers": servers_info}, indent=2)
    except Exception as e:
        logger.exception("Error listing MCP servers")
        return json.dumps({"error": str(e)})


def build_mcp_tools_for_deepagents() -> list:
    """
    Build MCP-related tools for deepagents.

    Returns:
        List of MCP tool objects compatible with deepagents
    """
    return [
        call_mcp_tool,
        get_mcp_servers,
    ]

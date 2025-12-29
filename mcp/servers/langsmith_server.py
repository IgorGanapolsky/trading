#!/usr/bin/env python3
"""
MCP Server for LangSmith Monitoring
Provides MCP tools for monitoring LangSmith traces and runs.
"""

import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Any

# MCP imports
try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
except ImportError:
    print("⚠️  MCP server dependencies not installed")
    Server = None
    stdio_server = None

logger = logging.getLogger(__name__)

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))


async def get_langsmith_runs_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Get recent LangSmith runs."""
    try:
        from .claude.skills.langsmith_monitor.scripts.langsmith_monitor import (
            LangSmithMonitor,
        )

        monitor = LangSmithMonitor()
        project = arguments.get("project", "igor-trading-system")
        hours = arguments.get("hours", 24)
        limit = arguments.get("limit", 50)

        result = monitor.get_recent_runs(project_name=project, hours=hours, limit=limit)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_langsmith_stats_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Get LangSmith project statistics."""
    try:
        from .claude.skills.langsmith_monitor.scripts.langsmith_monitor import (
            LangSmithMonitor,
        )

        monitor = LangSmithMonitor()
        project = arguments.get("project", "igor-trading-system")
        days = arguments.get("days", 7)

        result = monitor.get_project_stats(project_name=project, days=days)

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def check_langsmith_health_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Check LangSmith service health."""
    try:
        from .claude.skills.langsmith_monitor.scripts.langsmith_monitor import (
            LangSmithMonitor,
        )

        monitor = LangSmithMonitor()
        result = monitor.monitor_health()

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


if Server is not None:
    # Create MCP server
    server = Server("langsmith-monitor")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        """List available tools."""
        return [
            Tool(
                name="get_langsmith_runs",
                description="Get recent LangSmith runs for a project",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project name (default: igor-trading-system)",
                        },
                        "hours": {
                            "type": "integer",
                            "description": "Hours of history (default: 24)",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum runs to return (default: 50)",
                        },
                    },
                },
            ),
            Tool(
                name="get_langsmith_stats",
                description="Get LangSmith project statistics",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "project": {
                            "type": "string",
                            "description": "Project name (default: igor-trading-system)",
                        },
                        "days": {
                            "type": "integer",
                            "description": "Days of history (default: 7)",
                        },
                    },
                },
            ),
            Tool(
                name="check_langsmith_health",
                description="Check LangSmith service health and connectivity",
                inputSchema={"type": "object", "properties": {}},
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        """Handle tool calls."""
        if name == "get_langsmith_runs":
            return await get_langsmith_runs_tool(arguments)
        elif name == "get_langsmith_stats":
            return await get_langsmith_stats_tool(arguments)
        elif name == "check_langsmith_health":
            return await check_langsmith_health_tool(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    async def main():
        """Run MCP server."""
        async with stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    if __name__ == "__main__":
        asyncio.run(main())

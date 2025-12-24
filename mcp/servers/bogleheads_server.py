#!/usr/bin/env python3
"""
MCP Server for Bogleheads Forum Learning

Provides MCP tools for monitoring Bogleheads forum and integrating insights.
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
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))


async def monitor_forum_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Monitor Bogleheads forum for new insights."""
    try:
        from claude.skills.bogleheads_learner.scripts.bogleheads_learner import (
            BogleheadsLearner,
        )

        learner = BogleheadsLearner()
        result = learner.monitor_bogleheads_forum(
            topics=arguments.get("topics", ["Personal Investments"]),
            keywords=arguments.get("keywords", ["market timing", "risk"]),
            max_posts=arguments.get("max_posts", 50),
        )

        return [TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def get_signal_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Get Bogleheads trading signal for a symbol."""
    try:
        from src.utils.bogleheads_integration import get_bogleheads_signal_for_symbol

        symbol = arguments.get("symbol", "SPY")
        market_context = arguments.get("market_context", {})

        signal = get_bogleheads_signal_for_symbol(symbol, market_context)

        return [TextContent(type="text", text=json.dumps(signal, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


async def analyze_regime_tool(arguments: dict[str, Any]) -> list[TextContent]:
    """Analyze market regime from Bogleheads discussions."""
    try:
        from src.utils.bogleheads_integration import get_bogleheads_regime

        regime = get_bogleheads_regime()

        return [TextContent(type="text", text=json.dumps(regime, indent=2))]
    except Exception as e:
        return [TextContent(type="text", text=f"Error: {str(e)}")]


def create_server() -> Server | None:
    """Create MCP server with Bogleheads tools."""
    if not Server:
        return None

    server = Server("bogleheads-learner")

    @server.list_tools()
    async def list_tools() -> list[Tool]:
        return [
            Tool(
                name="monitor_bogleheads_forum",
                description="Monitor Bogleheads forum for new investing insights",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Forum topics to monitor",
                        },
                        "keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords to filter posts",
                        },
                        "max_posts": {
                            "type": "integer",
                            "description": "Maximum posts to analyze",
                        },
                    },
                },
            ),
            Tool(
                name="get_bogleheads_signal",
                description="Get trading signal based on Bogleheads forum wisdom",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "symbol": {
                            "type": "string",
                            "description": "Symbol to analyze",
                        },
                        "market_context": {
                            "type": "object",
                            "description": "Current market context",
                        },
                    },
                    "required": ["symbol"],
                },
            ),
            Tool(
                name="analyze_bogleheads_regime",
                description="Analyze market regime from Bogleheads discussions",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "timeframe": {
                            "type": "string",
                            "description": "Timeframe to analyze",
                        }
                    },
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[TextContent]:
        if name == "monitor_bogleheads_forum":
            return await monitor_forum_tool(arguments)
        elif name == "get_bogleheads_signal":
            return await get_signal_tool(arguments)
        elif name == "analyze_bogleheads_regime":
            return await analyze_regime_tool(arguments)
        else:
            raise ValueError(f"Unknown tool: {name}")

    return server


async def main():
    """Run MCP server."""
    server = create_server()
    if not server:
        logger.error("MCP server not available")
        return

    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())

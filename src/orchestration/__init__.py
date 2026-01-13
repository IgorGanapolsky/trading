"""
Orchestration module - High-level trading orchestration implementations.

This module contains specialized orchestrators for different trading workflows:
- MCPTradingOrchestrator: Model Context Protocol based trading
- ADK: Go Agent Development Kit integration

Note: This is distinct from src/orchestrator/ which provides the CLI entrypoint
and hybrid funnel pipeline. Both modules may be used together.
"""

__all__ = ["mcp_trading", "adk_client", "adk_integration"]

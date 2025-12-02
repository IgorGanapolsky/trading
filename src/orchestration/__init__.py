"""
Orchestration module - High-level trading orchestration implementations.

This module contains specialized orchestrators for different trading workflows:
- EliteOrchestrator: Main production orchestrator with MCP/ADK integration
- MCPTradingOrchestrator: Model Context Protocol based trading
- WorkflowOrchestrator: Workflow-based trade execution
- DeepAgents: Planning-based trading cycles
- ADK: Go Agent Development Kit integration

Note: This is distinct from src/orchestrator/ which provides the CLI entrypoint
and hybrid funnel pipeline. Both modules may be used together.
"""

__all__ = ["mcp_trading", "adk_client", "adk_integration", "elite_orchestrator"]

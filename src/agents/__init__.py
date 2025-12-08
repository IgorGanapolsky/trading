"""
Multi-Agent AI Trading System (2025 Standard)

Architecture inspired by:
- AlphaQuanter: Tool-orchestrated agentic RL framework
- P1GPT: Multi-agent LLM for multi-modal financial analysis
- Hi-DARTS: Hierarchical meta-agent coordination
- Trading-R1: LLM reasoning with reinforcement learning

Agents:
- MetaAgent: Coordinates all agents, adapts to market volatility
- ResearchAgent: Analyzes fundamentals, news, sentiment
- SignalAgent: Technical analysis + LLM reasoning
- RiskAgent: Portfolio risk, position sizing, stop-loss
- ExecutionAgent: Order execution, timing optimization
"""

__version__ = "2.0.0"
__all__ = [
    "MetaAgent",
    "ResearchAgent",
    "SignalAgent",
    "RiskAgent",
    "ExecutionAgent",
    "WorkflowAgent",
    "ApprovalAgent",
    "NotificationAgent",
    # Programmatic Tool Calling (PTC) - Anthropic advanced tool use
    "PTCOrchestrator",
    "PTCMetaAgent",
    "execute_ptc_trade",
    # OpenThinker Agent - Local reasoning specialist
    "OpenThinkerAgent",
    "create_openthinker_agent",
]

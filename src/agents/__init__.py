"""
Introspective Multi-Agent Trading System

This package implements a multi-agent architecture for trading decisions
with introspection capabilities at each step.

Agents:
    - ResearchAgent: Market analysis & sentiment with bias detection
    - SignalAgent: Entry/exit signals with indicator consensus
    - RiskAgent: Position sizing & safety with circuit breakers
    - ExecutionAgent: Order management with pre-flight validation
    - MasterOrchestrator: Coordinates all agents with final review

Author: Trading System
Created: 2025-11-03
"""

from src.agents.research_agent import ResearchAgent
from src.agents.signal_agent import SignalAgent
from src.agents.risk_agent import RiskAgent
from src.agents.execution_agent import ExecutionAgent
from src.agents.master_orchestrator import MasterOrchestrator

__all__ = [
    "ResearchAgent",
    "SignalAgent",
    "RiskAgent",
    "ExecutionAgent",
    "MasterOrchestrator",
]

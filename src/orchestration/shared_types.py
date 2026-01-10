"""
Shared Types for Orchestration

This module contains common type definitions used across orchestration modules
to avoid duplication and maintain consistency.

Extracted from:
- src/orchestration/elite_orchestrator.py
- src/orchestration/adaptive_orchestrator.py
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class PlanningPhase(Enum):
    """
    Planning phases for agentic trading flows.

    Represents the distinct stages in a trading cycle:
    - INITIALIZE: Setup and validation
    - DATA_COLLECTION: Gather market data from multiple sources
    - ANALYSIS: Multi-agent analysis and signal generation
    - RISK_ASSESSMENT: Risk validation and position sizing
    - EXECUTION: Trade execution and monitoring
    - AUDIT: Post-trade review and logging
    """

    INITIALIZE = "initialize"
    DATA_COLLECTION = "data_collection"
    ANALYSIS = "analysis"
    RISK_ASSESSMENT = "risk_assessment"
    EXECUTION = "execution"
    AUDIT = "audit"


class AgentType(Enum):
    """
    Agent types available in the multi-agent trading system.

    Represents different agent frameworks and their specializations:
    - CLAUDE_SKILLS: Claude Skills for core trading operations
    - GEMINI: Gemini agents for research and long-horizon planning
    - GO_ADK: Go ADK agents for high-speed execution
    - MCP: MCP orchestrator for multi-agent coordination
    - ML_MODEL: Machine learning models (LSTM, PPO, ensemble RL)
    """

    CLAUDE_SKILLS = "claude_skills"
    GEMINI = "gemini"
    GO_ADK = "go_adk"
    MCP = "mcp"
    ML_MODEL = "ml_model"


@dataclass
class TradePlan:
    """
    Planning-first trade plan with explicit phases and agent assignments.

    Represents a complete trading plan with:
    - Unique identification and timestamps
    - Target symbols for trading
    - Phase-by-phase execution plan with agent assignments
    - Decision tracking and context storage
    - Execution status

    Attributes:
        plan_id: Unique identifier for this plan
        timestamp: ISO format timestamp when plan was created
        symbols: List of trading symbols (e.g., ["SPY", "QQQ"])
        phases: Dictionary mapping phase names to phase configurations
        decisions: List of decisions made during plan execution
        context: Additional context data (complexity, regime, etc.)
        status: Current status of plan (planning, executing, completed, halted)
        git_commit: Optional git commit hash for audit trail
    """

    plan_id: str
    timestamp: str
    symbols: list[str]
    phases: dict[str, dict[str, Any]] = field(default_factory=dict)
    decisions: list[dict[str, Any]] = field(default_factory=list)
    context: dict[str, Any] = field(default_factory=dict)
    status: str = "planning"
    git_commit: str | None = None

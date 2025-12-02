"""
Semantic Blueprints for Trading Agents

Defines structured context for each agent in the multi-agent trading system.
These blueprints move beyond simple prompts to structured definitions of:
- Agent roles and responsibilities
- Input/output schemas
- Communication protocols
- Dependencies between agents
"""

import logging

from src.agent_framework.context_engine import (
    ContextPriority,
    SemanticBlueprint,
    get_context_engine,
)

logger = logging.getLogger(__name__)


def register_trading_agent_blueprints():
    """
    Register semantic blueprints for all trading agents.

    This function should be called during system initialization to ensure
    all agents have structured context definitions.
    """
    engine = get_context_engine()

    # Research Agent Blueprint
    research_blueprint = SemanticBlueprint(
        agent_id="research_agent",
        agent_name="Research Agent",
        role="Market Research Specialist",
        description=(
            "Analyzes company fundamentals, market microstructure, news sentiment, "
            "and alternative data sources to provide comprehensive market context."
        ),
        capabilities=[
            "Fundamental analysis (P/E, growth, margins)",
            "News sentiment analysis",
            "Social media signal processing",
            "Alternative data integration",
            "Market regime detection",
        ],
        inputs={
            "symbol": {
                "type": "string",
                "required": True,
                "description": "Stock symbol to research",
            },
            "timeframe": {
                "type": "string",
                "required": False,
                "default": "1Day",
                "description": "Data timeframe",
            },
            "include_sentiment": {
                "type": "boolean",
                "required": False,
                "default": True,
                "description": "Include sentiment analysis",
            },
        },
        outputs={
            "market_regime": {
                "type": "string",
                "description": "Detected market regime (bullish, bearish, range-bound)",
            },
            "narrative": {
                "type": "string",
                "description": "Two-sentence market narrative",
            },
            "supporting_metrics": {
                "type": "object",
                "description": "Key metrics supporting the analysis",
            },
            "sentiment_score": {
                "type": "float",
                "description": "Sentiment score (-1 to 1)",
            },
            "confidence": {
                "type": "float",
                "description": "Confidence in analysis (0 to 1)",
            },
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "research_result",
            "async": False,
        },
        dependencies=[],
        context_window_size=4000,
        priority=ContextPriority.HIGH,
    )
    engine.register_blueprint(research_blueprint)

    # Signal Agent Blueprint
    signal_blueprint = SemanticBlueprint(
        agent_id="signal_agent",
        agent_name="Signal Agent",
        role="Trading Signal Generator",
        description=(
            "Generates directional trade hypotheses with entry/exit targets based on "
            "technical analysis, momentum indicators, and pattern recognition."
        ),
        capabilities=[
            "Technical indicator calculation (MACD, RSI, Volume)",
            "Momentum scoring",
            "Pattern recognition",
            "Entry quality assessment",
            "Exit target calculation",
        ],
        inputs={
            "research_data": {
                "type": "object",
                "required": True,
                "description": "Output from research_agent",
            },
            "price_history": {
                "type": "dataframe",
                "required": True,
                "description": "Historical price data",
            },
            "market_features": {
                "type": "object",
                "required": False,
                "description": "Computed market features",
            },
        },
        outputs={
            "action": {
                "type": "string",
                "enum": ["BUY", "SELL", "HOLD"],
                "description": "Recommended action",
            },
            "conviction": {"type": "float", "description": "Conviction score (0 to 1)"},
            "entry_window": {"type": "object", "description": "Price range for entry"},
            "exit_plan": {
                "type": "object",
                "description": "Target prices and stop-loss",
            },
            "reasoning": {"type": "string", "description": "Explanation of signal"},
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "trading_signal",
            "async": False,
        },
        dependencies=["research_agent"],
        context_window_size=3000,
        priority=ContextPriority.CRITICAL,
    )
    engine.register_blueprint(signal_blueprint)

    # Risk Agent Blueprint
    risk_blueprint = SemanticBlueprint(
        agent_id="risk_agent",
        agent_name="Risk Agent",
        role="Risk Management Specialist",
        description=(
            "Applies portfolio risk guardrails, position sizing heuristics, and "
            "validates trades against risk limits before execution."
        ),
        capabilities=[
            "Portfolio risk assessment",
            "Position sizing (Kelly Criterion)",
            "Stop-loss calculation",
            "Circuit breaker checks",
            "Volatility-adjusted allocations",
        ],
        inputs={
            "signal": {
                "type": "object",
                "required": True,
                "description": "Output from signal_agent",
            },
            "portfolio_value": {
                "type": "float",
                "required": True,
                "description": "Current portfolio value",
            },
            "volatility": {
                "type": "float",
                "required": False,
                "description": "Asset volatility",
            },
            "historical_win_rate": {
                "type": "float",
                "required": False,
                "default": 0.60,
                "description": "Historical win rate",
            },
        },
        outputs={
            "decision": {
                "type": "string",
                "enum": ["APPROVE", "REVIEW", "REJECT"],
                "description": "Risk decision",
            },
            "position_size": {
                "type": "float",
                "description": "Calculated position size",
            },
            "stop_loss": {"type": "float", "description": "Stop-loss price"},
            "rationale": {"type": "string", "description": "Risk assessment rationale"},
            "risk_metrics": {"type": "object", "description": "Detailed risk metrics"},
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "risk_assessment",
            "async": False,
        },
        dependencies=["signal_agent"],
        context_window_size=2000,
        priority=ContextPriority.CRITICAL,
    )
    engine.register_blueprint(risk_blueprint)

    # Execution Agent Blueprint
    execution_blueprint = SemanticBlueprint(
        agent_id="execution_agent",
        agent_name="Execution Agent",
        role="Trade Execution Specialist",
        description=(
            "Prepares execution checklist, optimizes order placement, monitors "
            "execution quality, and records trade decisions."
        ),
        capabilities=[
            "Order type selection",
            "Execution timing optimization",
            "Anomaly detection",
            "Trade logging",
            "Execution monitoring",
        ],
        inputs={
            "risk_assessment": {
                "type": "object",
                "required": True,
                "description": "Output from risk_agent",
            },
            "market_conditions": {
                "type": "object",
                "required": True,
                "description": "Current market conditions",
            },
            "symbol": {
                "type": "string",
                "required": True,
                "description": "Symbol to trade",
            },
            "action": {
                "type": "string",
                "required": True,
                "enum": ["BUY", "SELL"],
                "description": "Trade action",
            },
        },
        outputs={
            "venue_preference": {
                "type": "string",
                "description": "Preferred execution venue",
            },
            "order_type": {"type": "string", "description": "Recommended order type"},
            "timing_notes": {"type": "string", "description": "Timing recommendations"},
            "execution_plan": {
                "type": "object",
                "description": "Detailed execution plan",
            },
            "logging_status": {
                "type": "string",
                "description": "Status of trade logging",
            },
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "execution_plan",
            "async": True,
        },
        dependencies=["risk_agent", "signal_agent"],
        context_window_size=2000,
        priority=ContextPriority.HIGH,
    )
    engine.register_blueprint(execution_blueprint)

    # Meta Agent Blueprint
    meta_blueprint = SemanticBlueprint(
        agent_id="meta_agent",
        agent_name="Meta Agent",
        role="Multi-Agent Coordinator",
        description=(
            "Coordinates specialized agents, synthesizes their outputs, and "
            "makes final trading decisions. Detects market regimes and weights "
            "agent recommendations dynamically."
        ),
        capabilities=[
            "Market regime detection",
            "Agent coordination",
            "Dynamic recommendation weighting",
            "Decision synthesis",
            "Workflow orchestration",
        ],
        inputs={
            "symbol": {
                "type": "string",
                "required": True,
                "description": "Symbol to analyze",
            },
            "market_payload": {
                "type": "object",
                "required": True,
                "description": "Complete market context",
            },
        },
        outputs={
            "coordinated_decision": {
                "type": "object",
                "description": "Final coordinated decision",
            },
            "market_regime": {
                "type": "string",
                "description": "Detected market regime",
            },
            "agent_weights": {
                "type": "object",
                "description": "Weights assigned to each agent",
            },
            "confidence": {"type": "float", "description": "Overall confidence"},
            "reasoning": {"type": "string", "description": "Decision reasoning"},
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "coordinated_decision",
            "async": False,
        },
        dependencies=[
            "research_agent",
            "signal_agent",
            "risk_agent",
            "execution_agent",
        ],
        context_window_size=10000,
        priority=ContextPriority.CRITICAL,
    )
    engine.register_blueprint(meta_blueprint)

    # Gemini Agent Blueprint
    gemini_blueprint = SemanticBlueprint(
        agent_id="gemini_agent",
        agent_name="Gemini Agent",
        role="Long-Horizon Research Specialist",
        description=(
            "Provides long-term research analysis, fundamental evaluation, "
            "and portfolio fit assessment using Gemini's reasoning capabilities."
        ),
        capabilities=[
            "Long-horizon planning",
            "Fundamental analysis",
            "Portfolio fit assessment",
            "Trend analysis",
            "Multi-modal reasoning",
        ],
        inputs={
            "symbol": {
                "type": "string",
                "required": True,
                "description": "Symbol to analyze",
            },
            "research_prompt": {
                "type": "string",
                "required": True,
                "description": "Research query",
            },
            "context": {
                "type": "object",
                "required": False,
                "description": "Additional context",
            },
        },
        outputs={
            "decision": {
                "type": "string",
                "enum": ["BUY", "SELL", "HOLD"],
                "description": "Recommendation",
            },
            "reasoning": {"type": "string", "description": "Detailed reasoning"},
            "confidence": {"type": "float", "description": "Confidence score"},
            "time_horizon": {
                "type": "string",
                "description": "Recommended time horizon",
            },
        },
        communication_protocol={
            "format": "MCP",
            "message_schema": "research_result",
            "async": False,
        },
        dependencies=[],
        context_window_size=8000,
        priority=ContextPriority.HIGH,
    )
    engine.register_blueprint(gemini_blueprint)

    # Langchain Agent Blueprint
    langchain_blueprint = SemanticBlueprint(
        agent_id="langchain_agent",
        agent_name="Langchain Agent",
        role="RAG and Multi-Modal Fusion Specialist",
        description=(
            "Uses Retrieval-Augmented Generation (RAG) to access knowledge base, "
            "processes multi-modal data, and provides validated trading signals."
        ),
        capabilities=[
            "RAG-based knowledge retrieval",
            "Multi-modal data fusion",
            "Sentiment analysis",
            "Price action validation",
            "News integration",
        ],
        inputs={
            "input": {
                "type": "string",
                "required": True,
                "description": "Query or prompt",
            },
            "symbol": {
                "type": "string",
                "required": False,
                "description": "Symbol context",
            },
        },
        outputs={
            "response": {"type": "string", "description": "Agent response"},
            "sources": {"type": "array", "description": "Information sources used"},
            "confidence": {"type": "float", "description": "Confidence in response"},
        },
        communication_protocol={
            "format": "LangChain",
            "message_schema": "agent_response",
            "async": False,
        },
        dependencies=[],
        context_window_size=6000,
        priority=ContextPriority.MEDIUM,
    )
    engine.register_blueprint(langchain_blueprint)

    logger.info("✅ Registered semantic blueprints for all trading agents")

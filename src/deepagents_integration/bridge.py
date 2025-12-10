"""
Bridge between deepagents and existing agent framework.

This module provides adapters to use deepagents alongside the existing
TradingAgent framework, allowing gradual migration and hybrid approaches.
"""

from __future__ import annotations

import logging
from typing import Any

from src.agent_framework import AgentResult, RunContext, TradingAgent

logger = logging.getLogger(__name__)


class DeepAgentsTradingAgent(TradingAgent):
    """
    Adapter that wraps a deepagent as a TradingAgent.

    This allows deepagents to be used within the existing agent framework
    while maintaining compatibility with the orchestrator.
    """

    def __init__(
        self,
        agent_name: str,
        deepagent: Any,
        task_prompt_template: str | None = None,
    ) -> None:
        """
        Initialize adapter.

        Args:
            agent_name: Name for the agent
            deepagent: DeepAgent instance from create_deep_agent
            task_prompt_template:  template for converting context to prompt
        """
        super().__init__(agent_name)
        self.deepagent = deepagent
        self.task_prompt_template = task_prompt_template or (
            "Analyze the following trading context and provide recommendations:\n\n"
            "{context_summary}\n\n"
            "Provide a structured analysis with actionable insights."
        )

    def execute(self, context: RunContext) -> AgentResult:
        """
        Execute deepagent within the TradingAgent framework.

        Args:
            context: Run context with market data and configuration

        Returns:
            AgentResult with deepagent's analysis
        """
        try:
            # Extract relevant context
            market_data = context.state_cache.get("market_data", {})
            config = context.config.data

            # Build prompt from context
            context_summary = self._build_context_summary(market_data, config)
            prompt = self.task_prompt_template.format(context_summary=context_summary)

            # Invoke deepagent (sync version)
            result = self.deepagent.invoke({"messages": [{"role": "user", "content": prompt}]})

            # Extract response
            response_text = self._extract_response(result)

            # Convert to AgentResult
            return AgentResult(
                name=self.agent_name,
                succeeded=True,
                payload={
                    "analysis": response_text,
                    "raw_result": result,
                    "context_used": context_summary,
                },
            )
        except Exception as exc:
            logger.exception(f"DeepAgent {self.agent_name} failed")
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                error=str(exc),
            )

    def _build_context_summary(self, market_data: dict, config: dict) -> str:
        """Build a summary of context for the deepagent."""
        summary_parts = []

        if market_data:
            symbols = list(market_data.get("frames", {}).keys())
            if symbols:
                summary_parts.append(f"Symbols analyzed: {', '.join(symbols)}")

        if config:
            summary_parts.append(f"Configuration: {config}")

        return "\n".join(summary_parts) if summary_parts else "No specific context provided."

    def _extract_response(self, result: Any) -> str:
        """Extract text response from deepagent result."""
        if isinstance(result, dict) and "messages" in result:
            messages = result["messages"]
            if messages:
                last_message = messages[-1]
                if hasattr(last_message, "content"):
                    return str(last_message.content)
                elif isinstance(last_message, dict) and "content" in last_message:
                    return str(last_message["content"])

        return str(result)


class HybridTradingAgent(TradingAgent):
    """
    Hybrid agent that uses both deepagents and traditional logic.

    Can delegate complex research to deepagents while using
    rule-based logic for execution-critical decisions.
    """

    def __init__(
        self,
        agent_name: str,
        deepagent: Any | None = None,
        fallback_agent: TradingAgent | None = None,
    ) -> None:
        """
        Initialize hybrid agent.

        Args:
            agent_name: Name for the agent
            deepagent:  deepagent for complex analysis
            fallback_agent: Fallback agent if deepagent unavailable
        """
        super().__init__(agent_name)
        self.deepagent = deepagent
        self.fallback_agent = fallback_agent

    def execute(self, context: RunContext) -> AgentResult:
        """
        Execute with deepagent if available, otherwise use fallback.

        Args:
            context: Run context

        Returns:
            AgentResult from deepagent or fallback
        """
        if self.deepagent:
            try:
                adapter = DeepAgentsTradingAgent(
                    agent_name=f"{self.agent_name}_deep",
                    deepagent=self.deepagent,
                )
                return adapter.execute(context)
            except Exception as exc:
                logger.warning(f"Deepagent failed, using fallback: {exc}")

        if self.fallback_agent:
            return self.fallback_agent.execute(context)

        return AgentResult(
            name=self.agent_name,
            succeeded=False,
            error="No agent available (deepagent failed and no fallback)",
        )


def create_deepagents_research_agent() -> DeepAgentsTradingAgent:
    """
    Factory function to create a research agent using deepagents.

    Returns:
        DeepAgentsTradingAgent configured for research
    """
    from .agents import create_trading_research_agent

    deepagent = create_trading_research_agent()
    return DeepAgentsTradingAgent(
        agent_name="deepagents-research",
        deepagent=deepagent,
        task_prompt_template=(
            "Conduct comprehensive research based on the following context:\n\n"
            "{context_summary}\n\n"
            "Provide:\n"
            "1. Market analysis\n"
            "2. Sentiment assessment\n"
            "3. Technical indicators\n"
            "4. Risk factors\n"
            "5. Investment recommendation"
        ),
    )


def create_hybrid_analysis_agent(
    fallback_agent: TradingAgent | None = None,
) -> HybridTradingAgent:
    """
    Factory function to create a hybrid analysis agent.

    Args:
        fallback_agent:  fallback agent

    Returns:
        HybridTradingAgent with deepagent and fallback
    """
    from .agents import create_market_analysis_agent

    try:
        deepagent = create_market_analysis_agent()
    except Exception as exc:
        logger.warning(f"Failed to create deepagent: {exc}")
        deepagent = None

    return HybridTradingAgent(
        agent_name="hybrid-analysis",
        deepagent=deepagent,
        fallback_agent=fallback_agent,
    )

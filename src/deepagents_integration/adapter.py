"""
Adapter to integrate deepagents with existing agent framework.

This allows deepagents to be used alongside existing TradingAgent implementations.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.agent_framework import AgentResult, RunContext, TradingAgent

logger = logging.getLogger(__name__)


class DeepAgentsAdapter(TradingAgent):
    """
    Adapter that wraps a deepagent as a TradingAgent.

    This allows deepagents to be used in the existing orchestration system
    alongside traditional TradingAgent implementations.
    """

    def __init__(
        self,
        agent_name: str,
        deepagent: Any,
        system_prompt: str | None = None,
    ) -> None:
        """
        Initialize adapter.

        Args:
            agent_name: Name for the agent (used in AgentResult)
            deepagent: Pre-configured deepagent instance
            system_prompt: Optional system prompt override
        """
        super().__init__(agent_name)
        self.deepagent = deepagent
        self.system_prompt = system_prompt

    def execute(self, context: RunContext) -> AgentResult:
        """
        Execute the deepagent as a TradingAgent.

        Args:
            context: Run context with configuration and state

        Returns:
            AgentResult with deepagent output
        """
        try:
            # Extract query from context
            query = self._extract_query(context)

            # Run deepagent (sync wrapper for async agent)
            result = asyncio.run(self._run_deepagent(query))

            # Convert to AgentResult
            return AgentResult(
                name=self.agent_name,
                succeeded=True,
                payload={
                    "query": query,
                    "response": result,
                    "messages": (result.get("messages", []) if isinstance(result, dict) else []),
                },
            )
        except Exception as e:
            logger.exception(f"DeepAgentsAdapter {self.agent_name} failed")
            return AgentResult(
                name=self.agent_name,
                succeeded=False,
                error=str(e),
            )

    def _extract_query(self, context: RunContext) -> str:
        """Extract query from context."""
        # Try multiple sources
        query = context.config.get("query")
        if query:
            return str(query)

        query = context.config.get("task")
        if query:
            return str(query)

        # Default query
        symbols = context.config.get("symbols", ["SPY"])
        symbol = symbols[0] if symbols else "SPY"
        return f"Analyze {symbol} and provide trading recommendation"

    async def _run_deepagent(self, query: str) -> dict[str, Any]:
        """Run the deepagent with a query."""
        try:
            result = await self.deepagent.ainvoke(
                {"messages": [{"role": "user", "content": query}]}
            )
            return result
        except Exception:
            logger.exception("Error running deepagent")
            raise


def create_research_agent_adapter(
    agent_name: str = "deepagents-research",
    **kwargs: Any,
) -> DeepAgentsAdapter:
    """
    Create a TradingAgent adapter for the research deepagent.

    Args:
        agent_name: Name for the agent
        **kwargs: Additional arguments passed to create_trading_research_agent

    Returns:
        DeepAgentsAdapter instance
    """
    from .agents import create_trading_research_agent

    deepagent = create_trading_research_agent(**kwargs)
    return DeepAgentsAdapter(agent_name=agent_name, deepagent=deepagent)


def create_analysis_agent_adapter(
    agent_name: str = "deepagents-analysis",
    **kwargs: Any,
) -> DeepAgentsAdapter:
    """
    Create a TradingAgent adapter for the analysis deepagent.

    Args:
        agent_name: Name for the agent
        **kwargs: Additional arguments passed to create_market_analysis_agent

    Returns:
        DeepAgentsAdapter instance
    """
    from .agents import create_market_analysis_agent

    deepagent = create_market_analysis_agent(**kwargs)
    return DeepAgentsAdapter(agent_name=agent_name, deepagent=deepagent)

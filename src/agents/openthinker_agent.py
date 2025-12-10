"""
OpenThinker Agent - Reasoning specialist for trading decisions.

Uses OpenThinker models (open-thoughts/OpenThinker-Agent-v1) for deep reasoning
on complex trading decisions. Integrates with the LLM Council as a reasoning
specialist.

Key capabilities:
- Multi-step mathematical reasoning (position sizing, risk calculations)
- Complex decision analysis (trade evaluation)
- Extended thinking chains for thorough analysis
- Local inference (no API costs)

Reference: https://github.com/open-thoughts/OpenThoughts-Agent
"""

import asyncio
import logging
from typing import Any

from src.agents.base_agent import BaseAgent
from src.core.local_llm import (
    LocalLLMBackend,
    LocalModel,
    OpenThinkerReasoner,
)

logger = logging.getLogger(__name__)


class OpenThinkerAgent(BaseAgent):
    """
    OpenThinker-based trading agent for deep reasoning analysis.

    Specializes in:
    - Complex multi-step trading decisions
    - Mathematical calculations (Kelly Criterion, position sizing)
    - Risk analysis with explicit reasoning chains
    - Contrarian viewpoint (devil's advocate role in Council)
    """

    def __init__(
        self,
        model: LocalModel = LocalModel.OPENTHINKER_7B,
        backend: LocalLLMBackend = LocalLLMBackend.OLLAMA,
        base_url: str | None = None,
        name: str = "OpenThinkerAgent",
        role: str = "Reasoning Specialist",
    ):
        """
        Initialize OpenThinker Agent.

        Args:
            model: OpenThinker model variant (7B or 32B)
            backend: Local LLM backend (ollama or vllm)
            base_url: Optional custom endpoint URL
            name: Agent name for logging
            role: Agent role description
        """
        super().__init__(
            name=name,
            role=role,
            model=model.value,
            use_context_engine=True,
        )

        self.reasoner = OpenThinkerReasoner(
            model=model,
            backend=backend,
            base_url=base_url,
        )
        self.local_model = model
        self.backend = backend
        self._available: bool | None = None

        logger.info(f"Initialized OpenThinkerAgent: model={model.value}, backend={backend.value}")

    async def check_availability(self) -> bool:
        """Check if OpenThinker is available for inference."""
        self._available = await self.reasoner.is_available()
        if not self._available:
            logger.warning(
                f"OpenThinker ({self.local_model.value}) not available. "
                "Install with: ollama pull openthinker:7b"
            )
        return self._available

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Synchronous analysis interface (required by BaseAgent).

        For async analysis, use analyze_async() instead.

        Args:
            data: Input data for analysis

        Returns:
            Analysis results
        """
        # Run async analysis in event loop
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Create task if loop is already running
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(asyncio.run, self.analyze_async(data))
                    return future.result()
            else:
                return loop.run_until_complete(self.analyze_async(data))
        except RuntimeError:
            # No event loop, create one
            return asyncio.run(self.analyze_async(data))

    async def analyze_async(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Async analysis using OpenThinker reasoning.

        Args:
            data: Input data containing:
                - query: The question to analyze
                - symbol: Optional stock symbol
                - market_data: Optional market data
                - context: Optional additional context

        Returns:
            Analysis results with reasoning chain
        """
        # Check availability
        if self._available is None:
            await self.check_availability()

        if not self._available:
            return {
                "success": False,
                "error": "OpenThinker not available",
                "reasoning": "",
                "decision": "HOLD",
                "confidence": 0.0,
            }

        query = data.get("query", "")
        symbol = data.get("symbol")
        market_data = data.get("market_data", {})
        context = data.get("context", {})

        # Add symbol and market data to context
        if symbol:
            context["symbol"] = symbol
        if market_data:
            context["market_data"] = market_data

        result = await self.reasoner.reason(query, context)

        # Log decision for audit trail
        if result.get("success"):
            self.log_decision(
                {
                    "action": result.get("decision", "HOLD"),
                    "confidence": result.get("confidence", 0.0),
                    "model": self.local_model.value,
                    "query": query[:100],  # Truncate for log
                }
            )

        return result

    async def validate_trade(
        self,
        symbol: str,
        action: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Validate a trading decision using deep reasoning.

        Used as a contrarian voice in the LLM Council - specifically
        looks for reasons to REJECT trades.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL)
            market_data: Current market data
            context: Additional context

        Returns:
            Validation result with approval/rejection and reasoning
        """
        if self._available is None:
            await self.check_availability()

        if not self._available:
            return {
                "approved": True,  # Fail-open
                "confidence": 0.0,
                "reasoning": "OpenThinker unavailable - defaulting to approve",
                "concerns": [],
            }

        # Devil's advocate prompt - look for reasons to reject
        query = f"""As a contrarian analyst, critically evaluate this trade proposal.

Symbol: {symbol}
Proposed Action: {action}

Market Data:
{_format_dict(market_data)}

Your role is to find flaws and risks in this trade. Consider:
1. What could go wrong with this trade?
2. Are there hidden risks not accounted for?
3. Is the timing appropriate given market conditions?
4. Does this trade align with sound risk management?
5. What would make you reject this trade?

Be thorough and skeptical. If you find significant concerns, REJECT the trade.
Only APPROVE if you cannot find meaningful objections.

Provide:
- DECISION: APPROVE or REJECT
- CONFIDENCE: 0.0 to 1.0
- CONCERNS: List of specific risks or issues
- REASONING: Detailed analysis"""

        full_context = {"symbol": symbol, "action": action, "market_data": market_data}
        if context:
            full_context.update(context)

        result = await self.reasoner.reason(query, full_context)

        # Parse approval from decision
        decision = result.get("decision", "HOLD")
        approved = decision not in ["REJECT", "SELL"]

        return {
            "approved": approved,
            "confidence": result.get("confidence", 0.5),
            "reasoning": result.get("reasoning", ""),
            "concerns": result.get("risks", []),
            "thinking": result.get("thinking"),
            "latency": result.get("latency", 0),
        }

    async def calculate_position_size(
        self,
        symbol: str,
        account_value: float,
        entry_price: float,
        stop_loss: float,
        risk_pct: float = 0.02,
    ) -> dict[str, Any]:
        """
        Calculate optimal position size using mathematical reasoning.

        Args:
            symbol: Stock symbol
            account_value: Total account value
            entry_price: Planned entry price
            stop_loss: Stop loss price
            risk_pct: Maximum risk per trade (default 2%)

        Returns:
            Position sizing with calculations shown
        """
        return await self.reasoner.calculate_position_size(
            symbol=symbol,
            account_value=account_value,
            risk_per_trade=risk_pct,
            entry_price=entry_price,
            stop_loss=stop_loss,
        )

    async def analyze_trade(
        self,
        symbol: str,
        action: str,
        market_data: dict[str, Any],
        portfolio_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Analyze a trade proposal with full reasoning chain.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL)
            market_data: Current market data
            portfolio_context: Portfolio information

        Returns:
            Detailed analysis with reasoning
        """
        return await self.reasoner.analyze_trade(
            symbol=symbol,
            action=action,
            market_data=market_data,
            portfolio_context=portfolio_context,
        )

    async def council_opinion(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Provide opinion for LLM Council deliberation.

        This method is called by the TradingCouncil to get OpenThinker's
        input during multi-model consensus.

        Args:
            query: The trading question
            context: Trading context

        Returns:
            Opinion with reasoning for council
        """
        if self._available is None:
            await self.check_availability()

        if not self._available:
            return {
                "success": False,
                "opinion": "",
                "confidence": 0.0,
                "model": self.local_model.value,
                "available": False,
            }

        result = await self.reasoner.reason(query, context)

        return {
            "success": result.get("success", False),
            "opinion": result.get("reasoning", ""),
            "decision": result.get("decision", "HOLD"),
            "confidence": result.get("confidence", 0.5),
            "key_factors": result.get("key_factors", []),
            "risks": result.get("risks", []),
            "thinking": result.get("thinking"),
            "model": self.local_model.value,
            "latency": result.get("latency", 0),
            "available": True,
        }

    async def close(self):
        """Close the agent and release resources."""
        await self.reasoner.close()
        logger.info("OpenThinkerAgent closed")


def _format_dict(d: dict[str, Any]) -> str:
    """Format dictionary for prompt."""
    lines = []
    for key, value in d.items():
        if isinstance(value, float):
            lines.append(f"- {key}: {value:.4f}")
        else:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


# Factory function for easy creation
async def create_openthinker_agent(
    model: LocalModel = LocalModel.OPENTHINKER_7B,
    check_availability: bool = True,
) -> OpenThinkerAgent:
    """
    Create and initialize an OpenThinker agent.

    Args:
        model: OpenThinker model variant
        check_availability: Check if model is available

    Returns:
        Initialized OpenThinkerAgent
    """
    agent = OpenThinkerAgent(model=model)

    if check_availability:
        available = await agent.check_availability()
        if not available:
            logger.warning(
                f"OpenThinker ({model.value}) not available. "
                "The agent will fail gracefully on requests."
            )

    return agent


# Example usage
if __name__ == "__main__":

    async def main():
        # Create agent
        agent = await create_openthinker_agent()

        # Check if available
        if agent._available:
            print("OpenThinker Agent is ready!")

            # Test trade validation
            result = await agent.validate_trade(
                symbol="AAPL",
                action="BUY",
                market_data={
                    "price": 185.50,
                    "change_pct": 1.2,
                    "rsi": 65,
                    "macd_signal": "bullish",
                    "volume": 50000000,
                },
            )

            print("\n=== Trade Validation ===")
            print(f"Approved: {result['approved']}")
            print(f"Confidence: {result['confidence']}")
            print(f"Concerns: {result['concerns']}")
            print(f"\nReasoning:\n{result['reasoning'][:500]}...")

        else:
            print("OpenThinker not available. Install with:")
            print("  ollama pull openthinker:7b")

        await agent.close()

    asyncio.run(main())

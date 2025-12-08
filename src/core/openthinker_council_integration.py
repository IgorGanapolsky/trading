"""
OpenThinker Council Integration - Adds local reasoning to LLM Council.

Integrates OpenThinker-Agent as a council member for:
- Contrarian analysis (devil's advocate)
- Mathematical reasoning (position sizing)
- Extended thinking chains
- Cost-free local inference

This module extends TradingCouncil with OpenThinker capabilities.
"""

import asyncio
import logging
from typing import Any

from src.agents.openthinker_agent import OpenThinkerAgent, create_openthinker_agent
from src.core.llm_council_integration import TradingCouncil
from src.core.local_llm import LocalModel

logger = logging.getLogger(__name__)


class EnhancedTradingCouncil(TradingCouncil):
    """
    Enhanced Trading Council with OpenThinker integration.

    Adds OpenThinker as a local reasoning specialist to the LLM Council.
    OpenThinker provides:
    - Contrarian viewpoint (devil's advocate role)
    - Mathematical reasoning for position sizing
    - Extended thinking chains for complex decisions
    - Cost-free local inference
    """

    def __init__(
        self,
        api_key: str | None = None,
        enabled: bool = True,
        openthinker_enabled: bool = True,
        openthinker_model: LocalModel = LocalModel.OPENTHINKER_7B,
    ):
        """
        Initialize Enhanced Trading Council.

        Args:
            api_key: OpenRouter API key for cloud models
            enabled: Whether cloud council is enabled
            openthinker_enabled: Whether to include OpenThinker
            openthinker_model: OpenThinker model variant (7B or 32B)
        """
        super().__init__(api_key=api_key, enabled=enabled)

        self.openthinker_enabled = openthinker_enabled
        self.openthinker_model = openthinker_model
        self.openthinker_agent: OpenThinkerAgent | None = None
        self._openthinker_available: bool | None = None

        logger.info(
            f"Enhanced Trading Council initialized: "
            f"cloud={enabled}, openthinker={openthinker_enabled}"
        )

    async def _initialize_openthinker(self) -> bool:
        """Initialize OpenThinker agent if not already done."""
        if self.openthinker_agent is not None:
            return self._openthinker_available or False

        if not self.openthinker_enabled:
            return False

        try:
            self.openthinker_agent = await create_openthinker_agent(
                model=self.openthinker_model,
                check_availability=True,
            )
            self._openthinker_available = self.openthinker_agent._available
            return self._openthinker_available or False
        except Exception as e:
            logger.warning(f"Failed to initialize OpenThinker: {e}")
            self._openthinker_available = False
            return False

    async def validate_trade(
        self,
        symbol: str,
        action: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Validate trade with both cloud council and OpenThinker.

        OpenThinker acts as a contrarian voice - if it finds significant
        concerns, the trade may be blocked even if cloud council approves.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL)
            market_data: Market data
            context: Additional context

        Returns:
            Enhanced validation result with both perspectives
        """
        # Initialize OpenThinker if needed
        await self._initialize_openthinker()

        # Run both validations in parallel
        tasks = []

        # Cloud council validation
        cloud_task = asyncio.create_task(
            super().validate_trade(symbol, action, market_data, context)
        )
        tasks.append(("cloud", cloud_task))

        # OpenThinker contrarian validation
        if self._openthinker_available and self.openthinker_agent:
            openthinker_task = asyncio.create_task(
                self.openthinker_agent.validate_trade(
                    symbol, action, market_data, context
                )
            )
            tasks.append(("openthinker", openthinker_task))

        # Wait for all tasks
        results = {}
        for name, task in tasks:
            try:
                results[name] = await task
            except Exception as e:
                logger.error(f"{name} validation failed: {e}")
                results[name] = {"approved": True, "error": str(e)}

        # Combine results
        cloud_result = results.get("cloud", {"approved": True})
        openthinker_result = results.get("openthinker")

        # Decision logic:
        # - If cloud rejects, reject
        # - If OpenThinker has high-confidence rejection, consider blocking
        # - Otherwise, approve
        approved = cloud_result.get("approved", True)
        final_decision = cloud_result.get("final_decision", "APPROVED" if approved else "REJECTED")

        openthinker_concerns = []
        openthinker_blocked = False

        if openthinker_result:
            openthinker_approved = openthinker_result.get("approved", True)
            openthinker_confidence = openthinker_result.get("confidence", 0.0)
            openthinker_concerns = openthinker_result.get("concerns", [])

            # If OpenThinker strongly rejects (high confidence), block trade
            if not openthinker_approved and openthinker_confidence >= 0.7:
                logger.warning(
                    f"OpenThinker BLOCKED {action} {symbol}: "
                    f"confidence={openthinker_confidence:.2f}, "
                    f"concerns={openthinker_concerns[:2]}"
                )
                approved = False
                openthinker_blocked = True
                final_decision = "BLOCKED_BY_OPENTHINKER"

            # Log OpenThinker analysis
            logger.info(
                f"OpenThinker analysis for {symbol}: "
                f"approved={openthinker_approved}, "
                f"confidence={openthinker_confidence:.2f}, "
                f"concerns={len(openthinker_concerns)}"
            )

        return {
            "approved": approved,
            "confidence": cloud_result.get("confidence", 0.0),
            "reasoning": cloud_result.get("reasoning", ""),
            "council_response": cloud_result.get("council_response"),
            "final_decision": final_decision,
            # OpenThinker additions
            "openthinker_result": openthinker_result,
            "openthinker_blocked": openthinker_blocked,
            "openthinker_concerns": openthinker_concerns,
            # PAL challenge (from parent)
            "challenge_result": cloud_result.get("challenge_result"),
        }

    async def get_trading_recommendation(
        self,
        symbol: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get trading recommendation with OpenThinker reasoning.

        Args:
            symbol: Stock symbol
            market_data: Market data
            context: Additional context

        Returns:
            Recommendation with both cloud and local analysis
        """
        await self._initialize_openthinker()

        # Get cloud recommendation
        cloud_result = await super().get_trading_recommendation(
            symbol, market_data, context
        )

        # Get OpenThinker analysis if available
        openthinker_result = None
        if self._openthinker_available and self.openthinker_agent:
            try:
                openthinker_result = await self.openthinker_agent.analyze_trade(
                    symbol=symbol,
                    action=cloud_result.get("action", "HOLD"),
                    market_data=market_data,
                    portfolio_context=context,
                )
            except Exception as e:
                logger.warning(f"OpenThinker analysis failed: {e}")

        # Combine results
        result = cloud_result.copy()
        result["openthinker_result"] = openthinker_result

        # If OpenThinker strongly disagrees, note it
        if openthinker_result:
            ot_decision = openthinker_result.get("decision", "HOLD")
            cloud_action = cloud_result.get("action", "HOLD")

            if ot_decision != cloud_action:
                result["disagreement"] = {
                    "cloud_action": cloud_action,
                    "openthinker_action": ot_decision,
                    "openthinker_confidence": openthinker_result.get("confidence", 0),
                    "openthinker_reasoning": openthinker_result.get("reasoning", "")[:500],
                }
                logger.info(
                    f"Council disagreement on {symbol}: "
                    f"cloud={cloud_action}, openthinker={ot_decision}"
                )

        return result

    async def calculate_position_size(
        self,
        symbol: str,
        account_value: float,
        entry_price: float,
        stop_loss: float,
        risk_pct: float = 0.02,
    ) -> dict[str, Any]:
        """
        Calculate position size using OpenThinker mathematical reasoning.

        This uses OpenThinker's strength in mathematical reasoning to
        calculate optimal position sizes with full calculation transparency.

        Args:
            symbol: Stock symbol
            account_value: Total account value
            entry_price: Planned entry price
            stop_loss: Stop loss price
            risk_pct: Maximum risk per trade (default 2%)

        Returns:
            Position sizing with step-by-step calculations
        """
        await self._initialize_openthinker()

        if not self._openthinker_available or not self.openthinker_agent:
            # Fallback to simple calculation
            risk_per_share = abs(entry_price - stop_loss)
            if risk_per_share <= 0:
                return {
                    "success": False,
                    "error": "Invalid stop loss (must differ from entry)",
                }

            dollar_risk = account_value * risk_pct
            shares = int(dollar_risk / risk_per_share)
            position_value = shares * entry_price

            return {
                "success": True,
                "shares": shares,
                "position_value": position_value,
                "dollar_risk": dollar_risk,
                "risk_per_share": risk_per_share,
                "reasoning": "Simple calculation (OpenThinker unavailable)",
            }

        # Use OpenThinker for detailed calculation
        return await self.openthinker_agent.calculate_position_size(
            symbol=symbol,
            account_value=account_value,
            entry_price=entry_price,
            stop_loss=stop_loss,
            risk_pct=risk_pct,
        )

    async def get_openthinker_opinion(
        self,
        query: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get standalone OpenThinker opinion on any trading question.

        Args:
            query: Trading question
            context: Context data

        Returns:
            OpenThinker's reasoned opinion
        """
        await self._initialize_openthinker()

        if not self._openthinker_available or not self.openthinker_agent:
            return {
                "success": False,
                "error": "OpenThinker not available",
                "available": False,
            }

        return await self.openthinker_agent.council_opinion(query, context)

    async def close(self):
        """Close all council connections."""
        super().close()
        if self.openthinker_agent:
            await self.openthinker_agent.close()


# Factory function
def create_enhanced_trading_council(
    enabled: bool = True,
    openthinker_enabled: bool = True,
    openthinker_model: LocalModel = LocalModel.OPENTHINKER_7B,
    api_key: str | None = None,
) -> EnhancedTradingCouncil:
    """
    Create an Enhanced Trading Council with OpenThinker.

    Args:
        enabled: Enable cloud council
        openthinker_enabled: Enable OpenThinker
        openthinker_model: OpenThinker model variant
        api_key: OpenRouter API key

    Returns:
        Configured EnhancedTradingCouncil
    """
    return EnhancedTradingCouncil(
        api_key=api_key,
        enabled=enabled,
        openthinker_enabled=openthinker_enabled,
        openthinker_model=openthinker_model,
    )


# Example usage
if __name__ == "__main__":

    async def main():
        # Create enhanced council
        council = create_enhanced_trading_council()

        # Test trade validation
        print("Testing Enhanced Trading Council...")

        result = await council.validate_trade(
            symbol="AAPL",
            action="BUY",
            market_data={
                "price": 185.50,
                "change_pct": 1.2,
                "rsi": 65,
                "macd_signal": "bullish",
                "volume": 50000000,
            },
            context={
                "portfolio_value": 100000,
                "current_exposure": 0.3,
            },
        )

        print("\n=== Trade Validation Result ===")
        print(f"Approved: {result['approved']}")
        print(f"Final Decision: {result['final_decision']}")
        print(f"Confidence: {result['confidence']}")

        if result.get("openthinker_result"):
            ot = result["openthinker_result"]
            print(f"\nOpenThinker Analysis:")
            print(f"  Approved: {ot.get('approved')}")
            print(f"  Confidence: {ot.get('confidence')}")
            print(f"  Concerns: {ot.get('concerns', [])[:3]}")

        if result.get("openthinker_blocked"):
            print("\n⚠️  Trade BLOCKED by OpenThinker contrarian analysis!")

        await council.close()

    asyncio.run(main())

"""
LLM Council Integration for Trading Decisions

This module provides easy integration of the LLM Council system into trading workflows.
The council provides consensus-based decisions through peer review and chairman synthesis.

Enhanced with PAL (Provider Abstraction Layer) integration for:
- Adversarial validation (Challenge tool) - prevents groupthink
- Decision audit logging - tracks accuracy over time
"""

import json
import logging
import os
from typing import Any

from src.core.multi_llm_analysis import (
    LLMCouncilAnalyzer,
    LLMModel,
)
from src.core.pal_integration import PALIntegration, get_pal

logger = logging.getLogger(__name__)


class TradingCouncil:
    """
    Trading-specific wrapper for LLM Council.

    Provides convenient methods for common trading decision scenarios:
    - Trade validation (BUY/SELL/HOLD decisions)
    - Risk assessment
    - Position sizing recommendations
    - Market analysis
    """

    def __init__(
        self,
        api_key: str | None = None,
        council_models: list[LLMModel] | None = None,
        chairman_model: LLMModel | None = None,
        enabled: bool = True,
        pal_challenge_enabled: bool = True,
        pal_challenge_threshold: float = 0.7,
    ):
        """
        Initialize Trading Council.

        Args:
            api_key: OpenRouter API key
            council_models: List of models in council
            chairman_model: Chairman model
            enabled: Whether council is enabled (can disable for testing)
            pal_challenge_enabled: Whether to run PAL challenge on approved trades
            pal_challenge_threshold: Risk score threshold to block trades (0-1)
        """
        self.enabled = enabled
        self.council = None
        self.pal_challenge_enabled = (
            pal_challenge_enabled and os.getenv("PAL_CHALLENGE_ENABLED", "true").lower() == "true"
        )
        self.pal_challenge_threshold = pal_challenge_threshold
        self._pal: PALIntegration | None = None

        if enabled:
            try:
                self.council = LLMCouncilAnalyzer(
                    api_key=api_key,
                    council_models=council_models,
                    chairman_model=chairman_model,
                )
                logger.info("Trading Council initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize Trading Council: {e}")
                self.enabled = False
        else:
            logger.info("Trading Council disabled")

        # Initialize PAL integration for adversarial validation
        if self.pal_challenge_enabled:
            try:
                self._pal = get_pal()
                logger.info(f"PAL Challenge enabled (threshold={pal_challenge_threshold})")
            except Exception as e:
                logger.warning(f"PAL Challenge unavailable: {e}")
                self.pal_challenge_enabled = False

    async def validate_trade(
        self,
        symbol: str,
        action: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Validate a trading decision using LLM Council consensus.

        Args:
            symbol: Stock symbol
            action: Proposed action (BUY/SELL/HOLD)
            market_data: Market data (price, indicators, etc.)
            context: Additional context (portfolio, risk limits, etc.)

        Returns:
            Dictionary with:
                - approved: bool
                - confidence: float (0-1)
                - reasoning: str
                - council_response: Full CouncilResponse object
        """
        if not self.enabled or not self.council:
            logger.warning("Trading Council not available, approving by default")
            return {
                "approved": True,
                "confidence": 0.5,
                "reasoning": "Council unavailable - fail-open",
                "council_response": None,
            }

        try:
            query = f"""Evaluate whether we should {action} {symbol}.

Proposed Action: {action}
Symbol: {symbol}

Market Data:
{json.dumps(market_data, indent=2)}
"""

            if context:
                query += f"\n\nContext:\n{json.dumps(context, indent=2)}"

                # Highlight Intelligent Investor analysis if available
                if context.get("intelligent_investor_analysis"):
                    ii_analysis = context["intelligent_investor_analysis"]
                    query += f"""

**Intelligent Investor Analysis (Graham-Buffett Principles):**
- Safety Rating: {ii_analysis.get("safety_rating", "N/A")}
- Defensive Investor Score: {ii_analysis.get("defensive_investor_score", "N/A")}/100
- Value Score: {ii_analysis.get("value_score", "N/A")}/100
- Margin of Safety: {ii_analysis.get("margin_of_safety_pct", 0) * 100 if ii_analysis.get("margin_of_safety_pct") else 0:.1f}%
- Mr. Market Sentiment: {ii_analysis.get("mr_market_sentiment", "N/A")}
- Quality Score: {ii_analysis.get("quality_score", "N/A")}/100
"""
                    if ii_analysis.get("reasons"):
                        query += f"\nReasons: {', '.join(ii_analysis['reasons'])}\n"
                    if ii_analysis.get("warnings"):
                        query += f"\nWarnings: {', '.join(ii_analysis['warnings'])}\n"

            query += """
Provide:
1. Recommendation: APPROVE or REJECT the {action} trade
2. Confidence level (0-1)
3. Key factors supporting your decision
4. Risks or concerns
5. Alternative recommendation if rejecting

Consider Graham-Buffett principles:
- Margin of safety
- Value investing principles
- Defensive investor criteria
- Quality of the investment
- Mr. Market's mood (overvaluation/undervaluation)

Format clearly with reasoning."""

            # System prompt follows Anthropic best practices:
            # - Role setting in system message
            # - Clear evaluation criteria with motivation
            # - Specific rejection criteria for conservative bias
            system_prompt = """You are an expert trading risk manager following Graham-Buffett value investing principles.

<role_context>
Your primary duty is capital preservation. A 50% loss requires 100% gain to recover.
You evaluate trades through the lens of margin of safety - buying $1 of value for $0.80.
</role_context>

<evaluation_criteria>
Evaluate trades objectively based on:
- Market conditions and technical indicators (timing)
- Graham-Buffett Intelligent Investor principles: margin of safety, intrinsic value, quality (value)
- Risk management principles: position sizing, stop losses, portfolio heat (risk)
- Portfolio context and diversification (concentration)
- Intelligent Investor safety analysis if provided (safety)
</evaluation_criteria>

<rejection_triggers>
Be conservative - reject trades with ANY of:
- High risk or low confidence (below 0.6)
- Insufficient margin of safety (below 20%)
- Poor value characteristics (P/E above 25 without exceptional growth)
- Overvaluation concerns (Mr. Market sentiment too bullish)
</rejection_triggers>"""

            council_response = await self.council.query_council(
                query, system_prompt, include_reviews=True
            )

            # Parse approval from final answer
            final_answer_lower = council_response.final_answer.lower()
            approved = (
                "approve" in final_answer_lower
                and "reject" not in final_answer_lower
                and "decline" not in final_answer_lower
            )

            # Extract individual votes for audit
            individual_votes = {}
            for model_name, response in council_response.individual_responses.items():
                response_lower = response.lower()
                if "approve" in response_lower or "buy" in response_lower:
                    individual_votes[model_name] = "APPROVE"
                elif "reject" in response_lower or "sell" in response_lower:
                    individual_votes[model_name] = "REJECT"
                else:
                    individual_votes[model_name] = "HOLD"

            # PAL Challenge: If council approved, run adversarial validation
            challenge_result = None
            final_decision = "APPROVED" if approved else "REJECTED"

            if approved and self.pal_challenge_enabled and self._pal:
                try:
                    challenge_result = await self._pal.challenge_recommendation(
                        symbol=symbol,
                        action=action,
                        council_reasoning=council_response.final_answer,
                        market_data=market_data,
                        context=context,
                    )

                    # If challenge identifies high risk, block the trade
                    if challenge_result.risk_score > self.pal_challenge_threshold:
                        logger.warning(
                            f"PAL Challenge BLOCKED {action} {symbol}: "
                            f"risk_score={challenge_result.risk_score:.2f} > "
                            f"threshold={self.pal_challenge_threshold}"
                        )
                        approved = False
                        final_decision = "BLOCKED"

                    logger.info(
                        f"PAL Challenge for {symbol}: risk={challenge_result.risk_score:.2f}, "
                        f"proceed={challenge_result.should_proceed}, "
                        f"concerns={len(challenge_result.concerns)}"
                    )
                except Exception as e:
                    logger.warning(f"PAL Challenge failed (continuing): {e}")

            # Record decision for audit (if PAL available)
            if self._pal:
                self._pal.record_decision(
                    symbol=symbol,
                    action=action,
                    council_decision="APPROVED" if "approve" in final_answer_lower else "REJECTED",
                    council_confidence=council_response.confidence,
                    individual_votes=individual_votes,
                    challenge_result=challenge_result,
                    final_decision=final_decision,
                )

            return {
                "approved": approved,
                "confidence": council_response.confidence,
                "reasoning": council_response.final_answer,
                "council_response": council_response,
                "individual_responses": council_response.individual_responses,
                "reviews": council_response.reviews,
                "challenge_result": challenge_result,
                "final_decision": final_decision,
            }

        except Exception as e:
            logger.error(f"Trading Council validation error: {e}", exc_info=True)
            return {
                "approved": True,  # Fail-open
                "confidence": 0.0,
                "reasoning": f"Council error: {str(e)}",
                "council_response": None,
                "challenge_result": None,
                "final_decision": "ERROR",
            }

    async def get_trading_recommendation(
        self,
        symbol: str,
        market_data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Get trading recommendation from LLM Council.

        Args:
            symbol: Stock symbol
            market_data: Market data
            context: Additional context

        Returns:
            Dictionary with recommendation, confidence, reasoning
        """
        if not self.enabled or not self.council:
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": "Council unavailable",
            }

        try:
            council_response = await self.council.analyze_trading_decision(
                symbol, market_data, context
            )

            # Parse action from final answer
            final_answer_lower = council_response.final_answer.lower()
            if "buy" in final_answer_lower and "sell" not in final_answer_lower:
                action = "BUY"
            elif "sell" in final_answer_lower:
                action = "SELL"
            else:
                action = "HOLD"

            return {
                "action": action,
                "confidence": council_response.confidence,
                "reasoning": council_response.final_answer,
                "council_response": council_response,
                "individual_responses": council_response.individual_responses,
            }

        except Exception as e:
            logger.error(f"Trading Council recommendation error: {e}", exc_info=True)
            return {
                "action": "HOLD",
                "confidence": 0.0,
                "reasoning": f"Council error: {str(e)}",
            }

    async def assess_risk(
        self,
        symbol: str,
        position_size: float,
        market_data: dict[str, Any],
        portfolio_context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Assess risk of a proposed position using LLM Council.

        Args:
            symbol: Stock symbol
            position_size: Proposed position size (dollars)
            market_data: Market data
            portfolio_context: Portfolio context (current positions, etc.)

        Returns:
            Dictionary with risk assessment
        """
        if not self.enabled or not self.council:
            return {
                "risk_level": "MEDIUM",
                "approved": True,
                "reasoning": "Council unavailable",
            }

        query = f"""Assess the risk of opening a ${position_size:,.2f} position in {symbol}.

Position Details:
- Symbol: {symbol}
- Position Size: ${position_size:,.2f}

Market Data:
{json.dumps(market_data, indent=2)}
"""

        if portfolio_context:
            query += f"\n\nPortfolio Context:\n{json.dumps(portfolio_context, indent=2)}"

        query += """
Provide:
1. Risk level: LOW/MEDIUM/HIGH
2. Approval: APPROVE or REJECT the position
3. Maximum recommended position size
4. Key risk factors
5. Risk mitigation recommendations

Format clearly with reasoning."""

        # System prompt with XML structure and motivation
        system_prompt = """You are an expert risk manager focused on capital preservation.

<role_context>
Risk management is the only edge that compounds - one blown account erases years of gains.
Your job is to say "no" to trades that violate risk limits, even if they look attractive.
</role_context>

<assessment_criteria>
Assess position risk based on:
- Portfolio concentration (no single position above 5%)
- Market volatility (higher vol = smaller position)
- Position size relative to portfolio (Kelly Criterion with half-sizing)
- Correlation with existing positions (sector/factor exposure)
- Market conditions (regime: trending, mean-reverting, or chaotic)
</assessment_criteria>

<risk_limits>
Be conservative - reject positions that:
- Would exceed 2% portfolio risk on a single trade
- Add correlated exposure to an already concentrated sector
- Size inappropriately for current volatility regime
</risk_limits>"""

        try:
            council_response = await self.council.query_council(
                query, system_prompt, include_reviews=True
            )

            # Parse risk level and approval
            final_answer_lower = council_response.final_answer.lower()
            if "high risk" in final_answer_lower or "high-risk" in final_answer_lower:
                risk_level = "HIGH"
            elif "low risk" in final_answer_lower or "low-risk" in final_answer_lower:
                risk_level = "LOW"
            else:
                risk_level = "MEDIUM"

            approved = "approve" in final_answer_lower and "reject" not in final_answer_lower

            return {
                "risk_level": risk_level,
                "approved": approved,
                "confidence": council_response.confidence,
                "reasoning": council_response.final_answer,
                "council_response": council_response,
            }

        except Exception as e:
            logger.error(f"Trading Council risk assessment error: {e}", exc_info=True)
            return {
                "risk_level": "MEDIUM",
                "approved": True,
                "reasoning": f"Council error: {str(e)}",
            }

    def close(self):
        """Close council connections."""
        if self.council:
            self.council.close()


# Convenience function for easy integration
def create_trading_council(
    enabled: bool = True,
    api_key: str | None = None,
) -> TradingCouncil:
    """
    Create a Trading Council instance.

    Args:
        enabled: Whether council is enabled
        api_key: OpenRouter API key (defaults to env var)

    Returns:
        TradingCouncil instance
    """
    return TradingCouncil(
        api_key=api_key,
        enabled=enabled,
    )

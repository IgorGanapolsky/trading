"""
RAG Trade Advisor - Integrate Options Knowledge into Live Trading Decisions

This module provides the bridge between RAG knowledge (McMillan, TastyTrade) and
live trading execution. It validates trades against expert rules BEFORE execution.

Key Features:
1. Query RAG before each options trade
2. Validate strategy vs IV regime (prevent buying expensive premium in high IV)
3. Get McMillan's expected move calculation
4. Cross-check sentiment signals with book knowledge
5. Provide trade approval/rejection with reasoning

Integration Points:
- Called by ExecutionAgent before executing options trades
- Used by OptionsProfitPlanner to validate theta harvest opportunities
- Integrated into MCPTradingOrchestrator for options decision flow

Usage:
    advisor = RAGTradeAdvisor()

    # Get trade advice before execution
    advice = advisor.get_trade_advice(
        ticker="SPY",
        strategy="iron_condor",
        iv_rank=65,
        sentiment="neutral",
        dte=30
    )

    if advice["approved"]:
        # Execute trade
        pass
    else:
        logger.warning(f"Trade rejected: {advice['rejection_reason']}")
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.rag.options_book_retriever import OptionsBookRetriever

logger = logging.getLogger(__name__)


class RAGTradeAdvisor:
    """
    High-level trade advisor that integrates RAG knowledge into trading decisions.

    This class sits between trading signals and execution, providing expert
    validation of trades against McMillan's rules and TastyTrade research.

    CRITICAL: Always consult RAG before executing options trades to prevent:
    - Buying expensive premium in high IV environments
    - Selling cheap premium in low IV environments
    - Using strategies incompatible with market conditions
    - Ignoring expected move calculations
    """

    def __init__(self, knowledge_base_path: Path | None = None):
        """
        Initialize the RAG Trade Advisor.

        Args:
            knowledge_base_path: Path to RAG knowledge chunks (optional)
        """
        self.retriever = OptionsBookRetriever()
        self.knowledge_base_path = knowledge_base_path or Path("rag_knowledge/chunks")

        # Load knowledge chunks
        self.mcmillan_chunks = self._load_chunks("mcmillan_options_strategic_investment_2025.json")
        self.tastytrade_chunks = self._load_chunks("tastytrade_options_education_2025.json")

        logger.info(
            f"RAGTradeAdvisor initialized with {len(self.mcmillan_chunks)} McMillan chunks "
            f"and {len(self.tastytrade_chunks)} TastyTrade chunks"
        )

    def _load_chunks(self, filename: str) -> list[dict[str, Any]]:
        """Load knowledge chunks from JSON file."""
        file_path = self.knowledge_base_path / filename

        if not file_path.exists():
            logger.warning(f"Knowledge file not found: {file_path}")
            return []

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)
                chunks = data.get("chunks", [])
                logger.info(f"Loaded {len(chunks)} chunks from {filename}")
                return chunks
        except Exception as e:
            logger.error(f"Failed to load {filename}: {e}")
            return []

    def get_trade_advice(
        self,
        ticker: str,
        strategy: str,
        iv_rank: float,
        sentiment: str = "neutral",
        dte: int = 30,
        stock_price: float | None = None,
        current_iv: float | None = None,
    ) -> dict[str, Any]:
        """
        Get comprehensive trade advice from RAG knowledge before execution.

        This is the MAIN method that should be called before every options trade.

        Args:
            ticker: Stock symbol (e.g., "SPY")
            strategy: Strategy name (e.g., "iron_condor", "covered_call")
            iv_rank: Current IV Rank (0-100)
            sentiment: Market sentiment ("bullish", "bearish", "neutral", "overbought", "oversold")
            dte: Days to expiration
            stock_price: Current stock price (optional)
            current_iv: Current implied volatility as decimal (e.g., 0.30)

        Returns:
            Dict with trade approval/rejection and detailed reasoning:
            {
                "approved": bool,
                "confidence": float (0-1),
                "recommendation": str,
                "rejection_reason": str | None,
                "mcmillan_guidance": str,
                "tastytrade_guidance": str,
                "iv_regime": dict,
                "expected_move": dict | None,
                "strategy_rules": dict,
                "book_references": list,
                "warnings": list[str],
            }
        """
        logger.info(
            f"🔍 RAG Trade Advice Request: {ticker} {strategy} | IV Rank: {iv_rank:.0f}% | "
            f"Sentiment: {sentiment} | DTE: {dte}"
        )

        advice = {
            "ticker": ticker,
            "strategy": strategy,
            "iv_rank": iv_rank,
            "sentiment": sentiment,
            "dte": dte,
            "timestamp": datetime.now().isoformat(),
            "approved": False,
            "confidence": 0.0,
            "recommendation": "",
            "rejection_reason": None,
            "mcmillan_guidance": "",
            "tastytrade_guidance": "",
            "iv_regime": {},
            "expected_move": None,
            "strategy_rules": {},
            "book_references": [],
            "warnings": [],
        }

        # Step 1: Validate strategy vs IV regime
        is_valid, validation_result = self.validate_strategy_vs_iv(strategy, iv_rank)
        advice["iv_regime"] = validation_result

        if not is_valid:
            advice["approved"] = False
            advice["rejection_reason"] = validation_result["rejection_reason"]
            advice["recommendation"] = f"REJECT: {validation_result['rejection_reason']}"
            logger.warning(f"❌ Trade REJECTED: {advice['rejection_reason']}")
            return advice

        # Step 2: Get McMillan's expected move calculation
        if current_iv and stock_price:
            try:
                expected_move_result = self.retriever.cross_check_expected_move(
                    ticker=ticker,
                    sentiment_signal=sentiment,
                    current_iv=current_iv,
                    dte=dte,
                    stock_price=stock_price,
                )
                advice["expected_move"] = expected_move_result

                # Add alignment warnings
                if not expected_move_result.get("alignment", {}).get("is_aligned", True):
                    advice["warnings"].append(
                        f"⚠️ Sentiment '{sentiment}' may not align with expected move: "
                        f"{expected_move_result.get('alignment', {}).get('message', 'N/A')}"
                    )
            except Exception as e:
                logger.warning(f"Failed to calculate expected move: {e}")
                advice["warnings"].append("Expected move calculation unavailable")

        # Step 3: Get strategy-specific guidance from RAG
        strategy_guidance = self.retriever.get_strategy_for_conditions(
            iv_rank=iv_rank,
            market_outlook=sentiment,
            days_to_expiration=dte,
            risk_tolerance="moderate",
        )
        advice["strategy_rules"] = strategy_guidance

        # Step 4: Get McMillan rules for this strategy
        mcmillan_rule = self.get_mcmillan_rule(strategy)
        advice["mcmillan_guidance"] = mcmillan_rule

        # Step 5: Get TastyTrade rules for this strategy
        tastytrade_rule = self.get_tastytrade_rule(strategy, dte, iv_rank)
        advice["tastytrade_guidance"] = tastytrade_rule

        # Step 6: Build comprehensive recommendation
        approval_score = 0.0
        reasons = []

        # IV regime alignment (most important)
        if is_valid:
            approval_score += 0.4
            reasons.append(f"✅ Strategy matches IV regime ({validation_result['regime']})")

        # Strategy recommendation match
        if strategy in strategy_guidance.get("recommended_strategy", ""):
            approval_score += 0.3
            reasons.append("✅ Strategy matches RAG recommendation")
        elif strategy in strategy_guidance.get("alternative_strategies", []):
            approval_score += 0.15
            reasons.append("✅ Strategy is alternative RAG recommendation")

        # DTE alignment (TastyTrade prefers 30-45 DTE)
        if 30 <= dte <= 45:
            approval_score += 0.2
            reasons.append("✅ DTE in optimal range (30-45)")
        elif dte < 21:
            advice["warnings"].append("⚠️ DTE < 21 increases gamma risk")

        # McMillan guidance presence
        if mcmillan_rule:
            approval_score += 0.1
            reasons.append("✅ McMillan guidance available")

        # Final approval decision
        advice["confidence"] = approval_score
        advice["approved"] = approval_score >= 0.5  # Require 50% confidence minimum

        if advice["approved"]:
            advice["recommendation"] = f"APPROVE: {'; '.join(reasons)}"
            logger.info(f"✅ Trade APPROVED with {approval_score:.1%} confidence")
        else:
            advice["recommendation"] = (
                f"REJECT: Insufficient confidence ({approval_score:.1%}). "
                f"Reasons: {'; '.join(reasons)}"
            )
            advice["rejection_reason"] = f"Low confidence ({approval_score:.1%})"
            logger.warning(f"❌ Trade REJECTED: {advice['rejection_reason']}")

        return advice

    def validate_strategy_vs_iv(
        self,
        strategy_name: str,
        iv_rank: float,
    ) -> tuple[bool, dict[str, Any]]:
        """
        Validate if strategy is appropriate for current IV regime.

        CRITICAL: This prevents buying expensive premium in high IV (disaster)
        and selling cheap premium in low IV (missed opportunity).

        Args:
            strategy_name: Strategy name (e.g., "iron_condor", "long_call")
            iv_rank: Current IV Rank (0-100)

        Returns:
            Tuple of (is_valid, validation_details)

        Example:
            >>> advisor = RAGTradeAdvisor()
            >>> is_valid, details = advisor.validate_strategy_vs_iv("long_call", 85)
            >>> print(is_valid)  # False - don't buy calls in high IV!
            >>> print(details["rejection_reason"])
            "Strategy long_call is FORBIDDEN in very_high IV regime (IV Rank: 85%)"
        """
        # Get IV regime from retriever
        regime_info = self.retriever.get_iv_regime(iv_rank)

        # Normalize strategy name for comparison
        normalized_strategy = strategy_name.lower().replace(" ", "_")

        result = {
            "strategy": strategy_name,
            "iv_rank": iv_rank,
            "regime": regime_info["regime"],
            "is_valid": False,
            "rejection_reason": None,
            "guidance": regime_info["guidance"],
            "allowed_strategies": regime_info["allowed_strategies"],
            "forbidden_strategies": regime_info["forbidden_strategies"],
        }

        # Check if strategy is forbidden
        if normalized_strategy in regime_info["forbidden_strategies"]:
            result["is_valid"] = False
            result["rejection_reason"] = (
                f"Strategy {strategy_name} is FORBIDDEN in {regime_info['regime']} "
                f"IV regime (IV Rank: {iv_rank:.0f}%). {regime_info['guidance']}"
            )
            logger.warning(f"🚫 {result['rejection_reason']}")
            return False, result

        # Check if strategy is allowed
        if normalized_strategy in regime_info["allowed_strategies"]:
            result["is_valid"] = True
            logger.info(
                f"✅ Strategy {strategy_name} is ALLOWED in {regime_info['regime']} "
                f"IV regime (IV Rank: {iv_rank:.0f}%)"
            )
            return True, result

        # Strategy not explicitly listed - use neutral stance
        result["is_valid"] = True
        result["rejection_reason"] = None
        logger.info(
            f"⚠️ Strategy {strategy_name} not explicitly listed for {regime_info['regime']} "
            f"IV regime - allowing with caution"
        )

        return True, result

    def get_mcmillan_rule(self, topic: str) -> str:
        """
        Get McMillan's rule/guidance for a specific topic or strategy.

        Args:
            topic: Topic or strategy name (e.g., "covered_call", "stop_loss", "gamma")

        Returns:
            Rule text from McMillan's book, or empty string if not found
        """
        topic_lower = topic.lower().replace(" ", "_")

        # Search through McMillan chunks
        relevant_chunks = []
        for chunk in self.mcmillan_chunks:
            chunk_topic = chunk.get("topic", "").lower()
            chunk_id = chunk.get("id", "").lower()
            chunk_strategy = chunk.get("strategy_type", "").lower()

            if (
                topic_lower in chunk_topic
                or topic_lower in chunk_id
                or topic_lower in chunk_strategy
            ):
                relevant_chunks.append(chunk)

        if not relevant_chunks:
            logger.debug(f"No McMillan rule found for '{topic}'")
            return ""

        # Combine relevant chunks
        combined = "\n\n".join(
            f"**{chunk['topic']}**: {chunk['content']}" for chunk in relevant_chunks[:3]
        )

        logger.info(f"Found {len(relevant_chunks)} McMillan rules for '{topic}'")
        return combined

    def get_tastytrade_rule(self, strategy: str, dte: int, iv_rank: float) -> str:
        """
        Get TastyTrade research guidance for a specific strategy.

        Args:
            strategy: Strategy name
            dte: Days to expiration
            iv_rank: Current IV Rank

        Returns:
            TastyTrade guidance text
        """
        strategy_lower = strategy.lower().replace(" ", "_")

        # Search through TastyTrade chunks
        relevant_chunks = []
        for chunk in self.tastytrade_chunks:
            chunk_topic = chunk.get("topic", "").lower()
            chunk_id = chunk.get("id", "").lower()
            chunk_strategy = chunk.get("strategy_type", "").lower()

            if (
                strategy_lower in chunk_topic
                or strategy_lower in chunk_id
                or strategy_lower in chunk_strategy
            ):
                relevant_chunks.append(chunk)

        if not relevant_chunks:
            # Get generic TastyTrade rules
            relevant_chunks = [
                chunk for chunk in self.tastytrade_chunks if "trading_rules" in chunk.get("id", "")
            ]

        if not relevant_chunks:
            logger.debug(f"No TastyTrade rule found for '{strategy}'")
            return ""

        # Build guidance with TastyTrade rules
        guidance_parts = []

        for chunk in relevant_chunks[:2]:
            guidance_parts.append(f"**{chunk['topic']}**: {chunk['content']}")

        # Add trading rules context
        try:
            rules = self.tastytrade_chunks[0].get("trading_rules", {})
            if rules:
                entry_rules = rules.get("entry_criteria", {})
                mgmt_rules = rules.get("management_rules", {})

                dte_range = entry_rules.get("dte_entry", [30, 45])
                dte_status = "✅" if dte_range[0] <= dte <= dte_range[1] else "⚠️"

                iv_min = entry_rules.get("iv_rank_minimum", 30)
                iv_status = "✅" if iv_rank >= iv_min else "⚠️"

                guidance_parts.append(
                    f"\n**TastyTrade Rules**:\n"
                    f"{dte_status} Optimal DTE: {dte_range[0]}-{dte_range[1]} (current: {dte})\n"
                    f"{iv_status} Min IV Rank: {iv_min}% (current: {iv_rank:.0f}%)\n"
                    f"Take Profit: {mgmt_rules.get('take_profit_target_percent', 50)}% of max profit\n"
                    f"Close by: {mgmt_rules.get('max_dte_before_close', 21)} DTE"
                )
        except Exception as e:
            logger.debug(f"Could not extract TastyTrade rules: {e}")

        combined = "\n\n".join(guidance_parts)
        logger.info(f"Found {len(relevant_chunks)} TastyTrade rules for '{strategy}'")
        return combined

    def get_trade_attribution(self, advice: dict[str, Any]) -> dict[str, Any]:
        """
        Generate trade attribution metadata for logging.

        This tracks which RAG knowledge influenced each trade decision.

        Args:
            advice: Trade advice dict from get_trade_advice()

        Returns:
            Attribution metadata dict
        """
        return {
            "timestamp": advice["timestamp"],
            "ticker": advice["ticker"],
            "strategy": advice["strategy"],
            "approved": advice["approved"],
            "confidence": advice["confidence"],
            "iv_regime": advice["iv_regime"]["regime"],
            "mcmillan_used": bool(advice["mcmillan_guidance"]),
            "tastytrade_used": bool(advice["tastytrade_guidance"]),
            "expected_move_used": advice["expected_move"] is not None,
            "warnings_count": len(advice["warnings"]),
        }

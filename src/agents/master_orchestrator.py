"""
Master Orchestrator - Multi-Agent Coordination with Introspection

This orchestrator coordinates all agents (Research, Signal, Risk, Execution)
and performs final introspection to validate the complete trading decision.

Key Features:
    - Coordinates all agents in sequence
    - Aggregates agent outputs
    - Final decision introspection
    - Trade execution coordination
    - Performance tracking

Author: Trading System
Created: 2025-11-03
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum

from src.agents.research_agent import ResearchAgent, ResearchOutput
from src.agents.signal_agent import SignalAgent, SignalOutput, SignalType
from src.agents.risk_agent import RiskAgent, RiskOutput
from src.agents.execution_agent import ExecutionAgent, ExecutionOutput

logger = logging.getLogger(__name__)


class DecisionStatus(Enum):
    """Final decision status."""
    APPROVED = "approved"
    REJECTED = "rejected"
    HOLD = "hold"


@dataclass
class OrchestratorIntrospection:
    """Final introspection results from orchestrator."""
    all_agents_aligned: bool
    confidence_aggregate: float
    risk_acceptable: bool
    contradictions: List[str]
    warnings: List[str]
    final_recommendation: str


@dataclass
class TradingDecision:
    """Final trading decision from orchestrator."""
    status: DecisionStatus
    symbol: str
    research: Optional[ResearchOutput]
    signal: Optional[SignalOutput]
    risk: Optional[RiskOutput]
    execution: Optional[ExecutionOutput]
    introspection: OrchestratorIntrospection
    timestamp: datetime
    summary: str


class MasterOrchestrator:
    """
    Master Orchestrator for coordinating all agents with introspection.

    This orchestrator runs all agents in sequence and performs final
    introspection to validate the complete trading decision.

    Attributes:
        research_agent: Research agent instance
        signal_agent: Signal agent instance
        risk_agent: Risk agent instance
        execution_agent: Execution agent instance
    """

    def __init__(
        self,
        research_agent: Optional[ResearchAgent] = None,
        signal_agent: Optional[SignalAgent] = None,
        risk_agent: Optional[RiskAgent] = None,
        execution_agent: Optional[ExecutionAgent] = None,
    ):
        """
        Initialize the Master Orchestrator.

        Args:
            research_agent: Research agent (created if None)
            signal_agent: Signal agent (created if None)
            risk_agent: Risk agent (created if None)
            execution_agent: Execution agent (created if None)
        """
        self.research_agent = research_agent or ResearchAgent()
        self.signal_agent = signal_agent or SignalAgent()
        self.risk_agent = risk_agent or RiskAgent()
        self.execution_agent = execution_agent or ExecutionAgent()

        logger.info("=" * 80)
        logger.info("MASTER ORCHESTRATOR INITIALIZED")
        logger.info("=" * 80)
        logger.info("All agents ready for coordinated decision-making")

    def make_trading_decision(
        self,
        symbols: List[str],
        portfolio_value: float,
        current_positions: Dict[str, float],
        daily_pnl: float,
        current_prices: Dict[str, float],
    ) -> List[TradingDecision]:
        """
        Make trading decisions for all symbols with full agent coordination.

        Args:
            symbols: List of symbols to analyze
            portfolio_value: Current portfolio value
            current_positions: Current positions (symbol -> value)
            daily_pnl: Today's profit/loss
            current_prices: Current prices (symbol -> price)

        Returns:
            List of TradingDecision objects
        """
        logger.info("=" * 80)
        logger.info("MASTER ORCHESTRATOR: Making Trading Decisions")
        logger.info("=" * 80)
        logger.info(f"Symbols: {symbols}")
        logger.info(f"Portfolio Value: ${portfolio_value:,.2f}")
        logger.info(f"Daily P&L: ${daily_pnl:+,.2f}")

        research_output = self.research_agent.analyze_market(symbols)

        decisions = []
        for symbol in symbols:
            decision = self._make_decision_for_symbol(
                symbol=symbol,
                research_output=research_output,
                portfolio_value=portfolio_value,
                current_positions=current_positions,
                daily_pnl=daily_pnl,
                current_price=current_prices.get(symbol, 0.0),
            )
            decisions.append(decision)

        logger.info("\n" + "=" * 80)
        logger.info("ORCHESTRATOR SUMMARY")
        logger.info("=" * 80)

        approved_count = sum(1 for d in decisions if d.status == DecisionStatus.APPROVED)
        rejected_count = sum(1 for d in decisions if d.status == DecisionStatus.REJECTED)
        hold_count = sum(1 for d in decisions if d.status == DecisionStatus.HOLD)

        logger.info(f"Decisions: {approved_count} APPROVED, {rejected_count} REJECTED, {hold_count} HOLD")

        for decision in decisions:
            if decision.status == DecisionStatus.APPROVED:
                logger.info(f"  ✓ {decision.symbol}: {decision.summary}")

        return decisions

    def _make_decision_for_symbol(
        self,
        symbol: str,
        research_output: ResearchOutput,
        portfolio_value: float,
        current_positions: Dict[str, float],
        daily_pnl: float,
        current_price: float,
    ) -> TradingDecision:
        """
        Make trading decision for a single symbol.

        Args:
            symbol: Symbol to analyze
            research_output: Research agent output
            portfolio_value: Current portfolio value
            current_positions: Current positions
            daily_pnl: Today's profit/loss
            current_price: Current price for symbol

        Returns:
            TradingDecision for the symbol
        """
        logger.info("\n" + "-" * 80)
        logger.info(f"Processing: {symbol}")
        logger.info("-" * 80)

        signal_output = self.signal_agent.generate_signal(
            symbol=symbol,
            research_output=research_output,
        )

        if signal_output.signal == SignalType.HOLD:
            logger.info(f"Signal Agent: HOLD - skipping risk/execution")
            introspection = self._perform_final_introspection(
                research=research_output,
                signal=signal_output,
                risk=None,
                execution=None,
            )
            return TradingDecision(
                status=DecisionStatus.HOLD,
                symbol=symbol,
                research=research_output,
                signal=signal_output,
                risk=None,
                execution=None,
                introspection=introspection,
                timestamp=datetime.now(),
                summary="HOLD: No actionable signal",
            )

        risk_output = self.risk_agent.assess_risk(
            signal_output=signal_output,
            portfolio_value=portfolio_value,
            current_positions=current_positions,
            daily_pnl=daily_pnl,
        )

        if not risk_output.approved:
            logger.info(f"Risk Agent: REJECTED - {risk_output.reason}")
            introspection = self._perform_final_introspection(
                research=research_output,
                signal=signal_output,
                risk=risk_output,
                execution=None,
            )
            return TradingDecision(
                status=DecisionStatus.REJECTED,
                symbol=symbol,
                research=research_output,
                signal=signal_output,
                risk=risk_output,
                execution=None,
                introspection=introspection,
                timestamp=datetime.now(),
                summary=f"REJECTED: {risk_output.reason}",
            )

        execution_output = self.execution_agent.validate_execution(
            signal_output=signal_output,
            risk_output=risk_output,
            current_price=current_price,
        )

        if not execution_output.approved:
            logger.info(f"Execution Agent: REJECTED - {execution_output.reason}")
            introspection = self._perform_final_introspection(
                research=research_output,
                signal=signal_output,
                risk=risk_output,
                execution=execution_output,
            )
            return TradingDecision(
                status=DecisionStatus.REJECTED,
                symbol=symbol,
                research=research_output,
                signal=signal_output,
                risk=risk_output,
                execution=execution_output,
                introspection=introspection,
                timestamp=datetime.now(),
                summary=f"REJECTED: {execution_output.reason}",
            )

        introspection = self._perform_final_introspection(
            research=research_output,
            signal=signal_output,
            risk=risk_output,
            execution=execution_output,
        )

        summary = (
            f"APPROVED: {execution_output.order_side.value.upper()} "
            f"{execution_output.quantity:.4f} shares @ ${execution_output.estimated_price:.2f}"
        )

        logger.info(f"✓ Final Decision: {summary}")

        return TradingDecision(
            status=DecisionStatus.APPROVED,
            symbol=symbol,
            research=research_output,
            signal=signal_output,
            risk=risk_output,
            execution=execution_output,
            introspection=introspection,
            timestamp=datetime.now(),
            summary=summary,
        )

    def _perform_final_introspection(
        self,
        research: ResearchOutput,
        signal: SignalOutput,
        risk: Optional[RiskOutput],
        execution: Optional[ExecutionOutput],
    ) -> OrchestratorIntrospection:
        """
        Perform final introspection across all agents.

        This is the final check that asks:
        - "Do all agents agree on this decision?"
        - "Is the aggregate confidence high enough?"
        - "Are there any contradictions between agents?"

        Args:
            research: Research agent output
            signal: Signal agent output
            risk: Risk agent output (optional)
            execution: Execution agent output (optional)

        Returns:
            OrchestratorIntrospection with final validation
        """
        logger.info("🔍 FINAL INTROSPECTION: Validating complete decision...")

        warnings = []
        contradictions = []

        confidences = [research.confidence, signal.confidence]
        confidence_aggregate = sum(confidences) / len(confidences)

        if research.introspection.bias_detected:
            warnings.append("Research agent detected bias")
            contradictions.append("Research bias may affect decision quality")

        if signal.introspection.indicator_consensus < 0.75:
            warnings.append("Signal agent has low indicator consensus")

        if risk and not risk.approved:
            contradictions.append("Risk agent rejected the trade")

        if execution and not execution.approved:
            contradictions.append("Execution agent rejected the trade")

        all_agents_aligned = len(contradictions) == 0
        risk_acceptable = risk is None or risk.approved

        if all_agents_aligned and confidence_aggregate > 0.7:
            final_recommendation = "PROCEED: All agents aligned with high confidence"
        elif all_agents_aligned and confidence_aggregate > 0.5:
            final_recommendation = "PROCEED: All agents aligned with moderate confidence"
        elif not all_agents_aligned:
            final_recommendation = "REJECT: Agent contradictions detected"
        else:
            final_recommendation = "HOLD: Low confidence across agents"

        logger.info(f"  All Agents Aligned: {all_agents_aligned}")
        logger.info(f"  Aggregate Confidence: {confidence_aggregate:.2f}")
        logger.info(f"  Risk Acceptable: {risk_acceptable}")
        logger.info(f"  Final Recommendation: {final_recommendation}")

        if warnings:
            for warning in warnings:
                logger.warning(f"  ⚠️  {warning}")

        return OrchestratorIntrospection(
            all_agents_aligned=all_agents_aligned,
            confidence_aggregate=confidence_aggregate,
            risk_acceptable=risk_acceptable,
            contradictions=contradictions,
            warnings=warnings,
            final_recommendation=final_recommendation,
        )

    def get_best_symbol(
        self,
        decisions: List[TradingDecision],
    ) -> Optional[TradingDecision]:
        """
        Get the best trading decision from a list of decisions.

        Args:
            decisions: List of trading decisions

        Returns:
            Best decision or None if no approved decisions
        """
        approved_decisions = [
            d for d in decisions
            if d.status == DecisionStatus.APPROVED
        ]

        if not approved_decisions:
            return None

        approved_decisions.sort(
            key=lambda d: d.introspection.confidence_aggregate,
            reverse=True,
        )

        return approved_decisions[0]

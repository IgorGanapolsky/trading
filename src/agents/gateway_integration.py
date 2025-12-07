"""
Gateway Integration for Anthropic Patterns

Integrates the human-in-the-loop checkpoints and error recovery
with the existing TradeGateway.

This module bridges:
- TradeGateway (existing risk enforcement)
- RiskCheckpoint (new multi-dimensional risk assessment)
- ErrorRecoveryFramework (new fallback strategies)
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from src.agents.anthropic_patterns import (
    HumanCheckpoint,
    RiskCheckpoint,
    RiskLevel,
    ErrorRecoveryFramework,
    create_trading_checkpoint,
    error_recovery,
)

logger = logging.getLogger(__name__)


@dataclass
class EnhancedGatewayDecision:
    """Extended gateway decision with human checkpoint info."""
    approved: bool
    requires_human_approval: bool
    checkpoint: Optional[HumanCheckpoint]
    risk_level: RiskLevel
    risk_reasons: list[str]
    original_decision: Any  # GatewayDecision from trade_gateway
    metadata: dict[str, Any]


class EnhancedTradeGateway:
    """
    Wrapper around TradeGateway that adds Anthropic's patterns.

    Flow:
    1. Original gateway evaluates trade (existing logic)
    2. If approved, run multi-dimensional risk checkpoint
    3. If HIGH/CRITICAL risk, require human approval
    4. Execute with error recovery framework
    """

    def __init__(self, gateway, approval_agent=None):
        """
        Args:
            gateway: Existing TradeGateway instance
            approval_agent: ApprovalAgent for human-in-the-loop
        """
        self.gateway = gateway
        self.approval_agent = approval_agent
        self.risk_checkpoint = RiskCheckpoint(
            trade_value_threshold=50.0,  # $50 for high-risk flag
            daily_loss_threshold=0.02,
            consecutive_losses=3,
            volatility_multiplier=2.0,
            correlation_threshold=0.8
        )
        self.error_recovery = error_recovery
        self.pending_checkpoints: dict[str, HumanCheckpoint] = {}

    async def evaluate_with_checkpoint(
        self,
        request,
        context: Optional[dict[str, Any]] = None
    ) -> EnhancedGatewayDecision:
        """
        Evaluate trade request with human checkpoint.

        Args:
            request: TradeRequest from trade_gateway
            context: Additional context for risk assessment

        Returns:
            EnhancedGatewayDecision with checkpoint info
        """
        # Step 1: Run original gateway evaluation
        original_decision = self.gateway.evaluate(request)

        if not original_decision.approved:
            # Original gateway rejected - no need for checkpoint
            return EnhancedGatewayDecision(
                approved=False,
                requires_human_approval=False,
                checkpoint=None,
                risk_level=RiskLevel.LOW,
                risk_reasons=original_decision.rejection_reasons,
                original_decision=original_decision,
                metadata={"stage": "gateway_rejected"}
            )

        # Step 2: Build context for risk assessment
        risk_context = self._build_risk_context(request, context)

        # Step 3: Run multi-dimensional risk assessment
        risk_level, risk_reasons = self.risk_checkpoint.assess_risk(risk_context)

        # Step 4: Create human checkpoint if needed
        checkpoint = None
        requires_human = False

        if risk_level in (RiskLevel.HIGH, RiskLevel.CRITICAL):
            checkpoint = create_trading_checkpoint(risk_context)
            checkpoint.risk_level = risk_level
            checkpoint.reasons = risk_reasons
            requires_human = True

            # Store pending checkpoint
            self.pending_checkpoints[checkpoint.checkpoint_id] = checkpoint

            logger.warning(
                f"🚨 Human approval required for {request.symbol}: "
                f"Risk level {risk_level.value}, reasons: {risk_reasons}"
            )

        return EnhancedGatewayDecision(
            approved=not requires_human,  # Not approved until human approves
            requires_human_approval=requires_human,
            checkpoint=checkpoint,
            risk_level=risk_level,
            risk_reasons=risk_reasons,
            original_decision=original_decision,
            metadata={
                "stage": "checkpoint_created" if requires_human else "auto_approved",
                "risk_context": risk_context
            }
        )

    def _build_risk_context(
        self,
        request,
        additional_context: Optional[dict] = None
    ) -> dict[str, Any]:
        """Build context for risk assessment."""
        context = {
            "symbol": request.symbol,
            "side": request.side,
            "trade_value": request.notional or 0,
            "timestamp": datetime.now().isoformat()
        }

        # Add gateway state
        context["daily_pnl_pct"] = (
            self.gateway.daily_pnl / self._get_account_equity()
            if hasattr(self.gateway, 'daily_pnl') else 0
        )

        # Merge additional context
        if additional_context:
            context.update(additional_context)

        return context

    def _get_account_equity(self) -> float:
        """Get account equity from gateway."""
        if hasattr(self.gateway, '_get_account_equity'):
            return self.gateway._get_account_equity()
        return 100000.0  # Default for paper trading

    async def wait_for_approval(
        self,
        checkpoint_id: str,
        timeout_seconds: int = 300
    ) -> tuple[bool, str]:
        """
        Wait for human approval of a checkpoint.

        Args:
            checkpoint_id: The checkpoint to wait for
            timeout_seconds: Maximum wait time

        Returns:
            Tuple of (approved, reason)
        """
        if checkpoint_id not in self.pending_checkpoints:
            return False, "Checkpoint not found"

        checkpoint = self.pending_checkpoints[checkpoint_id]

        if not self.approval_agent:
            # No approval agent - auto-approve with warning
            logger.warning("No approval agent configured - auto-approving")
            return True, "Auto-approved (no approval agent)"

        # Request approval
        result = self.approval_agent.analyze({
            "type": "request_approval",
            "approval_type": "trade",
            "context": checkpoint.context,
            "priority": "high" if checkpoint.risk_level == RiskLevel.HIGH else "critical",
            "timeout_seconds": timeout_seconds
        })

        if not result.get("approval_required"):
            return True, "Below threshold"

        # Wait for decision
        approval_id = result.get("approval_id")
        if approval_id:
            final_result = await self.approval_agent.wait_for_approval(
                approval_id,
                check_interval=5
            )

            approved = final_result.get("status") == "approved"
            reason = final_result.get("decision", {}).get("reason", "")

            # Update checkpoint
            checkpoint.resolved_at = datetime.now()
            checkpoint.resolution = "approved" if approved else "rejected"

            # Remove from pending
            del self.pending_checkpoints[checkpoint_id]

            return approved, reason

        return False, "Failed to create approval request"

    async def execute_with_recovery(
        self,
        decision: EnhancedGatewayDecision,
        execute_func,
        fallback_funcs: Optional[dict] = None
    ):
        """
        Execute trade with error recovery framework.

        Args:
            decision: The enhanced gateway decision
            execute_func: Function that executes the trade
            fallback_funcs: Optional fallback functions

        Returns:
            Execution result or error
        """
        if not decision.approved:
            return {
                "success": False,
                "error": "Trade not approved",
                "reasons": decision.risk_reasons
            }

        # Use error recovery framework
        success, result, error = await self.error_recovery.execute_with_recovery(
            tool_name="execute_trade",
            tool_func=execute_func,
            fallback_funcs=fallback_funcs,
            decision=decision.original_decision
        )

        if success:
            return {
                "success": True,
                "result": result,
                "risk_level": decision.risk_level.value
            }
        else:
            return {
                "success": False,
                "error": error,
                "risk_level": decision.risk_level.value
            }


def get_enhanced_gateway(gateway=None, approval_agent=None) -> EnhancedTradeGateway:
    """
    Factory function to create enhanced gateway.

    If no gateway provided, creates a new one.
    """
    if gateway is None:
        from src.risk.trade_gateway import TradeGateway
        gateway = TradeGateway(paper=True)

    if approval_agent is None:
        try:
            from src.agents.approval_agent import ApprovalAgent
            approval_agent = ApprovalAgent()
        except ImportError:
            logger.warning("ApprovalAgent not available")

    return EnhancedTradeGateway(gateway, approval_agent)


# Example usage and integration points
async def example_trade_flow():
    """
    Example of the enhanced trade flow with Anthropic patterns.

    This shows how to:
    1. Create enhanced gateway
    2. Evaluate trade with checkpoint
    3. Handle human approval if needed
    4. Execute with error recovery
    """
    from src.risk.trade_gateway import TradeGateway, TradeRequest

    # Create enhanced gateway
    base_gateway = TradeGateway(paper=True)
    enhanced_gateway = get_enhanced_gateway(base_gateway)

    # Create trade request
    request = TradeRequest(
        symbol="NVDA",
        side="buy",
        notional=75.0,  # Above $50 threshold
    )

    # Evaluate with checkpoint
    decision = await enhanced_gateway.evaluate_with_checkpoint(
        request,
        context={
            "consecutive_losses": 2,
            "current_volatility": 1.8,
            "normal_volatility": 1.0
        }
    )

    if decision.requires_human_approval:
        print(f"⚠️ Human approval required: {decision.risk_reasons}")

        # Wait for approval (in real system, this would notify CEO)
        approved, reason = await enhanced_gateway.wait_for_approval(
            decision.checkpoint.checkpoint_id,
            timeout_seconds=300
        )

        if not approved:
            print(f"❌ Trade rejected by human: {reason}")
            return

    # Execute with error recovery
    async def do_trade(decision):
        return base_gateway.execute(decision)

    result = await enhanced_gateway.execute_with_recovery(
        decision,
        do_trade
    )

    print(f"Trade result: {result}")

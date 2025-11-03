"""
Execution Agent - Order Management with Introspection

This agent executes trades with pre-flight validation and introspection
to detect execution issues and validate order parameters.

Key Features:
    - Pre-flight order validation
    - Order parameter checking
    - Execution timing optimization
    - Slippage estimation
    - Post-trade verification

Author: Trading System
Created: 2025-11-03
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class OrderType(Enum):
    """Order type classification."""
    MARKET = "market"
    LIMIT = "limit"
    STOP = "stop"
    STOP_LIMIT = "stop_limit"


class OrderSide(Enum):
    """Order side classification."""
    BUY = "buy"
    SELL = "sell"


@dataclass
class ExecutionIntrospection:
    """Introspection results for execution validation."""
    preflight_passed: bool
    parameter_errors: List[str]
    warnings: List[str]
    estimated_slippage: float
    execution_quality: str


@dataclass
class ExecutionOutput:
    """Output from execution agent."""
    approved: bool
    order_type: OrderType
    order_side: OrderSide
    symbol: str
    quantity: float
    estimated_price: float
    estimated_slippage: float
    introspection: ExecutionIntrospection
    timestamp: datetime
    reason: str


class ExecutionAgent:
    """
    Execution Agent for order management with introspection.

    This agent validates and executes trades with pre-flight checks
    and performs introspection to detect execution issues.

    Attributes:
        max_slippage: Maximum acceptable slippage (fraction)
        min_order_size: Minimum order size in dollars
        max_order_size: Maximum order size in dollars
    """

    MAX_SLIPPAGE = 0.001
    MIN_ORDER_SIZE = 1.0
    MAX_ORDER_SIZE = 100000.0

    def __init__(
        self,
        max_slippage: float = MAX_SLIPPAGE,
        min_order_size: float = MIN_ORDER_SIZE,
        max_order_size: float = MAX_ORDER_SIZE,
    ):
        """
        Initialize the Execution Agent.

        Args:
            max_slippage: Maximum acceptable slippage (fraction)
            min_order_size: Minimum order size in dollars
            max_order_size: Maximum order size in dollars
        """
        self.max_slippage = max_slippage
        self.min_order_size = min_order_size
        self.max_order_size = max_order_size

        logger.info("ExecutionAgent initialized")
        logger.info(f"  Max Slippage: {max_slippage:.2%}")
        logger.info(f"  Min Order Size: ${min_order_size:,.2f}")
        logger.info(f"  Max Order Size: ${max_order_size:,.2f}")

    def validate_execution(
        self,
        signal_output: any,
        risk_output: any,
        current_price: float,
    ) -> ExecutionOutput:
        """
        Validate execution with introspection.

        Args:
            signal_output: Output from signal agent
            risk_output: Output from risk agent
            current_price: Current market price

        Returns:
            ExecutionOutput with validation results
        """
        logger.info("=" * 80)
        logger.info(f"EXECUTION AGENT: Validating Execution for {signal_output.symbol}")
        logger.info("=" * 80)

        if not risk_output.approved:
            logger.warning("Risk agent rejected trade - SKIPPING execution")
            return self._create_rejection(
                signal_output.symbol,
                "Risk agent rejected trade",
            )

        order_side = self._determine_order_side(signal_output)
        if order_side is None:
            logger.warning("No actionable signal - SKIPPING execution")
            return self._create_rejection(
                signal_output.symbol,
                "No actionable signal (HOLD)",
            )

        quantity = risk_output.position_size / current_price

        introspection = self._perform_introspection(
            symbol=signal_output.symbol,
            quantity=quantity,
            price=current_price,
            position_size=risk_output.position_size,
        )

        if not introspection.preflight_passed:
            logger.warning("Pre-flight checks failed - REJECTING execution")
            return self._create_rejection(
                signal_output.symbol,
                "Pre-flight validation failed",
                introspection=introspection,
            )

        order_type = OrderType.MARKET

        reason = self._generate_reason(
            approved=True,
            order_side=order_side,
            quantity=quantity,
            price=current_price,
        )

        output = ExecutionOutput(
            approved=True,
            order_type=order_type,
            order_side=order_side,
            symbol=signal_output.symbol,
            quantity=quantity,
            estimated_price=current_price,
            estimated_slippage=introspection.estimated_slippage,
            introspection=introspection,
            timestamp=datetime.now(),
            reason=reason,
        )

        logger.info("Execution Validation: APPROVED")
        logger.info(
            "Order: %s %.4f shares @ $%.2f",
            order_side.value.upper(), quantity, current_price
        )
        logger.info(f"Estimated Slippage: {introspection.estimated_slippage:.4f}")
        logger.info(f"Execution Quality: {introspection.execution_quality}")

        if introspection.warnings:
            for warning in introspection.warnings:
                logger.warning(f"  ⚠️  {warning}")

        return output

    def _determine_order_side(self, signal_output: any) -> Optional[OrderSide]:
        """
        Determine order side from signal.

        Args:
            signal_output: Output from signal agent

        Returns:
            OrderSide or None if HOLD
        """
        from src.agents.signal_agent import SignalType

        if signal_output.signal == SignalType.BUY:
            return OrderSide.BUY
        elif signal_output.signal == SignalType.SELL:
            return OrderSide.SELL
        else:
            return None

    def _perform_introspection(
        self,
        symbol: str,
        quantity: float,
        price: float,
        position_size: float,
    ) -> ExecutionIntrospection:
        """
        Perform introspection to validate execution parameters.

        This asks:
        - "Are my order parameters valid?"
        - "Is the order size reasonable?"
        - "What's the expected slippage?"

        Args:
            symbol: Symbol to trade
            quantity: Order quantity
            price: Current price
            position_size: Position size in dollars

        Returns:
            ExecutionIntrospection with validation results
        """
        logger.info("🔍 INTROSPECTION: Validating execution parameters...")

        parameter_errors = []
        warnings = []

        if quantity <= 0:
            parameter_errors.append(f"Invalid quantity: {quantity}")

        if price <= 0:
            parameter_errors.append(f"Invalid price: {price}")

        if position_size < self.min_order_size:
            parameter_errors.append(
                f"Order size ${position_size:.2f} below minimum ${self.min_order_size:.2f}"
            )

        if position_size > self.max_order_size:
            parameter_errors.append(
                f"Order size ${position_size:.2f} above maximum ${self.max_order_size:.2f}"
            )

        estimated_slippage = self._estimate_slippage(position_size, price)

        if estimated_slippage > self.max_slippage:
            warnings.append(
                f"High estimated slippage: {estimated_slippage:.4f} > {self.max_slippage:.4f}"
            )

        if quantity < 1.0:
            warnings.append(f"Fractional shares: {quantity:.4f}")

        preflight_passed = len(parameter_errors) == 0

        if preflight_passed:
            if len(warnings) == 0:
                execution_quality = "excellent"
            elif len(warnings) == 1:
                execution_quality = "good"
            else:
                execution_quality = "fair"
        else:
            execution_quality = "failed"

        logger.info(f"  Pre-flight: {'PASSED' if preflight_passed else 'FAILED'}")
        logger.info(f"  Parameter Errors: {len(parameter_errors)}")
        logger.info(f"  Estimated Slippage: {estimated_slippage:.4f}")
        logger.info(f"  Execution Quality: {execution_quality}")

        return ExecutionIntrospection(
            preflight_passed=preflight_passed,
            parameter_errors=parameter_errors,
            warnings=warnings,
            estimated_slippage=estimated_slippage,
            execution_quality=execution_quality,
        )

    def _estimate_slippage(self, position_size: float, price: float) -> float:
        """
        Estimate execution slippage.

        Args:
            position_size: Position size in dollars
            price: Current price

        Returns:
            Estimated slippage as fraction of price
        """
        if position_size < 1000:
            return 0.0001
        elif position_size < 10000:
            return 0.0005
        else:
            return 0.001

    def _create_rejection(
        self,
        symbol: str,
        reason: str,
        introspection: Optional[ExecutionIntrospection] = None,
    ) -> ExecutionOutput:
        """Create a rejection output."""
        if introspection is None:
            introspection = ExecutionIntrospection(
                preflight_passed=False,
                parameter_errors=[reason],
                warnings=[],
                estimated_slippage=0.0,
                execution_quality="failed",
            )

        return ExecutionOutput(
            approved=False,
            order_type=OrderType.MARKET,
            order_side=OrderSide.BUY,
            symbol=symbol,
            quantity=0.0,
            estimated_price=0.0,
            estimated_slippage=0.0,
            introspection=introspection,
            timestamp=datetime.now(),
            reason=f"REJECTED: {reason}",
        )

    def _generate_reason(
        self,
        approved: bool,
        order_side: OrderSide,
        quantity: float,
        price: float,
    ) -> str:
        """Generate human-readable reason for execution decision."""
        if not approved:
            return "REJECTED: Execution validation failed"

        total_value = quantity * price
        return f"APPROVED: {order_side.value.upper()} {quantity:.4f} shares @ ${price:.2f} (${total_value:.2f})"

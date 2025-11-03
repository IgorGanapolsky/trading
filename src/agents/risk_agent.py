"""
Risk Agent - Position Sizing and Circuit Breakers with Introspection

This agent manages risk through position sizing, circuit breakers, and drawdown limits
with introspection to detect excessive risk and validate safety constraints.

Key Features:
    - Dynamic position sizing based on confidence
    - Circuit breakers for max daily loss
    - Drawdown monitoring and limits
    - Risk exposure validation
    - Safety constraint introspection

Author: Trading System
Created: 2025-11-03
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskIntrospection:
    """Introspection results for risk assessment."""
    safety_violations: List[str]
    risk_level: RiskLevel
    exposure_check: bool
    warnings: List[str]
    position_size_adjustment: float


@dataclass
class RiskOutput:
    """Output from risk agent."""
    approved: bool
    position_size: float
    max_loss: float
    risk_level: RiskLevel
    introspection: RiskIntrospection
    timestamp: datetime
    reason: str


class RiskAgent:
    """
    Risk Agent for position sizing and safety with introspection.

    This agent validates trading decisions against risk constraints and
    performs introspection to detect excessive risk and safety violations.

    Attributes:
        max_position_size: Maximum position size as fraction of portfolio
        max_daily_loss: Maximum daily loss as fraction of portfolio
        max_drawdown: Maximum drawdown as fraction of portfolio
        circuit_breaker_enabled: Whether circuit breaker is active
    """

    MAX_POSITION_SIZE = 0.10
    MAX_DAILY_LOSS = 0.02
    MAX_DRAWDOWN = 0.10
    MIN_CONFIDENCE_THRESHOLD = 0.5

    def __init__(
        self,
        max_position_size: float = MAX_POSITION_SIZE,
        max_daily_loss: float = MAX_DAILY_LOSS,
        max_drawdown: float = MAX_DRAWDOWN,
        min_confidence: float = MIN_CONFIDENCE_THRESHOLD,
    ):
        """
        Initialize the Risk Agent.

        Args:
            max_position_size: Maximum position size as fraction of portfolio
            max_daily_loss: Maximum daily loss as fraction of portfolio
            max_drawdown: Maximum drawdown as fraction of portfolio
            min_confidence: Minimum confidence threshold for trades
        """
        self.max_position_size = max_position_size
        self.max_daily_loss = max_daily_loss
        self.max_drawdown = max_drawdown
        self.min_confidence = min_confidence

        self.circuit_breaker_triggered = False
        self.daily_loss = 0.0
        self.last_reset = datetime.now().date()

        logger.info("RiskAgent initialized")
        logger.info(f"  Max Position Size: {max_position_size:.1%}")
        logger.info(f"  Max Daily Loss: {max_daily_loss:.1%}")
        logger.info(f"  Max Drawdown: {max_drawdown:.1%}")
        logger.info(f"  Min Confidence: {min_confidence:.1%}")

    def assess_risk(
        self,
        signal_output: any,
        portfolio_value: float,
        current_positions: Dict[str, float],
        daily_pnl: float,
    ) -> RiskOutput:
        """
        Assess risk and determine position size with introspection.

        Args:
            signal_output: Output from signal agent
            portfolio_value: Current portfolio value
            current_positions: Current positions (symbol -> value)
            daily_pnl: Today's profit/loss

        Returns:
            RiskOutput with approval and position sizing
        """
        logger.info("=" * 80)
        logger.info("RISK AGENT: Assessing Risk")
        logger.info("=" * 80)

        self._reset_daily_counters()

        self.daily_loss = min(0, daily_pnl)

        introspection = self._perform_introspection(
            signal_output=signal_output,
            portfolio_value=portfolio_value,
            current_positions=current_positions,
            daily_pnl=daily_pnl,
        )

        if introspection.safety_violations:
            logger.warning("Safety violations detected - REJECTING trade")
            return self._create_rejection(introspection, "Safety violations detected")

        if self.circuit_breaker_triggered:
            logger.warning("Circuit breaker active - REJECTING trade")
            return self._create_rejection(introspection, "Circuit breaker triggered")

        if signal_output.confidence < self.min_confidence:
            logger.warning(f"Low confidence ({signal_output.confidence:.2f}) - REJECTING trade")
            return self._create_rejection(introspection, "Confidence below threshold")

        base_position_size = self._calculate_base_position_size(
            portfolio_value=portfolio_value,
            confidence=signal_output.confidence,
        )

        adjusted_position_size = base_position_size * (1 + introspection.position_size_adjustment)
        adjusted_position_size = max(0, min(adjusted_position_size, self.max_position_size * portfolio_value))

        max_loss = adjusted_position_size * 0.02

        reason = self._generate_reason(
            approved=True,
            position_size=adjusted_position_size,
            introspection=introspection,
        )

        output = RiskOutput(
            approved=True,
            position_size=adjusted_position_size,
            max_loss=max_loss,
            risk_level=introspection.risk_level,
            introspection=introspection,
            timestamp=datetime.now(),
            reason=reason,
        )

        logger.info(f"Risk Assessment: APPROVED")
        logger.info(f"Position Size: ${adjusted_position_size:,.2f}")
        logger.info(f"Max Loss: ${max_loss:,.2f}")
        logger.info(f"Risk Level: {introspection.risk_level.value}")

        if introspection.warnings:
            for warning in introspection.warnings:
                logger.warning(f"  ⚠️  {warning}")

        return output

    def _reset_daily_counters(self):
        """Reset daily counters if new day."""
        today = datetime.now().date()
        if today > self.last_reset:
            self.daily_loss = 0.0
            self.circuit_breaker_triggered = False
            self.last_reset = today
            logger.debug("Daily counters reset")

    def _perform_introspection(
        self,
        signal_output: any,
        portfolio_value: float,
        current_positions: Dict[str, float],
        daily_pnl: float,
    ) -> RiskIntrospection:
        """
        Perform introspection to detect excessive risk and safety violations.

        This asks:
        - "Am I taking too much risk?"
        - "Are we violating any safety constraints?"
        - "Is our exposure too concentrated?"

        Args:
            signal_output: Output from signal agent
            portfolio_value: Current portfolio value
            current_positions: Current positions
            daily_pnl: Today's profit/loss

        Returns:
            RiskIntrospection with safety checks and warnings
        """
        logger.info("🔍 INTROSPECTION: Checking risk constraints...")

        safety_violations = []
        warnings = []
        position_size_adjustment = 0.0

        daily_loss_pct = abs(self.daily_loss) / portfolio_value if portfolio_value > 0 else 0
        if daily_loss_pct >= self.max_daily_loss:
            safety_violations.append(
                f"Daily loss limit exceeded: {daily_loss_pct:.2%} >= {self.max_daily_loss:.2%}"
            )
            self.circuit_breaker_triggered = True
        elif daily_loss_pct >= self.max_daily_loss * 0.75:
            warnings.append(
                f"Approaching daily loss limit: {daily_loss_pct:.2%} of {self.max_daily_loss:.2%}"
            )
            position_size_adjustment -= 0.5

        total_exposure = sum(abs(v) for v in current_positions.values())
        exposure_pct = total_exposure / portfolio_value if portfolio_value > 0 else 0

        if exposure_pct > 0.5:
            warnings.append(f"High portfolio exposure: {exposure_pct:.1%}")
            position_size_adjustment -= 0.3
            exposure_check = False
        else:
            exposure_check = True

        if hasattr(signal_output, 'introspection'):
            if signal_output.introspection.extreme_conditions:
                warnings.append("Signal agent detected extreme conditions")
                position_size_adjustment -= 0.4

        if signal_output.confidence < 0.6:
            warnings.append(f"Low signal confidence: {signal_output.confidence:.2f}")
            position_size_adjustment -= 0.3

        if safety_violations:
            risk_level = RiskLevel.CRITICAL
        elif len(warnings) >= 3:
            risk_level = RiskLevel.HIGH
        elif len(warnings) >= 1:
            risk_level = RiskLevel.MEDIUM
        else:
            risk_level = RiskLevel.LOW

        logger.info(f"  Risk Level: {risk_level.value}")
        logger.info(f"  Safety Violations: {len(safety_violations)}")
        logger.info(f"  Exposure Check: {exposure_check}")
        logger.info(f"  Position Size Adjustment: {position_size_adjustment:+.2f}")

        return RiskIntrospection(
            safety_violations=safety_violations,
            risk_level=risk_level,
            exposure_check=exposure_check,
            warnings=warnings,
            position_size_adjustment=position_size_adjustment,
        )

    def _calculate_base_position_size(
        self,
        portfolio_value: float,
        confidence: float,
    ) -> float:
        """
        Calculate base position size based on confidence.

        Args:
            portfolio_value: Current portfolio value
            confidence: Signal confidence (0.0 to 1.0)

        Returns:
            Base position size in dollars
        """
        confidence_scaled = (confidence - self.min_confidence) / (1.0 - self.min_confidence)
        confidence_scaled = max(0.0, min(1.0, confidence_scaled))

        size_fraction = self.max_position_size * confidence_scaled

        return portfolio_value * size_fraction

    def _create_rejection(
        self,
        introspection: RiskIntrospection,
        reason: str,
    ) -> RiskOutput:
        """Create a rejection output."""
        return RiskOutput(
            approved=False,
            position_size=0.0,
            max_loss=0.0,
            risk_level=introspection.risk_level,
            introspection=introspection,
            timestamp=datetime.now(),
            reason=f"REJECTED: {reason}",
        )

    def _generate_reason(
        self,
        approved: bool,
        position_size: float,
        introspection: RiskIntrospection,
    ) -> str:
        """Generate human-readable reason for risk decision."""
        if not approved:
            return "REJECTED: Safety constraints violated"

        risk_desc = introspection.risk_level.value.upper()
        return f"APPROVED: ${position_size:,.2f} position ({risk_desc} risk)"

    def update_daily_pnl(self, pnl: float):
        """
        Update daily P&L and check circuit breaker.

        Args:
            pnl: Current daily profit/loss
        """
        self._reset_daily_counters()
        self.daily_loss = min(0, pnl)

        if abs(self.daily_loss) >= self.max_daily_loss * self.max_position_size * 100000:
            self.circuit_breaker_triggered = True
            logger.warning("🚨 CIRCUIT BREAKER TRIGGERED - Trading halted for today")

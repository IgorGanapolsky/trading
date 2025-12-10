"""
Bond Risk Management Module

Provides duration-adjusted risk management for fixed income positions.
Implements:
- DV01 (Dollar Value of 01) limits
- Duration-based stop losses
- Convexity hedging signals
- Bond correlation monitoring

Author: Trading System
Created: 2025-12-03
"""

import logging
import os
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class BondRiskLevel(Enum):
    """Bond portfolio risk levels."""

    LOW = "low"  # Duration < 3, all AAA
    MODERATE = "moderate"  # Duration 3-7, avg AA
    ELEVATED = "elevated"  # Duration 7-12, avg A
    HIGH = "high"  # Duration > 12 or below A


@dataclass
class DurationRiskMetrics:
    """Duration-based risk metrics for a bond position."""

    symbol: str
    duration: float  # Modified duration in years
    dv01: float  # Dollar value of 01 bp rate move
    position_value: float
    duration_contribution: float  # Contribution to portfolio duration
    max_loss_100bp: float  # Estimated loss if rates rise 100bp


@dataclass
class BondRiskAssessment:
    """Overall bond portfolio risk assessment."""

    total_bond_value: float
    portfolio_duration: float
    portfolio_dv01: float
    risk_level: BondRiskLevel
    max_position_pct: float  # Current max single position %
    duration_limit_breach: bool
    correlation_to_equities: float
    recommendations: list[str]
    timestamp: datetime


class BondRiskManager:
    """
    Risk manager for fixed income positions.

    Implements bond-specific risk controls including:
    - Duration limits by yield curve regime
    - DV01 position limits
    - Stop losses adjusted for duration
    - Correlation monitoring with equities
    """

    # Duration limits (years)
    MAX_PORTFOLIO_DURATION = 8.0  # Default max portfolio duration
    MAX_POSITION_DURATION = 20.0  # Single position limit

    # DV01 limits (dollars per $10k portfolio)
    MAX_DV01_PER_10K = 50.0  # Max $50 DV01 per $10k portfolio

    # Allocation limits
    MAX_SINGLE_BOND_PCT = 0.20  # Max 20% in single bond ETF
    MAX_HY_PCT = 0.15  # Max 15% in high yield
    MAX_BOND_TOTAL_PCT = 0.40  # Max 40% total in bonds

    # Stop loss parameters (adjusted for duration)
    BASE_STOP_PCT = 0.03  # 3% base stop for short duration
    DURATION_STOP_MULTIPLIER = 0.002  # Add 0.2% per year of duration

    # Default duration estimates for common bond ETFs
    DURATION_ESTIMATES = {
        "SHY": 1.9,
        "IEF": 7.5,
        "TLT": 16.5,
        "BND": 6.1,
        "AGG": 6.2,
        "LQD": 8.5,
        "VCIT": 6.3,
        "JNK": 3.8,
        "HYG": 3.9,
        "MUB": 6.3,
        "VTEB": 5.6,
        "TIP": 6.5,
        "SCHP": 6.8,
    }

    def __init__(
        self,
        max_portfolio_duration: float | None = None,
        max_bond_allocation: float | None = None,
        max_hy_allocation: float | None = None,
    ):
        """
        Initialize Bond Risk Manager.

        Args:
            max_portfolio_duration: Override default max duration
            max_bond_allocation: Override default max bond allocation
            max_hy_allocation: Override default max high yield allocation
        """
        self.max_portfolio_duration = max_portfolio_duration or float(
            os.getenv("MAX_BOND_DURATION", str(self.MAX_PORTFOLIO_DURATION))
        )
        self.max_bond_allocation = max_bond_allocation or float(
            os.getenv("MAX_BOND_ALLOCATION", str(self.MAX_BOND_TOTAL_PCT))
        )
        self.max_hy_allocation = max_hy_allocation or float(
            os.getenv("MAX_HY_ALLOCATION", str(self.MAX_HY_PCT))
        )

        logger.info(
            f"BondRiskManager initialized: max_duration={self.max_portfolio_duration}, "
            f"max_bonds={self.max_bond_allocation * 100}%, max_hy={self.max_hy_allocation * 100}%"
        )

    def calculate_position_metrics(
        self,
        symbol: str,
        position_value: float,
        portfolio_value: float,
        duration_override: float | None = None,
    ) -> DurationRiskMetrics:
        """
        Calculate duration-based risk metrics for a bond position.

        Args:
            symbol: Bond ETF symbol
            position_value: Current position value in dollars
            portfolio_value: Total portfolio value
            duration_override: Override estimated duration

        Returns:
            DurationRiskMetrics with calculated values
        """
        # Get duration
        duration = duration_override or self.DURATION_ESTIMATES.get(symbol, 5.0)

        # Calculate DV01 (Dollar Value of 1 bp)
        # DV01 = Position Value × Duration × 0.0001
        dv01 = position_value * duration * 0.0001

        # Duration contribution to portfolio
        if portfolio_value > 0:
            position_weight = position_value / portfolio_value
            duration_contribution = duration * position_weight
        else:
            duration_contribution = 0

        # Estimated loss if rates rise 100bp
        max_loss_100bp = position_value * duration * 0.01

        return DurationRiskMetrics(
            symbol=symbol,
            duration=duration,
            dv01=round(dv01, 2),
            position_value=position_value,
            duration_contribution=round(duration_contribution, 3),
            max_loss_100bp=round(max_loss_100bp, 2),
        )

    def calculate_duration_stop_loss(
        self,
        entry_price: float,
        duration: float,
        direction: str = "long",
    ) -> float:
        """
        Calculate duration-adjusted stop loss price.

        Longer duration bonds need wider stops due to higher volatility.

        Args:
            entry_price: Entry price
            duration: Bond/ETF duration in years
            direction: "long" or "short"

        Returns:
            Stop loss price
        """
        # Calculate stop percentage
        # Base 3% + 0.2% per year of duration
        stop_pct = self.BASE_STOP_PCT + (duration * self.DURATION_STOP_MULTIPLIER)

        # Cap at reasonable maximum
        stop_pct = min(stop_pct, 0.10)  # Max 10% stop

        if direction == "long":
            stop_price = entry_price * (1 - stop_pct)
        else:
            stop_price = entry_price * (1 + stop_pct)

        logger.debug(
            f"Duration stop: entry={entry_price:.2f}, duration={duration:.1f}yr, "
            f"stop_pct={stop_pct * 100:.1f}%, stop={stop_price:.2f}"
        )

        return round(stop_price, 2)

    def assess_portfolio_risk(
        self,
        bond_positions: list[dict[str, Any]],
        portfolio_value: float,
        equity_correlation: float | None = None,
    ) -> BondRiskAssessment:
        """
        Assess overall bond portfolio risk.

        Args:
            bond_positions: List of bond position dicts with 'symbol' and 'market_value'
            portfolio_value: Total portfolio value
            equity_correlation: Optional pre-calculated equity correlation

        Returns:
            BondRiskAssessment with recommendations
        """
        if not bond_positions:
            return BondRiskAssessment(
                total_bond_value=0,
                portfolio_duration=0,
                portfolio_dv01=0,
                risk_level=BondRiskLevel.LOW,
                max_position_pct=0,
                duration_limit_breach=False,
                correlation_to_equities=0,
                recommendations=["No bond positions to assess"],
                timestamp=datetime.now(),
            )

        # Calculate portfolio metrics
        total_bond_value = sum(float(pos.get("market_value", 0)) for pos in bond_positions)

        portfolio_duration = 0
        portfolio_dv01 = 0
        max_position_pct = 0
        hy_value = 0

        for pos in bond_positions:
            symbol = pos.get("symbol", "")
            value = float(pos.get("market_value", 0))

            metrics = self.calculate_position_metrics(
                symbol=symbol,
                position_value=value,
                portfolio_value=portfolio_value,
            )

            portfolio_duration += metrics.duration_contribution
            portfolio_dv01 += metrics.dv01

            position_pct = value / portfolio_value if portfolio_value > 0 else 0
            max_position_pct = max(max_position_pct, position_pct)

            # Track high yield
            if symbol in ["JNK", "HYG"]:
                hy_value += value

        # Determine risk level
        if portfolio_duration < 3:
            risk_level = BondRiskLevel.LOW
        elif portfolio_duration < 7:
            risk_level = BondRiskLevel.MODERATE
        elif portfolio_duration < 12:
            risk_level = BondRiskLevel.ELEVATED
        else:
            risk_level = BondRiskLevel.HIGH

        # Check limits
        duration_breach = portfolio_duration > self.max_portfolio_duration

        # Generate recommendations
        recommendations = []

        if duration_breach:
            recommendations.append(
                f"REDUCE DURATION: Portfolio duration {portfolio_duration:.1f}yr "
                f"exceeds limit {self.max_portfolio_duration}yr. "
                "Consider shifting from TLT to SHY/IEF."
            )

        bond_pct = total_bond_value / portfolio_value if portfolio_value > 0 else 0
        if bond_pct > self.max_bond_allocation:
            recommendations.append(
                f"REDUCE BOND ALLOCATION: {bond_pct * 100:.1f}% exceeds "
                f"limit {self.max_bond_allocation * 100}%."
            )

        hy_pct = hy_value / portfolio_value if portfolio_value > 0 else 0
        if hy_pct > self.max_hy_allocation:
            recommendations.append(
                f"REDUCE HIGH YIELD: {hy_pct * 100:.1f}% exceeds "
                f"limit {self.max_hy_allocation * 100}%."
            )

        if max_position_pct > self.MAX_SINGLE_BOND_PCT:
            recommendations.append(
                f"CONCENTRATION RISK: Single position at {max_position_pct * 100:.1f}% "
                f"exceeds limit {self.MAX_SINGLE_BOND_PCT * 100}%."
            )

        # DV01 check
        dv01_per_10k = (portfolio_dv01 / portfolio_value) * 10000 if portfolio_value > 0 else 0
        if dv01_per_10k > self.MAX_DV01_PER_10K:
            recommendations.append(
                f"DV01 RISK: ${dv01_per_10k:.0f} per $10k exceeds limit ${self.MAX_DV01_PER_10K}."
            )

        if not recommendations:
            recommendations.append("Bond portfolio within all risk limits.")

        # Estimate equity correlation (simplified)
        if equity_correlation is None:
            # Treasury bonds typically -0.2 to 0.2 correlation
            # High yield more correlated (0.5+)
            treasury_value = sum(
                float(p.get("market_value", 0))
                for p in bond_positions
                if p.get("symbol") in ["SHY", "IEF", "TLT", "BND", "AGG"]
            )
            if total_bond_value > 0:
                treasury_pct = treasury_value / total_bond_value
                equity_correlation = 0.5 - (treasury_pct * 0.6)  # Rough estimate
            else:
                equity_correlation = 0

        return BondRiskAssessment(
            total_bond_value=round(total_bond_value, 2),
            portfolio_duration=round(portfolio_duration, 2),
            portfolio_dv01=round(portfolio_dv01, 2),
            risk_level=risk_level,
            max_position_pct=round(max_position_pct, 4),
            duration_limit_breach=duration_breach,
            correlation_to_equities=round(equity_correlation, 2),
            recommendations=recommendations,
            timestamp=datetime.now(),
        )

    def validate_bond_trade(
        self,
        symbol: str,
        trade_value: float,
        current_positions: list[dict[str, Any]],
        portfolio_value: float,
    ) -> tuple[bool, str]:
        """
        Validate a proposed bond trade against risk limits.

        Args:
            symbol: Bond ETF symbol
            trade_value: Proposed trade value
            current_positions: Current bond positions
            portfolio_value: Total portfolio value

        Returns:
            Tuple of (is_valid, reason)
        """
        if portfolio_value <= 0:
            return False, "Invalid portfolio value"

        # Get current bond exposure
        current_bond_value = sum(float(pos.get("market_value", 0)) for pos in current_positions)

        # Check total bond allocation after trade
        new_bond_value = current_bond_value + trade_value
        new_bond_pct = new_bond_value / portfolio_value

        if new_bond_pct > self.max_bond_allocation:
            return False, (
                f"Trade would exceed max bond allocation: "
                f"{new_bond_pct * 100:.1f}% > {self.max_bond_allocation * 100}%"
            )

        # Check single position limit
        current_symbol_value = sum(
            float(pos.get("market_value", 0))
            for pos in current_positions
            if pos.get("symbol") == symbol
        )
        new_position_value = current_symbol_value + trade_value
        position_pct = new_position_value / portfolio_value

        if position_pct > self.MAX_SINGLE_BOND_PCT:
            return False, (
                f"Trade would exceed single position limit: "
                f"{position_pct * 100:.1f}% > {self.MAX_SINGLE_BOND_PCT * 100}%"
            )

        # Check high yield limit
        if symbol in ["JNK", "HYG"]:
            current_hy = sum(
                float(pos.get("market_value", 0))
                for pos in current_positions
                if pos.get("symbol") in ["JNK", "HYG"]
            )
            new_hy_pct = (current_hy + trade_value) / portfolio_value

            if new_hy_pct > self.max_hy_allocation:
                return False, (
                    f"Trade would exceed high yield limit: "
                    f"{new_hy_pct * 100:.1f}% > {self.max_hy_allocation * 100}%"
                )

        # Check duration impact
        duration = self.DURATION_ESTIMATES.get(symbol, 5.0)

        current_assessment = self.assess_portfolio_risk(current_positions, portfolio_value)

        new_duration_contribution = (trade_value / portfolio_value) * duration
        projected_duration = current_assessment.portfolio_duration + new_duration_contribution

        if projected_duration > self.max_portfolio_duration:
            return False, (
                f"Trade would breach duration limit: "
                f"{projected_duration:.1f}yr > {self.max_portfolio_duration}yr"
            )

        return True, "Trade validated"

    def get_duration_hedge_recommendation(
        self,
        current_positions: list[dict[str, Any]],
        portfolio_value: float,
        target_duration: float | None = None,
    ) -> dict[str, Any]:
        """
        Get recommendation for adjusting portfolio duration.

        Args:
            current_positions: Current bond positions
            portfolio_value: Total portfolio value
            target_duration: Target portfolio duration (default: max_duration * 0.7)

        Returns:
            Dictionary with hedge recommendation
        """
        if target_duration is None:
            target_duration = self.max_portfolio_duration * 0.7

        assessment = self.assess_portfolio_risk(current_positions, portfolio_value)
        current_duration = assessment.portfolio_duration

        if current_duration <= target_duration:
            return {
                "action": "none",
                "current_duration": current_duration,
                "target_duration": target_duration,
                "message": "Duration within target range",
            }

        # Calculate duration reduction needed
        duration_excess = current_duration - target_duration

        # Recommend shifting from long to short
        recommendations = []

        # Find TLT exposure
        tlt_value = sum(
            float(pos.get("market_value", 0))
            for pos in current_positions
            if pos.get("symbol") == "TLT"
        )

        if tlt_value > 0:
            # Calculate how much TLT to reduce
            # Reducing TLT (16.5yr) and buying SHY (1.9yr) reduces duration by ~14.6yr per dollar
            duration_swing = 16.5 - 1.9  # 14.6 years
            swap_amount = (duration_excess / duration_swing) * portfolio_value

            recommendations.append(
                {
                    "action": "swap",
                    "sell": "TLT",
                    "buy": "SHY",
                    "amount": round(min(swap_amount, tlt_value), 2),
                    "expected_duration_reduction": round(duration_excess, 2),
                }
            )

        return {
            "action": "reduce_duration",
            "current_duration": round(current_duration, 2),
            "target_duration": round(target_duration, 2),
            "duration_excess": round(duration_excess, 2),
            "recommendations": recommendations,
        }


# Test
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    manager = BondRiskManager()

    # Test positions
    test_positions = [
        {"symbol": "SHY", "market_value": 1000},
        {"symbol": "IEF", "market_value": 2000},
        {"symbol": "TLT", "market_value": 1500},
        {"symbol": "LQD", "market_value": 1000},
        {"symbol": "JNK", "market_value": 500},
    ]
    portfolio_value = 100000

    print("\n" + "=" * 80)
    print("BOND RISK ASSESSMENT")
    print("=" * 80)

    assessment = manager.assess_portfolio_risk(test_positions, portfolio_value)

    print(f"\nTotal Bond Value: ${assessment.total_bond_value:,.2f}")
    print(f"Portfolio Duration: {assessment.portfolio_duration:.1f} years")
    print(f"Portfolio DV01: ${assessment.portfolio_dv01:.2f}")
    print(f"Risk Level: {assessment.risk_level.value}")
    print(f"Max Position: {assessment.max_position_pct * 100:.1f}%")
    print(f"Duration Breach: {assessment.duration_limit_breach}")
    print(f"Equity Correlation: {assessment.correlation_to_equities:.2f}")

    print("\nRecommendations:")
    for rec in assessment.recommendations:
        print(f"  - {rec}")

    # Test duration stop
    print("\n" + "-" * 80)
    print("DURATION-ADJUSTED STOP LOSSES")
    print("-" * 80)

    for symbol in ["SHY", "IEF", "TLT"]:
        duration = manager.DURATION_ESTIMATES[symbol]
        entry = 100.0
        stop = manager.calculate_duration_stop_loss(entry, duration)
        pct = ((entry - stop) / entry) * 100
        print(f"{symbol}: Duration {duration:.1f}yr | Entry $100 | Stop ${stop:.2f} ({pct:.1f}%)")

    # Test trade validation
    print("\n" + "-" * 80)
    print("TRADE VALIDATION")
    print("-" * 80)

    valid, reason = manager.validate_bond_trade("TLT", 5000, test_positions, portfolio_value)
    print(f"$5,000 TLT trade: {'VALID' if valid else 'REJECTED'} - {reason}")

    valid, reason = manager.validate_bond_trade("JNK", 20000, test_positions, portfolio_value)
    print(f"$20,000 JNK trade: {'VALID' if valid else 'REJECTED'} - {reason}")

    print("\n" + "=" * 80)

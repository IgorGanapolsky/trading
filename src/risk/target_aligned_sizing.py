"""
Target-Aligned Position Sizing

Position sizing aligned with the $100/day profit target.
This module computes position sizes that balance capital efficiency
with risk constraints to maximize probability of hitting target.

Includes slippage-aware adjustments to prevent over-sizing in illiquid assets.

Author: Trading System
Created: 2025-12-03
Updated: 2025-12-04 - Added slippage model integration
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Optional

from src.risk.slippage_model import SlippageModel, SlippageModelType, get_default_slippage_model

logger = logging.getLogger(__name__)


@dataclass
class PositionSizeResult:
    """Result of position sizing calculation."""

    shares: float
    notional: float
    risk_per_share: float
    total_risk: float
    position_pct: float
    expected_profit: float
    profit_to_target_pct: float
    sizing_method: str
    confidence: float
    notes: list[str]
    slippage_cost_pct: float = 0.0  # Estimated round-trip slippage cost
    slippage_adjusted: bool = False  # Whether size was reduced for slippage

    def to_dict(self) -> dict[str, Any]:
        return {
            "shares": round(self.shares, 4),
            "notional": round(self.notional, 2),
            "risk_per_share": round(self.risk_per_share, 4),
            "total_risk": round(self.total_risk, 2),
            "position_pct": round(self.position_pct, 4),
            "expected_profit": round(self.expected_profit, 2),
            "profit_to_target_pct": round(self.profit_to_target_pct, 2),
            "sizing_method": self.sizing_method,
            "confidence": round(self.confidence, 2),
            "notes": self.notes,
            "slippage_cost_pct": round(self.slippage_cost_pct, 4),
            "slippage_adjusted": self.slippage_adjusted,
        }


class TargetAlignedSizer:
    """
    Position sizer that optimizes for the $100/day target.

    This sizer:
    - Calculates sizes based on target profit contribution
    - Applies Kelly-inspired sizing with volatility adjustment
    - Enforces daily loss limits aligned with target recovery
    - Supports multiple position types (equity, options)
    """

    def __init__(
        self,
        capital: float = 10000.0,
        daily_target: float = 100.0,
        max_position_pct: float = 0.15,
        max_daily_risk_pct: float = 0.03,
        min_position_pct: float = 0.02,
        avg_trades_per_day: int = 1,
        target_win_rate: float = 0.55,
        avg_win_loss_ratio: float = 1.5,
        slippage_model: Optional[SlippageModel] = None,
        max_slippage_pct: float = 1.0,  # Max acceptable round-trip slippage
    ):
        """
        Initialize the target-aligned sizer.

        Args:
            capital: Trading capital
            daily_target: Daily profit target ($100)
            max_position_pct: Max position as % of capital
            max_daily_risk_pct: Max daily loss allowed
            min_position_pct: Minimum position size to bother with
            avg_trades_per_day: Expected trades per day
            target_win_rate: Target win rate (55%)
            avg_win_loss_ratio: Average win / average loss
            slippage_model: SlippageModel instance for cost estimation
            max_slippage_pct: Maximum acceptable slippage (reduces size above this)
        """
        self.capital = capital
        self.daily_target = daily_target
        self.max_position_pct = max_position_pct
        self.max_daily_risk_pct = max_daily_risk_pct
        self.min_position_pct = min_position_pct
        self.avg_trades_per_day = max(1, avg_trades_per_day)
        self.target_win_rate = target_win_rate
        self.avg_win_loss_ratio = avg_win_loss_ratio
        self.max_slippage_pct = max_slippage_pct

        # Initialize slippage model
        self.slippage_model = slippage_model or get_default_slippage_model()
        logger.info("Slippage model integrated into position sizing")

        # Daily tracking
        self._daily_exposure = 0.0
        self._daily_risk_taken = 0.0
        self._trades_today = 0

        # Derived constraints
        self._max_position_value = capital * max_position_pct
        self._max_daily_loss = capital * max_daily_risk_pct
        self._per_trade_target = daily_target / avg_trades_per_day

    def reset_daily(self) -> None:
        """Reset daily tracking counters."""
        self._daily_exposure = 0.0
        self._daily_risk_taken = 0.0
        self._trades_today = 0
        logger.debug("Daily sizer counters reset")

    def calculate_size(
        self,
        symbol: str,
        entry_price: float,
        stop_loss_price: float | None = None,
        take_profit_price: float | None = None,
        volatility: float | None = None,
        signal_strength: float = 0.5,
        rl_confidence: float = 0.5,
        sentiment_score: float = 0.0,
        avg_daily_volume: float | None = None,
    ) -> PositionSizeResult:
        """
        Calculate optimal position size for a trade.

        Args:
            symbol: Ticker symbol
            entry_price: Entry price
            stop_loss_price: Stop loss price (optional, will estimate if not provided)
            take_profit_price: Target price (optional)
            volatility: Historical volatility (optional)
            signal_strength: Signal strength from strategy (0-1)
            rl_confidence: RL model confidence (0-1)
            sentiment_score: Sentiment score (-1 to 1)
            avg_daily_volume: Average daily volume for slippage calculation

        Returns:
            PositionSizeResult with recommended sizing (slippage-adjusted)
        """
        notes = []
        slippage_adjusted = False
        slippage_cost_pct = 0.0

        if entry_price <= 0:
            return self._empty_result("Invalid entry price")

        # Estimate stop loss if not provided
        if stop_loss_price is None:
            stop_loss_pct = volatility * 2 if volatility else 0.02
            stop_loss_price = entry_price * (1 - stop_loss_pct)
            notes.append(f"Estimated stop at {stop_loss_pct * 100:.1f}%")

        # Calculate risk per share
        risk_per_share = abs(entry_price - stop_loss_price)

        if risk_per_share <= 0:
            return self._empty_result("No risk per share calculated")

        # Calculate potential reward
        if take_profit_price:
            reward_per_share = abs(take_profit_price - entry_price)
        else:
            reward_per_share = risk_per_share * self.avg_win_loss_ratio
            notes.append(f"Estimated reward at {self.avg_win_loss_ratio}x risk")

        # Method 1: Target-based sizing
        # What size gives us the per-trade target profit (assuming win)?
        target_based_shares = (
            self._per_trade_target / reward_per_share if reward_per_share > 0 else 0
        )

        # Method 2: Risk-based sizing (2% rule)
        # Max risk = 2% of capital, so shares = max_risk / risk_per_share
        max_risk = self._max_daily_loss / self.avg_trades_per_day
        risk_based_shares = max_risk / risk_per_share

        # Method 3: Kelly-based sizing
        kelly_fraction = self._calculate_kelly(
            win_prob=self._estimate_win_prob(signal_strength, rl_confidence, sentiment_score),
            win_loss_ratio=reward_per_share / risk_per_share if risk_per_share > 0 else 1.0,
        )
        kelly_notional = self.capital * kelly_fraction
        kelly_based_shares = kelly_notional / entry_price if entry_price > 0 else 0

        # Blend methods with confidence weighting
        blended_confidence = (
            signal_strength * 0.4 + rl_confidence * 0.4 + (sentiment_score + 1) / 2 * 0.2
        )

        if blended_confidence > 0.7:
            # High confidence: weight toward target-based (aggressive)
            shares = target_based_shares * 0.6 + kelly_based_shares * 0.3 + risk_based_shares * 0.1
            method = "target_weighted"
        elif blended_confidence > 0.5:
            # Medium confidence: balanced approach
            shares = kelly_based_shares * 0.5 + risk_based_shares * 0.3 + target_based_shares * 0.2
            method = "balanced"
        else:
            # Low confidence: conservative (risk-based)
            shares = risk_based_shares * 0.7 + kelly_based_shares * 0.3
            method = "risk_weighted"
            notes.append("Low confidence - conservative sizing")

        # SLIPPAGE ADJUSTMENT (new Dec 2025)
        # Estimate slippage and reduce position size if too costly
        slippage_cost_pct = self.slippage_model.estimate_round_trip_cost(
            price=entry_price,
            quantity=shares,
            symbol=symbol,
            volume=avg_daily_volume,
            volatility=volatility,
        )

        # If slippage exceeds threshold, reduce position size proportionally
        if slippage_cost_pct > self.max_slippage_pct:
            # Reduce position to bring slippage within acceptable range
            reduction_factor = self.max_slippage_pct / slippage_cost_pct
            original_shares = shares
            shares = shares * reduction_factor
            slippage_adjusted = True
            notes.append(
                f"Slippage-adjusted: {slippage_cost_pct:.2f}% > {self.max_slippage_pct}% max, "
                f"reduced from {original_shares:.2f} to {shares:.2f} shares"
            )
            logger.info(
                f"{symbol}: Position reduced {(1 - reduction_factor) * 100:.1f}% due to slippage "
                f"({slippage_cost_pct:.2f}% estimated round-trip cost)"
            )
        elif slippage_cost_pct > 0.5:
            # Warn about significant but acceptable slippage
            notes.append(f"Slippage warning: {slippage_cost_pct:.2f}% round-trip cost")

        # Apply constraints
        notional = shares * entry_price

        # Max position constraint
        if notional > self._max_position_value:
            shares = self._max_position_value / entry_price
            notional = self._max_position_value
            notes.append("Capped at max position size")

        # Min position constraint
        min_notional = self.capital * self.min_position_pct
        if notional < min_notional:
            return self._empty_result(f"Position too small: ${notional:.2f} < ${min_notional:.2f}")

        # Daily exposure constraint
        remaining_capacity = self.capital - self._daily_exposure
        if notional > remaining_capacity:
            shares = remaining_capacity / entry_price
            notional = remaining_capacity
            notes.append(f"Reduced due to daily exposure limit (${self._daily_exposure:.2f} used)")

        # Daily risk constraint
        remaining_risk = self._max_daily_loss - self._daily_risk_taken
        trade_risk = shares * risk_per_share
        if trade_risk > remaining_risk:
            shares = remaining_risk / risk_per_share
            notional = shares * entry_price
            trade_risk = remaining_risk
            notes.append(f"Reduced due to daily risk limit (${self._daily_risk_taken:.2f} risked)")

        # Final calculations
        expected_profit = shares * reward_per_share * self.target_win_rate
        profit_to_target_pct = (
            (expected_profit / self.daily_target) * 100 if self.daily_target > 0 else 0
        )
        position_pct = notional / self.capital if self.capital > 0 else 0

        # Update tracking
        self._daily_exposure += notional
        self._daily_risk_taken += trade_risk
        self._trades_today += 1

        return PositionSizeResult(
            shares=shares,
            notional=notional,
            risk_per_share=risk_per_share,
            total_risk=trade_risk,
            position_pct=position_pct,
            expected_profit=expected_profit,
            profit_to_target_pct=profit_to_target_pct,
            sizing_method=method,
            confidence=blended_confidence,
            notes=notes,
            slippage_cost_pct=slippage_cost_pct,
            slippage_adjusted=slippage_adjusted,
        )

    def _calculate_kelly(self, win_prob: float, win_loss_ratio: float) -> float:
        """Calculate Kelly fraction with caps."""
        if win_prob <= 0 or win_loss_ratio <= 0:
            return 0.0

        # Kelly: f* = (bp - q) / b
        # where b = win/loss ratio, p = win prob, q = 1-p
        b = win_loss_ratio
        p = win_prob
        q = 1 - p

        kelly = (b * p - q) / b

        # Cap at 15% (half-Kelly is often recommended)
        kelly = max(0.0, min(0.15, kelly * 0.5))

        return kelly

    def _estimate_win_prob(
        self,
        signal_strength: float,
        rl_confidence: float,
        sentiment_score: float,
    ) -> float:
        """Estimate win probability from signals."""
        # Base win rate
        base = self.target_win_rate

        # Adjust based on signals (each can add/subtract up to 10%)
        adjustment = 0.0
        adjustment += (signal_strength - 0.5) * 0.2  # +/- 10%
        adjustment += (rl_confidence - 0.5) * 0.15  # +/- 7.5%
        adjustment += sentiment_score * 0.05  # +/- 5%

        win_prob = base + adjustment

        # Clamp to reasonable range
        return max(0.35, min(0.75, win_prob))

    def _empty_result(self, reason: str) -> PositionSizeResult:
        """Return an empty result with reason."""
        logger.debug(f"Position sizing rejected: {reason}")
        return PositionSizeResult(
            shares=0.0,
            notional=0.0,
            risk_per_share=0.0,
            total_risk=0.0,
            position_pct=0.0,
            expected_profit=0.0,
            profit_to_target_pct=0.0,
            sizing_method="rejected",
            confidence=0.0,
            notes=[reason],
        )

    def get_daily_status(self) -> dict[str, Any]:
        """Get current daily status."""
        return {
            "capital": self.capital,
            "daily_target": self.daily_target,
            "trades_today": self._trades_today,
            "daily_exposure": round(self._daily_exposure, 2),
            "exposure_pct": round((self._daily_exposure / self.capital) * 100, 2),
            "daily_risk_taken": round(self._daily_risk_taken, 2),
            "risk_taken_pct": round((self._daily_risk_taken / self._max_daily_loss) * 100, 2),
            "remaining_capacity": round(self.capital - self._daily_exposure, 2),
            "remaining_risk_budget": round(self._max_daily_loss - self._daily_risk_taken, 2),
        }


class DailyLossLimiter:
    """
    Enforces daily loss limits with progressive circuit breakers.

    Levels:
    - Level 1 (1.5% loss): Reduce position sizes by 50%
    - Level 2 (2.5% loss): Only allow exits, no new entries
    - Level 3 (3% loss): Halt all trading for the day
    """

    def __init__(
        self,
        capital: float = 10000.0,
        level1_pct: float = 1.5,
        level2_pct: float = 2.5,
        level3_pct: float = 3.0,
    ):
        self.capital = capital
        self.level1_threshold = capital * (level1_pct / 100)
        self.level2_threshold = capital * (level2_pct / 100)
        self.level3_threshold = capital * (level3_pct / 100)

        self._daily_loss = 0.0
        self._current_level = 0
        self._halted = False

    def record_pnl(self, pnl: float) -> int:
        """
        Record P&L and return current circuit breaker level.

        Returns:
            0 = No limit, 1 = Reduced sizing, 2 = Exits only, 3 = Halted
        """
        self._daily_loss -= pnl  # Loss is positive

        if self._daily_loss >= self.level3_threshold:
            self._current_level = 3
            self._halted = True
            logger.warning(
                f"CIRCUIT BREAKER LEVEL 3: Trading halted (loss: ${self._daily_loss:.2f})"
            )
        elif self._daily_loss >= self.level2_threshold:
            self._current_level = 2
            logger.warning(f"CIRCUIT BREAKER LEVEL 2: Exits only (loss: ${self._daily_loss:.2f})")
        elif self._daily_loss >= self.level1_threshold:
            self._current_level = 1
            logger.warning(
                f"CIRCUIT BREAKER LEVEL 1: Reduced sizing (loss: ${self._daily_loss:.2f})"
            )
        else:
            self._current_level = 0

        return self._current_level

    def can_enter_position(self) -> bool:
        """Check if new positions are allowed."""
        return self._current_level < 2

    def can_trade(self) -> bool:
        """Check if any trading is allowed."""
        return not self._halted

    def get_size_multiplier(self) -> float:
        """Get position size multiplier based on current level."""
        if self._current_level >= 2:
            return 0.0
        elif self._current_level == 1:
            return 0.5
        return 1.0

    def reset_daily(self) -> None:
        """Reset for new trading day."""
        self._daily_loss = 0.0
        self._current_level = 0
        self._halted = False
        logger.info("Daily loss limiter reset")

    def get_status(self) -> dict[str, Any]:
        """Get current status."""
        return {
            "daily_loss": round(self._daily_loss, 2),
            "current_level": self._current_level,
            "halted": self._halted,
            "can_enter": self.can_enter_position(),
            "can_trade": self.can_trade(),
            "size_multiplier": self.get_size_multiplier(),
            "thresholds": {
                "level1": round(self.level1_threshold, 2),
                "level2": round(self.level2_threshold, 2),
                "level3": round(self.level3_threshold, 2),
            },
        }


# Convenience function for integration
def create_target_aligned_sizer(
    capital: float | None = None,
    daily_target: float = 100.0,
) -> TargetAlignedSizer:
    """Create a target-aligned sizer with defaults."""
    if capital is None:
        capital = float(os.getenv("ACCOUNT_EQUITY", "10000"))

    return TargetAlignedSizer(
        capital=capital,
        daily_target=daily_target,
        max_position_pct=float(os.getenv("MAX_POSITION_PCT", "0.15")),
        max_daily_risk_pct=float(os.getenv("MAX_DAILY_RISK_PCT", "0.03")),
    )

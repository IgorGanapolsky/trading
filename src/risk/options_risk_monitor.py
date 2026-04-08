"""Options Risk Monitor - Monitors options positions for risk.

Implements CLAUDE.md trading rules:
- Stop-loss: Close at 1x credit received ($60 max loss for $60 credit)
- For credit spreads: Close when spread value rises to 2x entry credit
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

from src.core.trading_constants import IC_PROFIT_TARGET_PCT, IRON_CONDOR_STOP_LOSS_MULTIPLIER

logger = logging.getLogger(__name__)

# Default stop-loss multiplier: close when loss = 1x credit received.
DEFAULT_STOP_LOSS_MULTIPLIER = IRON_CONDOR_STOP_LOSS_MULTIPLIER

# All credit-based strategy types subject to stop-loss / profit-target monitoring.
MONITORED_POSITION_TYPES = {"credit_spread", "iron_condor", "bull_put_spread", "bear_call_spread"}

# Canonical profit target from trading_constants (single source of truth)
DEFAULT_PROFIT_TARGET_PCT = IC_PROFIT_TARGET_PCT


@dataclass
class OptionsPosition:
    """Represents an options position for risk monitoring."""

    symbol: str  # OCC option symbol
    underlying: str  # Underlying stock symbol
    position_type: str  # 'covered_call', 'credit_spread', 'iron_condor', etc.
    side: Literal["long", "short"]
    quantity: int
    entry_price: float  # For credit spreads: the credit received per share
    current_price: float  # Current spread value (cost to close)
    delta: float
    gamma: float
    theta: float
    vega: float
    expiration_date: date
    strike: float
    opened_at: datetime
    credit_received: float = field(default=0.0)  # Total credit received for the spread


class OptionsRiskMonitor:
    """Monitors risk for options positions.

    Implements the 1x credit stop-loss rule from canonical trading constants:
    - Credit received: ~$60 per spread
    - Stop-loss trigger: When loss reaches 1x credit ($60)
    - Close when spread value rises to 2x entry credit ($120)
    """

    def __init__(
        self,
        max_loss_percent: float = 5.0,
        stop_loss_multiplier: float = DEFAULT_STOP_LOSS_MULTIPLIER,
        profit_target_pct: float = DEFAULT_PROFIT_TARGET_PCT,
        paper: bool = True,
    ):
        """Initialize the options risk monitor.

        Args:
            max_loss_percent: Maximum loss as percent of portfolio (default 5%)
            stop_loss_multiplier: Close position when loss = multiplier * credit (default 1.0)
            profit_target_pct: Close at this % of max profit (default 0.50 = 50%)
            paper: Paper trading mode (default True)
        """
        self.max_loss_percent = max_loss_percent
        self.stop_loss_multiplier = stop_loss_multiplier
        self.profit_target_pct = profit_target_pct
        self.paper = paper
        self.positions: dict = {}

    def add_position(
        self, position: OptionsPosition | dict, position_data: dict | None = None
    ) -> None:
        """Track an options position.

        Args:
            position: Either an OptionsPosition object or a symbol string (for backwards compat)
            position_data: Position data dict (only used if position is a string)
        """
        if isinstance(position, OptionsPosition):
            self.positions[position.symbol] = position
        else:
            # Backwards compatibility: position is symbol string
            self.positions[position] = position_data

    def remove_position(self, symbol: str) -> None:
        """Stop tracking a position."""
        self.positions.pop(symbol, None)

    def check_risk(self, symbol: str) -> dict:
        """Check risk status for a position.

        Returns dict with:
        - status: 'ok', 'warning', 'critical', or 'unknown'
        - message: Human-readable status message
        - current_loss: Current unrealized loss (positive = loss)
        - max_loss: Maximum allowed loss before stop-loss triggers
        - loss_ratio: current_loss / max_loss (1.0 = at stop-loss)
        """
        position = self.positions.get(symbol)
        if not position:
            return {"status": "unknown", "message": "Position not found"}

        # Handle both OptionsPosition objects and legacy dict format
        if isinstance(position, OptionsPosition):
            entry_price = position.entry_price
            current_price = position.current_price
            position_type = position.position_type
            credit = position.credit_received or entry_price
        else:
            # Legacy dict format
            entry_price = position.get("entry_price", 0)
            current_price = position.get("current_price", 0)
            position_type = position.get("position_type", "unknown")
            credit = position.get("credit_received", entry_price)

        # Calculate loss for credit-based strategies
        # For credit positions: we received credit, loss = current_price - entry_price
        if position_type in MONITORED_POSITION_TYPES:
            current_loss = max(0, current_price - entry_price)
            max_loss = credit * self.stop_loss_multiplier
            loss_ratio = current_loss / max_loss if max_loss > 0 else 0

            if loss_ratio >= 1.0:
                status = "critical"
                message = f"STOP-LOSS TRIGGERED: Loss ${current_loss:.2f} >= {self.stop_loss_multiplier}x credit ${max_loss:.2f}"
            elif loss_ratio >= 0.75:
                status = "warning"
                message = (
                    f"Approaching stop-loss: Loss ${current_loss:.2f} ({loss_ratio:.0%} of max)"
                )
            else:
                status = "ok"
                message = (
                    f"Position within limits: Loss ${current_loss:.2f} ({loss_ratio:.0%} of max)"
                )

            return {
                "status": status,
                "symbol": symbol,
                "message": message,
                "current_loss": current_loss,
                "max_loss": max_loss,
                "loss_ratio": loss_ratio,
                "entry_price": entry_price,
                "current_price": current_price,
            }

        # Default for non-credit-spread positions
        return {
            "status": "ok",
            "symbol": symbol,
            "message": "Position type not monitored for stop-loss",
            "current_risk": 0.0,
            "max_allowed": self.max_loss_percent,
        }

    def get_total_exposure(self) -> float:
        """Get total options exposure."""
        total = 0.0
        for p in self.positions.values():
            if isinstance(p, OptionsPosition):
                # Use current price * quantity * 100 (options multiplier)
                total += abs(p.current_price * p.quantity * 100)
            elif isinstance(p, dict):
                total += p.get("value", 0)
        return total

    def should_close_position(self, symbol: str) -> tuple[bool, str]:
        """Determine if position should be closed for risk.

        Implements credit stop-loss rule:
        - For credit spreads: Close when loss reaches stop_loss_multiplier * credit
        - Default 1.0x: $60 credit -> close when loss = $60 (spread value = $120)

        Returns:
            tuple[bool, str]: (should_close, reason)
        """
        position = self.positions.get(symbol)
        if not position:
            return False, "Position not found"

        # Handle both OptionsPosition objects and legacy dict format
        if isinstance(position, OptionsPosition):
            entry_price = position.entry_price
            current_price = position.current_price
            position_type = position.position_type
            credit = position.credit_received or entry_price
        else:
            # Legacy dict format
            entry_price = position.get("entry_price", 0)
            current_price = position.get("current_price", 0)
            position_type = position.get("position_type", "unknown")
            credit = position.get("credit_received", entry_price)

        # Only apply exit rules to credit-based strategies
        if position_type not in MONITORED_POSITION_TYPES:
            return False, f"Position type '{position_type}' not subject to exit rules"

        # ============================================================
        # PROFIT EXIT (75% target for positive EV)
        # ============================================================
        # For credit spread: profit = entry_price - current_price (credit received - cost to close)
        current_profit = entry_price - current_price
        profit_target = credit * self.profit_target_pct

        if current_profit >= profit_target:
            pct_label = f"{self.profit_target_pct:.0%}"
            logger.info(
                f"🎯 {pct_label} PROFIT TARGET HIT for {symbol}: "
                f"Profit ${current_profit:.2f} >= target ${profit_target:.2f}"
            )
            return True, (
                f"{pct_label} profit target reached: "
                f"Profit ${current_profit:.2f} >= target ${profit_target:.2f} "
                f"(entry=${entry_price:.2f}, current=${current_price:.2f}, close for profit!)"
            )

        # ============================================================
        # STOP-LOSS CHECK (1x credit for positive EV)
        # ============================================================
        # For credit spread: loss = current_price - entry_price (cost to close - credit received)
        current_loss = current_price - entry_price

        # Calculate max allowed loss
        max_loss = credit * self.stop_loss_multiplier
        mult_label = f"{self.stop_loss_multiplier}x"

        # Check if stop-loss should trigger
        if current_loss >= max_loss:
            logger.warning(
                f"STOP-LOSS TRIGGERED for {symbol}: "
                f"Loss ${current_loss:.2f} >= {mult_label} credit ${max_loss:.2f}"
            )
            return True, (
                f"{mult_label} credit stop-loss triggered: "
                f"Loss ${current_loss:.2f} >= max ${max_loss:.2f} "
                f"(entry=${entry_price:.2f}, current=${current_price:.2f})"
            )

        # Position is still within risk limits
        remaining = max_loss - current_loss
        return False, (
            f"Position within risk limits: "
            f"Loss ${current_loss:.2f} / max ${max_loss:.2f} "
            f"(${remaining:.2f} remaining before stop-loss)"
        )

    def update_position_price(self, symbol: str, new_price: float) -> bool:
        """Update the current price for a tracked position.

        Args:
            symbol: The position symbol to update
            new_price: The new current price (cost to close)

        Returns:
            bool: True if position was found and updated
        """
        position = self.positions.get(symbol)
        if not position:
            return False

        if isinstance(position, OptionsPosition):
            # Create a new position with updated price (dataclass is immutable by default)
            self.positions[symbol] = OptionsPosition(
                symbol=position.symbol,
                underlying=position.underlying,
                position_type=position.position_type,
                side=position.side,
                quantity=position.quantity,
                entry_price=position.entry_price,
                current_price=new_price,  # Updated
                delta=position.delta,
                gamma=position.gamma,
                theta=position.theta,
                vega=position.vega,
                expiration_date=position.expiration_date,
                strike=position.strike,
                opened_at=position.opened_at,
                credit_received=position.credit_received,
            )
        else:
            # Legacy dict format
            position["current_price"] = new_price

        return True

    def run_risk_check(
        self, current_prices: dict | None = None, executor: object | None = None
    ) -> dict:
        """Run comprehensive risk check on all tracked positions.

        This is the main entry point for portfolio-wide risk monitoring.
        Checks all positions for stop-loss triggers and profit targets.

        Args:
            current_prices: Optional dict mapping symbols to current prices.
                           If provided, position prices will be updated before checking.
            executor: Optional executor object (not currently used, for interface compat)

        Returns:
            Dict with:
            - positions_checked: Number of positions evaluated
            - stop_loss_exits: List of positions that hit stop-loss
            - profit_exits: List of positions that hit profit target
            - delta_analysis: Dict with net_delta and rebalance_needed
            - position_results: Detailed results for each position
        """
        # Update prices if provided
        if current_prices:
            for symbol, price in current_prices.items():
                self.update_position_price(symbol, price)

        stop_loss_exits = []
        profit_exits = []
        position_results = []
        total_delta = 0.0

        for symbol in list(self.positions.keys()):
            # Check if position should be closed
            should_close, reason = self.should_close_position(symbol)

            # Get detailed risk status
            risk_status = self.check_risk(symbol)

            # Track delta for rebalancing
            position = self.positions.get(symbol)
            if isinstance(position, OptionsPosition):
                total_delta += position.delta * position.quantity * 100

            result = {
                "symbol": symbol,
                "risk_status": risk_status,
                "should_close": should_close,
                "reason": reason,
            }
            position_results.append(result)

            if should_close:
                if "profit" in reason.lower():
                    profit_exits.append({"symbol": symbol, "reason": reason})
                else:
                    stop_loss_exits.append({"symbol": symbol, "reason": reason})

        # Delta rebalancing: flag if net delta is too high (>60 or <-60)
        rebalance_needed = abs(total_delta) > 60

        return {
            "positions_checked": len(self.positions),
            "stop_loss_exits": stop_loss_exits,
            "profit_exits": profit_exits,
            "delta_analysis": {
                "net_delta": total_delta,
                "rebalance_needed": rebalance_needed,
            },
            "position_results": position_results,
        }

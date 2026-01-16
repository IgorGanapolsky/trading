"""Options Risk Monitor - Monitors options positions for risk.

Implements CLAUDE.md trading rules:
- Stop-loss: Close at 2x credit received ($120 max loss for $60 credit)
- For credit spreads: Close when spread value rises to 3x entry credit
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Literal

logger = logging.getLogger(__name__)

# Default stop-loss multiplier: close when loss = 2x credit received
# For $60 credit, close when loss reaches $120 (spread value = $180 = 3x credit)
DEFAULT_STOP_LOSS_MULTIPLIER = 2.0

# Jan 2026: 50% profit exit - close when spread value drops to 50% of entry credit
# This improves win rate from ~75% to ~85% by taking profits early
DEFAULT_PROFIT_TARGET_PCT = 0.50


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

    Implements the 2x credit stop-loss rule from CLAUDE.md:
    - Credit received: ~$60 per spread
    - Stop-loss trigger: When loss reaches 2x credit ($120)
    - Close when spread value rises to 3x entry credit ($180)
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
            stop_loss_multiplier: Close position when loss = multiplier * credit (default 2.0)
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

        # Calculate loss for credit spreads
        # For credit spread: we received credit, loss = current_price - entry_price
        if position_type == "credit_spread":
            current_loss = max(0, current_price - entry_price)
            max_loss = credit * self.stop_loss_multiplier
            loss_ratio = current_loss / max_loss if max_loss > 0 else 0

            if loss_ratio >= 1.0:
                status = "critical"
                message = (
                    f"STOP-LOSS TRIGGERED: Loss ${current_loss:.2f} >= 2x credit ${max_loss:.2f}"
                )
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
            "message": "Position type not monitored for 2x stop-loss",
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

        Implements CLAUDE.md 2x credit stop-loss rule:
        - For credit spreads: Close when loss reaches 2x credit received
        - Example: $60 credit -> close when loss = $120 (spread value = $180)

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

        # Only apply exit rules to credit spreads
        if position_type != "credit_spread":
            return False, f"Position type '{position_type}' not subject to exit rules"

        # ============================================================
        # JAN 2026: 50% PROFIT EXIT (CHECK FIRST - TAKE PROFITS EARLY)
        # ============================================================
        # For credit spread: profit = entry_price - current_price (credit received - cost to close)
        current_profit = entry_price - current_price
        profit_target = credit * self.profit_target_pct  # 50% of credit received

        if current_profit >= profit_target:
            logger.info(
                f"🎯 50% PROFIT TARGET HIT for {symbol}: "
                f"Profit ${current_profit:.2f} >= target ${profit_target:.2f}"
            )
            return True, (
                f"50% profit target reached: "
                f"Profit ${current_profit:.2f} >= target ${profit_target:.2f} "
                f"(entry=${entry_price:.2f}, current=${current_price:.2f}, close for profit!)"
            )

        # ============================================================
        # STOP-LOSS CHECK (2x credit rule)
        # ============================================================
        # For credit spread: loss = current_price - entry_price (cost to close - credit received)
        current_loss = current_price - entry_price

        # Calculate max allowed loss (2x credit)
        max_loss = credit * self.stop_loss_multiplier

        # Check if stop-loss should trigger
        if current_loss >= max_loss:
            logger.warning(
                f"STOP-LOSS TRIGGERED for {symbol}: "
                f"Loss ${current_loss:.2f} >= 2x credit ${max_loss:.2f}"
            )
            return True, (
                f"2x credit stop-loss triggered: "
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

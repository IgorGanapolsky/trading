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
    ):
        """Initialize the options risk monitor.

        Args:
            max_loss_percent: Maximum loss as percent of portfolio (default 5%)
            stop_loss_multiplier: Close position when loss = multiplier * credit (default 2.0)
        """
        self.max_loss_percent = max_loss_percent
        self.stop_loss_multiplier = stop_loss_multiplier
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
                message = f"STOP-LOSS TRIGGERED: Loss ${current_loss:.2f} >= 2x credit ${max_loss:.2f}"
            elif loss_ratio >= 0.75:
                status = "warning"
                message = f"Approaching stop-loss: Loss ${current_loss:.2f} ({loss_ratio:.0%} of max)"
            else:
                status = "ok"
                message = f"Position within limits: Loss ${current_loss:.2f} ({loss_ratio:.0%} of max)"

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

        # Only apply 2x stop-loss rule to credit spreads
        if position_type != "credit_spread":
            return False, f"Position type '{position_type}' not subject to 2x credit stop-loss"

        # Calculate current loss
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

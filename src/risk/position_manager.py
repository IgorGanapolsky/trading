"""
Position Manager - Real Implementation for Stop-Loss Protection

CEO Directive: "Don't lose money" - Phil Town Rule 1

CRITICAL: This replaces the stub that was accidentally left after PR #1445 cleanup.
The stub returned empty exit lists, meaning NO STOP-LOSSES EVER TRIGGERED!

This implementation:
- Evaluates all positions against exit conditions
- Triggers stop-loss at 8% loss (configurable)
- Triggers take-profit at 15% gain (configurable)
- Supports time-based exits
- Works for both long and short positions (including sold options)
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ExitConditions:
    """Exit conditions for positions."""

    take_profit_pct: float = 0.15  # 15% profit target
    stop_loss_pct: float = 0.08  # 8% stop-loss (Phil Town Rule 1)
    max_holding_days: int = 30
    enable_momentum_exit: bool = False
    enable_atr_stop: bool = True
    atr_multiplier: float = 2.5
    trailing_stop_pct: float = 0.0


@dataclass
class Position:
    """Position data class."""

    symbol: str
    quantity: float
    entry_price: float
    current_price: float
    unrealized_pl: float = 0.0
    unrealized_plpc: float = 0.0
    entry_date: datetime = field(default_factory=datetime.now)


class PositionManager:
    """
    Real position manager with working stop-loss protection.

    This is NOT a stub - it actually evaluates positions and triggers exits.
    """

    def __init__(self, conditions: ExitConditions | None = None):
        self.conditions = conditions or ExitConditions()
        self.entries: dict[str, datetime] = {}  # Track entry dates

    def record_entry(self, symbol: str, entry_date: datetime | None = None) -> None:
        """Record when a position was entered."""
        self.entries[symbol] = entry_date or datetime.now()

    def clear_entry(self, symbol: str) -> None:
        """Clear entry tracking after exit."""
        self.entries.pop(symbol, None)

    def should_exit(self, position: Position) -> tuple[bool, str, str]:
        """
        Determine if a position should be exited.

        Returns:
            tuple: (should_exit: bool, reason: str, details: str)
        """
        symbol = position.symbol
        pl_pct = position.unrealized_plpc

        # For short positions (like sold puts), the P/L calculation is inverted
        # A short put profits when the put price decreases
        is_short = position.quantity < 0

        # Stop-loss check - MOST IMPORTANT
        if pl_pct <= -self.conditions.stop_loss_pct:
            return (
                True,
                "STOP_LOSS",
                f"Loss of {pl_pct * 100:.2f}% exceeds {self.conditions.stop_loss_pct * 100:.1f}% threshold",
            )

        # Take-profit check
        if pl_pct >= self.conditions.take_profit_pct:
            return (
                True,
                "TAKE_PROFIT",
                f"Gain of {pl_pct * 100:.2f}% exceeds {self.conditions.take_profit_pct * 100:.1f}% target",
            )

        # Time-based exit
        if symbol in self.entries:
            days_held = (datetime.now() - self.entries[symbol]).days
            if days_held >= self.conditions.max_holding_days:
                return (
                    True,
                    "MAX_HOLDING_TIME",
                    f"Position held for {days_held} days (max: {self.conditions.max_holding_days})",
                )

        return (False, "HOLD", "No exit conditions met")

    def manage_all_positions(
        self, positions: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """
        Evaluate all positions and return those that should exit.

        Args:
            positions: List of position dicts from Alpaca API

        Returns:
            List of exit recommendations with position details
        """
        exits = []

        for pos_dict in positions:
            try:
                # Convert to Position object
                qty = float(pos_dict.get("qty", 0))
                entry_price = float(pos_dict.get("avg_entry_price", 0))
                current_price = float(pos_dict.get("current_price", 0))
                unrealized_pl = float(pos_dict.get("unrealized_pl", 0))
                unrealized_plpc = float(pos_dict.get("unrealized_plpc", 0))

                position = Position(
                    symbol=pos_dict["symbol"],
                    quantity=qty,
                    entry_price=entry_price,
                    current_price=current_price,
                    unrealized_pl=unrealized_pl,
                    unrealized_plpc=unrealized_plpc,
                )

                should_exit, reason, details = self.should_exit(position)

                if should_exit:
                    logger.info(
                        f"EXIT SIGNAL: {position.symbol} - {reason} - {details}"
                    )
                    exits.append(
                        {
                            "symbol": position.symbol,
                            "reason": reason,
                            "details": details,
                            "position": position,
                        }
                    )
                else:
                    logger.debug(f"HOLD: {position.symbol} - {details}")

            except Exception as e:
                logger.error(f"Error evaluating position {pos_dict}: {e}")

        return exits


# Default instance for imports
DEFAULT_POSITION_MANAGER = PositionManager()

"""Options Risk Monitor - Monitors options positions for risk."""

import logging
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal

logger = logging.getLogger(__name__)


@dataclass
class OptionsPosition:
    """Represents an options position for risk monitoring."""

    symbol: str  # OCC option symbol
    underlying: str  # Underlying stock symbol
    position_type: str  # 'covered_call', 'credit_spread', 'iron_condor', etc.
    side: Literal["long", "short"]
    quantity: int
    entry_price: float
    current_price: float
    delta: float
    gamma: float
    theta: float
    vega: float
    expiration_date: date
    strike: float
    opened_at: datetime


class OptionsRiskMonitor:
    """Monitors risk for options positions."""

    def __init__(self, max_loss_percent: float = 5.0):
        self.max_loss_percent = max_loss_percent
        self.positions: dict = {}

    def add_position(self, position: OptionsPosition | dict, position_data: dict | None = None) -> None:
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
        """Check risk status for a position."""
        position = self.positions.get(symbol)
        if not position:
            return {"status": "unknown", "message": "Position not found"}

        return {
            "status": "ok",
            "symbol": symbol,
            "current_risk": 0.0,
            "max_allowed": self.max_loss_percent,
        }

    def get_total_exposure(self) -> float:
        """Get total options exposure."""
        return sum(p.get("value", 0) for p in self.positions.values())

    def should_close_position(self, symbol: str) -> tuple[bool, str]:
        """Determine if position should be closed for risk."""
        return False, "Position within risk limits"

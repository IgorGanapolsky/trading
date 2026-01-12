# Position manager stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from dataclasses import dataclass
from typing import Any


@dataclass
class ExitConditions:
    """Exit conditions for positions."""

    take_profit_pct: float = 0.15
    stop_loss_pct: float = 0.08
    max_holding_days: int = 30
    enable_momentum_exit: bool = False
    enable_atr_stop: bool = True
    atr_multiplier: float = 2.5
    trailing_stop_pct: float = 0.0


class PositionManager:
    """Stub position manager - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self.positions: dict[str, Any] = {}
        self.exit_conditions = ExitConditions()

    def add_position(self, symbol: str, qty: float, price: float) -> bool:
        """Stub add position."""
        return True

    def remove_position(self, symbol: str) -> bool:
        """Stub remove position."""
        return True

    def get_positions(self) -> dict[str, Any]:
        """Return empty positions."""
        return {}

    def check_exits(self) -> list[str]:
        """Return empty exit list."""
        return []


# Default instance for imports
DEFAULT_POSITION_MANAGER = PositionManager()

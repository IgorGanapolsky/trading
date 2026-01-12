# Options risk monitor stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from dataclasses import dataclass
from typing import Any


@dataclass
class OptionsPosition:
    """Options position data."""
    symbol: str = ""
    underlying: str = ""
    strike: float = 0.0
    expiration: str = ""
    option_type: str = "call"
    qty: int = 0
    avg_cost: float = 0.0


class OptionsRiskMonitor:
    """Stub options risk monitor - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self.positions: list[OptionsPosition] = []

    def add_position(self, position: OptionsPosition) -> bool:
        """Stub add position."""
        return True

    def check_greeks(self) -> dict[str, Any]:
        """Return stub greeks."""
        return {"delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0}

    def get_total_exposure(self) -> float:
        """Return zero exposure."""
        return 0.0

# VIX circuit breaker stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from dataclasses import dataclass
from enum import Enum


class AlertLevel(Enum):
    """VIX alert levels."""
    NORMAL = "normal"
    ELEVATED = "elevated"
    HIGH = "high"
    VERY_HIGH = "very_high"
    EXTREME = "extreme"
    SPIKE = "spike"


@dataclass
class VIXStatus:
    """VIX status data."""
    current_level: float = 15.0
    alert_level: AlertLevel = AlertLevel.NORMAL
    message: str = "Stub VIX status"


class VIXCircuitBreaker:
    """Stub VIX circuit breaker - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def get_current_status(self, force_refresh: bool = False) -> VIXStatus:
        """Return stub status."""
        return VIXStatus()

    def should_halt_trading(self) -> bool:
        """Never halt in stub."""
        return False

    def get_position_multiplier(self) -> float:
        """Return full position size."""
        return 1.0

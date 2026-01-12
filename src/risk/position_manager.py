"""Stub - position_manager (original deleted in cleanup)."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ExitReason(Enum):
    """Stub for ExitReason."""
    STOP_LOSS = "stop_loss"
    TAKE_PROFIT = "take_profit"
    TIME_DECAY = "time_decay"


@dataclass
class ExitConditions:
    """Stub for ExitConditions."""
    stop_loss_pct: float = 0.03
    take_profit_pct: float = 0.03
    max_holding_days: int = 10


class PositionManager:
    """Stub for PositionManager."""

    def __init__(self, *args, **kwargs):
        pass

    def evaluate_exit(self, *args, **kwargs) -> dict[str, Any]:
        return {"should_exit": False}

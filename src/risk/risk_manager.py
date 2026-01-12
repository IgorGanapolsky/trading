"""Stub - risk_manager (original deleted in cleanup)."""

from typing import Any


class RiskManager:
    """Stub for RiskManager."""

    def __init__(self, *args, **kwargs):
        pass

    def check_trade(self, *args, **kwargs) -> dict[str, Any]:
        return {"approved": True}

    def calculate_position_size(self, *args, **kwargs) -> float:
        return 0.0

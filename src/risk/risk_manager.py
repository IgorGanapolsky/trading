# Risk manager stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from typing import Any


class RiskManager:
    """Stub risk manager - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        self.max_position_size = 0.05
        self.max_daily_loss = 0.02

    def check_position_size(self, symbol: str, qty: float) -> bool:
        """Always passes in stub."""
        return True

    def check_daily_loss(self, loss: float) -> bool:
        """Always passes in stub."""
        return True

    def get_position_limit(self, symbol: str) -> float:
        """Return default position limit."""
        return 100.0

    def calculate_risk(self, *args, **kwargs) -> dict[str, Any]:
        """Return stub risk calculation."""
        return {"risk_score": 0.0, "status": "stub"}

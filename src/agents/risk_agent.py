"""Stub file - RiskAgent (created for position_sizer skill dependency)."""

from typing import Any


class RiskAgent:
    """Stub for RiskAgent - provides minimal risk assessment interface."""

    name = "RiskAgent"
    role = "risk_assessment"

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        pass

    def analyze(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Minimal risk assessment - approves trades by default.

        Args:
            data: Input containing symbol, confidence, volatility, etc.

        Returns:
            Risk assessment with APPROVE action for stub behavior.
        """
        symbol = data.get("symbol", "UNKNOWN")
        return {
            "action": "APPROVE",
            "symbol": symbol,
            "position_size": 0.01,  # Conservative 1% position
            "risk_score": 0.5,
            "reason": "Stub RiskAgent - default approval",
        }

    def _calculate_position_size(
        self,
        account_value: float,
        risk_per_trade: float = 0.01,
        **kwargs: Any,
    ) -> float:
        """Calculate position size as percentage of account value."""
        return account_value * risk_per_trade

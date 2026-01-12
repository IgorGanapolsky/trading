# Trade gateway stub - original deleted in cleanup PR #1445
# Minimal implementation to prevent import errors

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RejectionReason(Enum):
    """Trade rejection reasons."""
    NONE = "none"
    INSUFFICIENT_FUNDS = "insufficient_funds"
    POSITION_LIMIT = "position_limit"
    RISK_LIMIT = "risk_limit"
    MARKET_CLOSED = "market_closed"


@dataclass
class TradeRequest:
    """Trade request data."""
    symbol: str = ""
    side: str = "buy"
    qty: float = 0.0
    order_type: str = "market"

    def __post_init__(self):
        pass


class TradeGateway:
    """Stub trade gateway - not used in Phil Town strategy."""

    def __init__(self, *args, **kwargs):
        pass

    def validate(self, request: TradeRequest) -> tuple[bool, RejectionReason]:
        """Always passes validation in stub."""
        return True, RejectionReason.NONE

    def execute(self, request: TradeRequest) -> dict[str, Any]:
        """Stub execute."""
        return {"status": "stub", "message": "Trade gateway is a stub"}

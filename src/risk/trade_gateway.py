"""Stub - trade_gateway (original deleted in cleanup)."""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RejectionReason(Enum):
    """Stub for RejectionReason."""
    NONE = "none"
    INSUFFICIENT_CAPITAL = "insufficient_capital"
    RISK_LIMIT = "risk_limit"
    MARKET_CLOSED = "market_closed"


@dataclass
class TradeRequest:
    """Stub for TradeRequest."""
    symbol: str = ""
    side: str = "buy"
    qty: float = 0.0
    strategy: str = ""


class TradeGateway:
    """Stub for TradeGateway."""

    def __init__(self, *args, **kwargs):
        pass

    def validate(self, request: TradeRequest) -> tuple[bool, RejectionReason]:
        return (True, RejectionReason.NONE)

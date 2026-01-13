"""Mandatory Trade Gate stub - allows all trades."""

from dataclasses import dataclass, field
from typing import Any


class TradeBlockedError(Exception):
    """Exception raised when trade is blocked."""

    pass


@dataclass
class TradeGateResult:
    """Result of trade gate validation."""

    approved: bool = True
    reason: str = ""
    rag_warnings: list[str] = field(default_factory=list)
    ml_anomalies: list[str] = field(default_factory=list)


def validate_trade_mandatory(
    symbol: str = "",
    amount: float = 0.0,
    side: str = "",
    strategy: str = "",
    context: dict[str, Any] | None = None,
) -> TradeGateResult:
    """Stub validator - allows all trades.

    Args:
        symbol: Ticker symbol
        amount: Trade amount (notional or shares)
        side: BUY or SELL
        strategy: Strategy name
        context: Account context (equity, buying_power)

    Returns:
        TradeGateResult with approved=True
    """
    return TradeGateResult(approved=True)

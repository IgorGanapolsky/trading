"""
Order execution helpers via `AlpacaTrader`.
"""

from __future__ import annotations

from typing import Any

from mcp.client import get_alpaca_trader
from mcp.utils import ensure_env_var


def _get_trader(paper: bool = True):
    return ensure_env_var(lambda: get_alpaca_trader(paper=paper), "AlpacaTrader (check API keys)")


def validate_order_amount(
    symbol: str, amount: float, tier: str | None = None, *, paper: bool = True
) -> None:
    """
    Apply the trading safety checks before submitting an order.
    """

    trader = _get_trader(paper)
    trader.validate_order_amount(symbol=symbol, amount=amount, tier=tier)


def submit_market_order(
    symbol: str,
    amount_usd: float,
    side: str = "buy",
    tier: str | None = None,
    *,
    paper: bool = True,
) -> dict[str, Any]:
    """
    Submit a market order via Alpaca.
    """

    trader = _get_trader(paper)
    return trader.execute_order(
        symbol=symbol,
        amount_usd=amount_usd,
        side=side,
        tier=tier,
    )


def set_stop_loss(
    symbol: str,
    qty: float,
    stop_price: float,
    *,
    paper: bool = True,
) -> dict[str, Any]:
    """
    Set a stop-loss order for an open position.
    """

    trader = _get_trader(paper)
    return trader.set_stop_loss(symbol=symbol, qty=qty, stop_price=stop_price)

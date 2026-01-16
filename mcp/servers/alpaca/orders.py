"""
Order execution helpers via `AlpacaTrader`.

Protected by governance middleware:
- Input validation (Pydantic)
- Output sanitization (Anti-injection)
"""

from __future__ import annotations

from typing import Any

from mcp.client import get_alpaca_trader
from mcp.governance import OrderRequest, sanitize_response, validate_request
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

    Protected by governance middleware:
    - Validates symbol against allowlist
    - Enforces max order amount ($248)
    - Requires paper trading mode
    - Sanitizes response output
    """
    # Input validation (Pydantic)
    validated = validate_request(
        OrderRequest,
        {
            "symbol": symbol,
            "amount_usd": amount_usd,
            "side": side,
            "tier": tier,
            "paper": paper,
        },
    )

    trader = _get_trader(validated.paper)
    result = trader.execute_order(
        symbol=validated.symbol,
        amount_usd=validated.amount_usd,
        side=validated.side,
        tier=validated.tier,
    )

    # Output sanitization (Anti-injection)
    return sanitize_response(result)


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

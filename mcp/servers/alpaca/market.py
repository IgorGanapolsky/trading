"""
Market data helpers backed by `AlpacaTrader`.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from mcp.client import get_alpaca_trader
from mcp.utils import ensure_env_var


def _get_trader(paper: bool = True):
    return ensure_env_var(lambda: get_alpaca_trader(paper=paper), "AlpacaTrader (check API keys)")


def get_account_snapshot(paper: bool = True) -> dict[str, Any]:
    """
    Retrieve account information from Alpaca.
    """

    trader = _get_trader(paper)
    return trader.get_account_info()


def get_latest_bars(symbols: Iterable[str], limit: int = 200, paper: bool = True) -> dict[str, Any]:
    """
    Fetch the latest bars for a list of symbols.
    """

    trader = _get_trader(paper)
    market_data = {}

    for symbol in symbols:
        bars = trader.get_historical_bars(
            symbol=symbol,
            timeframe="1Day",
            limit=limit,
        )
        market_data[symbol] = bars

    return market_data


def get_portfolio_positions(paper: bool = True) -> list[dict[str, Any]]:
    """
    Return current portfolio positions.
    """

    trader = _get_trader(paper)
    positions = trader.get_all_positions()
    return positions

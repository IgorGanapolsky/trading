"""
Shared Alpaca API Client Utility

This module provides a centralized way to create Alpaca trading clients,
avoiding code duplication across scripts.

Created: Jan 8, 2026
Reason: DRY violation - get_alpaca_client() was duplicated in 5+ scripts
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_alpaca_client(paper: bool = True):
    """
    Get Alpaca trading client.

    Args:
        paper: If True (default), use paper trading. Set to False for live trading.
               Note: Live trading requires explicit confirmation and is dangerous.

    Returns:
        TradingClient instance or None if creation fails.

    Environment variables required:
        - ALPACA_API_KEY: Your Alpaca API key
        - ALPACA_SECRET_KEY: Your Alpaca secret key
    """
    try:
        from alpaca.trading.client import TradingClient

        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.error("ALPACA_API_KEY and ALPACA_SECRET_KEY environment variables required")
            return None

        return TradingClient(api_key, secret_key, paper=paper)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create Alpaca client: {e}")
        return None


def get_options_client(paper: bool = True):
    """
    Get Alpaca options client.

    Note: Options trading uses the same TradingClient as equities in alpaca-py.
    This function is provided for semantic clarity.

    Args:
        paper: If True (default), use paper trading.

    Returns:
        TradingClient instance or None if creation fails.
    """
    return get_alpaca_client(paper=paper)


def get_account_info(client) -> Optional[dict]:
    """
    Get account information from Alpaca.

    Args:
        client: TradingClient instance from get_alpaca_client()

    Returns:
        Dictionary with equity, cash, buying_power or None on failure.
    """
    if client is None:
        return None

    try:
        account = client.get_account()
        return {
            "equity": float(account.equity),
            "cash": float(account.cash),
            "buying_power": float(account.buying_power),
        }
    except Exception as e:
        logger.error(f"Failed to get account info: {e}")
        return None

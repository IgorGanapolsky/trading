"""
Shared Alpaca API Client Utility

This module provides a centralized way to create Alpaca trading clients,
avoiding code duplication across scripts.

Created: Jan 8, 2026
Reason: DRY violation - get_alpaca_client() was duplicated in 5+ scripts

Updated: Jan 12, 2026
- Added get_alpaca_credentials() to prioritize $5K paper account
- All code must use get_alpaca_credentials() for API key access
"""

import logging
import os
from typing import Optional

logger = logging.getLogger(__name__)


def get_alpaca_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get Alpaca API credentials with proper priority (paper trading).

    Priority order (first found wins):
    1. ALPACA_PAPER_TRADING_5K_API_KEY / ALPACA_PAPER_TRADING_5K_API_SECRET ($5K account - PRIMARY)
    2. ALPACA_PAPER_TRADING_API_KEY / ALPACA_PAPER_TRADING_API_SECRET ($100K account)
    3. ALPACA_API_KEY / ALPACA_SECRET_KEY (legacy fallback)

    Returns:
        Tuple of (api_key, secret_key) or (None, None) if not found.
    """
    api_key = (
        os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY")
        or os.getenv("ALPACA_PAPER_TRADING_API_KEY")
        or os.getenv("ALPACA_API_KEY")
    )
    secret_key = (
        os.getenv("ALPACA_PAPER_TRADING_5K_API_SECRET")
        or os.getenv("ALPACA_PAPER_TRADING_API_SECRET")
        or os.getenv("ALPACA_SECRET_KEY")
    )

    if api_key:
        if os.getenv("ALPACA_PAPER_TRADING_5K_API_KEY"):
            logger.debug("Using $5K paper trading account credentials")
        elif os.getenv("ALPACA_PAPER_TRADING_API_KEY"):
            logger.debug("Using $100K paper trading account credentials")
        else:
            logger.debug("Using legacy ALPACA_API_KEY credentials")

    return api_key, secret_key


def get_brokerage_credentials() -> tuple[Optional[str], Optional[str]]:
    """
    Get Alpaca BROKERAGE (live) API credentials.

    Uses ALPACA_BROKERAGE_TRADING_API_KEY/SECRET for real money trading.

    Returns:
        Tuple of (api_key, secret_key) or (None, None) if not found.
    """
    api_key = os.getenv("ALPACA_BROKERAGE_TRADING_API_KEY")
    secret_key = os.getenv("ALPACA_BROKERAGE_TRADING_API_SECRET")

    if api_key:
        logger.info("Using BROKERAGE (live) trading credentials")
    else:
        logger.warning("Brokerage credentials not found - set ALPACA_BROKERAGE_TRADING_API_KEY")

    return api_key, secret_key


def get_brokerage_client():
    """
    Get Alpaca BROKERAGE (live money) trading client.

    WARNING: This uses real money! Only for actual trading.

    Returns:
        TradingClient instance for live trading or None if creation fails.
    """
    try:
        from alpaca.trading.client import TradingClient

        api_key, secret_key = get_brokerage_credentials()

        if not api_key or not secret_key:
            logger.error("Brokerage credentials not found. Set ALPACA_BROKERAGE_TRADING_API_KEY")
            return None

        return TradingClient(api_key, secret_key, paper=False)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create brokerage client: {e}")
        return None


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

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error(
                "Alpaca credentials not found. Set ALPACA_PAPER_TRADING_5K_API_KEY or ALPACA_API_KEY"
            )
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


def get_options_data_client():
    """
    Get Alpaca options historical data client.

    Used for fetching options chain data, IV, greeks, etc.

    Returns:
        OptionHistoricalDataClient instance or None if creation fails.
    """
    try:
        from alpaca.data.historical.option import OptionHistoricalDataClient

        api_key, secret_key = get_alpaca_credentials()

        if not api_key or not secret_key:
            logger.error("Alpaca credentials not found for options data client")
            return None

        return OptionHistoricalDataClient(api_key, secret_key)
    except ImportError:
        logger.error("alpaca-py not installed. Add to requirements.txt")
        return None
    except Exception as e:
        logger.error(f"Failed to create options data client: {e}")
        return None


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

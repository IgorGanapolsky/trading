"""
Ticker Validator - HARD BLOCK on non-SPY trades.

Created: January 20, 2026
Root cause: SOFI position opened today violating SPY ONLY rule, causing -$150 loss.

Per CLAUDE.md:
- Primary strategy: IRON CONDORS on SPY ONLY
- NO individual stocks. The $100K success was SPY. The $5K failure was SOFI.
"""

import logging
from typing import NoReturn

logger = logging.getLogger(__name__)

# WHITELIST: Only these tickers are allowed for trading
# Per CLAUDE.md "Ticker Selection (Jan 19, 2026 - Simplified)"
ALLOWED_TICKERS = frozenset({"SPY"})


class TickerViolationError(Exception):
    """Raised when attempting to trade a non-whitelisted ticker."""

    pass


def validate_ticker(ticker: str, context: str = "") -> str:
    """
    Validate that a ticker is in the whitelist.

    Args:
        ticker: The ticker symbol to validate
        context: Optional context for logging (e.g., "iron_condor_trader")

    Returns:
        The normalized (uppercase) ticker if valid

    Raises:
        TickerViolationError: If ticker is not in whitelist
    """
    normalized = ticker.upper().strip()

    if normalized not in ALLOWED_TICKERS:
        error_msg = (
            f"TICKER VIOLATION: '{normalized}' is NOT in whitelist {ALLOWED_TICKERS}. "
            f"Context: {context or 'unknown'}. "
            f"Per CLAUDE.md: SPY ONLY - NO individual stocks."
        )
        logger.error(error_msg)
        raise TickerViolationError(error_msg)

    logger.info(f"Ticker '{normalized}' validated OK. Context: {context or 'unknown'}")
    return normalized


def is_allowed_ticker(ticker: str) -> bool:
    """
    Check if a ticker is in the whitelist without raising an exception.

    Args:
        ticker: The ticker symbol to check

    Returns:
        True if ticker is allowed, False otherwise
    """
    return ticker.upper().strip() in ALLOWED_TICKERS


def block_trade(reason: str) -> NoReturn:
    """
    Block a trade with a specific reason. Always raises.

    Args:
        reason: The reason for blocking the trade

    Raises:
        TickerViolationError: Always
    """
    error_msg = f"TRADE BLOCKED: {reason}"
    logger.error(error_msg)
    raise TickerViolationError(error_msg)

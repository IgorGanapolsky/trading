"""
TICKER WHITELIST - CRITICAL SAFETY GATE

Per CLAUDE.md and Trading System Directive v2.0:
- Permitted Tickers: SPY ONLY (whitelist enforced)
- Red Line: ❌ Never trade non-whitelisted tickers

This module MUST be imported by ALL trading scripts before execution.
Any attempt to trade non-SPY tickers will be BLOCKED.

Created: Jan 21, 2026
Reason: SOFI position violated SPY-only rule, blocked trading for 2 days
"""

import logging

logger = logging.getLogger(__name__)

# WHITELIST - SPY ONLY
# Do NOT add other tickers without CEO approval
ALLOWED_TICKERS = frozenset({"SPY"})

# Options on allowed tickers are permitted
# Format: SPY + date + P/C + strike (e.g., SPY260220P00653000)
ALLOWED_UNDERLYING = frozenset({"SPY"})


class TickerWhitelistViolation(Exception):
    """Raised when attempting to trade non-whitelisted ticker."""

    pass


def extract_underlying(symbol: str) -> str:
    """
    Extract underlying ticker from option symbol.

    Examples:
        SPY260220P00653000 -> SPY
        SOFI260213P00032000 -> SOFI
        SPY -> SPY
    """
    # Options have format: UNDERLYING + YYMMDD + P/C + STRIKE
    # Underlying is letters at the start
    underlying = ""
    for char in symbol:
        if char.isalpha():
            underlying += char
        else:
            break
    return underlying.upper() if underlying else symbol.upper()


def is_ticker_allowed(symbol: str) -> bool:
    """
    Check if ticker/symbol is allowed for trading.

    Args:
        symbol: Stock ticker or option symbol

    Returns:
        True if allowed, False otherwise
    """
    underlying = extract_underlying(symbol)
    return underlying in ALLOWED_UNDERLYING


def validate_ticker(symbol: str, raise_on_violation: bool = True) -> bool:
    """
    Validate ticker against whitelist. MUST be called before any trade.

    Args:
        symbol: Stock ticker or option symbol
        raise_on_violation: If True, raise exception on violation

    Returns:
        True if valid

    Raises:
        TickerWhitelistViolation: If ticker not in whitelist and raise_on_violation=True
    """
    underlying = extract_underlying(symbol)

    if underlying not in ALLOWED_UNDERLYING:
        error_msg = (
            f"BLOCKED: {symbol} (underlying: {underlying}) is NOT in whitelist. "
            f"Allowed: {ALLOWED_UNDERLYING}. "
            f"Per CLAUDE.md: SPY ONLY - No individual stocks."
        )
        logger.error(error_msg)

        if raise_on_violation:
            raise TickerWhitelistViolation(error_msg)
        return False

    logger.info(f"ALLOWED: {symbol} (underlying: {underlying}) passed whitelist check")
    return True


def enforce_spy_only(func):
    """
    Decorator to enforce SPY-only rule on trading functions.

    Usage:
        @enforce_spy_only
        def execute_trade(symbol, ...):
            ...
    """

    def wrapper(*args, **kwargs):
        # Try to find symbol in args or kwargs
        symbol = kwargs.get("symbol") or (args[0] if args else None)

        if symbol:
            validate_ticker(symbol, raise_on_violation=True)

        return func(*args, **kwargs)

    return wrapper


# Self-test on import
if __name__ == "__main__":
    print("=== TICKER WHITELIST TESTS ===")

    # Should pass
    assert is_ticker_allowed("SPY")
    assert is_ticker_allowed("SPY260220P00653000")
    assert is_ticker_allowed("SPY260115C00700000")

    # Should fail
    assert not is_ticker_allowed("SOFI")
    assert not is_ticker_allowed("SOFI260213P00032000")
    assert not is_ticker_allowed("AAPL")
    assert not is_ticker_allowed("TSLA")

    print("✅ All whitelist tests passed!")
    print(f"Allowed tickers: {ALLOWED_UNDERLYING}")

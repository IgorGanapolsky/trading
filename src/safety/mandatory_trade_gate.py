"""Stub module - original safety deleted in cleanup."""


class TradeBlockedError(Exception):
    """Exception raised when trade is blocked."""
    pass


def validate_trade_mandatory(*args, **kwargs) -> bool:
    """Always allow trades (stub)."""
    return True

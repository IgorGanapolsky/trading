"""
Market Hours Utility - Centralized trading hours validation.

Provides consistent market hour checking across all strategies and execution paths.
Prevents trades outside regular market hours (9:30 AM - 4:00 PM ET).
"""

import logging
import os
from datetime import datetime, time
from enum import Enum
from typing import NamedTuple
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# Eastern Time zone for US markets
ET = ZoneInfo("America/New_York")


class MarketSession(Enum):
    """Market session types."""

    PRE_MARKET = "pre_market"  # 4:00 AM - 9:30 AM ET
    REGULAR = "regular"  # 9:30 AM - 4:00 PM ET
    AFTER_HOURS = "after_hours"  # 4:00 PM - 8:00 PM ET
    CLOSED = "closed"  # 8:00 PM - 4:00 AM ET (overnight)
    WEEKEND = "weekend"


class MarketStatus(NamedTuple):
    """Market status with details."""

    is_open: bool
    session: MarketSession
    can_trade: bool  # Whether trading is allowed in current session
    reason: str
    current_time_et: datetime
    next_open: str | None  # Human-readable next open time


# Market hours (ET)
MARKET_OPEN = time(9, 30)
MARKET_CLOSE = time(16, 0)
PRE_MARKET_OPEN = time(4, 0)
AFTER_HOURS_CLOSE = time(20, 0)

# Extended hours trading preference (default: regular hours only)
ALLOW_PRE_MARKET = os.getenv("ALLOW_PRE_MARKET_TRADING", "false").lower() == "true"
ALLOW_AFTER_HOURS = os.getenv("ALLOW_AFTER_HOURS_TRADING", "false").lower() == "true"


def is_market_open(check_time: datetime | None = None, allow_extended: bool = False) -> bool:
    """
    Check if the market is open for regular trading.

    Args:
        check_time: Time to check (default: current time)
        allow_extended: Allow pre-market and after-hours (default: False)

    Returns:
        True if market is open for trading
    """
    status = get_market_status(check_time, allow_extended)
    return status.can_trade


def get_market_status(
    check_time: datetime | None = None, allow_extended: bool = False
) -> MarketStatus:
    """
    Get detailed market status.

    Args:
        check_time: Time to check (default: current time)
        allow_extended: Allow pre-market and after-hours (default: False)

    Returns:
        MarketStatus with session info and trading permission
    """
    # Get current time in ET
    if check_time is None:
        now_et = datetime.now(ET)
    else:
        # Convert to ET if timezone-aware, assume ET if naive
        if check_time.tzinfo is None:
            now_et = check_time.replace(tzinfo=ET)
        else:
            now_et = check_time.astimezone(ET)

    current_time = now_et.time()
    weekday = now_et.weekday()

    # Weekend check (Saturday=5, Sunday=6)
    if weekday >= 5:
        day_name = "Saturday" if weekday == 5 else "Sunday"
        return MarketStatus(
            is_open=False,
            session=MarketSession.WEEKEND,
            can_trade=False,
            reason=f"Weekend - market closed ({day_name})",
            current_time_et=now_et,
            next_open="Monday 9:30 AM ET",
        )

    # Determine session based on time
    if PRE_MARKET_OPEN <= current_time < MARKET_OPEN:
        session = MarketSession.PRE_MARKET
        can_trade = allow_extended or ALLOW_PRE_MARKET
        reason = "Pre-market session (4:00 AM - 9:30 AM ET)"
        if not can_trade:
            reason += " - extended hours trading disabled"
        next_open = "9:30 AM ET today" if not can_trade else None

    elif MARKET_OPEN <= current_time < MARKET_CLOSE:
        session = MarketSession.REGULAR
        can_trade = True
        reason = "Regular market hours (9:30 AM - 4:00 PM ET)"
        next_open = None

    elif MARKET_CLOSE <= current_time < AFTER_HOURS_CLOSE:
        session = MarketSession.AFTER_HOURS
        can_trade = allow_extended or ALLOW_AFTER_HOURS
        reason = "After-hours session (4:00 PM - 8:00 PM ET)"
        if not can_trade:
            reason += " - extended hours trading disabled"
        next_open = "9:30 AM ET tomorrow" if not can_trade else None

    else:  # Overnight (8:00 PM - 4:00 AM)
        session = MarketSession.CLOSED
        can_trade = False
        reason = "Market closed (overnight)"
        next_open = "4:00 AM ET (pre-market) or 9:30 AM ET (regular)"

    return MarketStatus(
        is_open=(session == MarketSession.REGULAR),
        session=session,
        can_trade=can_trade,
        reason=reason,
        current_time_et=now_et,
        next_open=next_open,
    )


def validate_trading_hours(
    check_time: datetime | None = None,
    allow_extended: bool = False,
    raise_on_closed: bool = False,
) -> tuple[bool, str]:
    """
    Validate if trading is allowed at the given time.

    This is the primary function strategies should call before executing trades.

    Args:
        check_time: Time to check (default: current time)
        allow_extended: Allow pre-market and after-hours (default: False)
        raise_on_closed: Raise ValueError if market closed (default: False)

    Returns:
        Tuple of (can_trade: bool, reason: str)

    Raises:
        ValueError: If raise_on_closed=True and market is closed
    """
    status = get_market_status(check_time, allow_extended)

    if not status.can_trade:
        msg = f"Trading not allowed: {status.reason}"
        if status.next_open:
            msg += f". Next open: {status.next_open}"

        logger.warning(msg)

        if raise_on_closed:
            raise ValueError(msg)

    return status.can_trade, status.reason


def get_next_market_open(from_time: datetime | None = None) -> datetime:
    """
    Get the next market open time.

    Args:
        from_time: Starting time (default: current time)

    Returns:
        datetime of next market open (9:30 AM ET)
    """
    if from_time is None:
        now_et = datetime.now(ET)
    else:
        if from_time.tzinfo is None:
            now_et = from_time.replace(tzinfo=ET)
        else:
            now_et = from_time.astimezone(ET)

    # If before market open today and it's a weekday, return today's open
    if now_et.weekday() < 5 and now_et.time() < MARKET_OPEN:
        return now_et.replace(hour=9, minute=30, second=0, microsecond=0)

    # Otherwise, find next weekday
    next_open = now_et.replace(hour=9, minute=30, second=0, microsecond=0)
    days_ahead = 1
    while True:
        next_open = next_open.replace(day=next_open.day + days_ahead)
        if next_open.weekday() < 5:  # Monday = 0, Friday = 4
            return next_open
        days_ahead = 1


# Convenience alias
is_trading_allowed = validate_trading_hours

"""
Finnhub API client for economic calendar and earnings calendar.

Used to avoid trading during major economic events (Fed meetings, GDP releases, etc.)
and earnings announcements.
"""

from __future__ import annotations

import logging
import os
from datetime import date, timedelta

import requests

logger = logging.getLogger(__name__)


class FinnhubClient:
    """Client for Finnhub API (economic calendar, earnings calendar)."""

    BASE_URL = "https://finnhub.io/api/v1"

    # Major economic events that should trigger trading avoidance
    MAJOR_EVENT_TYPES = [
        "FOMC",  # Federal Open Market Committee meetings
        "GDP",  # Gross Domestic Product releases
        "CPI",  # Consumer Price Index
        "PPI",  # Producer Price Index
        "Employment",  # Employment data (NFP, unemployment)
        "Interest Rate Decision",  # Central bank rate decisions
    ]

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")
        if not self.api_key:
            logger.warning("FINNHUB_API_KEY not set. Economic calendar checks will be unavailable.")

    def get_economic_calendar(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[dict]:
        """
        Get economic calendar events for a date range.

        Args:
            start_date: Start date (defaults to today)
            end_date: End date (defaults to today)

        Returns:
            List of economic events
        """
        if not self.api_key:
            logger.debug("Finnhub API key not available")
            return []

        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = date.today()

        try:
            url = f"{self.BASE_URL}/calendar/economic"
            params = {
                "token": self.api_key,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            # Check for API errors (plan limitations, etc.)
            if "error" in data:
                error_msg = data.get("error", "Unknown error")
                if "access" in error_msg.lower() or "permission" in error_msg.lower():
                    logger.warning(
                        "Finnhub economic calendar requires premium plan - feature unavailable"
                    )
                    return []
                logger.warning("Finnhub API error: %s", error_msg)
                return []

            events = data.get("economicCalendar", [])
            logger.info("Fetched %d economic events from Finnhub", len(events))
            return events
        except Exception as exc:
            logger.warning("Failed to fetch economic calendar: %s", exc)
            return []

    def has_major_event_today(self) -> bool:
        """
        Check if there's a major economic event today.

        Returns:
            True if major event today, False otherwise
        """
        if not self.api_key:
            return False

        events = self.get_economic_calendar()
        if not events:
            return False

        today_str = date.today().strftime("%Y-%m-%d")
        for event in events:
            event_date = event.get("date", "")
            event_type = event.get("event", "")

            # Check if event is today
            if event_date.startswith(today_str):
                # Check if it's a major event type
                for major_type in self.MAJOR_EVENT_TYPES:
                    if major_type.upper() in event_type.upper():
                        logger.warning(
                            "Major economic event today: %s (%s)",
                            event_type,
                            event_date,
                        )
                        return True

        return False

    def get_earnings_calendar(
        self, start_date: date | None = None, end_date: date | None = None
    ) -> list[dict]:
        """
        Get earnings calendar for a date range.

        Args:
            start_date: Start date (defaults to today)
            end_date: End date (defaults to today + 7 days)

        Returns:
            List of earnings announcements
        """
        if not self.api_key:
            logger.debug("Finnhub API key not available")
            return []

        if start_date is None:
            start_date = date.today()
        if end_date is None:
            end_date = date.today() + timedelta(days=7)

        try:
            url = f"{self.BASE_URL}/calendar/earnings"
            params = {
                "token": self.api_key,
                "from": start_date.strftime("%Y-%m-%d"),
                "to": end_date.strftime("%Y-%m-%d"),
            }

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            earnings = data.get("earningsCalendar", [])
            logger.info("Fetched %d earnings announcements from Finnhub", len(earnings))
            return earnings
        except Exception as exc:
            logger.warning("Failed to fetch earnings calendar: %s", exc)
            return []

    def is_earnings_week(self, symbol: str | None = None) -> bool:
        """
        Check if it's earnings week for a symbol (or any major symbol).

        Args:
            symbol: Optional symbol to check (if None, checks for major indices)

        Returns:
            True if earnings week, False otherwise
        """
        if not self.api_key:
            return False

        # Check next 7 days for earnings
        earnings = self.get_earnings_calendar(
            start_date=date.today(), end_date=date.today() + timedelta(days=7)
        )

        if symbol:
            # Check specific symbol
            symbol_upper = symbol.upper()
            for earning in earnings:
                if earning.get("symbol", "").upper() == symbol_upper:
                    return True
        else:
            # Check for major symbols (SPY, QQQ, VOO components)
            major_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]
            for earning in earnings:
                earning_symbol = earning.get("symbol", "").upper()
                if earning_symbol in major_symbols:
                    logger.info("Earnings week detected for %s", earning_symbol)
                    return True

        return False

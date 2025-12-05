"""
Earnings Whisper Collector for RAG System

Collects earnings expectations, whisper numbers, and earnings calendar data.
Provides insights into market expectations vs. analyst estimates.
"""

from __future__ import annotations
import logging
import re
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class EarningsWhisperCollector(BaseNewsCollector):
    """
    Collector for earnings expectations and whisper numbers.

    Collects:
    - Earnings calendar (upcoming reports)
    - Whisper numbers (market expectations)
    - Analyst estimates vs. whisper spread
    - Historical earnings surprise data
    - Pre-earnings sentiment
    """

    BASE_URL = "https://www.earningswhispers.com"
    CALENDAR_URL = "https://www.earningswhispers.com/calendar"
    STOCK_URL = "https://www.earningswhispers.com/stocks/{symbol}"

    # Alternative free sources for earnings data
    YAHOO_EARNINGS_URL = "https://finance.yahoo.com/calendar/earnings"
    NASDAQ_EARNINGS_URL = "https://www.nasdaq.com/market-activity/earnings"

    def __init__(self):
        super().__init__(source_name="earnings_whisper")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect earnings data for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., "NVDA")
            days_back: Days to look back for historical earnings

        Returns:
            List of earnings data and expectations
        """
        results = []

        # Get earnings whisper data
        whisper_data = self._collect_whisper_data(ticker)
        if whisper_data:
            results.append(whisper_data)

        # Get historical earnings surprises
        surprises = self._collect_earnings_surprises(ticker)
        results.extend(surprises)

        # Get upcoming earnings date
        calendar_data = self._get_earnings_date(ticker)
        if calendar_data:
            results.append(calendar_data)

        logger.info(f"Collected {len(results)} earnings entries for {ticker}")
        return results

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect upcoming earnings calendar for the week.

        Returns:
            List of upcoming earnings reports
        """
        results = []

        # Get this week's earnings calendar
        calendar = self._collect_earnings_calendar()
        results.extend(calendar)

        logger.info(f"Collected {len(results)} earnings calendar entries")
        return results

    def _collect_whisper_data(self, ticker: str) -> dict[str, Any] | None:
        """
        Collect whisper number and expectations for a ticker.

        Args:
            ticker: Stock symbol

        Returns:
            Whisper data dictionary or None
        """
        url = self.STOCK_URL.format(symbol=ticker.lower())

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                # Fallback to Yahoo Finance
                return self._collect_yahoo_earnings(ticker)

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract whisper number
            whisper_elem = soup.find(class_=re.compile(r"whisper|estimate"))
            whisper_num = None
            if whisper_elem:
                match = re.search(r"\$?([-\d.]+)", whisper_elem.text)
                if match:
                    whisper_num = float(match.group(1))

            # Extract analyst estimate
            estimate_elem = soup.find(class_=re.compile(r"analyst|consensus"))
            analyst_est = None
            if estimate_elem:
                match = re.search(r"\$?([-\d.]+)", estimate_elem.text)
                if match:
                    analyst_est = float(match.group(1))

            # Extract earnings date
            date_elem = soup.find(class_=re.compile(r"date|when|report"))
            earnings_date = None
            if date_elem:
                earnings_date = date_elem.text.strip()

            # Calculate spread and sentiment
            if whisper_num and analyst_est:
                spread = whisper_num - analyst_est
                # Positive spread = market expects beat = bullish
                if spread > 0:
                    sentiment = 0.65
                    expectation = "BEAT_EXPECTED"
                elif spread < 0:
                    sentiment = 0.35
                    expectation = "MISS_EXPECTED"
                else:
                    sentiment = 0.5
                    expectation = "INLINE_EXPECTED"
            else:
                spread = 0
                sentiment = 0.5
                expectation = "UNKNOWN"

            entry = self.normalize_article(
                title=f"Earnings Whisper: {ticker}",
                content=f"Whisper: ${whisper_num}, Analyst: ${analyst_est}, Spread: ${spread:.2f}",
                url=url,
                published_date=datetime.now().isoformat(),
                ticker=ticker,
                sentiment=sentiment,
            )
            entry["whisper_eps"] = whisper_num
            entry["analyst_eps"] = analyst_est
            entry["spread"] = spread
            entry["earnings_date"] = earnings_date
            entry["expectation"] = expectation
            entry["signal_type"] = "earnings_whisper"

            return entry

        except Exception as e:
            logger.error(f"Error collecting whisper data for {ticker}: {e}")
            return self._collect_yahoo_earnings(ticker)

    def _collect_yahoo_earnings(self, ticker: str) -> dict[str, Any] | None:
        """
        Fallback to Yahoo Finance for earnings data.

        Args:
            ticker: Stock symbol

        Returns:
            Earnings data or None
        """
        url = f"https://finance.yahoo.com/quote/{ticker}/analysis"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Find earnings estimate tables
            tables = soup.find_all("table")
            current_qtr_est = None
            next_qtr_est = None

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 2:
                        label = cells[0].text.strip().lower()
                        if "current qtr" in label or "current quarter" in label:
                            match = re.search(r"([-\d.]+)", cells[1].text)
                            if match:
                                current_qtr_est = float(match.group(1))
                        elif "next qtr" in label or "next quarter" in label:
                            match = re.search(r"([-\d.]+)", cells[1].text)
                            if match:
                                next_qtr_est = float(match.group(1))

            if current_qtr_est is None:
                return None

            entry = self.normalize_article(
                title=f"Yahoo Earnings Estimate: {ticker}",
                content=f"Current Qtr Est: ${current_qtr_est}, Next Qtr Est: ${next_qtr_est}",
                url=url,
                published_date=datetime.now().isoformat(),
                ticker=ticker,
                sentiment=0.5,
            )
            entry["current_qtr_estimate"] = current_qtr_est
            entry["next_qtr_estimate"] = next_qtr_est
            entry["signal_type"] = "earnings_estimate"
            entry["source_type"] = "yahoo"

            return entry

        except Exception as e:
            logger.error(f"Error collecting Yahoo earnings for {ticker}: {e}")
            return None

    def _collect_earnings_surprises(self, ticker: str) -> list[dict[str, Any]]:
        """
        Collect historical earnings surprise data.

        Args:
            ticker: Stock symbol

        Returns:
            List of historical earnings surprises
        """
        results = []
        url = f"https://finance.yahoo.com/quote/{ticker}/history"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for earnings history table
            tables = soup.find_all("table")
            for table in tables:
                header = table.find("thead")
                if header and "eps" in header.text.lower():
                    rows = table.find_all("tr")[1:5]  # Last 4 quarters
                    for row in rows:
                        cells = row.find_all("td")
                        if len(cells) >= 4:
                            try:
                                date = cells[0].text.strip()
                                estimate = self._parse_float(cells[1].text)
                                actual = self._parse_float(cells[2].text)
                                surprise = self._parse_float(cells[3].text)

                                # Positive surprise is bullish
                                if surprise > 0:
                                    sentiment = 0.7
                                elif surprise < 0:
                                    sentiment = 0.3
                                else:
                                    sentiment = 0.5

                                entry = self.normalize_article(
                                    title=f"Earnings History: {ticker} ({date})",
                                    content=f"Est: ${estimate}, Actual: ${actual}, Surprise: {surprise}%",
                                    url=url,
                                    published_date=date,
                                    ticker=ticker,
                                    sentiment=sentiment,
                                )
                                entry["estimate_eps"] = estimate
                                entry["actual_eps"] = actual
                                entry["surprise_pct"] = surprise
                                entry["signal_type"] = "earnings_history"

                                results.append(entry)
                            except (ValueError, IndexError):
                                continue

        except Exception as e:
            logger.error(f"Error collecting earnings surprises for {ticker}: {e}")

        return results

    def _get_earnings_date(self, ticker: str) -> dict[str, Any] | None:
        """
        Get next earnings date for a ticker.

        Args:
            ticker: Stock symbol

        Returns:
            Earnings date info or None
        """
        url = f"https://finance.yahoo.com/quote/{ticker}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                return None

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for earnings date
            earnings_elem = soup.find(text=re.compile(r"Earnings Date", re.I))
            if earnings_elem:
                parent = earnings_elem.find_parent("tr")
                if parent:
                    cells = parent.find_all("td")
                    if len(cells) >= 2:
                        date_text = cells[1].text.strip()

                        # Check if earnings is within next 7 days
                        days_until = self._days_until_earnings(date_text)

                        if days_until is not None and days_until <= 7:
                            sentiment = 0.5  # Neutral, but flagged as important
                            alert_level = "HIGH"
                        elif days_until is not None and days_until <= 14:
                            sentiment = 0.5
                            alert_level = "MEDIUM"
                        else:
                            sentiment = 0.5
                            alert_level = "LOW"

                        entry = self.normalize_article(
                            title=f"Upcoming Earnings: {ticker}",
                            content=f"Earnings date: {date_text}",
                            url=url,
                            published_date=datetime.now().isoformat(),
                            ticker=ticker,
                            sentiment=sentiment,
                        )
                        entry["earnings_date"] = date_text
                        entry["days_until"] = days_until
                        entry["alert_level"] = alert_level
                        entry["signal_type"] = "earnings_calendar"

                        return entry

        except Exception as e:
            logger.error(f"Error getting earnings date for {ticker}: {e}")

        return None

    def _collect_earnings_calendar(self) -> list[dict[str, Any]]:
        """
        Collect this week's earnings calendar.

        Returns:
            List of upcoming earnings reports
        """
        results = []

        try:
            response = requests.get(self.YAHOO_EARNINGS_URL, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Find earnings calendar table
            table = soup.find("table")
            if table:
                rows = table.find_all("tr")[1:30]  # Top 30 earnings
                for row in rows:
                    cells = row.find_all("td")
                    if len(cells) >= 3:
                        try:
                            ticker_elem = cells[0].find("a")
                            ticker = (
                                ticker_elem.text.strip() if ticker_elem else cells[0].text.strip()
                            )

                            company = cells[1].text.strip() if len(cells) > 1 else ticker
                            time = cells[2].text.strip() if len(cells) > 2 else "N/A"

                            # Extract EPS estimate if available
                            eps_est = None
                            if len(cells) > 3:
                                match = re.search(r"([-\d.]+)", cells[3].text)
                                if match:
                                    eps_est = float(match.group(1))

                            entry = self.normalize_article(
                                title=f"Earnings Today: {ticker} ({company})",
                                content=f"{ticker} reports {time}, EPS Est: ${eps_est}",
                                url=self.YAHOO_EARNINGS_URL,
                                published_date=datetime.now().isoformat(),
                                ticker=ticker,
                                sentiment=0.5,
                            )
                            entry["company"] = company
                            entry["report_time"] = time
                            entry["eps_estimate"] = eps_est
                            entry["signal_type"] = "earnings_today"

                            results.append(entry)
                        except (ValueError, IndexError):
                            continue

        except Exception as e:
            logger.error(f"Error collecting earnings calendar: {e}")

        return results

    def _parse_float(self, text: str) -> float:
        """Parse float from text."""
        try:
            text = text.replace("$", "").replace("%", "").replace(",", "").strip()
            return float(text)
        except (ValueError, AttributeError):
            return 0.0

    def _days_until_earnings(self, date_text: str) -> int | None:
        """
        Calculate days until earnings from date text.

        Args:
            date_text: Date string like "Dec 15, 2025"

        Returns:
            Days until earnings or None
        """
        try:
            # Try various date formats
            for fmt in ["%b %d, %Y", "%B %d, %Y", "%m/%d/%Y", "%Y-%m-%d"]:
                try:
                    earnings_date = datetime.strptime(date_text.split(" - ")[0].strip(), fmt)
                    delta = earnings_date - datetime.now()
                    return max(0, delta.days)
                except ValueError:
                    continue
        except Exception:
            pass
        return None

    def collect_daily_snapshot(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Collect daily earnings snapshot.

        Args:
            tickers: Optional list of tickers to focus on

        Returns:
            Combined earnings data
        """
        results = []

        # Today's earnings calendar
        calendar = self.collect_market_news()
        results.extend(calendar)

        # Ticker-specific earnings data
        if tickers:
            for ticker in tickers:
                ticker_data = self.collect_ticker_news(ticker)
                results.extend(ticker_data)

        logger.info(f"Daily earnings snapshot: {len(results)} entries")
        return results

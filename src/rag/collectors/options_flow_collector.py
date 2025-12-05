"""
Options Flow Collector for RAG System

Collects unusual options activity data to identify institutional trading signals.
Sources: Barchart, MarketChameleon (free tiers), Yahoo Finance options chain analysis.
"""

from __future__ import annotations
import logging
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.rag.collectors.base_collector import BaseNewsCollector

logger = logging.getLogger(__name__)


class OptionsFlowCollector(BaseNewsCollector):
    """
    Collector for unusual options activity data.

    Tracks:
    - Large volume spikes vs. open interest
    - Unusual call/put ratios
    - Block trades (institutional orders)
    - Sweeps (aggressive multi-exchange orders)

    This provides "smart money" signals that can inform trading decisions.
    """

    BARCHART_URL = "https://www.barchart.com/options/unusual-activity/stocks"
    YAHOO_OPTIONS_URL = "https://finance.yahoo.com/quote/{symbol}/options"

    def __init__(self):
        super().__init__(source_name="options_flow")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect options flow data for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., "NVDA")
            days_back: Not directly used, but maintains interface consistency

        Returns:
            List of unusual options activity entries
        """
        results = []

        # Try Yahoo Finance options chain for basic data
        yahoo_data = self._collect_yahoo_options(ticker)
        results.extend(yahoo_data)

        logger.info(f"Collected {len(results)} options flow entries for {ticker}")
        return results

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect market-wide unusual options activity.

        Returns:
            List of top unusual options activity across all stocks
        """
        results = []

        # Collect from Barchart unusual activity page
        barchart_data = self._collect_barchart_unusual()
        results.extend(barchart_data)

        logger.info(f"Collected {len(results)} market-wide unusual options entries")
        return results

    def _collect_yahoo_options(self, ticker: str) -> list[dict[str, Any]]:
        """
        Collect options chain data from Yahoo Finance.

        Args:
            ticker: Stock symbol

        Returns:
            List of options activity entries
        """
        results = []
        url = self.YAHOO_OPTIONS_URL.format(symbol=ticker)

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            if response.status_code != 200:
                logger.warning(f"Yahoo options fetch failed for {ticker}: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Look for high volume options
            # Parse options tables for unusual volume
            tables = soup.find_all("table")
            for table in tables:
                rows = table.find_all("tr")
                for row in rows[1:10]:  # Skip header, limit to top entries
                    cells = row.find_all("td")
                    if len(cells) >= 7:
                        try:
                            strike = cells[2].text.strip() if len(cells) > 2 else "N/A"
                            volume = cells[4].text.strip() if len(cells) > 4 else "0"
                            open_interest = cells[5].text.strip() if len(cells) > 5 else "0"

                            # Parse volume to check for unusual activity
                            vol_num = self._parse_number(volume)
                            oi_num = self._parse_number(open_interest)

                            # Flag if volume > 2x open interest (unusual)
                            if oi_num > 0 and vol_num > (oi_num * 2):
                                entry = self.normalize_article(
                                    title=f"Unusual Options: {ticker} Strike ${strike}",
                                    content=f"Volume {volume} vs OI {open_interest} ({vol_num / oi_num:.1f}x)",
                                    url=url,
                                    published_date=datetime.now().isoformat(),
                                    ticker=ticker,
                                    sentiment=0.6 if "call" in table.text.lower() else 0.4,
                                )
                                entry["strike"] = strike
                                entry["volume"] = vol_num
                                entry["open_interest"] = oi_num
                                entry["vol_oi_ratio"] = (
                                    round(vol_num / oi_num, 2) if oi_num > 0 else 0
                                )
                                entry["signal_type"] = "unusual_volume"
                                results.append(entry)
                        except (ValueError, IndexError):
                            continue

        except Exception as e:
            logger.error(f"Error collecting Yahoo options for {ticker}: {e}")

        return results

    def _collect_barchart_unusual(self) -> list[dict[str, Any]]:
        """
        Collect unusual options activity from Barchart.

        Returns:
            List of unusual activity entries
        """
        results = []

        try:
            response = requests.get(self.BARCHART_URL, headers=self.headers, timeout=15)
            if response.status_code != 200:
                logger.warning(f"Barchart fetch failed: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Find unusual activity table
            table = soup.find("table", class_="bc-table-scrollable-inner")
            if not table:
                # Try alternative selector
                table = soup.find("table")

            if table:
                rows = table.find_all("tr")
                for row in rows[1:20]:  # Top 20 unusual activity
                    cells = row.find_all("td")
                    if len(cells) >= 5:
                        try:
                            symbol = cells[0].text.strip()
                            option_type = cells[1].text.strip() if len(cells) > 1 else "Unknown"
                            strike = cells[2].text.strip() if len(cells) > 2 else "N/A"
                            exp_date = cells[3].text.strip() if len(cells) > 3 else "N/A"
                            volume = cells[4].text.strip() if len(cells) > 4 else "0"

                            # Determine sentiment from option type
                            is_call = "call" in option_type.lower()
                            sentiment = 0.7 if is_call else 0.3

                            entry = self.normalize_article(
                                title=f"Unusual {option_type}: {symbol}",
                                content=f"{symbol} {strike} {exp_date} - Volume: {volume}",
                                url=self.BARCHART_URL,
                                published_date=datetime.now().isoformat(),
                                ticker=symbol,
                                sentiment=sentiment,
                            )
                            entry["option_type"] = option_type
                            entry["strike"] = strike
                            entry["expiration"] = exp_date
                            entry["volume"] = self._parse_number(volume)
                            entry["signal_type"] = "unusual_activity"
                            entry["signal_strength"] = "high"
                            results.append(entry)
                        except (ValueError, IndexError):
                            continue

        except Exception as e:
            logger.error(f"Error collecting Barchart unusual activity: {e}")

        return results

    def _parse_number(self, text: str) -> int:
        """Parse number from text, handling K/M suffixes."""
        try:
            text = text.replace(",", "").strip()
            if "K" in text.upper():
                return int(float(text.upper().replace("K", "")) * 1000)
            elif "M" in text.upper():
                return int(float(text.upper().replace("M", "")) * 1000000)
            return int(float(text))
        except (ValueError, AttributeError):
            return 0

    def collect_daily_snapshot(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Collect daily options flow snapshot.

        Args:
            tickers: Optional list of tickers to focus on

        Returns:
            Combined options flow data
        """
        results = []

        # Market-wide unusual activity
        market_flow = self.collect_market_news()
        results.extend(market_flow)

        # Ticker-specific if provided
        if tickers:
            for ticker in tickers:
                ticker_flow = self.collect_ticker_news(ticker)
                results.extend(ticker_flow)

        logger.info(f"Daily options flow snapshot: {len(results)} entries")
        return results

"""
Finviz Screener Collector for RAG System

Collects stock screener data, technical signals, and market insights from Finviz.
Free tier provides delayed data, suitable for end-of-day analysis.
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


class FinvizCollector(BaseNewsCollector):
    """
    Collector for Finviz screener and market data.

    Collects:
    - Stock screener signals (oversold/overbought, new highs/lows)
    - Technical patterns (double bottom, breakout, etc.)
    - Insider trading activity
    - Analyst upgrades/downgrades
    - Sector performance
    """

    BASE_URL = "https://finviz.com"
    QUOTE_URL = "https://finviz.com/quote.ashx?t={symbol}"
    SCREENER_URL = "https://finviz.com/screener.ashx"
    NEWS_URL = "https://finviz.com/news.ashx"

    # Predefined screener filters for actionable signals
    SCREENER_FILTERS = {
        "oversold": "ta_rsi_os",  # RSI oversold
        "overbought": "ta_rsi_ob",  # RSI overbought
        "new_high": "ta_newhigh",  # New 52-week high
        "new_low": "ta_newlow",  # New 52-week low
        "unusual_volume": "sh_avgvol_o500,sh_relvol_o2",  # High relative volume
        "golden_cross": "ta_sma20_pa,ta_sma50_pa",  # Price above 20/50 SMA
        "death_cross": "ta_sma20_pb,ta_sma50_pb",  # Price below 20/50 SMA
    }

    def __init__(self):
        super().__init__(source_name="finviz")
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }

    def collect_ticker_news(self, ticker: str, days_back: int = 7) -> list[dict[str, Any]]:
        """
        Collect Finviz data for a specific ticker.

        Args:
            ticker: Stock symbol (e.g., "NVDA")
            days_back: Not directly used (Finviz shows recent data)

        Returns:
            List of technical signals and news for the ticker
        """
        results = []

        try:
            url = self.QUOTE_URL.format(symbol=ticker)
            response = requests.get(url, headers=self.headers, timeout=10)

            if response.status_code != 200:
                logger.warning(f"Finviz quote fetch failed for {ticker}: {response.status_code}")
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Extract fundamental/technical snapshot
            snapshot = self._extract_quote_snapshot(soup, ticker, url)
            if snapshot:
                results.append(snapshot)

            # Extract news headlines
            news = self._extract_ticker_news(soup, ticker, url)
            results.extend(news)

            # Extract analyst ratings
            ratings = self._extract_analyst_ratings(soup, ticker, url)
            if ratings:
                results.append(ratings)

            # Extract insider trading
            insider = self._extract_insider_activity(soup, ticker, url)
            if insider:
                results.append(insider)

        except Exception as e:
            logger.error(f"Error collecting Finviz data for {ticker}: {e}")

        logger.info(f"Collected {len(results)} Finviz entries for {ticker}")
        return results

    def collect_market_news(self, days_back: int = 1) -> list[dict[str, Any]]:
        """
        Collect market-wide screener signals.

        Returns:
            List of market signals (oversold stocks, breakouts, etc.)
        """
        results = []

        # Collect stocks matching each signal type
        for signal_name, filter_code in self.SCREENER_FILTERS.items():
            try:
                signal_stocks = self._run_screener(signal_name, filter_code)
                results.extend(signal_stocks)
            except Exception as e:
                logger.warning(f"Screener {signal_name} failed: {e}")

        logger.info(f"Collected {len(results)} market screener signals")
        return results

    def _extract_quote_snapshot(
        self, soup: BeautifulSoup, ticker: str, url: str
    ) -> dict[str, Any] | None:
        """Extract key metrics from quote page."""
        try:
            snapshot_table = soup.find("table", class_="snapshot-table2")
            if not snapshot_table:
                return None

            metrics = {}
            cells = snapshot_table.find_all("td")

            # Parse key-value pairs from table
            for i in range(0, len(cells) - 1, 2):
                key = cells[i].text.strip()
                value = cells[i + 1].text.strip()
                metrics[key] = value

            # Extract key trading signals
            rsi = self._parse_float(metrics.get("RSI (14)", "50"))
            perf_week = metrics.get("Perf Week", "0%")
            perf_month = metrics.get("Perf Month", "0%")
            rel_volume = self._parse_float(metrics.get("Rel Volume", "1"))
            sma20 = metrics.get("SMA20", "0%")
            sma50 = metrics.get("SMA50", "0%")

            # Determine sentiment from RSI
            if rsi < 30:
                sentiment = 0.7  # Oversold = bullish signal
                signal = "RSI_OVERSOLD"
            elif rsi > 70:
                sentiment = 0.3  # Overbought = bearish signal
                signal = "RSI_OVERBOUGHT"
            else:
                sentiment = 0.5
                signal = "NEUTRAL"

            # Boost sentiment if high relative volume
            if rel_volume > 2:
                signal += "_HIGH_VOLUME"

            entry = self.normalize_article(
                title=f"Finviz Snapshot: {ticker}",
                content=f"RSI: {rsi:.1f}, Week: {perf_week}, Month: {perf_month}, RelVol: {rel_volume:.2f}",
                url=url,
                published_date=datetime.now().isoformat(),
                ticker=ticker,
                sentiment=sentiment,
            )
            entry["signal_type"] = signal
            entry["rsi"] = rsi
            entry["rel_volume"] = rel_volume
            entry["sma20"] = sma20
            entry["sma50"] = sma50
            entry["perf_week"] = perf_week
            entry["perf_month"] = perf_month
            entry["metrics"] = metrics

            return entry

        except Exception as e:
            logger.error(f"Error extracting Finviz snapshot for {ticker}: {e}")
            return None

    def _extract_ticker_news(
        self, soup: BeautifulSoup, ticker: str, base_url: str
    ) -> list[dict[str, Any]]:
        """Extract news headlines from ticker page."""
        results = []

        try:
            news_table = soup.find("table", id="news-table")
            if not news_table:
                return []

            rows = news_table.find_all("tr")
            for row in rows[:10]:  # Top 10 headlines
                cells = row.find_all("td")
                if len(cells) >= 2:
                    time_cell = cells[0].text.strip()
                    link = cells[1].find("a")
                    if link:
                        headline = link.text.strip()
                        news_url = link.get("href", base_url)

                        entry = self.normalize_article(
                            title=headline,
                            content=f"{ticker} news: {headline}",
                            url=news_url,
                            published_date=datetime.now().isoformat(),
                            ticker=ticker,
                            sentiment=0.5,  # Neutral until analyzed
                        )
                        entry["time"] = time_cell
                        entry["signal_type"] = "news"
                        results.append(entry)

        except Exception as e:
            logger.error(f"Error extracting Finviz news for {ticker}: {e}")

        return results

    def _extract_analyst_ratings(
        self, soup: BeautifulSoup, ticker: str, url: str
    ) -> dict[str, Any] | None:
        """Extract analyst ratings and price targets."""
        try:
            # Look for analyst recommendations table
            tables = soup.find_all("table", class_="fullview-ratings-outer")
            if not tables:
                return None

            upgrades = 0
            downgrades = 0
            price_targets = []

            for table in tables:
                rows = table.find_all("tr")
                for row in rows:
                    text = row.text.lower()
                    if "upgrade" in text:
                        upgrades += 1
                    elif "downgrade" in text:
                        downgrades += 1

                    # Extract price targets
                    pt_match = re.search(r"\$(\d+(?:\.\d+)?)", row.text)
                    if pt_match:
                        price_targets.append(float(pt_match.group(1)))

            if upgrades == 0 and downgrades == 0:
                return None

            # Sentiment based on upgrade/downgrade ratio
            if upgrades > downgrades:
                sentiment = 0.7
            elif downgrades > upgrades:
                sentiment = 0.3
            else:
                sentiment = 0.5

            avg_pt = sum(price_targets) / len(price_targets) if price_targets else 0

            entry = self.normalize_article(
                title=f"Analyst Activity: {ticker}",
                content=f"Upgrades: {upgrades}, Downgrades: {downgrades}, Avg PT: ${avg_pt:.2f}",
                url=url,
                published_date=datetime.now().isoformat(),
                ticker=ticker,
                sentiment=sentiment,
            )
            entry["signal_type"] = "analyst_ratings"
            entry["upgrades"] = upgrades
            entry["downgrades"] = downgrades
            entry["avg_price_target"] = avg_pt

            return entry

        except Exception as e:
            logger.error(f"Error extracting analyst ratings for {ticker}: {e}")
            return None

    def _extract_insider_activity(
        self, soup: BeautifulSoup, ticker: str, url: str
    ) -> dict[str, Any] | None:
        """Extract insider trading activity."""
        try:
            # Look for insider trading table
            insider_table = soup.find("table", class_="body-table")
            if not insider_table:
                return None

            buys = 0
            sells = 0
            total_value = 0

            rows = insider_table.find_all("tr")
            for row in rows[1:]:  # Skip header
                cells = row.find_all("td")
                if len(cells) >= 5:
                    transaction = cells[3].text.strip().lower()
                    value_text = cells[4].text.strip()

                    if "buy" in transaction or "purchase" in transaction:
                        buys += 1
                    elif "sale" in transaction or "sell" in transaction:
                        sells += 1

                    # Parse transaction value
                    value_match = re.search(r"[\d,]+", value_text.replace(",", ""))
                    if value_match:
                        total_value += int(value_match.group())

            if buys == 0 and sells == 0:
                return None

            # Insider buying is bullish signal
            if buys > sells:
                sentiment = 0.75
                signal = "INSIDER_BUYING"
            elif sells > buys:
                sentiment = 0.25
                signal = "INSIDER_SELLING"
            else:
                sentiment = 0.5
                signal = "INSIDER_NEUTRAL"

            entry = self.normalize_article(
                title=f"Insider Activity: {ticker}",
                content=f"Buys: {buys}, Sells: {sells}, Value: ${total_value:,}",
                url=url,
                published_date=datetime.now().isoformat(),
                ticker=ticker,
                sentiment=sentiment,
            )
            entry["signal_type"] = signal
            entry["insider_buys"] = buys
            entry["insider_sells"] = sells
            entry["total_value"] = total_value

            return entry

        except Exception as e:
            logger.error(f"Error extracting insider activity for {ticker}: {e}")
            return None

    def _run_screener(self, signal_name: str, filter_code: str) -> list[dict[str, Any]]:
        """
        Run a screener with specific filters.

        Args:
            signal_name: Human-readable signal name
            filter_code: Finviz filter parameter

        Returns:
            List of stocks matching the screen
        """
        results = []
        url = f"{self.SCREENER_URL}?v=111&f={filter_code}"

        try:
            response = requests.get(url, headers=self.headers, timeout=15)
            if response.status_code != 200:
                return []

            soup = BeautifulSoup(response.text, "html.parser")

            # Find screener results table
            table = soup.find("table", id="screener-views-table")
            if not table:
                return []

            rows = table.find_all("tr")[1:15]  # Top 15 results
            for row in rows:
                cells = row.find_all("td")
                if len(cells) >= 2:
                    ticker_link = cells[1].find("a")
                    if ticker_link:
                        ticker = ticker_link.text.strip()

                        # Determine sentiment based on signal type
                        if signal_name in ["oversold", "new_low"]:
                            sentiment = 0.7  # Potential bounce
                        elif signal_name in ["overbought", "new_high"]:
                            sentiment = 0.4  # Potential reversal
                        elif signal_name == "golden_cross":
                            sentiment = 0.75
                        elif signal_name == "death_cross":
                            sentiment = 0.25
                        else:
                            sentiment = 0.6

                        entry = self.normalize_article(
                            title=f"Screener: {ticker} - {signal_name.replace('_', ' ').title()}",
                            content=f"{ticker} triggered {signal_name} screen",
                            url=url,
                            published_date=datetime.now().isoformat(),
                            ticker=ticker,
                            sentiment=sentiment,
                        )
                        entry["signal_type"] = f"screener_{signal_name}"
                        entry["screener_url"] = url
                        results.append(entry)

        except Exception as e:
            logger.error(f"Error running screener {signal_name}: {e}")

        return results

    def _parse_float(self, text: str) -> float:
        """Parse float from text, handling percentages and special chars."""
        try:
            text = text.replace("%", "").replace(",", "").strip()
            return float(text)
        except (ValueError, AttributeError):
            return 0.0

    def collect_daily_snapshot(self, tickers: list[str] | None = None) -> list[dict[str, Any]]:
        """Collect daily Finviz snapshot."""
        results = []

        # Market-wide screener signals
        market_signals = self.collect_market_news()
        results.extend(market_signals)

        # Ticker-specific data
        if tickers:
            for ticker in tickers:
                ticker_data = self.collect_ticker_news(ticker)
                results.extend(ticker_data)

        logger.info(f"Daily Finviz snapshot: {len(results)} entries")
        return results

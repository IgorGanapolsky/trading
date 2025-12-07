#!/usr/bin/env python3
"""
Financial Data Fetcher Skill - Implementation
Fetches real-time and historical market data from Alpaca and other sources
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime, timedelta
from functools import wraps
from typing import Any, Optional

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../.."))

from dotenv import load_dotenv

load_dotenv()

try:
    from alpaca.data.historical import StockHistoricalDataClient
    from alpaca.data.requests import (
        StockBarsRequest,
        StockLatestQuoteRequest,
        StockSnapshotRequest,
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    from alpaca.trading.client import TradingClient

    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    # Create dummy classes for type hints when alpaca is not installed
    TimeFrame = type("TimeFrame", (), {})
    TimeFrameUnit = type("TimeFrameUnit", (), {})
    print("Warning: alpaca-py not installed. Install with: pip install alpaca-py")

try:
    import yfinance as yf

    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    print("Warning: yfinance not installed. Install with: pip install yfinance")


# Simple in-memory cache
_cache = {}
_cache_ttl = 300  # 5 minutes


def cached(ttl=300):
    """Cache decorator for API calls"""

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Create cache key from function name and arguments
            cache_key = f"{func.__name__}:{str(args)}:{str(kwargs)}"

            # Check cache
            if cache_key in _cache:
                cached_time, cached_result = _cache[cache_key]
                if time.time() - cached_time < ttl:
                    return cached_result

            # Call function and cache result
            result = func(*args, **kwargs)
            _cache[cache_key] = (time.time(), result)
            return result

        return wrapper

    return decorator


def error_response(error_msg: str, error_code: str = "ERROR") -> dict[str, Any]:
    """Standard error response format"""
    return {"success": False, "error": error_msg, "error_code": error_code}


def success_response(data: Any) -> dict[str, Any]:
    """Standard success response format"""
    return {"success": True, "data": data}


class FinancialDataFetcher:
    """Main class for fetching financial data"""

    def __init__(self):
        """Initialize API clients"""
        self.alpaca_api_key = os.getenv("ALPACA_API_KEY")
        self.alpaca_secret = os.getenv("ALPACA_SECRET_KEY")
        self.paper_trading = os.getenv("PAPER_TRADING", "true").lower() == "true"

        if ALPACA_AVAILABLE and self.alpaca_api_key and self.alpaca_secret:
            self.data_client = StockHistoricalDataClient(self.alpaca_api_key, self.alpaca_secret)
            self.trading_client = TradingClient(
                self.alpaca_api_key, self.alpaca_secret, paper=self.paper_trading
            )
        else:
            self.data_client = None
            self.trading_client = None

    def _parse_timeframe(self, timeframe_str: str) -> TimeFrame:
        """Parse timeframe string to Alpaca TimeFrame object"""
        timeframe_map = {
            "1Min": TimeFrame(1, TimeFrameUnit.Minute),
            "5Min": TimeFrame(5, TimeFrameUnit.Minute),
            "15Min": TimeFrame(15, TimeFrameUnit.Minute),
            "1Hour": TimeFrame(1, TimeFrameUnit.Hour),
            "1Day": TimeFrame(1, TimeFrameUnit.Day),
        }
        return timeframe_map.get(timeframe_str, TimeFrame(1, TimeFrameUnit.Day))

    @cached(ttl=300)
    def get_price_data(
        self,
        symbols: list[str],
        timeframe: str = "1Day",
        start_date: str | None = None,
        end_date: str | None = None,
        limit: int = 100,
    ) -> dict[str, Any]:
        """
        Fetch historical price data for symbols

        Args:
            symbols: List of ticker symbols
            timeframe: Bar timeframe (1Min, 5Min, 1Hour, 1Day)
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
            limit: Number of bars to fetch

        Returns:
            Dict with success status and data
        """
        try:
            if not symbols:
                return error_response("No symbols provided", "INVALID_INPUT")

            # Use Alpaca if available
            if self.data_client:
                return self._get_price_data_alpaca(symbols, timeframe, start_date, end_date, limit)

            # Fall back to yfinance
            elif YFINANCE_AVAILABLE:
                return self._get_price_data_yfinance(
                    symbols, timeframe, start_date, end_date, limit
                )

            else:
                return error_response("No data source available", "NO_DATA_SOURCE")

        except Exception as e:
            return error_response(f"Error fetching price data: {str(e)}", "FETCH_ERROR")

    def _get_price_data_alpaca(
        self,
        symbols: list[str],
        timeframe: str,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Fetch price data from Alpaca"""
        try:
            # Parse dates
            if start_date:
                start = datetime.strptime(start_date, "%Y-%m-%d")
            else:
                start = datetime.now() - timedelta(days=30)

            end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()

            # Create request
            request = StockBarsRequest(
                symbol_or_symbols=symbols,
                timeframe=self._parse_timeframe(timeframe),
                start=start,
                end=end,
                limit=limit,
            )

            # Fetch data
            bars = self.data_client.get_stock_bars(request)

            # Format response
            result = {}
            for symbol in symbols:
                if symbol in bars:
                    result[symbol] = [
                        {
                            "timestamp": bar.timestamp.isoformat(),
                            "open": float(bar.open),
                            "high": float(bar.high),
                            "low": float(bar.low),
                            "close": float(bar.close),
                            "volume": int(bar.volume),
                            "vwap": (
                                float(bar.vwap) if hasattr(bar, "vwap") and bar.vwap else None
                            ),
                        }
                        for bar in bars[symbol]
                    ]
                else:
                    result[symbol] = []

            return success_response(result)

        except Exception as e:
            return error_response(f"Alpaca API error: {str(e)}", "ALPACA_ERROR")

    def _get_price_data_yfinance(
        self,
        symbols: list[str],
        timeframe: str,
        start_date: str | None,
        end_date: str | None,
        limit: int,
    ) -> dict[str, Any]:
        """Fetch price data from yfinance (fallback)"""
        try:
            # Map timeframe to yfinance interval
            interval_map = {
                "1Min": "1m",
                "5Min": "5m",
                "15Min": "15m",
                "1Hour": "1h",
                "1Day": "1d",
            }
            interval = interval_map.get(timeframe, "1d")

            # Calculate period if no dates provided
            period = "1mo" if not start_date else None

            result = {}
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)

                    if period:
                        df = ticker.history(period=period, interval=interval)
                    else:
                        df = ticker.history(start=start_date, end=end_date, interval=interval)

                    if len(df) > limit:
                        df = df.tail(limit)

                    result[symbol] = [
                        {
                            "timestamp": row.name.isoformat(),
                            "open": float(row["Open"]),
                            "high": float(row["High"]),
                            "low": float(row["Low"]),
                            "close": float(row["Close"]),
                            "volume": int(row["Volume"]),
                            "vwap": None,
                        }
                        for _, row in df.iterrows()
                    ]
                except Exception as e:
                    result[symbol] = []
                    print(f"Warning: Could not fetch data for {symbol}: {e}")

            return success_response(result)

        except Exception as e:
            return error_response(f"yfinance error: {str(e)}", "YFINANCE_ERROR")

    @cached(ttl=60)
    def get_market_snapshot(self, symbols: list[str]) -> dict[str, Any]:
        """
        Get real-time market snapshot for symbols

        Args:
            symbols: List of ticker symbols

        Returns:
            Dict with current quotes and market data
        """
        try:
            if not symbols:
                return error_response("No symbols provided", "INVALID_INPUT")

            if not self.data_client:
                return error_response("Alpaca client not available", "NO_CLIENT")

            # Create request
            request = StockSnapshotRequest(symbol_or_symbols=symbols)

            # Fetch snapshots
            snapshots = self.data_client.get_stock_snapshot(request)

            # Format response
            result = {}
            for symbol in symbols:
                if symbol in snapshots:
                    snap = snapshots[symbol]
                    result[symbol] = {
                        "price": (float(snap.latest_trade.price) if snap.latest_trade else None),
                        "bid": (float(snap.latest_quote.bid_price) if snap.latest_quote else None),
                        "ask": (float(snap.latest_quote.ask_price) if snap.latest_quote else None),
                        "bid_size": (
                            int(snap.latest_quote.bid_size) if snap.latest_quote else None
                        ),
                        "ask_size": (
                            int(snap.latest_quote.ask_size) if snap.latest_quote else None
                        ),
                        "last_trade_time": (
                            snap.latest_trade.timestamp.isoformat() if snap.latest_trade else None
                        ),
                        "volume": (int(snap.daily_bar.volume) if snap.daily_bar else None),
                        "vwap": (
                            float(snap.daily_bar.vwap)
                            if snap.daily_bar and hasattr(snap.daily_bar, "vwap")
                            else None
                        ),
                    }
                else:
                    result[symbol] = None

            return success_response(result)

        except Exception as e:
            return error_response(f"Error fetching market snapshot: {str(e)}", "FETCH_ERROR")

    def get_latest_news(self, symbols: list[str], limit: int = 10) -> dict[str, Any]:
        """
        Fetch latest financial news for symbols

        Args:
            symbols: List of ticker symbols
            limit: Number of news items to fetch

        Returns:
            Dict with news articles
        """
        try:
            # Note: Alpaca News API requires subscription
            # For now, return placeholder indicating this needs implementation
            return success_response(
                [
                    {
                        "symbol": symbol,
                        "headline": "News API requires implementation",
                        "summary": "Alpaca News API requires paid subscription. Consider alternatives like Alpha Vantage, Finnhub, or NewsAPI.",
                        "source": "System",
                        "url": "",
                        "published_at": datetime.now().isoformat(),
                        "sentiment": "neutral",
                    }
                    for symbol in symbols
                ]
            )

        except Exception as e:
            return error_response(f"Error fetching news: {str(e)}", "FETCH_ERROR")

    def get_fundamentals(
        self, symbols: list[str], metrics: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Fetch fundamental data for symbols

        Args:
            symbols: List of ticker symbols
            metrics: Specific metrics to fetch (optional)

        Returns:
            Dict with fundamental data
        """
        try:
            if not YFINANCE_AVAILABLE:
                return error_response("yfinance not available", "NO_DATA_SOURCE")

            result = {}
            for symbol in symbols:
                try:
                    ticker = yf.Ticker(symbol)
                    info = ticker.info

                    result[symbol] = {
                        "market_cap": info.get("marketCap"),
                        "pe_ratio": info.get("trailingPE"),
                        "forward_pe": info.get("forwardPE"),
                        "eps": info.get("trailingEps"),
                        "dividend_yield": info.get("dividendYield"),
                        "beta": info.get("beta"),
                        "52_week_high": info.get("fiftyTwoWeekHigh"),
                        "52_week_low": info.get("fiftyTwoWeekLow"),
                        "avg_volume": info.get("averageVolume"),
                        "shares_outstanding": info.get("sharesOutstanding"),
                    }
                except Exception as e:
                    result[symbol] = None
                    print(f"Warning: Could not fetch fundamentals for {symbol}: {e}")

            return success_response(result)

        except Exception as e:
            return error_response(f"Error fetching fundamentals: {str(e)}", "FETCH_ERROR")


def main():
    """CLI interface for the skill"""
    parser = argparse.ArgumentParser(description="Financial Data Fetcher Skill")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # get_price_data command
    price_parser = subparsers.add_parser("get_price_data", help="Fetch price data")
    price_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    price_parser.add_argument(
        "--timeframe", default="1Day", help="Timeframe (1Min, 5Min, 1Hour, 1Day)"
    )
    price_parser.add_argument("--start-date", help="Start date (YYYY-MM-DD)")
    price_parser.add_argument("--end-date", help="End date (YYYY-MM-DD)")
    price_parser.add_argument("--limit", type=int, default=100, help="Number of bars")

    # get_market_snapshot command
    snapshot_parser = subparsers.add_parser("get_market_snapshot", help="Get market snapshot")
    snapshot_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")

    # get_latest_news command
    news_parser = subparsers.add_parser("get_latest_news", help="Fetch latest news")
    news_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")
    news_parser.add_argument("--limit", type=int, default=10, help="Number of news items")

    # get_fundamentals command
    fund_parser = subparsers.add_parser("get_fundamentals", help="Fetch fundamentals")
    fund_parser.add_argument("--symbols", nargs="+", required=True, help="Ticker symbols")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize fetcher
    fetcher = FinancialDataFetcher()

    # Execute command
    if args.command == "get_price_data":
        result = fetcher.get_price_data(
            symbols=args.symbols,
            timeframe=args.timeframe,
            start_date=args.start_date,
            end_date=args.end_date,
            limit=args.limit,
        )
    elif args.command == "get_market_snapshot":
        result = fetcher.get_market_snapshot(symbols=args.symbols)
    elif args.command == "get_latest_news":
        result = fetcher.get_latest_news(symbols=args.symbols, limit=args.limit)
    elif args.command == "get_fundamentals":
        result = fetcher.get_fundamentals(symbols=args.symbols)
    else:
        print(f"Unknown command: {args.command}")
        return

    # Print result
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
# ruff: noqa: UP045

"""
Trading-specific tools for deepagents.

Wraps existing trading utilities into deepagents-compatible tools.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime

from langchain_core.tools import tool

from src.utils.market_data import get_market_data_provider

logger = logging.getLogger(__name__)


# Lazy import to avoid breaking crypto trading when RAG dependencies aren't installed
def _get_sentiment_store():
    """Lazy import of SentimentRAGStore."""
    try:
        from src.rag.sentiment_store import SentimentRAGStore

        return SentimentRAGStore
    except ImportError as e:
        logger.warning(f"SentimentRAGStore not available: {e}")
        return None


@tool
def get_market_data(
    symbol: str,
    lookback_days: int = 60,
    timeframe: str = "1Day",
) -> str:
    """
    Fetch historical market data (OHLCV) for a symbol.

    Args:
        symbol: Stock ticker symbol (e.g., 'AAPL', 'SPY')
        lookback_days: Number of days of historical data to fetch (default: 60)
        timeframe: Data timeframe - '1Day', '1Hour', '5Min' (default: '1Day')

    Returns:
        JSON string with market data including dates, open, high, low, close, volume
    """
    try:
        provider = get_market_data_provider()
        df = provider.get_daily_bars(symbol=symbol, lookback_days=lookback_days)

        if df.empty:
            return json.dumps({"error": f"No data available for {symbol}"})

        # Convert DataFrame to JSON-serializable format
        data = {
            "symbol": symbol,
            "rows": len(df),
            "start_date": df.index[0].isoformat() if len(df) > 0 else None,
            "end_date": df.index[-1].isoformat() if len(df) > 0 else None,
            "latest_close": float(df["Close"].iloc[-1]) if len(df) > 0 else None,
            "latest_volume": float(df["Volume"].iloc[-1]) if len(df) > 0 else None,
            "data": [
                {
                    "date": date.isoformat(),
                    "open": float(row["Open"]),
                    "high": float(row["High"]),
                    "low": float(row["Low"]),
                    "close": float(row["Close"]),
                    "volume": float(row["Volume"]),
                }
                for date, row in df.tail(100).iterrows()  # Return last 100 bars
            ],
        }
        return json.dumps(data, indent=2)
    except Exception as e:
        logger.exception(f"Error fetching market data for {symbol}")
        return json.dumps({"error": str(e)})


@tool
def query_sentiment(
    query: str,
    ticker: str | None = None,
    limit: int = 5,
) -> str:
    """
    Search historical sentiment data using semantic search.

    Args:
        query: Natural language query about market sentiment (e.g., "bullish momentum")
        ticker: Optional ticker symbol to filter results
        limit: Maximum number of results to return (default: 5)

    Returns:
        JSON string with sentiment entries matching the query
    """
    try:
        SentimentRAGStore = _get_sentiment_store()
        if SentimentRAGStore is None:
            return json.dumps(
                {"error": "SentimentRAGStore not available - RAG dependencies not installed"}
            )

        store = SentimentRAGStore()
        results = store.query(query=query, ticker=ticker, top_k=limit)

        if not results:
            return json.dumps({"message": "No matching sentiment entries found"})

        formatted = []
        for entry in results:
            metadata = entry.get("metadata", {})
            formatted.append(
                {
                    "id": entry.get("id"),
                    "score": entry.get("score"),
                    "snapshot_date": metadata.get("snapshot_date"),
                    "ticker": metadata.get("ticker"),
                    "sentiment_score": metadata.get("sentiment_score"),
                    "confidence": metadata.get("confidence"),
                    "market_regime": metadata.get("market_regime"),
                    "sources": metadata.get("source_list"),
                }
            )

        return json.dumps(formatted, indent=2)
    except Exception as e:
        logger.exception(f"Error querying sentiment: {query}")
        return json.dumps({"error": str(e)})


@tool
def get_sentiment_history(
    ticker: str,
    limit: int = 5,
) -> str:
    """
    Get recent sentiment history for a ticker.

    Args:
        ticker: Stock ticker symbol (e.g., 'SPY', 'NVDA')
        limit: Number of recent entries to return (default: 5)

    Returns:
        JSON string with recent sentiment snapshots for the ticker
    """
    try:
        SentimentRAGStore = _get_sentiment_store()
        if SentimentRAGStore is None:
            return json.dumps(
                {"error": "SentimentRAGStore not available - RAG dependencies not installed"}
            )

        store = SentimentRAGStore()
        results = store.get_ticker_history(ticker=ticker, limit=limit)

        if not results:
            return json.dumps({"message": f"No sentiment history found for {ticker}"})

        formatted = []
        for entry in results:
            metadata = entry.get("metadata", {})
            formatted.append(
                {
                    "id": entry.get("id"),
                    "snapshot_date": metadata.get("snapshot_date"),
                    "ticker": metadata.get("ticker"),
                    "sentiment_score": metadata.get("sentiment_score"),
                    "confidence": metadata.get("confidence"),
                    "market_regime": metadata.get("market_regime"),
                    "sources": metadata.get("source_list"),
                }
            )

        return json.dumps(formatted, indent=2)
    except Exception as e:
        logger.exception(f"Error fetching sentiment history for {ticker}")
        return json.dumps({"error": str(e)})


@tool
def analyze_technical_indicators(
    symbol: str,
    lookback_days: int = 60,
) -> str:
    """
    Calculate technical indicators for a symbol.

    Args:
        symbol: Stock ticker symbol
        lookback_days: Number of days of data to use for calculations

    Returns:
        JSON string with technical indicators (RSI, MACD, volume ratio, etc.)
    """
    try:
        from src.utils.technical_indicators import (
            calculate_macd,
            calculate_rsi,
            calculate_volume_ratio,
        )

        provider = get_market_data_provider()
        df = provider.get_daily_bars(symbol=symbol, lookback_days=lookback_days)

        if df.empty:
            return json.dumps({"error": f"No data available for {symbol}"})

        if len(df) < 26:
            return json.dumps({"error": f"Insufficient data for {symbol} (need at least 26 bars)"})

        # Calculate indicators
        macd_value, macd_signal, macd_histogram = calculate_macd(df["Close"])
        rsi_val = calculate_rsi(df["Close"])
        volume_ratio = calculate_volume_ratio(df)

        indicators = {
            "symbol": symbol,
            "macd": {
                "value": float(macd_value),
                "signal": float(macd_signal),
                "histogram": float(macd_histogram),
            },
            "rsi": float(rsi_val),
            "volume_ratio": float(volume_ratio),
            "current_price": float(df["Close"].iloc[-1]),
            "calculation_date": datetime.now().isoformat(),
        }

        return json.dumps(indicators, indent=2)
    except Exception as e:
        logger.exception(f"Error calculating technical indicators for {symbol}")
        return json.dumps({"error": str(e)})


def build_trading_tools() -> list:
    """
    Build all trading-specific tools for deepagents.

    Returns:
        List of tool objects compatible with deepagents
    """
    return [
        get_market_data,
        query_sentiment,
        get_sentiment_history,
        analyze_technical_indicators,
    ]

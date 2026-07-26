"""Market Data Regime Feed Adapter with Multi-Provider Fallback.

Resolves the Alpaca SIP subscription error on free tier by attempting:
1. Alpaca Historical Stock Data API
2. Yahoo Finance (yfinance) fallback
3. Safe default / soft-flag gracefully without blocking execution.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)


def get_spy_historical_closes(days: int = 250) -> list[float]:
    """Fetch SPY daily close prices over the last N days with multi-provider fallback."""
    # Provider 1: Alpaca StockHistoricalDataClient
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from src.utils.alpaca_client import get_alpaca_credentials

        key, secret = get_alpaca_credentials()
        if key and secret:
            client = StockHistoricalDataClient(key, secret)
            end = datetime.now(timezone.utc)
            start = end - timedelta(days=days + 30)
            req = StockBarsRequest(
                symbol_or_symbols=["SPY"],
                timeframe=TimeFrame.Day,
                start=start,
                end=end,
            )
            bars = client.get_stock_bars(req)
            rows = bars.data.get("SPY") if hasattr(bars, "data") else None
            if rows and len(rows) >= days:
                return [float(b.close) for b in rows]
    except Exception as exc:
        logger.debug("Alpaca historical closes fetch failed: %s", exc)

    # Provider 2: yfinance Fallback
    try:
        import yfinance as yf

        ticker = yf.Ticker("SPY")
        hist = ticker.history(period="1y")
        if not hist.empty and len(hist) >= 200:
            return [float(c) for c in hist["Close"].tolist()]
    except Exception as exc:
        logger.debug("yfinance historical closes fetch failed: %s", exc)

    return []


def compute_spy_200_dma() -> dict[str, Any]:
    """Compute SPY current price relative to 200-day moving average."""
    closes = get_spy_historical_closes(250)
    if not closes or len(closes) < 200:
        return {
            "current_price": None,
            "dma_200": None,
            "above_200_dma": None,
            "status": "INSUFFICIENT_DATA",
        }

    current_price = closes[-1]
    dma_200 = sum(closes[-200:]) / 200.0
    above_200_dma = current_price >= dma_200

    return {
        "current_price": round(current_price, 2),
        "dma_200": round(dma_200, 2),
        "above_200_dma": above_200_dma,
        "pct_above_200_dma": round(((current_price - dma_200) / dma_200) * 100.0, 2),
        "status": "OK",
    }

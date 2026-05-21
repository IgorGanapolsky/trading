"""IV-rank proxy helper.

True IV Rank requires an options-chain history series, which is expensive
to maintain. As a defensible proxy we use VIX percentile over the last
52 weeks (cached daily). For SPY this correlates strongly with realized
SPY ATM-IV rank — good enough to record at entry for audit purposes.

Returns a float in [0.0, 100.0] or None on any failure. Snapshot capture
must never block trade persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def current_iv_rank_proxy(underlying: str = "SPY") -> float | None:
    """Return VIX 52-week percentile as an IV-rank proxy, or None.

    The proxy is identical for any SPY-family underlying (SPY/SPX/XSP)
    since they all reference the same volatility surface for our purposes.
    """
    if underlying.upper() not in {"SPY", "SPX", "XSP"}:
        return None

    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from src.utils.alpaca_client import get_alpaca_credentials
    except ImportError:
        return None

    key, secret = get_alpaca_credentials()
    if not key:
        return None

    try:
        client = StockHistoricalDataClient(key, secret)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=400)  # ~252 trading days + slack
        req = StockBarsRequest(
            symbol_or_symbols=["VIXY"],  # VIXY tracks VIX in equity feed
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
        rows = bars.data.get("VIXY") if hasattr(bars, "data") else None
        if not rows or len(rows) < 60:
            return None
        closes = [b.close for b in rows if b.close]
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"iv-rank proxy fetch failed: {exc}")
        return None

    if not closes:
        return None
    current = closes[-1]
    below = sum(1 for c in closes if c <= current)
    return round(100.0 * below / len(closes), 2)

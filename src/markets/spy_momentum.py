"""SPY momentum helpers — best-effort returns over rolling windows.

Used by `_capture_market_snapshot` in the iron-condor trader to record
short- and long-window returns at entry time, so audits of the next
30-trade validation cohort can condition on momentum regime (a factor
the May-19 audit could not test because it was never recorded).

Returns are decimal (0.012 = +1.2%). Each fetch is best-effort — if the
data source is unavailable or insufficient history exists, the helper
returns None for that value rather than raising. Snapshot capture must
never block trade persistence.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

logger = logging.getLogger(__name__)


def compute_returns(
    symbol: str = "SPY",
    window_short: int = 5,
    window_long: int = 20,
) -> tuple[float | None, float | None]:
    """Return (short_window_return, long_window_return) as decimals, or Nones.

    Tries Alpaca daily bars first. Returns (None, None) on any failure.
    """
    try:
        from alpaca.data.historical import StockHistoricalDataClient
        from alpaca.data.requests import StockBarsRequest
        from alpaca.data.timeframe import TimeFrame
        from src.utils.alpaca_client import get_alpaca_credentials
    except ImportError:
        return None, None

    key, secret = get_alpaca_credentials()
    if not key:
        return None, None

    try:
        client = StockHistoricalDataClient(key, secret)
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=window_long + 10)
        req = StockBarsRequest(
            symbol_or_symbols=[symbol],
            timeframe=TimeFrame.Day,
            start=start,
            end=end,
        )
        bars = client.get_stock_bars(req)
        rows = bars.data.get(symbol) if hasattr(bars, "data") else None
        if not rows or len(rows) < window_long + 1:
            return None, None
        closes = [b.close for b in rows]
    except Exception as exc:  # noqa: BLE001
        logger.debug(f"momentum fetch failed: {exc}")
        return None, None

    if len(closes) < window_long + 1:
        return None, None

    last = closes[-1]
    short_ago = closes[-window_short - 1]
    long_ago = closes[-window_long - 1]
    short_ret = (last - short_ago) / short_ago if short_ago else None
    long_ret = (last - long_ago) / long_ago if long_ago else None
    return short_ret, long_ret

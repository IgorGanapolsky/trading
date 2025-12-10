import types
from datetime import datetime, timedelta, timezone

from src.utils.market_data import DataSource, MarketDataProvider


class _FakeBar:
    """Simple stand-in for Alpaca bar objects."""

    def __init__(self, ts, open_=100.0, high=101.0, low=99.0, close=100.5, volume=1_000_000):
        self.timestamp = ts
        self.open = open_
        self.high = high
        self.low = low
        self.close = close
        self.volume = volume


class _FakeAlpacaClient:
    """Return a synthetic barset with enough history to pass validation."""

    def __init__(self, symbol: str, bars: list[_FakeBar]):
        self.symbol = symbol
        self._bars = bars

    def get_stock_bars(self, req):  # pragma: no cover - simple passthrough
        return types.SimpleNamespace(data={self.symbol: self._bars})


def test_alpaca_primary_does_not_fallback_to_yfinance(monkeypatch, caplog):
    """
    Ensure Alpaca fetch returns sufficient bars so yfinance fallback is not used.

    This guards against noisy warnings like:
    'Paid sources unavailable/unreliable. Trying yfinance (unreliable free source).'
    """

    symbol = "TSTALP"
    lookback_days = 60

    # Build 90 days of synthetic bars to exceed validation thresholds.
    now = datetime.now(timezone.utc)
    bars = [_FakeBar(ts=now - timedelta(days=i)) for i in range(90)]

    provider = MarketDataProvider()

    # Disable Polygon to force Alpaca path, and inject fake Alpaca client.
    provider.polygon_api_key = None
    provider._alpaca_api = _FakeAlpacaClient(symbol, bars)

    # If yfinance is called, fail the test.
    def _fail_yf(*args, **kwargs):
        raise AssertionError("yfinance should not be called when Alpaca returns sufficient data")

    monkeypatch.setattr(provider, "_fetch_yfinance_with_retries", _fail_yf)

    with caplog.at_level("WARNING"):
        result = provider.get_daily_bars(symbol, lookback_days=lookback_days)

    assert result.source == DataSource.ALPACA
    assert len(result.data) >= lookback_days

    # Confirm no warnings mention yfinance fallback.
    fallback_warnings = [rec for rec in caplog.records if "yfinance" in rec.getMessage()]
    assert not fallback_warnings

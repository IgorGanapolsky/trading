"""The regime average fetch must name its market data feed explicitly.

Regression for AGENT-260. Omitting `feed` let the SDK fall back to a data tier this
account is not entitled to. Every request failed, the 200-day average returned None,
and `fail_closed_on_missing` correctly refused every entry -- silently, for 12 days,
while the scheduled check reported success.

The assertion is on the request kwargs, not on a live call: the defect was a missing
argument, so the argument is what the test pins.
"""

from __future__ import annotations

import sys
import types

import pytest

from src.risk import put_credit_regime


@pytest.fixture
def captured(monkeypatch):
    """Stub the Alpaca SDK and capture the bar-request kwargs."""
    seen: dict = {}

    class FakeBarsRequest:
        def __init__(self, **kwargs):
            seen.update(kwargs)

    class FakeBar:
        close = 100.0

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def get_stock_bars(self, req):
            return types.SimpleNamespace(data={"SPY": [FakeBar() for _ in range(250)]})

    monkeypatch.setitem(
        sys.modules,
        "alpaca.data.historical",
        types.SimpleNamespace(StockHistoricalDataClient=FakeClient),
    )
    monkeypatch.setitem(
        sys.modules,
        "alpaca.data.requests",
        types.SimpleNamespace(StockBarsRequest=FakeBarsRequest),
    )
    monkeypatch.setitem(
        sys.modules,
        "alpaca.data.timeframe",
        types.SimpleNamespace(TimeFrame=types.SimpleNamespace(Day="1Day")),
    )
    monkeypatch.setattr(
        put_credit_regime,
        "get_alpaca_credentials",
        lambda: ("k", "s"),
        raising=False,
    )
    monkeypatch.setitem(
        sys.modules,
        "src.utils.alpaca_client",
        types.SimpleNamespace(get_alpaca_credentials=lambda: ("k", "s")),
    )
    return seen


def test_request_names_its_feed_explicitly(captured, monkeypatch) -> None:
    monkeypatch.delenv("ALPACA_DATA_FEED", raising=False)
    sma, above, err = put_credit_regime._spy_sma_200(100.0)

    assert err is None, f"unexpected error: {err}"
    assert "feed" in captured, "request omitted feed; SDK would fall back to an unentitled tier"
    assert captured["feed"] == "iex"
    assert sma == pytest.approx(100.0)
    assert above is True


def test_feed_is_overridable_by_env(captured, monkeypatch) -> None:
    monkeypatch.setenv("ALPACA_DATA_FEED", "sip")
    put_credit_regime._spy_sma_200(100.0)
    assert captured["feed"] == "sip", "operator override must be honoured"

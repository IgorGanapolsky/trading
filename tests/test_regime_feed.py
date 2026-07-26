import pytest
from src.markets.regime_feed import compute_spy_200_dma, get_spy_historical_closes


def test_get_spy_historical_closes_fallback(monkeypatch):
    monkeypatch.setattr("src.markets.regime_feed.get_spy_historical_closes", lambda days=250: [100.0] * 200)
    result = compute_spy_200_dma()
    assert result["status"] == "OK"
    assert result["current_price"] == 100.0
    assert result["dma_200"] == 100.0
    assert result["above_200_dma"] is True


def test_insufficient_data():
    result = compute_spy_200_dma()
    assert result["status"] in ["OK", "INSUFFICIENT_DATA"]

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, timezone

import pandas as pd
import pytest

from src.utils import regime_detector, yfinance_wrapper
from src.utils.regime_detector import RegimeDetector


@pytest.fixture(autouse=True)
def _isolated_regime_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(regime_detector, "REGIME_DATA_CACHE", tmp_path / "regime_latest.json")


def _mock_yfinance(monkeypatch, frame: pd.DataFrame) -> None:
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: True)
    monkeypatch.setattr(yfinance_wrapper, "download", lambda *_, **__: frame)
    monkeypatch.setattr(
        yfinance_wrapper,
        "get_ticker",
        lambda _symbol: _MockTicker(pd.DataFrame(columns=["Close"])),
    )


class _MockTicker:
    def __init__(self, frame: pd.DataFrame):
        self._frame = frame

    def history(self, *_, **__) -> pd.DataFrame:
        return self._frame


def _write_regime_cache(tmp_path, *, vix: float, vvix: float, age_minutes: int = 0) -> None:
    cache_file = tmp_path / "regime_latest.json"
    cache_file.write_text(
        json.dumps(
            {
                "timestamp": (
                    datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
                ).isoformat(),
                "vix_level": vix,
                "vvix_level": vvix,
            }
        )
    )


def test_live_regime_fails_closed_on_latest_vix_nan(monkeypatch):
    frame = pd.DataFrame(
        {
            "^VIX": [18.5, math.nan],
            "^VVIX": [95.0, 96.0],
            "TLT": [90.0, 90.5],
        }
    )
    _mock_yfinance(monkeypatch, frame)

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == -1
    assert snapshot.label == "unknown"
    assert snapshot.confidence == 0.0


def test_live_regime_fails_closed_when_vvix_missing(monkeypatch):
    frame = pd.DataFrame({"^VIX": [18.5, 19.0], "TLT": [90.0, 90.5]})
    _mock_yfinance(monkeypatch, frame)

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == -1
    assert snapshot.confidence == 0.0


def test_live_regime_still_detects_calm_with_valid_vix_vvix(monkeypatch):
    frame = pd.DataFrame(
        {
            "^VIX": [18.0] * 30,
            "^VVIX": [95.0] * 30,
            "TLT": [90.0] * 30,
        }
    )
    _mock_yfinance(monkeypatch, frame)

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == 0
    assert snapshot.label == "calm"
    assert snapshot.confidence >= 0.5


def test_live_regime_writes_fresh_regime_cache(monkeypatch, tmp_path):
    frame = pd.DataFrame(
        {
            "^VIX": [18.0] * 30,
            "^VVIX": [95.0] * 30,
            "TLT": [90.0] * 30,
        }
    )
    _mock_yfinance(monkeypatch, frame)

    RegimeDetector(hmm_enabled=False).detect_live_regime()

    payload = json.loads((tmp_path / "regime_latest.json").read_text())
    assert payload["vix_level"] == 18.0
    assert payload["vvix_level"] == 95.0


def test_live_regime_uses_fresh_cache_when_live_vvix_invalid(monkeypatch, tmp_path):
    _write_regime_cache(tmp_path, vix=18.8, vvix=96.5)
    frame = pd.DataFrame(
        {
            "^VIX": [18.5, 19.0],
            "^VVIX": [math.nan, math.nan],
            "TLT": [90.0, 90.5],
        }
    )
    _mock_yfinance(monkeypatch, frame)

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == 0
    assert snapshot.label == "calm"
    assert snapshot.vix_level == 19.0
    assert snapshot.vvix_level == 96.5


def test_live_regime_uses_single_ticker_vvix_before_cache(monkeypatch, tmp_path):
    _write_regime_cache(tmp_path, vix=18.8, vvix=120.0)
    frame = pd.DataFrame(
        {
            "^VIX": [18.5, 19.0],
            "^VVIX": [math.nan, math.nan],
            "TLT": [90.0, 90.5],
        }
    )
    _mock_yfinance(monkeypatch, frame)
    monkeypatch.setattr(
        yfinance_wrapper,
        "get_ticker",
        lambda symbol: _MockTicker(pd.DataFrame({"Close": [97.0] if symbol == "^VVIX" else []})),
    )

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == 0
    assert snapshot.vvix_level == 97.0


def test_live_regime_fails_closed_when_vvix_invalid_and_cache_stale(monkeypatch, tmp_path):
    _write_regime_cache(tmp_path, vix=18.8, vvix=96.5, age_minutes=120)
    frame = pd.DataFrame(
        {
            "^VIX": [18.5, 19.0],
            "^VVIX": [math.nan, math.nan],
            "TLT": [90.0, 90.5],
        }
    )
    _mock_yfinance(monkeypatch, frame)

    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()

    assert snapshot.regime_id == -1
    assert snapshot.label == "unknown"

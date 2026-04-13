from __future__ import annotations

import math

import pandas as pd

from src.utils import yfinance_wrapper
from src.utils.regime_detector import RegimeDetector


def _mock_yfinance(monkeypatch, frame: pd.DataFrame) -> None:
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: True)
    monkeypatch.setattr(yfinance_wrapper, "download", lambda *_, **__: frame)


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

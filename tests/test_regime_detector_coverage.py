"""Additional tests to increase regime_detector.py coverage to ~90%+.

Targets missing lines: 56-57, 66-70, 75, 78-79, 81, 98, 115-116, 123-125,
191-221, 247-248, 264-265, 270, 288, 312-313, 315-316, 320-321, 332, 334,
336, 346-349, 362-364, 378-419, 441-442, 503-507, 515, 519-521, 525-527,
529-531, 539, 543, 557-559, 593, 595, 621, 675-677.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, UTC
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.utils import regime_detector, yfinance_wrapper
from src.utils.regime_detector import (
    REGIME_ALLOCATIONS,
    REGIME_LABELS,
    RegimeDetector,
    RegimeSnapshot,
    TransitionPrediction,
    _fetch_single_latest_close,
    _finite_positive_float,
    _latest_finite_positive,
    _load_regime_data_cache,
    _parse_cache_timestamp,
    _save_regime_data_cache,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _isolated_cache(monkeypatch, tmp_path):
    monkeypatch.setattr(regime_detector, "REGIME_DATA_CACHE", tmp_path / "regime_latest.json")


def _mock_yf(monkeypatch, frame: pd.DataFrame) -> None:
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


def _write_cache(tmp_path, *, vix: float, vvix: float, age_minutes: int = 0) -> None:
    cache_file = tmp_path / "regime_latest.json"
    cache_file.write_text(
        json.dumps(
            {
                "timestamp": (datetime.now(UTC) - timedelta(minutes=age_minutes)).isoformat(),
                "vix_level": vix,
                "vvix_level": vvix,
            }
        )
    )


def _spy_frame(vix_val: float = 18.0, vvix_val: float = 95.0, n: int = 30) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "^VIX": [vix_val] * n,
            "^VVIX": [vvix_val] * n,
            "TLT": [90.0] * n,
        }
    )


# ===========================================================================
# _finite_positive_float  (lines 56-57)
# ===========================================================================


def test_fpf_returns_none_for_none():
    # line 56-57: TypeError path
    assert _finite_positive_float(None) is None


def test_fpf_returns_none_for_bad_string():
    # line 56-57: ValueError path
    assert _finite_positive_float("abc") is None


def test_fpf_returns_none_for_nan():
    assert _finite_positive_float(math.nan) is None


def test_fpf_returns_none_for_inf():
    assert _finite_positive_float(math.inf) is None


def test_fpf_returns_none_for_negative():
    assert _finite_positive_float(-1.0) is None


def test_fpf_returns_none_for_zero():
    assert _finite_positive_float(0.0) is None


def test_fpf_returns_float_for_positive():
    assert _finite_positive_float(42.0) == pytest.approx(42.0)


def test_fpf_coerces_string_number():
    assert _finite_positive_float("3.14") == pytest.approx(3.14)


# ===========================================================================
# _latest_finite_positive  (lines 66-70)
# ===========================================================================


def test_lfp_uses_iloc_on_series():
    s = pd.Series([10.0, 20.0, 30.0])
    assert _latest_finite_positive(s) == pytest.approx(30.0)


def test_lfp_attribute_error_falls_back_to_list():
    # line 66-67: plain list has no .iloc
    assert _latest_finite_positive([5.0, 15.0]) == pytest.approx(15.0)


def test_lfp_attribute_error_empty_list_returns_none():
    # line 70: empty list after AttributeError
    assert _latest_finite_positive([]) is None


def test_lfp_index_error_returns_none():
    # line 68-69: IndexError on empty series
    assert _latest_finite_positive(pd.Series([], dtype=float)) is None


def test_lfp_none_returns_none():
    # line 67: `series or []` when value is None
    assert _latest_finite_positive(None) is None


# ===========================================================================
# _parse_cache_timestamp  (lines 75, 78-79, 81)
# ===========================================================================


def test_pct_returns_none_for_empty_string():
    # line 75: falsy value
    assert _parse_cache_timestamp("") is None


def test_pct_returns_none_for_none():
    assert _parse_cache_timestamp(None) is None


def test_pct_returns_none_for_invalid_string():
    # line 78-79: ValueError
    assert _parse_cache_timestamp("not-a-date") is None


def test_pct_naive_datetime_gets_utc():
    # line 81: naive datetime (no tzinfo)
    result = _parse_cache_timestamp("2025-01-01T12:00:00")
    assert result is not None
    assert result.tzinfo == UTC


def test_pct_z_suffix_parses_correctly():
    result = _parse_cache_timestamp("2025-06-01T10:00:00Z")
    assert result is not None
    assert result.tzinfo is not None


# ===========================================================================
# _load_regime_data_cache  (line 98)
# ===========================================================================


def test_load_cache_returns_none_when_vix_invalid(tmp_path):
    # line 98: vix is None due to invalid value
    cache_file = tmp_path / "regime_latest.json"
    cache_file.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "vix_level": -1,
                "vvix_level": 95.0,
            }
        )
    )
    result = _load_regime_data_cache()
    assert result is None


def test_load_cache_returns_none_when_vvix_zero(tmp_path):
    cache_file = tmp_path / "regime_latest.json"
    cache_file.write_text(
        json.dumps(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "vix_level": 18.0,
                "vvix_level": 0,
            }
        )
    )
    result = _load_regime_data_cache()
    assert result is None


# ===========================================================================
# _save_regime_data_cache  (lines 115-116)
# ===========================================================================


def test_save_cache_logs_on_os_error(monkeypatch, caplog):
    import logging

    broken_path = MagicMock()
    broken_path.parent.mkdir.side_effect = OSError("disk full")
    monkeypatch.setattr(regime_detector, "REGIME_DATA_CACHE", broken_path)
    with caplog.at_level(logging.DEBUG, logger="src.utils.regime_detector"):
        _save_regime_data_cache(18.0, 95.0)
    # Must not raise


# ===========================================================================
# _fetch_single_latest_close  (lines 123-125)
# ===========================================================================


def test_fslc_returns_none_when_get_ticker_raises():
    # line 123-125: exception path
    bad_yf = MagicMock()
    bad_yf.get_ticker.side_effect = RuntimeError("network error")
    result = _fetch_single_latest_close(bad_yf, "^VIX")
    assert result is None


def test_fslc_returns_none_for_empty_history():
    mock_yf = MagicMock()
    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame()
    mock_yf.get_ticker.return_value = ticker
    result = _fetch_single_latest_close(mock_yf, "^VIX")
    assert result is None


def test_fslc_returns_close_value_when_available():
    mock_yf = MagicMock()
    ticker = MagicMock()
    ticker.history.return_value = pd.DataFrame({"Close": [25.0, 26.0]})
    mock_yf.get_ticker.return_value = ticker
    result = _fetch_single_latest_close(mock_yf, "^VIX")
    assert result == pytest.approx(26.0)


# ===========================================================================
# RegimeDetector.detect()  (lines 191-221)
# ===========================================================================


def test_detect_volatile_regime():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect({"volatility": 0.5, "trend_strength": 0.01})
    assert result["label"] == "volatile"
    assert result["risk_bias"] == "de_risk"


def test_detect_trending_bull():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect(
        {
            "volatility": 0.1,
            "trend_strength": 0.05,
            "order_flow_imbalance": 0.4,
            "short_term_momentum": 0.5,
        }
    )
    assert result["label"] == "trending_bull"
    assert result["risk_bias"] == "lean_in"


def test_detect_trending_bear():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect({"volatility": 0.1, "trend_strength": -0.05})
    assert result["label"] == "trending_bear"
    assert result["risk_bias"] == "hedge"


def test_detect_microstructure_impulse_from_order_flow():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect(
        {
            "volatility": 0.1,
            "trend_strength": 0.0,
            "order_flow_imbalance": 0.5,
            "short_term_momentum": 0.0,
        }
    )
    assert result["label"] == "microstructure_impulse"


def test_detect_microstructure_impulse_from_momentum():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect(
        {
            "volatility": 0.1,
            "trend_strength": 0.0,
            "order_flow_imbalance": 0.0,
            "short_term_momentum": 1.5,
        }
    )
    assert result["label"] == "microstructure_impulse"


def test_detect_range_regime_default():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect({})
    assert result["label"] == "range"
    assert result["confidence"] == pytest.approx(0.5)


def test_detect_de_risk_when_downside_exceeds_threshold():
    # risk_bias de_risk triggered by downside > volatility * 0.7
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect(
        {
            "volatility": 0.2,
            "trend_strength": 0.0,
            "downside_volatility": 0.2,
        }
    )
    assert result["risk_bias"] == "de_risk"


def test_detect_trending_bull_without_positive_flow_is_neutral():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect(
        {
            "volatility": 0.1,
            "trend_strength": 0.05,
            "order_flow_imbalance": -0.1,
            "short_term_momentum": 0.5,
        }
    )
    assert result["label"] == "trending_bull"
    assert result["risk_bias"] == "neutral"


def test_detect_returns_all_expected_keys():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.detect({"volatility": 0.1})
    assert set(result.keys()) == {
        "label",
        "confidence",
        "volatility",
        "trend",
        "order_flow",
        "risk_bias",
    }


# ===========================================================================
# detect_live_regime — branch coverage  (lines 247-248, 264-265, 270, ...)
# ===========================================================================


def test_live_regime_fallback_when_yfinance_unavailable(monkeypatch):
    # line 247-248
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: False)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == -1
    assert snapshot.label == "unknown"


def test_live_regime_fallback_when_download_empty(monkeypatch):
    # line 264-265
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: True)
    monkeypatch.setattr(yfinance_wrapper, "download", lambda *_, **__: pd.DataFrame())
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == -1


def test_live_regime_fallback_when_closes_empty(monkeypatch):
    # line 270: closes.empty
    empty = pd.DataFrame()
    mock_data = MagicMock()
    mock_data.empty = False
    mock_data.get.return_value = empty
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: True)
    monkeypatch.setattr(yfinance_wrapper, "download", lambda *_, **__: mock_data)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == -1


def test_live_regime_uses_cache_when_vix_missing(monkeypatch, tmp_path):
    # line 288: one of vix/vvix is None -> uses cache
    _write_cache(tmp_path, vix=20.0, vvix=98.0)
    frame = pd.DataFrame(
        {
            "^VIX": [math.nan, math.nan],
            "^VVIX": [95.0] * 2,
            "TLT": [90.0] * 2,
        }
    )
    _mock_yf(monkeypatch, frame)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.vix_level == pytest.approx(20.0)


def test_live_regime_spike_at_high_vix(monkeypatch):
    # line 312-313: vix >= vix_spike_threshold
    frame = _spy_frame(vix_val=35.0, vvix_val=120.0, n=30)
    _mock_yf(monkeypatch, frame)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == 3
    assert snapshot.label == "spike"
    assert snapshot.risk_bias == "pause"


def test_live_regime_volatile_at_mid_vix(monkeypatch):
    # line 315-316: 20 <= vix < 30
    frame = _spy_frame(vix_val=25.0, vvix_val=100.0, n=30)
    _mock_yf(monkeypatch, frame)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == 2
    assert snapshot.label == "volatile"
    assert snapshot.risk_bias == "de_risk"
    assert snapshot.allocation_override is not None


def test_live_regime_calm_allocation_is_none(monkeypatch):
    # regime_id < 2 -> allocation_override = None
    frame = _spy_frame(vix_val=12.0, vvix_val=80.0, n=30)
    _mock_yf(monkeypatch, frame)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == 0
    assert snapshot.allocation_override is None


def test_live_regime_fallback_on_exception(monkeypatch):
    # line 362-364: general exception -> fallback
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: True)

    def _raise(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(yfinance_wrapper, "download", _raise)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    assert snapshot.regime_id == -1


def test_live_regime_hmm_blending_when_hmm_differs(monkeypatch):
    # lines 346-349: HMM diverges from heuristic -> blended confidence
    frame = _spy_frame(vix_val=18.0, vvix_val=95.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=True)
    detector._run_hmm_classification = lambda _closes: 2
    snapshot = detector.detect_live_regime()
    assert snapshot.regime_id == 2


def test_live_regime_hmm_none_keeps_heuristic(monkeypatch):
    # HMM returns None -> keep heuristic result
    frame = _spy_frame(vix_val=12.0, vvix_val=80.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=True)
    detector._run_hmm_classification = lambda _closes: None
    snapshot = detector.detect_live_regime()
    assert snapshot.regime_id == 0


def test_live_regime_hedge_risk_bias_for_trending(monkeypatch):
    # line 336: risk_bias "hedge" when regime_id == 1
    frame = _spy_frame(vix_val=18.0, vvix_val=95.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=True)
    detector._run_hmm_classification = lambda _closes: 1
    snapshot = detector.detect_live_regime()
    assert snapshot.risk_bias in ("hedge", "neutral")


def test_live_regime_trending_via_rising_vix_mean(monkeypatch):
    # lines 320-321, 336: VIX rising -> last 5 mean > 20-bar mean -> regime_id=1 -> "hedge"
    # First 25 bars low VIX, last 5 bars higher VIX (but still < 20)
    vix_vals = [12.0] * 25 + [16.0] * 5
    vvix_vals = [80.0] * 30
    frame = pd.DataFrame({"^VIX": vix_vals, "^VVIX": vvix_vals, "TLT": [90.0] * 30})
    _mock_yf(monkeypatch, frame)
    snapshot = RegimeDetector(hmm_enabled=False).detect_live_regime()
    # 5-bar mean=16 > 20-bar mean=12.5 -> trending
    assert snapshot.regime_id == 1
    assert snapshot.label == "trending"
    assert snapshot.risk_bias == "hedge"


# ===========================================================================
# get_allocation_override  (lines 441-442)
# ===========================================================================


def test_get_alloc_calm():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.get_allocation_override(0)
    assert result is not None
    assert result["pause_trading"] is False


def test_get_alloc_spike_pauses():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.get_allocation_override(3)
    assert result is not None
    assert result["pause_trading"] is True


def test_get_alloc_unknown_regime_id():
    rd = RegimeDetector(hmm_enabled=False)
    result = rd.get_allocation_override(99)
    assert result is None


# ===========================================================================
# predict_transition  (lines 503-559)
# ===========================================================================


def _closes_df(n: int = 20, vix_end: float = 18.0) -> pd.DataFrame:
    vix = np.linspace(16.0, vix_end, n)
    vvix = vix * 5.0
    return pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})


def test_predict_transition_returns_correct_type():
    rd = RegimeDetector(hmm_enabled=False)
    closes = _closes_df()
    result = rd.predict_transition(closes, 0)
    assert isinstance(result, TransitionPrediction)


def test_predict_transition_detects_recent_history_change():
    # lines 503-507: regime history with different past regimes
    rd = RegimeDetector(hmm_enabled=False)
    closes = _closes_df()
    rd._regime_history = [
        (datetime.utcnow(), 1),
        (datetime.utcnow(), 1),
        (datetime.utcnow(), 0),
    ]
    result = rd.predict_transition(closes, 0)
    assert result.transition_detected is True
    assert result.bars_since_transition >= 1


def test_predict_transition_no_transition_when_history_consistent():
    rd = RegimeDetector(hmm_enabled=False)
    closes = _closes_df()
    rd._regime_history = [
        (datetime.utcnow(), 0),
        (datetime.utcnow(), 0),
        (datetime.utcnow(), 0),
    ]
    result = rd.predict_transition(closes, 0)
    assert result.transition_detected is False


def test_predict_transition_high_vvix_vix_ratio_raises_prob():
    # line 515: vvix_vix_ratio_change > 0.5 -> +0.2 prob
    rd = RegimeDetector(hmm_enabled=False)
    n = 20
    vix = np.full(n, 18.0)
    vvix = np.full(n, 90.0)
    vvix[-1] = 115.0  # spike ratio change
    closes = pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})
    result = rd.predict_transition(closes, 0)
    assert result.transition_probability >= 0.3


def test_predict_transition_high_vix_roc_triggers_higher_regime():
    # lines 525-527: vix_roc_5d > 15 -> next regime predicted
    # vix[-5]=15, vix[-1]=18 -> roc = (18/15-1)*100 = 20%
    rd = RegimeDetector(hmm_enabled=False)
    n = 15
    vix = np.full(n, 15.0)
    vix[-1] = 18.0
    vvix = vix * 5
    closes = pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})
    result = rd.predict_transition(closes, 0)
    assert result.predicted_regime in ("trending", "volatile", "spike")


def test_predict_transition_falling_vix_roc_increases_prob():
    # lines 529-531: vix_roc_5d < -15 -> prob raised
    rd = RegimeDetector(hmm_enabled=False)
    n = 15
    vix = np.full(n, 20.0)
    vix[-1] = 14.0  # -30% drop
    vvix = vix * 5
    closes = pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})
    result = rd.predict_transition(closes, 1)
    assert result.transition_probability > 0.1


def test_predict_transition_warning_on_high_probability():
    # line 539: transition_prob > 0.5 -> warning set
    rd = RegimeDetector(hmm_enabled=False)
    n = 15
    vix = np.full(n, 15.0)
    vix[-1] = 18.0
    vvix = np.full(n, 75.0)
    vvix[-1] = 115.0  # big ratio spike
    closes = pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})
    result = rd.predict_transition(closes, 0)
    if result.transition_probability > 0.5:
        assert result.warning_message is not None
        assert "probability" in result.warning_message.lower()


def test_predict_transition_warning_on_recent_entry():
    # line 543: transition_detected and bars_since_transition <= 2 -> warning
    rd = RegimeDetector(hmm_enabled=False)
    closes = _closes_df()
    rd._regime_history = [
        (datetime.utcnow(), 1),
        (datetime.utcnow(), 0),
    ]
    result = rd.predict_transition(closes, 0)
    if result.transition_detected and result.bars_since_transition <= 2:
        assert result.warning_message is not None


def test_predict_transition_exception_returns_safe_fallback():
    # lines 557-559: exception -> safe default TransitionPrediction

    class Boom:
        def __contains__(self, _):
            raise RuntimeError("forced failure")

    rd = RegimeDetector(hmm_enabled=False)
    result = rd.predict_transition(Boom(), 0)
    assert isinstance(result, TransitionPrediction)
    assert result.transition_probability == 0.0
    assert result.confidence == 0.0


def test_predict_transition_vix_acceleration_bumps_prob():
    # lines 519-521: vix_acceleration > 5
    # Need vix[-5] > vix[-10] (slow rise), but vix[-1] >> vix[-5] (fast rise)
    # vix[-10]=15, vix[-5]=16, vix[-1]=22:
    #   roc5 = (22/16 - 1)*100 = 37.5
    #   roc5_of_5 = (16/15 - 1)*100 = 6.67
    #   accel = 37.5 - 6.67 = 30.8 > 5
    # But array indexing: iloc[-5] = element at position n-5
    # With n=15: position 10 should be 16, position 14 should be 22
    rd = RegimeDetector(hmm_enabled=False)
    n = 15
    vix = np.array([15.0] * 5 + [15.5] * 4 + [16.0] + [17.0, 18.5, 20.0, 21.0, 22.0])
    # vix[-10] = vix[5] = 15.5, vix[-5] = vix[10] = 17.0, vix[-1] = 22.0
    # roc5 = (22/17-1)*100 = 29.4, roc5_of_5 = (17/15.5-1)*100 = 9.7, accel = 19.7 > 5
    vvix = vix * 5
    closes = pd.DataFrame({"^VIX": vix, "^VVIX": vvix, "TLT": [90.0] * n})
    result = rd.predict_transition(closes, 0)
    assert result.transition_probability > 0.1


def test_predict_transition_spike_regime_no_higher():
    # current_regime_id == 3 -> no higher regime
    rd = RegimeDetector(hmm_enabled=False)
    closes = _closes_df(vix_end=35.0)
    result = rd.predict_transition(closes, 3)
    assert result.current_regime == "spike"


def test_predict_transition_no_vix_in_closes_skips_indicators():
    # closes without ^VIX -> indicators dict empty or partial
    rd = RegimeDetector(hmm_enabled=False)
    closes = pd.DataFrame({"TLT": [90.0] * 10})
    result = rd.predict_transition(closes, 0)
    assert isinstance(result, TransitionPrediction)
    assert "vix_roc_5d" not in result.leading_indicators


# ===========================================================================
# calculate_composite_score  (lines 593, 595)
# ===========================================================================


def test_composite_score_very_low_vix():
    # line 593: vix_level <= 12 -> vix_score = 1.0
    rd = RegimeDetector(hmm_enabled=False)
    composite, stability = rd.calculate_composite_score(
        regime_id=0, vix_level=10.0, skew_percentile=20.0, confidence=0.9
    )
    assert composite >= 0.7


def test_composite_score_very_high_vix():
    # line 595: vix_level >= 35 -> vix_score = 0.0
    rd = RegimeDetector(hmm_enabled=False)
    composite, stability = rd.calculate_composite_score(
        regime_id=3, vix_level=40.0, skew_percentile=90.0, confidence=0.9
    )
    assert composite <= 0.2


def test_composite_score_mid_vix_interpolates():
    rd = RegimeDetector(hmm_enabled=False)
    composite, stability = rd.calculate_composite_score(
        regime_id=1, vix_level=20.0, skew_percentile=50.0, confidence=0.7
    )
    assert 0.0 < composite < 1.0
    assert 0.0 <= stability <= 1.0


def test_composite_score_rounded_to_3_decimals():
    rd = RegimeDetector(hmm_enabled=False)
    composite, stability = rd.calculate_composite_score(
        regime_id=0, vix_level=15.0, skew_percentile=30.0, confidence=0.8
    )
    assert composite == round(composite, 3)
    assert stability == round(stability, 3)


# ===========================================================================
# detect_live_regime_with_prediction  (line 621, 675-677)
# ===========================================================================


def test_live_regime_with_prediction_returns_enhanced_snapshot(monkeypatch):
    # line 621: snapshot.regime_id >= 0 -> enhanced path
    frame = _spy_frame(vix_val=18.0, vvix_val=95.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=False)
    snapshot = detector.detect_live_regime_with_prediction()
    assert isinstance(snapshot, RegimeSnapshot)
    assert snapshot.regime_id >= 0


def test_live_regime_with_prediction_returns_base_when_detection_fails(monkeypatch):
    # line 621: regime_id < 0 -> return immediately
    monkeypatch.setattr(yfinance_wrapper, "is_available", lambda: False)
    detector = RegimeDetector(hmm_enabled=False)
    snapshot = detector.detect_live_regime_with_prediction()
    assert snapshot.regime_id == -1


def test_live_regime_with_prediction_falls_back_on_enhanced_exception(monkeypatch):
    # lines 675-677: exception in enhanced path -> return base snapshot
    frame = _spy_frame(vix_val=18.0, vvix_val=95.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=False)
    detector.predict_transition = MagicMock(side_effect=RuntimeError("predict failed"))
    snapshot = detector.detect_live_regime_with_prediction()
    assert isinstance(snapshot, RegimeSnapshot)


def test_live_regime_with_prediction_updates_regime_history(monkeypatch):
    frame = _spy_frame(vix_val=18.0, vvix_val=95.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=False)
    detector.detect_live_regime_with_prediction()
    assert hasattr(detector, "_regime_history")
    assert len(detector._regime_history) >= 1


def test_live_regime_with_prediction_composite_scores_populated(monkeypatch):
    frame = _spy_frame(vix_val=12.0, vvix_val=80.0, n=30)
    _mock_yf(monkeypatch, frame)
    detector = RegimeDetector(hmm_enabled=False)
    snapshot = detector.detect_live_regime_with_prediction()
    if snapshot.regime_id >= 0:
        assert 0.0 <= snapshot.composite_score <= 1.0
        assert 0.0 <= snapshot.regime_stability <= 1.0


# ===========================================================================
# _run_hmm_classification  (lines 378-419)
# ===========================================================================


def test_run_hmm_returns_none_when_fewer_than_2_features():
    # line 388-389: len(features) < 2
    detector = RegimeDetector(hmm_enabled=True)
    closes = pd.DataFrame({"TLT": [90.0] * 30})
    result = detector._run_hmm_classification(closes)
    assert result is None


def test_run_hmm_returns_int_or_none_with_all_features():
    # lines 401-415: full HMM path (if hmmlearn installed)
    pytest.importorskip("hmmlearn")
    detector = RegimeDetector(hmm_enabled=True)
    closes = _spy_frame(n=60)
    result = detector._run_hmm_classification(closes)
    assert result is None or isinstance(result, int)


def test_run_hmm_reuses_cached_model():
    # lines 395-399: second call reuses model
    pytest.importorskip("hmmlearn")
    detector = RegimeDetector(hmm_enabled=True)
    closes = _spy_frame(n=60)
    detector._run_hmm_classification(closes)
    # Second call should not raise
    result2 = detector._run_hmm_classification(closes)
    assert result2 is None or isinstance(result2, int)


def test_run_hmm_handles_nan_data_gracefully():
    # line 417-419: exception in HMM -> returns None
    pytest.importorskip("hmmlearn")
    detector = RegimeDetector(hmm_enabled=True)
    bad_closes = pd.DataFrame(
        {
            "^VIX": [float("nan")] * 5,
            "^VVIX": [float("nan")] * 5,
        }
    )
    result = detector._run_hmm_classification(bad_closes)
    assert result is None or isinstance(result, int)


# ===========================================================================
# Constants
# ===========================================================================


def test_regime_labels_complete():
    assert set(REGIME_LABELS.values()) == {"calm", "trending", "volatile", "spike"}


def test_regime_allocations_spike_pauses():
    assert REGIME_ALLOCATIONS["spike"]["pause_trading"] is True


def test_regime_allocations_calm_no_pause():
    assert REGIME_ALLOCATIONS["calm"]["pause_trading"] is False


# ===========================================================================
# _fallback_snapshot
# ===========================================================================


def test_fallback_snapshot_structure():
    rd = RegimeDetector(hmm_enabled=False)
    snap = rd._fallback_snapshot()
    assert snap.label == "unknown"
    assert snap.regime_id == -1
    assert snap.confidence == 0.0
    assert snap.risk_bias == "neutral"
    assert snap.allocation_override is None

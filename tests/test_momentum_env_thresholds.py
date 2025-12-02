import math
import os

import pandas as pd
from src.strategies.legacy_momentum import LegacyMomentumCalculator
from src.utils.technical_indicators import calculate_technical_score


def _synthetic_hist(n=60, start=100.0, step=0.2):
    rows = []
    price = start
    for i in range(n):
        high = price * 1.005
        low = price * 0.995
        close = price
        vol = 1_000_000 + (i * 1000)
        rows.append({"High": high, "Low": low, "Close": close, "Volume": vol})
        price += step
    return pd.DataFrame(rows)


def test_env_driven_momentum_thresholds_loaded():
    os.environ["MOMENTUM_MACD_THRESHOLD"] = "0.3"
    os.environ["MOMENTUM_RSI_OVERBOUGHT"] = "60"
    os.environ["MOMENTUM_VOLUME_MIN"] = "1.2"

    calc = LegacyMomentumCalculator()
    assert math.isclose(calc.macd_threshold, 0.3, rel_tol=1e-6)
    assert math.isclose(calc.rsi_overbought, 60.0, rel_tol=1e-6)
    assert math.isclose(calc.volume_min, 1.2, rel_tol=1e-6)


def test_calculate_technical_score_filters():
    hist = _synthetic_hist()

    # Force rejection by MACD threshold
    score, indicators = calculate_technical_score(
        hist, "SPY", macd_threshold=10.0, rsi_overbought=100.0, volume_min=0.0
    )
    assert score == 0.0
    assert "macd_histogram" in indicators

    # Force rejection by volume threshold
    score2, indicators2 = calculate_technical_score(
        hist, "SPY", macd_threshold=-10.0, rsi_overbought=100.0, volume_min=5.0
    )
    assert score2 == 0.0
    assert "volume_ratio" in indicators2

    # Pass case when thresholds are lenient
    score3, indicators3 = calculate_technical_score(
        hist, "SPY", macd_threshold=-10.0, rsi_overbought=100.0, volume_min=0.0
    )
    assert score3 > 0.0

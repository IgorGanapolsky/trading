from __future__ import annotations

import pandas as pd
import pytest

from src.risk.risk_manager import RiskManager
from src.signals.ath_breakout_signal import generate_ath_breakout_signal


def _ohlcv(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Open": [price - 0.25 for price in closes],
            "High": [price + 0.50 for price in closes],
            "Low": [price - 0.50 for price in closes],
            "Close": closes,
            "Volume": [1_000_000] * len(closes),
        }
    )


def test_detects_clean_prior_high_breakout():
    closes = [100 + i * 0.2 for i in range(40)] + [110.0]
    signal = generate_ath_breakout_signal(_ohlcv(closes), symbol="SPY", confirmation_bars=1)

    assert signal.status == "breakout"
    assert signal.bias == "bullish_continuation"
    assert signal.current_price == pytest.approx(110.0)
    assert signal.prior_high < signal.current_price
    assert signal.stop_price < signal.prior_high
    assert signal.target_2r > signal.target_1r > signal.current_price


def test_detects_retest_holding_prior_high_support():
    closes = [100 + i * 0.1 for i in range(35)]
    closes += [105.5, 106.0, 105.2]
    hist = _ohlcv(closes)
    hist.loc[hist.index[-4], "High"] = 105.0
    hist.loc[hist.index[-2], "Close"] = 106.0
    hist.loc[hist.index[-1], "Close"] = 105.1
    hist.loc[hist.index[-1], "Low"] = 104.8

    signal = generate_ath_breakout_signal(
        hist,
        symbol="SPY",
        support_buffer_atr=0.75,
        confirmation_bars=2,
    )

    assert signal.status == "holding_prior_high"
    assert signal.bias == "bullish_continuation"
    assert signal.current_price >= signal.support_floor


def test_detects_failed_breakout_after_close_below_support_floor():
    closes = [100 + i * 0.1 for i in range(35)]
    closes += [105.5, 106.0, 103.0]
    hist = _ohlcv(closes)
    hist.loc[hist.index[-4], "High"] = 105.0
    hist.loc[hist.index[-2], "Close"] = 106.0
    hist.loc[hist.index[-1], "Close"] = 103.0
    hist.loc[hist.index[-1], "Low"] = 102.5

    signal = generate_ath_breakout_signal(
        hist,
        symbol="SPY",
        support_buffer_atr=0.25,
        confirmation_bars=2,
    )

    assert signal.status == "failed_breakout"
    assert signal.bias == "exit_or_hedge"
    assert signal.current_price < signal.support_floor


def test_returns_insufficient_data_for_missing_columns():
    signal = generate_ath_breakout_signal(pd.DataFrame({"Close": [1.0] * 40}))

    assert signal.status == "insufficient_data"
    assert signal.confidence == 0.0


def test_stop_based_position_sizing_uses_invalidation_level_and_caps_notional():
    risk = RiskManager(portfolio_value=50_000, max_position_pct=0.10, max_daily_loss_pct=0.01)

    size = risk.calculate_stop_based_position_size(entry_price=500.0, stop_price=490.0)

    assert size["quantity"] == 10
    assert size["notional"] == pytest.approx(5_000.0)
    assert size["max_loss"] == pytest.approx(100.0)
    assert size["risk_per_share"] == pytest.approx(10.0)


def test_stop_based_position_sizing_rejects_zero_stop_distance():
    risk = RiskManager(portfolio_value=50_000)

    size = risk.calculate_stop_based_position_size(entry_price=500.0, stop_price=500.0)

    assert size["quantity"] == 0
    assert "identical" in size["reason"]

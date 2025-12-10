import math
import os

import pandas as pd
from src.risk.risk_manager import RiskManager


def _make_hist(n=30, base=100.0, step=0.5):
    rows = []
    price = base
    for _i in range(n):
        high = price + step
        low = price - step
        close = price
        rows.append({"High": high, "Low": low, "Close": close})
        price += 0.1  # gentle drift
    return pd.DataFrame(rows)


def test_calculate_stop_loss_with_hist():
    hist = _make_hist(n=40, base=100.0, step=1.0)
    rm = RiskManager()
    entry = 100.0
    stop = rm.calculate_stop_loss(
        ticker="SPY", entry_price=entry, direction="long", atr_multiplier=2.0, hist=hist
    )
    assert 0 < stop < entry
    # ATR of ~1.0 implies stop near 98.0 (allow tolerance)
    assert math.isclose(stop, 98.0, rel_tol=0.05, abs_tol=0.75)


def test_calculate_size_volatility_scaling():
    hist = _make_hist(n=40, base=100.0, step=2.0)  # Higher volatility
    os.environ["DAILY_INVESTMENT"] = "10.0"
    rm = RiskManager(use_atr_scaling=True, atr_period=14)

    # Without hist (no scaling)
    size_no_hist = rm.calculate_size(
        ticker="SPY",
        account_equity=10000.0,
        signal_strength=0.8,
        rl_confidence=0.8,
        sentiment_score=0.0,
        multiplier=1.0,
        current_price=100.0,
    )
    # With hist (apply scaling)
    size_with_hist = rm.calculate_size(
        ticker="SPY",
        account_equity=10000.0,
        signal_strength=0.8,
        rl_confidence=0.8,
        sentiment_score=0.0,
        multiplier=1.0,
        current_price=100.0,
        hist=hist,
    )

    # Base notional = daily_budget * blended_confidence * sentiment_multiplier * multiplier
    # blended_confidence = (signal_strength + rl_confidence) / 2 = (0.8 + 0.8) / 2 = 0.8
    # base_notional = 10 * 0.8 * 1.0 * 1.0 = 8.0
    # The actual size is capped by `daily_budget` (hard cap) = 10.0 * 0.8 = 8.0
    assert math.isclose(size_no_hist, 8.0, rel_tol=0.01)
    assert size_with_hist <= size_no_hist

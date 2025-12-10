"""
Volatility-based features for trading strategy research.

Provides realized volatility, GARCH volatility, and regime-conditional volatility.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_realized_volatility(
    returns: pd.Series,
    window: int = 20,
    annualize: bool = True,
    method: str = "std",
) -> pd.Series:
    """
    Calculate realized volatility using rolling standard deviation.

    Args:
        returns: Return series
        window: Rolling window size
        annualize: Whether to annualize (multiply by sqrt(252))
        method: 'std' for standard deviation, 'parkinson' for Parkinson estimator

    Returns:
        Series of realized volatility
    """
    if method == "std":
        vol = returns.rolling(window=window).std()
    elif method == "parkinson":
        # Parkinson estimator requires high/low data
        # For now, fall back to std
        vol = returns.rolling(window=window).std()
        logger.warning("Parkinson estimator requires high/low data, using std")
    else:
        raise ValueError(f"Unknown method: {method}")

    if annualize:
        # Annualize assuming 252 trading days
        vol = vol * np.sqrt(252)

    return vol


def calculate_garch_volatility(
    returns: pd.Series,
    p: int = 1,
    q: int = 1,
) -> pd.Series:
    """
    Calculate GARCH volatility (simplified version).

    Note: This is a simplified GARCH implementation.
    For production use, consider using arch library.

    Args:
        returns: Return series
        p: GARCH lag order
        q: ARCH lag order

    Returns:
        Series of GARCH volatility
    """
    try:
        from arch import arch_model

        # Fit GARCH model
        model = arch_model(returns * 100, vol="Garch", p=p, q=q, rescale=False)
        fitted = model.fit(disp="off")
        vol = fitted.conditional_volatility / 100  # Convert back from percentage

        # Align with original index
        vol = pd.Series(vol, index=returns.index)
        return vol

    except ImportError:
        logger.warning(
            "arch library not available. Install with: pip install arch. "
            "Falling back to realized volatility."
        )
        return calculate_realized_volatility(returns)


def calculate_regime_conditional_volatility(
    returns: pd.Series,
    regime_indicator: pd.Series,
    window: int = 20,
) -> pd.DataFrame:
    """
    Calculate volatility conditional on market regime.

    Args:
        returns: Return series
        regime_indicator: Series indicating market regime (e.g., 'bull', 'bear', 'choppy')
        window: Rolling window size

    Returns:
        DataFrame with volatility for each regime
    """
    results = {}
    unique_regimes = regime_indicator.unique()

    for regime in unique_regimes:
        mask = regime_indicator == regime
        regime_returns = returns[mask]
        regime_vol = calculate_realized_volatility(regime_returns, window=window)
        results[f"vol_{regime}"] = regime_vol

    return pd.DataFrame(results)


def calculate_atr_volatility(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    window: int = 14,
) -> pd.Series:
    """
    Calculate Average True Range (ATR) as a volatility proxy.

    Args:
        high: High prices
        low: Low prices
        close: Close prices
        window: Rolling window size

    Returns:
        Series of ATR values
    """
    # True Range = max(high - low, abs(high - prev_close), abs(low - prev_close))
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = true_range.rolling(window=window).mean()

    return atr

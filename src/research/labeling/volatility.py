"""
Volatility labeling functions.

Creates volatility/realized variance labels.
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def create_volatility_labels(
    returns: pd.Series,
    window: int = 20,
    method: str = "realized",
) -> pd.Series:
    """
    Create realized volatility labels.

    Args:
        returns: Return series
        window: Rolling window size for volatility calculation
        method: 'realized' (rolling std) or 'garch' (GARCH volatility)

    Returns:
        Series of volatility labels
    """
    if method == "realized":
        # Realized volatility (rolling standard deviation)
        vol = returns.rolling(window=window).std()
        # Annualize
        vol = vol * np.sqrt(252)
    elif method == "garch":
        try:
            from arch import arch_model

            # Fit GARCH model
            model = arch_model(returns * 100, vol="Garch", p=1, q=1, rescale=False)
            fitted = model.fit(disp="off")
            vol = fitted.conditional_volatility / 100
            vol = pd.Series(vol, index=returns.index)
        except ImportError:
            logger.warning("arch library not available. Falling back to realized volatility.")
            vol = returns.rolling(window=window).std() * np.sqrt(252)
    else:
        raise ValueError(f"Unknown method: {method}")

    return vol


def create_volatility_regime_labels(
    returns: pd.Series,
    window: int = 20,
    regimes: list[str] = None,
) -> pd.Series:
    """
    Create volatility regime labels (low/medium/high).

    Args:
        returns: Return series
        window: Rolling window size
        regimes: List of regime names, e.g., ['low', 'medium', 'high']

    Returns:
        Series of regime labels
    """
    if regimes is None:
        regimes = ["low", "medium", "high"]

    vol = create_volatility_labels(returns, window=window)

    # Create percentiles
    vol_33 = vol.quantile(0.33)
    vol_67 = vol.quantile(0.67)

    # Assign regimes
    labels = pd.Series("medium", index=vol.index, dtype=object)
    labels[vol <= vol_33] = "low"
    labels[vol >= vol_67] = "high"

    return labels

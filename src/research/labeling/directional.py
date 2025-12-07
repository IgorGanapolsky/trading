"""
Directional labeling functions.

Creates directional labels (up/down) over multiple horizons.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def create_directional_labels(
    returns: pd.Series,
    horizons: list[str] | None = None,
    threshold: float = 0.01,
    method: str = "binary",
) -> pd.DataFrame:
    """
    Create directional labels (up/down) over multiple horizons.

    Args:
        returns: Return series
        horizons: List of horizon strings, e.g., ['5m', '1h', '1d']
        threshold: Minimum return threshold for positive label
        method: 'binary' (0/1) or 'ternary' (-1/0/1)

    Returns:
        DataFrame with columns for each horizon
    """
    if horizons is None:
        horizons = ["5m", "1h", "1d", "1w"]

    # Map horizon strings to periods (assuming daily data)
    horizon_map = {
        "5m": 1,  # 5 minutes (if minute data)
        "1h": 60,  # 1 hour (if minute data)
        "1d": 1,  # 1 day
        "1w": 5,  # 1 week (5 trading days)
        "1mo": 21,  # 1 month (~21 trading days)
        "3mo": 63,  # 3 months (~63 trading days)
    }

    results = {}
    for horizon in horizons:
        periods = horizon_map.get(horizon, 1)
        forward_returns = returns.shift(-periods)

        if method == "binary":
            # Binary: 1 if return > threshold, 0 otherwise
            labels = (forward_returns > threshold).astype(int)
        elif method == "ternary":
            # Ternary: 1 if return > threshold, -1 if return < -threshold, 0 otherwise
            labels = pd.Series(0, index=forward_returns.index)
            labels[forward_returns > threshold] = 1
            labels[forward_returns < -threshold] = -1
        else:
            raise ValueError(f"Unknown method: {method}. Use 'binary' or 'ternary'")

        results[f"label_{horizon}"] = labels

    return pd.DataFrame(results)


def create_magnitude_labels(
    returns: pd.Series,
    horizons: list[str] | None = None,
) -> pd.DataFrame:
    """
    Create magnitude labels (regression targets).

    Args:
        returns: Return series
        horizons: List of horizon strings

    Returns:
        DataFrame with forward returns as labels
    """
    if horizons is None:
        horizons = ["1d", "1w", "1mo"]

    horizon_map = {
        "1d": 1,
        "1w": 5,
        "1mo": 21,
        "3mo": 63,
    }

    results = {}
    for horizon in horizons:
        periods = horizon_map.get(horizon, 1)
        forward_returns = returns.shift(-periods)
        results[f"label_{horizon}"] = forward_returns

    return pd.DataFrame(results)

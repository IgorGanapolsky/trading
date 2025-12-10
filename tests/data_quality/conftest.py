import numpy as np
import pandas as pd
import pytest


@pytest.fixture
def data_fixture():
    """
    Create a sample DataFrame with OHLCV data for testing.
    """
    dates = pd.date_range(start="2023-01-01", periods=100, freq="D")

    # Create realistic-looking data
    np.random.seed(42)
    close = np.random.normal(100, 5, 100).cumsum()
    close = close - close.min() + 100  # Ensure positive

    data = pd.DataFrame(
        {
            "Open": close + np.random.normal(0, 1, 100),
            "High": close + np.abs(np.random.normal(0, 2, 100)),
            "Low": close - np.abs(np.random.normal(0, 2, 100)),
            "Close": close,
            "Volume": np.abs(np.random.normal(1000000, 500000, 100)),
        },
        index=dates,
    )

    # Ensure consistency
    data["High"] = data[["Open", "Close", "High"]].max(axis=1)
    data["Low"] = data[["Open", "Close", "Low"]].min(axis=1)

    return data

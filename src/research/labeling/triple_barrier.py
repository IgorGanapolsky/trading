"""
Triple-barrier labeling functions.

Creates event-based labels using the triple-barrier method.
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def create_triple_barrier_labels(
    prices: pd.Series,
    upper_barrier: float = 0.02,
    lower_barrier: float = -0.01,
    max_holding_period: int = 5,
    time_barrier: bool = True,
) -> pd.DataFrame:
    """
    Create event-based labels using triple-barrier method.

    The triple-barrier method labels each observation based on which barrier
    is hit first: upper barrier (profit), lower barrier (loss), or time barrier.

    Args:
        prices: Price series
        upper_barrier: Upper profit barrier (e.g., 0.02 = 2%)
        lower_barrier: Lower loss barrier (e.g., -0.01 = -1%)
        max_holding_period: Maximum holding period (time barrier)
        time_barrier: Whether to use time barrier

    Returns:
        DataFrame with columns:
        - label: 1 if upper barrier hit, -1 if lower barrier hit, 0 if time barrier
        - barrier_hit: Which barrier was hit ('upper', 'lower', 'time')
        - holding_period: Number of periods held
    """
    labels = []
    barrier_hits = []
    holding_periods = []

    for i in range(len(prices)):
        current_price = prices.iloc[i]
        upper_price = current_price * (1 + upper_barrier)
        lower_price = current_price * (1 + lower_barrier)

        label = 0
        barrier_hit = "time"
        holding_period = max_holding_period

        # Look forward to see which barrier is hit first
        for j in range(1, min(max_holding_period + 1, len(prices) - i)):
            future_price = prices.iloc[i + j]

            # Check upper barrier
            if future_price >= upper_price:
                label = 1
                barrier_hit = "upper"
                holding_period = j
                break

            # Check lower barrier
            if future_price <= lower_price:
                label = -1
                barrier_hit = "lower"
                holding_period = j
                break

        labels.append(label)
        barrier_hits.append(barrier_hit)
        holding_periods.append(holding_period)

    return pd.DataFrame(
        {
            "label": labels,
            "barrier_hit": barrier_hits,
            "holding_period": holding_periods,
        },
        index=prices.index,
    )


def create_side_labels(
    prices: pd.Series,
    upper_barrier: float = 0.02,
    lower_barrier: float = -0.01,
    max_holding_period: int = 5,
) -> pd.Series:
    """
    Create side labels (long/short) using triple-barrier method.

    Args:
        prices: Price series
        upper_barrier: Upper profit barrier
        lower_barrier: Lower loss barrier
        max_holding_period: Maximum holding period

    Returns:
        Series of labels: 1 (long), -1 (short), 0 (neutral)
    """
    triple_barrier = create_triple_barrier_labels(
        prices, upper_barrier, lower_barrier, max_holding_period
    )

    # Convert to side labels: 1 if upper barrier hit, -1 if lower barrier hit, 0 otherwise
    side_labels = triple_barrier["label"].copy()
    side_labels[triple_barrier["barrier_hit"] == "time"] = 0

    return side_labels

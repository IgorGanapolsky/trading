"""
Data Labeling Pipeline for Supervised Learning Targets

This module provides sophisticated labeling methods for creating supervised
learning targets in trading ML systems:

1. Triple-Barrier Method: Labels based on which barrier is touched first
   - Upper barrier (take profit)
   - Lower barrier (stop loss)
   - Time barrier (max holding period)

2. Directional Labels: Simple forward return direction at multiple horizons

3. Volatility Labels: Forward realized volatility for vol prediction

4. Event-Based Labels: Labels based on specific market events

Reference: López de Prado, "Advances in Financial Machine Learning" (2018)

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BarrierLabel(Enum):
    """Triple-barrier label outcomes."""

    TAKE_PROFIT = 1  # Hit upper barrier first
    STOP_LOSS = -1  # Hit lower barrier first
    TIME_BARRIER = 0  # Hit time barrier (no clear direction)


@dataclass
class TripleBarrierConfig:
    """Configuration for triple-barrier labeling."""

    # Barrier settings
    profit_taking_multiplier: float = 2.0  # ATR multiplier for profit target
    stop_loss_multiplier: float = 1.0  # ATR multiplier for stop loss
    max_holding_days: int = 10  # Maximum holding period

    # ATR settings for dynamic barriers
    atr_period: int = 20
    use_dynamic_barriers: bool = True

    # Fixed barriers (used if use_dynamic_barriers=False)
    fixed_profit_pct: float = 0.02  # 2% fixed profit target
    fixed_stop_pct: float = 0.01  # 1% fixed stop loss

    # Minimum sample requirements
    min_samples: int = 100


@dataclass
class LabelingResult:
    """Result from labeling operation."""

    labels: pd.Series
    metadata: dict[str, Any]
    barriers: pd.DataFrame | None = None  # Barrier levels used
    touch_times: pd.Series | None = None  # When barrier was touched
    returns: pd.Series | None = None  # Returns at barrier touch


class TripleBarrierLabeler:
    """
    Triple-Barrier Method for labeling trading signals.

    The triple-barrier method creates labels based on which barrier is touched first:
    - Upper barrier: Price reaches profit target → Label = 1 (positive)
    - Lower barrier: Price reaches stop loss → Label = -1 (negative)
    - Time barrier: Holding period expires → Label = 0 or sign of return

    This method is superior to simple forward returns because it:
    1. Incorporates path dependency (not just end point)
    2. Reflects realistic trading outcomes (exits at profit/loss)
    3. Provides cleaner classification targets

    Args:
        config: TripleBarrierConfig with labeling parameters
    """

    def __init__(self, config: TripleBarrierConfig | None = None):
        self.config = config or TripleBarrierConfig()

    def fit_transform(
        self,
        df: pd.DataFrame,
        events: pd.DatetimeIndex | None = None,
    ) -> LabelingResult:
        """
        Apply triple-barrier labeling to price data.

        Args:
            df: OHLCV DataFrame with at least Close column
            events: Optional DatetimeIndex of specific events to label
                   If None, all dates are labeled

        Returns:
            LabelingResult with labels, barriers, and metadata
        """
        if "Close" not in df.columns:
            raise ValueError("DataFrame must have 'Close' column")

        close = df["Close"]

        # Use all dates if no specific events provided
        if events is None:
            events = df.index[self.config.atr_period :]  # Skip warmup period

        # Calculate barriers
        if self.config.use_dynamic_barriers:
            barriers = self._compute_dynamic_barriers(df)
        else:
            barriers = self._compute_fixed_barriers(close)

        # Apply triple-barrier to each event
        labels = []
        touch_times = []
        barrier_returns = []

        for event_date in events:
            if event_date not in close.index:
                continue

            label, touch_time, ret = self._apply_triple_barrier(close, event_date, barriers)
            labels.append(label)
            touch_times.append(touch_time)
            barrier_returns.append(ret)

        result_labels = pd.Series(labels, index=events[: len(labels)])
        result_touch_times = pd.Series(touch_times, index=events[: len(touch_times)])
        result_returns = pd.Series(barrier_returns, index=events[: len(barrier_returns)])

        # Compute metadata
        label_counts = result_labels.value_counts()
        metadata = {
            "total_samples": len(result_labels),
            "take_profit_count": label_counts.get(1, 0),
            "stop_loss_count": label_counts.get(-1, 0),
            "time_barrier_count": label_counts.get(0, 0),
            "take_profit_pct": label_counts.get(1, 0) / len(result_labels) * 100,
            "stop_loss_pct": label_counts.get(-1, 0) / len(result_labels) * 100,
            "avg_holding_period": (result_touch_times - events[: len(touch_times)]).mean(),
            "config": {
                "profit_multiplier": self.config.profit_taking_multiplier,
                "stop_multiplier": self.config.stop_loss_multiplier,
                "max_holding_days": self.config.max_holding_days,
                "use_dynamic_barriers": self.config.use_dynamic_barriers,
            },
            "created_at": datetime.now().isoformat(),
        }

        logger.info(
            f"Triple-barrier labeling complete: {len(result_labels)} samples, "
            f"TP={metadata['take_profit_pct']:.1f}%, SL={metadata['stop_loss_pct']:.1f}%"
        )

        return LabelingResult(
            labels=result_labels,
            metadata=metadata,
            barriers=barriers,
            touch_times=result_touch_times,
            returns=result_returns,
        )

    def _compute_dynamic_barriers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute ATR-based dynamic barriers."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # Calculate ATR
        prev_close = close.shift(1)
        tr = pd.concat(
            [
                high - low,
                abs(high - prev_close),
                abs(low - prev_close),
            ],
            axis=1,
        ).max(axis=1)
        atr = tr.rolling(self.config.atr_period).mean()

        # Compute barriers
        barriers = pd.DataFrame(index=df.index)
        barriers["upper"] = close + atr * self.config.profit_taking_multiplier
        barriers["lower"] = close - atr * self.config.stop_loss_multiplier
        barriers["atr"] = atr

        return barriers

    def _compute_fixed_barriers(self, close: pd.Series) -> pd.DataFrame:
        """Compute fixed percentage barriers."""
        barriers = pd.DataFrame(index=close.index)
        barriers["upper"] = close * (1 + self.config.fixed_profit_pct)
        barriers["lower"] = close * (1 - self.config.fixed_stop_pct)
        barriers["atr"] = close * self.config.fixed_stop_pct  # Pseudo-ATR

        return barriers

    def _apply_triple_barrier(
        self,
        close: pd.Series,
        event_date: pd.Timestamp,
        barriers: pd.DataFrame,
    ) -> tuple[int, pd.Timestamp, float]:
        """
        Apply triple-barrier method for a single event.

        Returns:
            Tuple of (label, touch_time, return)
        """
        # Get event index
        try:
            event_idx = close.index.get_loc(event_date)
        except KeyError:
            return 0, event_date, 0.0

        # Get barrier levels at event time
        upper_barrier = barriers["upper"].iloc[event_idx]
        lower_barrier = barriers["lower"].iloc[event_idx]
        entry_price = close.iloc[event_idx]

        # Define the forward path
        max_idx = min(event_idx + self.config.max_holding_days, len(close) - 1)
        if event_idx >= max_idx:
            return 0, event_date, 0.0

        forward_path = close.iloc[event_idx + 1 : max_idx + 1]

        if len(forward_path) == 0:
            return 0, event_date, 0.0

        # Check which barrier is touched first
        upper_touches = forward_path >= upper_barrier
        lower_touches = forward_path <= lower_barrier

        upper_first = upper_touches.idxmax() if upper_touches.any() else None
        lower_first = lower_touches.idxmax() if lower_touches.any() else None

        # Determine which barrier was hit first
        if upper_first is not None and lower_first is not None:
            # Both barriers touched - which was first?
            if close.index.get_loc(upper_first) <= close.index.get_loc(lower_first):
                touch_time = upper_first
                label = 1  # Take profit
            else:
                touch_time = lower_first
                label = -1  # Stop loss
        elif upper_first is not None:
            touch_time = upper_first
            label = 1
        elif lower_first is not None:
            touch_time = lower_first
            label = -1
        else:
            # Time barrier hit
            touch_time = forward_path.index[-1]
            final_price = forward_path.iloc[-1]
            ret = (final_price - entry_price) / entry_price
            label = int(np.sign(ret))  # Sign of return at time barrier

        # Calculate return at touch time
        touch_price = close.loc[touch_time]
        ret = (touch_price - entry_price) / entry_price

        return label, touch_time, ret


class DirectionalLabeler:
    """
    Simple directional labels at multiple horizons.

    Creates binary/ternary labels based on forward return direction.
    """

    def __init__(
        self,
        horizons: list[int] = None,
        threshold: float = 0.0,
        use_ternary: bool = False,
        neutral_band_pct: float = 0.001,
    ):
        """
        Initialize directional labeler.

        Args:
            horizons: List of forward horizons (in trading days)
            threshold: Return threshold for label (default 0 = any positive)
            use_ternary: If True, use -1/0/1 labels with neutral band
            neutral_band_pct: Size of neutral band for ternary labels
        """
        self.horizons = horizons or [1, 5, 10, 21, 63]
        self.threshold = threshold
        self.use_ternary = use_ternary
        self.neutral_band_pct = neutral_band_pct

    def fit_transform(self, df: pd.DataFrame) -> LabelingResult:
        """
        Create directional labels for all horizons.

        Args:
            df: DataFrame with 'Close' column

        Returns:
            LabelingResult with label DataFrame and metadata
        """
        close = df["Close"]
        labels = pd.DataFrame(index=df.index)

        for horizon in self.horizons:
            # Calculate forward return
            fwd_ret = close.pct_change(horizon).shift(-horizon)

            if self.use_ternary:
                # Ternary labels: -1 (down), 0 (neutral), 1 (up)
                labels[f"direction_{horizon}d"] = np.where(
                    fwd_ret > self.neutral_band_pct,
                    1,
                    np.where(fwd_ret < -self.neutral_band_pct, -1, 0),
                )
            else:
                # Binary labels: 0 (down), 1 (up)
                labels[f"direction_{horizon}d"] = (fwd_ret > self.threshold).astype(int)

            # Store raw forward returns
            labels[f"fwd_ret_{horizon}d"] = fwd_ret

        # Compute metadata
        metadata = {
            "horizons": self.horizons,
            "use_ternary": self.use_ternary,
            "threshold": self.threshold,
            "sample_counts": {
                col: labels[col].value_counts().to_dict()
                for col in labels.columns
                if col.startswith("direction_")
            },
            "created_at": datetime.now().isoformat(),
        }

        return LabelingResult(
            labels=labels,
            metadata=metadata,
        )


class VolatilityLabeler:
    """
    Volatility-based labels for vol prediction models.

    Creates labels based on forward realized volatility.
    """

    def __init__(
        self,
        horizons: list[int] = None,
        vol_percentiles: list[float] = None,
    ):
        """
        Initialize volatility labeler.

        Args:
            horizons: List of forward horizons for vol calculation
            vol_percentiles: Percentiles for volatility regime classification
        """
        self.horizons = horizons or [5, 10, 21]
        self.vol_percentiles = vol_percentiles or [25, 50, 75]

    def fit_transform(self, df: pd.DataFrame) -> LabelingResult:
        """
        Create volatility labels.

        Args:
            df: DataFrame with 'Close' column

        Returns:
            LabelingResult with vol labels and metadata
        """
        close = df["Close"]
        labels = pd.DataFrame(index=df.index)

        for horizon in self.horizons:
            # Calculate forward realized volatility
            fwd_returns = close.pct_change().shift(-horizon)
            fwd_vol = fwd_returns.rolling(horizon).std() * np.sqrt(252)
            fwd_vol = fwd_vol.shift(-horizon + 1)  # Align with prediction point

            labels[f"fwd_vol_{horizon}d"] = fwd_vol

            # Create vol regime labels based on historical percentiles
            labels[f"vol_regime_{horizon}d"] = pd.cut(
                fwd_vol,
                bins=[0] + [fwd_vol.quantile(p / 100) for p in self.vol_percentiles] + [np.inf],
                labels=list(range(len(self.vol_percentiles) + 1)),
            )

            # High vol indicator
            labels[f"high_vol_{horizon}d"] = (fwd_vol > fwd_vol.rolling(252).quantile(0.75)).astype(
                int
            )

        metadata = {
            "horizons": self.horizons,
            "vol_percentiles": self.vol_percentiles,
            "created_at": datetime.now().isoformat(),
        }

        return LabelingResult(
            labels=labels,
            metadata=metadata,
        )


class EventLabeler:
    """
    Event-based labeling for specific market conditions.

    Creates labels based on events like earnings, FOMC, etc.
    """

    def __init__(self, event_window: int = 5):
        """
        Initialize event labeler.

        Args:
            event_window: Days before/after event to include
        """
        self.event_window = event_window

    def label_around_events(
        self,
        df: pd.DataFrame,
        event_dates: list[pd.Timestamp],
        event_type: str = "generic",
    ) -> LabelingResult:
        """
        Create labels around specific events.

        Args:
            df: OHLCV DataFrame
            event_dates: List of event dates
            event_type: Type of event for metadata

        Returns:
            LabelingResult with event labels
        """
        close = df["Close"]
        labels = pd.DataFrame(index=df.index)

        # Initialize columns
        labels["in_event_window"] = 0
        labels["days_to_event"] = np.nan
        labels["event_type"] = ""
        labels["pre_event_ret"] = np.nan
        labels["post_event_ret"] = np.nan

        for event_date in event_dates:
            if event_date not in close.index:
                continue

            event_idx = close.index.get_loc(event_date)

            # Mark event window
            window_start = max(0, event_idx - self.event_window)
            window_end = min(len(close), event_idx + self.event_window + 1)

            for i in range(window_start, window_end):
                idx = close.index[i]
                labels.loc[idx, "in_event_window"] = 1
                labels.loc[idx, "days_to_event"] = i - event_idx
                labels.loc[idx, "event_type"] = event_type

            # Calculate pre/post event returns
            if event_idx >= self.event_window:
                pre_ret = close.iloc[event_idx] / close.iloc[event_idx - self.event_window] - 1
                labels.loc[event_date, "pre_event_ret"] = pre_ret

            if event_idx + self.event_window < len(close):
                post_ret = close.iloc[event_idx + self.event_window] / close.iloc[event_idx] - 1
                labels.loc[event_date, "post_event_ret"] = post_ret

        metadata = {
            "event_type": event_type,
            "event_count": len(event_dates),
            "event_window": self.event_window,
            "created_at": datetime.now().isoformat(),
        }

        return LabelingResult(
            labels=labels,
            metadata=metadata,
        )


def create_complete_labels(
    df: pd.DataFrame,
    triple_barrier: bool = True,
    directional: bool = True,
    volatility: bool = True,
) -> pd.DataFrame:
    """
    Create a complete set of labels for ML training.

    Args:
        df: OHLCV DataFrame
        triple_barrier: Include triple-barrier labels
        directional: Include directional labels
        volatility: Include volatility labels

    Returns:
        DataFrame with all requested labels
    """
    all_labels = pd.DataFrame(index=df.index)

    if triple_barrier:
        tb_labeler = TripleBarrierLabeler()
        tb_result = tb_labeler.fit_transform(df)
        all_labels["triple_barrier"] = tb_result.labels
        all_labels["tb_return"] = tb_result.returns

    if directional:
        dir_labeler = DirectionalLabeler()
        dir_result = dir_labeler.fit_transform(df)
        for col in dir_result.labels.columns:
            all_labels[col] = dir_result.labels[col]

    if volatility:
        vol_labeler = VolatilityLabeler()
        vol_result = vol_labeler.fit_transform(df)
        for col in vol_result.labels.columns:
            all_labels[col] = vol_result.labels[col]

    return all_labels


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("DATA LABELING PIPELINE DEMO")
    print("=" * 80)

    # Create sample data
    dates = pd.date_range("2023-01-01", periods=500, freq="D")
    np.random.seed(42)
    close = 100 * (1 + np.random.randn(500).cumsum() * 0.015)
    high = close * (1 + np.abs(np.random.randn(500)) * 0.01)
    low = close * (1 - np.abs(np.random.randn(500)) * 0.01)

    df = pd.DataFrame(
        {
            "Open": close * (1 + np.random.randn(500) * 0.005),
            "High": high,
            "Low": low,
            "Close": close,
            "Volume": np.random.randint(1000000, 10000000, 500),
        },
        index=dates,
    )

    # Triple-barrier labeling
    print("\n1. Triple-Barrier Labeling:")
    tb_labeler = TripleBarrierLabeler()
    tb_result = tb_labeler.fit_transform(df)
    print(f"   Total samples: {tb_result.metadata['total_samples']}")
    print(f"   Take Profit: {tb_result.metadata['take_profit_pct']:.1f}%")
    print(f"   Stop Loss: {tb_result.metadata['stop_loss_pct']:.1f}%")
    print(f"   Time Barrier: {tb_result.metadata['time_barrier_count']}")

    # Directional labeling
    print("\n2. Directional Labeling:")
    dir_labeler = DirectionalLabeler(horizons=[5, 21])
    dir_result = dir_labeler.fit_transform(df)
    print(f"   Horizons: {dir_result.metadata['horizons']}")
    for col, counts in dir_result.metadata["sample_counts"].items():
        print(f"   {col}: {counts}")

    # Volatility labeling
    print("\n3. Volatility Labeling:")
    vol_labeler = VolatilityLabeler(horizons=[5, 21])
    vol_result = vol_labeler.fit_transform(df)
    print(f"   Horizons: {vol_result.metadata['horizons']}")
    print(f"   Columns: {list(vol_result.labels.columns)}")

    # Complete labels
    print("\n4. Complete Labels:")
    all_labels = create_complete_labels(df)
    print(f"   Total columns: {len(all_labels.columns)}")
    print(f"   Columns: {list(all_labels.columns)}")

    print("\n" + "=" * 80)

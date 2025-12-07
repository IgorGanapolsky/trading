"""
Feature library for alpha research.

Provides standardized feature computation functions.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd


@dataclass
class FeatureConfig:
    """Configuration for feature computation."""

    momentum_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 60])
    volatility_windows: list[int] = field(default_factory=lambda: [5, 10, 20, 60])
    volume_windows: list[int] = field(default_factory=lambda: [5, 10, 20])
    rsi_window: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_window: int = 20
    bb_std: float = 2.0


def compute_momentum_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    Compute momentum-based features.

    Args:
        df: DataFrame with OHLCV data
        windows: List of lookback windows

    Returns:
        DataFrame with momentum features
    """
    if windows is None:
        windows = [5, 10, 20, 60]

    close = df["Close"]
    features = pd.DataFrame(index=df.index)

    for w in windows:
        features[f"return_{w}d"] = close.pct_change(w)
        features[f"return_{w}d_rank"] = features[f"return_{w}d"].rank(pct=True)

    for w in windows:
        features[f"mom_{w}d"] = close / close.shift(w) - 1

    for fast, slow in [(5, 20), (10, 60), (20, 60)]:
        if fast in windows and slow in windows:
            features[f"mom_cross_{fast}_{slow}"] = (
                close.rolling(fast).mean() / close.rolling(slow).mean() - 1
            )

    return features


def compute_volatility_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    Compute volatility-based features.

    Args:
        df: DataFrame with OHLCV data
        windows: List of lookback windows

    Returns:
        DataFrame with volatility features
    """
    if windows is None:
        windows = [5, 10, 20, 60]

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    returns = close.pct_change()

    features = pd.DataFrame(index=df.index)

    for w in windows:
        features[f"vol_{w}d"] = returns.rolling(w).std() * np.sqrt(252)

    for w in windows:
        tr = pd.concat(
            [
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs(),
            ],
            axis=1,
        ).max(axis=1)
        features[f"atr_{w}d"] = tr.rolling(w).mean()

    for w in windows:
        features[f"range_{w}d"] = (high.rolling(w).max() - low.rolling(w).min()) / close

    vol_20 = returns.rolling(20).std()
    vol_60 = returns.rolling(60).std()
    features["vol_ratio_20_60"] = vol_20 / vol_60

    return features


def compute_volume_features(
    df: pd.DataFrame,
    windows: list[int] | None = None,
) -> pd.DataFrame:
    """
    Compute volume-based features.

    Args:
        df: DataFrame with OHLCV data
        windows: List of lookback windows

    Returns:
        DataFrame with volume features
    """
    if windows is None:
        windows = [5, 10, 20]

    volume = df["Volume"]
    close = df["Close"]
    features = pd.DataFrame(index=df.index)

    for w in windows:
        avg_vol = volume.rolling(w).mean()
        features[f"vol_ratio_{w}d"] = volume / avg_vol

    cumvol = (volume * np.sign(close.diff())).cumsum()
    features["obv"] = cumvol
    features["obv_pct"] = cumvol.pct_change(20)

    typical_price = (df["High"] + df["Low"] + close) / 3
    vwap = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
    features["vwap_dev"] = (close - vwap) / vwap

    features["volume_price_corr"] = volume.rolling(20).corr(close.pct_change().abs())

    return features


def compute_technical_features(
    df: pd.DataFrame,
    config: FeatureConfig | None = None,
) -> pd.DataFrame:
    """
    Compute technical indicator features.

    Args:
        df: DataFrame with OHLCV data
        config: Feature configuration

    Returns:
        DataFrame with technical features
    """
    if config is None:
        config = FeatureConfig()

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    features = pd.DataFrame(index=df.index)

    delta = close.diff()
    gain = delta.where(delta > 0, 0).rolling(config.rsi_window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(config.rsi_window).mean()
    rs = gain / loss.replace(0, np.nan)
    features["rsi"] = 100 - (100 / (1 + rs))

    ema_fast = close.ewm(span=config.macd_fast).mean()
    ema_slow = close.ewm(span=config.macd_slow).mean()
    macd = ema_fast - ema_slow
    signal = macd.ewm(span=config.macd_signal).mean()
    features["macd"] = macd
    features["macd_signal"] = signal
    features["macd_hist"] = macd - signal

    sma = close.rolling(config.bb_window).mean()
    std = close.rolling(config.bb_window).std()
    features["bb_upper"] = sma + config.bb_std * std
    features["bb_lower"] = sma - config.bb_std * std
    features["bb_width"] = (features["bb_upper"] - features["bb_lower"]) / sma
    features["bb_pct"] = (close - features["bb_lower"]) / (
        features["bb_upper"] - features["bb_lower"]
    )

    low_14 = low.rolling(14).min()
    high_14 = high.rolling(14).max()
    features["stoch_k"] = 100 * (close - low_14) / (high_14 - low_14)
    features["stoch_d"] = features["stoch_k"].rolling(3).mean()

    return features


class FeatureLibrary:
    """
    Unified feature library for alpha research.

    Example:
        >>> lib = FeatureLibrary()
        >>> features = lib.compute_all(df)
        >>> print(features.columns.tolist())
    """

    def __init__(self, config: FeatureConfig | None = None):
        self.config = config or FeatureConfig()

    def compute_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all available features."""
        features = pd.concat(
            [
                compute_momentum_features(df, self.config.momentum_windows),
                compute_volatility_features(df, self.config.volatility_windows),
                compute_volume_features(df, self.config.volume_windows),
                compute_technical_features(df, self.config),
            ],
            axis=1,
        )

        return features

    def compute_subset(
        self,
        df: pd.DataFrame,
        categories: list[str],
    ) -> pd.DataFrame:
        """
        Compute features for specific categories.

        Args:
            df: OHLCV DataFrame
            categories: List of categories ('momentum', 'volatility', 'volume', 'technical')

        Returns:
            DataFrame with selected features
        """
        feature_dfs = []

        if "momentum" in categories:
            feature_dfs.append(compute_momentum_features(df, self.config.momentum_windows))
        if "volatility" in categories:
            feature_dfs.append(compute_volatility_features(df, self.config.volatility_windows))
        if "volume" in categories:
            feature_dfs.append(compute_volume_features(df, self.config.volume_windows))
        if "technical" in categories:
            feature_dfs.append(compute_technical_features(df, self.config))

        if not feature_dfs:
            return pd.DataFrame(index=df.index)

        return pd.concat(feature_dfs, axis=1)

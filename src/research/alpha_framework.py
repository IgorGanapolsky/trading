"""
Alpha Research Framework - Feature Library and Signal Generation

This module provides a comprehensive feature library for alpha research,
including returns, volatility, volume, technicals, cross-sectional ranks,
and market microstructure features.

Features are organized into categories:
    - Returns: Multi-horizon returns, log returns, risk-adjusted returns
    - Volatility: Realized vol, Parkinson, Garman-Klass, regime indicators
    - Volume: Volume momentum, VWAP deviation, accumulation/distribution
    - Technicals: MACD, RSI, Bollinger, ATR, ADX, stochastic
    - Cross-sectional: Ranks, z-scores, sector-relative metrics
    - Microstructure: Bid-ask spread, order imbalance, trade intensity

Author: Trading System
Created: 2025-12-02
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class FeatureConfig:
    """Configuration for feature generation."""

    # Return horizons (trading days)
    return_horizons: list[int] = field(default_factory=lambda: [1, 5, 10, 21, 63, 126, 252])

    # Volatility windows
    volatility_windows: list[int] = field(default_factory=lambda: [5, 10, 21, 63])

    # Volume windows
    volume_windows: list[int] = field(default_factory=lambda: [5, 10, 20])

    # Technical indicator parameters
    rsi_period: int = 14
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bb_period: int = 20
    bb_std: float = 2.0
    atr_period: int = 14
    adx_period: int = 14

    # Minimum data requirements
    min_history_days: int = 252


class FeatureLibrary:
    """
    Comprehensive feature library for alpha research.

    Provides standardized feature computation with proper naming conventions,
    NaN handling, and feature metadata tracking.
    """

    def __init__(self, config: FeatureConfig | None = None):
        self.config = config or FeatureConfig()
        self._feature_registry: dict[str, dict[str, Any]] = {}

    def compute_all_features(
        self,
        df: pd.DataFrame,
        include_returns: bool = True,
        include_volatility: bool = True,
        include_volume: bool = True,
        include_technicals: bool = True,
        include_microstructure: bool = False,
    ) -> pd.DataFrame:
        """
        Compute all requested feature categories.

        Args:
            df: OHLCV DataFrame with columns: Open, High, Low, Close, Volume
            include_returns: Include return-based features
            include_volatility: Include volatility features
            include_volume: Include volume-based features
            include_technicals: Include technical indicators
            include_microstructure: Include microstructure features (requires bid/ask)

        Returns:
            DataFrame with all computed features
        """
        features = df.copy()

        if include_returns:
            features = self._add_return_features(features)

        if include_volatility:
            features = self._add_volatility_features(features)

        if include_volume:
            features = self._add_volume_features(features)

        if include_technicals:
            features = self._add_technical_features(features)

        if include_microstructure and "bid" in df.columns and "ask" in df.columns:
            features = self._add_microstructure_features(features)

        logger.info(
            f"Computed {len(features.columns) - len(df.columns)} features ({len(features)} rows)"
        )
        return features

    def _add_return_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add return-based features."""
        close = df["Close"]

        for horizon in self.config.return_horizons:
            # Simple returns
            df[f"ret_{horizon}d"] = close.pct_change(horizon)

            # Log returns
            df[f"log_ret_{horizon}d"] = np.log(close / close.shift(horizon))

            # Volatility-adjusted returns (risk-adjusted)
            if horizon >= 5:
                vol = close.pct_change().rolling(horizon).std()
                df[f"ret_vol_adj_{horizon}d"] = df[f"ret_{horizon}d"] / (vol + 1e-8)

            self._register_feature(f"ret_{horizon}d", "returns", {"horizon": horizon})
            self._register_feature(f"log_ret_{horizon}d", "returns", {"horizon": horizon})

        # Momentum (rate of change)
        for horizon in [10, 21, 63]:
            df[f"momentum_{horizon}d"] = close / close.shift(horizon) - 1
            self._register_feature(f"momentum_{horizon}d", "momentum", {"horizon": horizon})

        # Acceleration (change in momentum)
        df["momentum_accel_21d"] = df["momentum_21d"] - df["momentum_21d"].shift(5)

        return df

    def _add_volatility_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volatility features."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        open_price = df["Open"]

        for window in self.config.volatility_windows:
            # Realized volatility (close-to-close)
            ret = close.pct_change()
            df[f"vol_realized_{window}d"] = ret.rolling(window).std() * np.sqrt(252)

            # Parkinson volatility (using high/low)
            hl_ratio = np.log(high / low)
            df[f"vol_parkinson_{window}d"] = hl_ratio.rolling(window).apply(
                lambda x: np.sqrt(np.sum(x**2) / (4 * np.log(2) * len(x)))
            ) * np.sqrt(252)

            # Garman-Klass volatility (OHLC)
            df[f"vol_garman_klass_{window}d"] = self._garman_klass_vol(
                high, low, open_price, close, window
            )

            self._register_feature(f"vol_realized_{window}d", "volatility", {"window": window})
            self._register_feature(f"vol_parkinson_{window}d", "volatility", {"window": window})

        # Volatility regime indicator
        vol_21 = df["vol_realized_21d"]
        vol_63 = (
            df["vol_realized_63d"]
            if "vol_realized_63d" in df.columns
            else vol_21.rolling(63).mean()
        )
        df["vol_regime"] = vol_21 / (vol_63 + 1e-8)

        # High/Low range ratio
        df["range_ratio"] = (high - low) / close

        return df

    def _garman_klass_vol(
        self,
        high: pd.Series,
        low: pd.Series,
        open_price: pd.Series,
        close: pd.Series,
        window: int,
    ) -> pd.Series:
        """Compute Garman-Klass volatility estimator."""
        log_hl = np.log(high / low) ** 2
        log_co = np.log(close / open_price) ** 2

        gk = 0.5 * log_hl - (2 * np.log(2) - 1) * log_co
        return gk.rolling(window).mean().apply(np.sqrt) * np.sqrt(252)

    def _add_volume_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add volume-based features."""
        volume = df["Volume"]
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        for window in self.config.volume_windows:
            # Volume moving average ratio
            df[f"volume_ma_ratio_{window}d"] = volume / volume.rolling(window).mean()

            # Volume momentum
            df[f"volume_momentum_{window}d"] = volume.pct_change(window)

            self._register_feature(f"volume_ma_ratio_{window}d", "volume", {"window": window})

        # VWAP and deviation
        typical_price = (high + low + close) / 3
        df["vwap_20d"] = (typical_price * volume).rolling(20).sum() / volume.rolling(20).sum()
        df["vwap_deviation"] = (close - df["vwap_20d"]) / df["vwap_20d"]

        # Accumulation/Distribution Line
        mfm = ((close - low) - (high - close)) / (high - low + 1e-8)
        mfv = mfm * volume
        df["ad_line"] = mfv.cumsum()
        df["ad_line_momentum"] = df["ad_line"].pct_change(5)

        # On-Balance Volume
        obv = np.where(close > close.shift(1), volume, np.where(close < close.shift(1), -volume, 0))
        df["obv"] = pd.Series(obv, index=df.index).cumsum()
        df["obv_momentum"] = df["obv"].pct_change(5)

        # Chaikin Money Flow
        df["cmf_20d"] = mfv.rolling(20).sum() / volume.rolling(20).sum()

        return df

    def _add_technical_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add technical indicator features."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]
        volume = df["Volume"]

        # RSI
        df["rsi"] = self._compute_rsi(close, self.config.rsi_period)
        df["rsi_divergence"] = df["rsi"] - df["rsi"].shift(5)

        # MACD
        exp1 = close.ewm(span=self.config.macd_fast, adjust=False).mean()
        exp2 = close.ewm(span=self.config.macd_slow, adjust=False).mean()
        df["macd"] = exp1 - exp2
        df["macd_signal"] = df["macd"].ewm(span=self.config.macd_signal, adjust=False).mean()
        df["macd_histogram"] = df["macd"] - df["macd_signal"]
        df["macd_histogram_momentum"] = df["macd_histogram"] - df["macd_histogram"].shift(3)

        # Bollinger Bands
        sma = close.rolling(self.config.bb_period).mean()
        std = close.rolling(self.config.bb_period).std()
        df["bb_upper"] = sma + self.config.bb_std * std
        df["bb_lower"] = sma - self.config.bb_std * std
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / sma
        df["bb_position"] = (close - df["bb_lower"]) / (df["bb_upper"] - df["bb_lower"] + 1e-8)

        # ATR
        df["atr"] = self._compute_atr(high, low, close, self.config.atr_period)
        df["atr_pct"] = df["atr"] / close

        # ADX
        df["adx"], df["+di"], df["-di"] = self._compute_adx(
            high, low, close, self.config.adx_period
        )

        # Stochastic Oscillator
        lowest_low = low.rolling(14).min()
        highest_high = high.rolling(14).max()
        df["stoch_k"] = 100 * (close - lowest_low) / (highest_high - lowest_low + 1e-8)
        df["stoch_d"] = df["stoch_k"].rolling(3).mean()

        # Money Flow Index (volume-weighted RSI)
        df["mfi"] = self._compute_mfi(high, low, close, volume, 14)

        # Williams %R
        df["williams_r"] = -100 * (highest_high - close) / (highest_high - lowest_low + 1e-8)

        # CCI
        tp = (high + low + close) / 3
        sma_tp = tp.rolling(20).mean()
        mad = tp.rolling(20).apply(lambda x: np.abs(x - x.mean()).mean())
        df["cci"] = (tp - sma_tp) / (0.015 * mad + 1e-8)

        # Register all technical features
        for col in [
            "rsi",
            "macd",
            "macd_signal",
            "macd_histogram",
            "bb_position",
            "atr",
            "adx",
            "stoch_k",
            "mfi",
            "cci",
        ]:
            self._register_feature(col, "technical", {})

        return df

    def _add_microstructure_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add market microstructure features (requires bid/ask data)."""
        if "bid" not in df.columns or "ask" not in df.columns:
            logger.warning("Microstructure features require bid/ask columns")
            return df

        bid = df["bid"]
        ask = df["ask"]
        mid = (bid + ask) / 2

        # Bid-ask spread
        df["spread_abs"] = ask - bid
        df["spread_pct"] = df["spread_abs"] / mid

        # Spread moving average
        df["spread_ma_5d"] = df["spread_pct"].rolling(5).mean()

        # Quote imbalance
        if "bid_size" in df.columns and "ask_size" in df.columns:
            total_size = df["bid_size"] + df["ask_size"]
            df["quote_imbalance"] = (df["bid_size"] - df["ask_size"]) / (total_size + 1e-8)

        return df

    def _compute_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Compute Relative Strength Index."""
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(period).mean()
        rs = gain / (loss + 1e-8)
        return 100 - (100 / (1 + rs))

    def _compute_atr(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> pd.Series:
        """Compute Average True Range."""
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(period).mean()

    def _compute_adx(
        self, high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        """Compute Average Directional Index and +DI/-DI."""
        # True Range
        prev_close = close.shift(1)
        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

        # Directional Movement
        up_move = high - high.shift(1)
        down_move = low.shift(1) - low
        plus_dm = np.where((up_move > down_move) & (up_move > 0), up_move, 0)
        minus_dm = np.where((down_move > up_move) & (down_move > 0), down_move, 0)

        # Smoothed values
        atr = pd.Series(tr, index=high.index).rolling(period).mean()
        plus_di = 100 * pd.Series(plus_dm, index=high.index).rolling(period).mean() / (atr + 1e-8)
        minus_di = 100 * pd.Series(minus_dm, index=high.index).rolling(period).mean() / (atr + 1e-8)

        # ADX
        dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di + 1e-8)
        adx = dx.rolling(period).mean()

        return adx, plus_di, minus_di

    def _compute_mfi(
        self,
        high: pd.Series,
        low: pd.Series,
        close: pd.Series,
        volume: pd.Series,
        period: int = 14,
    ) -> pd.Series:
        """Compute Money Flow Index."""
        tp = (high + low + close) / 3
        mf = tp * volume
        mf_positive = np.where(tp > tp.shift(1), mf, 0)
        mf_negative = np.where(tp < tp.shift(1), mf, 0)

        mf_positive_sum = pd.Series(mf_positive, index=close.index).rolling(period).sum()
        mf_negative_sum = pd.Series(mf_negative, index=close.index).rolling(period).sum()

        mr = mf_positive_sum / (mf_negative_sum + 1e-8)
        return 100 - (100 / (1 + mr))

    def _register_feature(self, name: str, category: str, metadata: dict[str, Any]) -> None:
        """Register a feature with its metadata."""
        self._feature_registry[name] = {
            "category": category,
            "created_at": datetime.now().isoformat(),
            **metadata,
        }

    def get_feature_registry(self) -> dict[str, dict[str, Any]]:
        """Get the feature registry."""
        return self._feature_registry.copy()

    def list_features_by_category(self, category: str) -> list[str]:
        """List all features in a category."""
        return [
            name
            for name, meta in self._feature_registry.items()
            if meta.get("category") == category
        ]


class AlphaResearcher:
    """
    Alpha Research Framework for systematic strategy development.

    Provides a structured workflow for:
    1. Signal generation from feature library
    2. Signal evaluation and ranking
    3. Alpha combination and ensemble
    4. Out-of-sample testing

    Usage:
        researcher = AlphaResearcher()
        signals = researcher.generate_signals(df, ["momentum", "mean_reversion"])
        ranked = researcher.rank_signals(signals, returns)
        combined = researcher.combine_alphas(ranked, weights=[0.6, 0.4])
    """

    def __init__(self, feature_library: FeatureLibrary | None = None):
        self.feature_library = feature_library or FeatureLibrary()
        self._alpha_registry: dict[str, dict[str, Any]] = {}

    def generate_signals(
        self,
        df: pd.DataFrame,
        signal_types: list[str],
    ) -> pd.DataFrame:
        """
        Generate alpha signals from specified signal types.

        Args:
            df: OHLCV DataFrame with features
            signal_types: List of signal types to generate

        Returns:
            DataFrame with signal columns
        """
        signals = pd.DataFrame(index=df.index)

        for signal_type in signal_types:
            if signal_type == "momentum":
                signals["alpha_momentum"] = self._momentum_signal(df)
            elif signal_type == "mean_reversion":
                signals["alpha_mean_reversion"] = self._mean_reversion_signal(df)
            elif signal_type == "volatility_breakout":
                signals["alpha_vol_breakout"] = self._volatility_breakout_signal(df)
            elif signal_type == "volume_flow":
                signals["alpha_volume_flow"] = self._volume_flow_signal(df)
            elif signal_type == "trend_following":
                signals["alpha_trend"] = self._trend_following_signal(df)
            else:
                logger.warning(f"Unknown signal type: {signal_type}")

        return signals

    def _momentum_signal(self, df: pd.DataFrame) -> pd.Series:
        """Generate momentum alpha signal."""
        # Multi-period momentum composite
        mom_1m = df.get("momentum_21d", df["Close"].pct_change(21))
        mom_3m = df.get("momentum_63d", df["Close"].pct_change(63))

        # Volatility-adjusted momentum
        vol = df.get("vol_realized_21d", df["Close"].pct_change().rolling(21).std())

        signal = (0.6 * mom_1m + 0.4 * mom_3m) / (vol + 1e-8)
        return self._normalize_signal(signal)

    def _mean_reversion_signal(self, df: pd.DataFrame) -> pd.Series:
        """Generate mean reversion alpha signal."""
        close = df["Close"]

        # Distance from moving average
        sma_20 = close.rolling(20).mean()
        z_score = (close - sma_20) / close.rolling(20).std()

        # RSI oversold/overbought
        rsi = df.get("rsi", self.feature_library._compute_rsi(close))
        rsi_signal = (50 - rsi) / 50  # Normalized RSI contrarian

        # Bollinger Band position (contrarian)
        bb_pos = df.get("bb_position", 0.5)
        bb_signal = 0.5 - bb_pos  # Contrarian: buy low, sell high

        signal = -0.4 * z_score + 0.3 * rsi_signal + 0.3 * bb_signal
        return self._normalize_signal(signal)

    def _volatility_breakout_signal(self, df: pd.DataFrame) -> pd.Series:
        """Generate volatility breakout alpha signal."""
        close = df["Close"]
        high = df["High"]
        low = df["Low"]

        # ATR breakout
        atr = df.get("atr", self.feature_library._compute_atr(high, low, close))
        upper_band = close.shift(1) + 2 * atr
        lower_band = close.shift(1) - 2 * atr

        breakout_up = (close > upper_band).astype(float)
        breakout_down = (close < lower_band).astype(float)

        signal = breakout_up - breakout_down
        return self._normalize_signal(signal)

    def _volume_flow_signal(self, df: pd.DataFrame) -> pd.Series:
        """Generate volume flow alpha signal."""
        # Accumulation/Distribution momentum
        ad_mom = df.get("ad_line_momentum", 0)

        # OBV momentum
        obv_mom = df.get("obv_momentum", 0)

        # CMF
        cmf = df.get("cmf_20d", 0)

        signal = 0.4 * ad_mom + 0.3 * obv_mom + 0.3 * cmf
        return self._normalize_signal(signal)

    def _trend_following_signal(self, df: pd.DataFrame) -> pd.Series:
        """Generate trend following alpha signal."""
        close = df["Close"]

        # MACD crossover
        macd = df.get("macd", 0)
        macd_signal_line = df.get("macd_signal", 0)
        macd_signal = np.sign(macd - macd_signal_line)

        # ADX trend strength
        adx = df.get("adx", 25)
        trend_strength = (adx - 25) / 25  # Normalized: 0 at ADX=25, 1 at ADX=50

        # Moving average alignment
        sma_20 = close.rolling(20).mean()
        sma_50 = close.rolling(50).mean()
        sma_200 = close.rolling(200).mean()
        ma_alignment = (
            np.sign(sma_20 - sma_50) + np.sign(sma_50 - sma_200) + np.sign(close - sma_20)
        ) / 3

        signal = 0.4 * macd_signal + 0.3 * trend_strength + 0.3 * ma_alignment
        return self._normalize_signal(signal)

    def _normalize_signal(self, signal: pd.Series) -> pd.Series:
        """Normalize signal to [-1, 1] range using z-score."""
        mean = signal.rolling(252, min_periods=21).mean()
        std = signal.rolling(252, min_periods=21).std()
        z_score = (signal - mean) / (std + 1e-8)
        return z_score.clip(-3, 3) / 3  # Cap at 3 std, then scale to [-1, 1]

    def rank_signals(
        self,
        signals: pd.DataFrame,
        forward_returns: pd.Series,
        holding_period: int = 5,
    ) -> pd.DataFrame:
        """
        Rank alpha signals by their predictive power.

        Args:
            signals: DataFrame with alpha signals
            forward_returns: Series of forward returns
            holding_period: Holding period for IC calculation

        Returns:
            DataFrame with signal rankings and IC values
        """
        results = []

        for col in signals.columns:
            if col.startswith("alpha_"):
                # Calculate Information Coefficient (rank correlation)
                ic = signals[col].corr(forward_returns, method="spearman")

                # Calculate IC mean and std over rolling windows
                rolling_ic = signals[col].rolling(63).corr(forward_returns.rolling(63))
                ic_mean = rolling_ic.mean()
                ic_std = rolling_ic.std()
                ic_ir = ic_mean / (ic_std + 1e-8)  # Information Ratio

                results.append(
                    {
                        "signal": col,
                        "ic": ic,
                        "ic_mean": ic_mean,
                        "ic_std": ic_std,
                        "ic_ir": ic_ir,
                        "holding_period": holding_period,
                    }
                )

        return pd.DataFrame(results).sort_values("ic_ir", ascending=False)

    def combine_alphas(
        self,
        signals: pd.DataFrame,
        weights: list[float] | None = None,
        method: str = "weighted",
    ) -> pd.Series:
        """
        Combine multiple alpha signals into a composite signal.

        Args:
            signals: DataFrame with alpha signals
            weights: Optional weights for each signal
            method: Combination method ("weighted", "rank_weighted", "equal")

        Returns:
            Combined alpha signal
        """
        alpha_cols = [col for col in signals.columns if col.startswith("alpha_")]

        if not alpha_cols:
            raise ValueError("No alpha columns found in signals DataFrame")

        if method == "equal" or weights is None:
            weights = [1.0 / len(alpha_cols)] * len(alpha_cols)

        if len(weights) != len(alpha_cols):
            raise ValueError(f"Weights length ({len(weights)}) != signals ({len(alpha_cols)})")

        # Normalize weights
        weights = np.array(weights) / np.sum(weights)

        if method == "rank_weighted":
            # Convert to ranks before weighting
            ranked = signals[alpha_cols].rank(pct=True)
            combined = (ranked * weights).sum(axis=1)
        else:
            # Direct weighted combination
            combined = (signals[alpha_cols] * weights).sum(axis=1)

        return combined


# Convenience function
def create_research_dataset(
    symbol: str,
    start_date: str,
    end_date: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Create a complete research dataset with features and targets.

    Args:
        symbol: Stock symbol
        start_date: Start date (YYYY-MM-DD)
        end_date: End date (YYYY-MM-DD)

    Returns:
        Tuple of (features_df, targets_df)
    """
    import yfinance as yf

    # Fetch data
    ticker = yf.Ticker(symbol)
    df = ticker.history(start=start_date, end=end_date)

    if df.empty:
        raise ValueError(f"No data available for {symbol}")

    # Generate features
    feature_lib = FeatureLibrary()
    features = feature_lib.compute_all_features(df)

    # Generate targets (forward returns at multiple horizons)
    targets = pd.DataFrame(index=df.index)
    for horizon in [1, 5, 10, 21]:
        targets[f"fwd_ret_{horizon}d"] = features["Close"].pct_change(horizon).shift(-horizon)
        targets[f"fwd_direction_{horizon}d"] = (targets[f"fwd_ret_{horizon}d"] > 0).astype(int)

    return features, targets


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    print("=" * 80)
    print("ALPHA RESEARCH FRAMEWORK DEMO")
    print("=" * 80)

    # Create sample data
    dates = pd.date_range("2023-01-01", periods=500, freq="D")
    np.random.seed(42)
    close = 100 * (1 + np.random.randn(500).cumsum() * 0.01)
    df = pd.DataFrame(
        {
            "Open": close * (1 + np.random.randn(500) * 0.005),
            "High": close * (1 + np.abs(np.random.randn(500)) * 0.01),
            "Low": close * (1 - np.abs(np.random.randn(500)) * 0.01),
            "Close": close,
            "Volume": np.random.randint(1000000, 10000000, 500),
        },
        index=dates,
    )

    # Initialize feature library
    feature_lib = FeatureLibrary()
    features = feature_lib.compute_all_features(df)
    print(f"\nGenerated {len(features.columns)} features")

    # Initialize alpha researcher
    researcher = AlphaResearcher(feature_lib)
    signals = researcher.generate_signals(
        features,
        ["momentum", "mean_reversion", "trend_following", "volume_flow"],
    )
    print(f"\nGenerated {len(signals.columns)} alpha signals")

    # Rank signals
    forward_returns = features["Close"].pct_change(5).shift(-5)
    rankings = researcher.rank_signals(signals, forward_returns)
    print("\nSignal Rankings:")
    print(rankings)

    # Combine alphas
    combined = researcher.combine_alphas(signals, method="equal")
    print(f"\nCombined alpha signal shape: {combined.shape}")

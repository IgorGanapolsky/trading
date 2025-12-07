"""
Technical indicator features for trading strategy research.

Provides standardized technical indicators (RSI, MACD, Bollinger Bands, etc.).
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def calculate_technical_indicators(
    prices: pd.Series,
    volume: pd.Series | None = None,
    indicators: list[str] | None = None,
) -> pd.DataFrame:
    """
    Calculate multiple technical indicators at once.

    Args:
        prices: Price series (typically Close)
        volume: Volume series (optional)
        indicators: List of indicators to calculate. If None, calculates all.

    Returns:
        DataFrame with technical indicator columns
    """
    if indicators is None:
        indicators = [
            "rsi",
            "macd",
            "bollinger",
            "sma",
            "ema",
            "stochastic",
        ]

    results = {}

    if "rsi" in indicators:
        results["rsi"] = calculate_rsi(prices)

    if "macd" in indicators:
        macd_data = calculate_macd(prices)
        results["macd"] = macd_data["macd"]
        results["macd_signal"] = macd_data["signal"]
        results["macd_histogram"] = macd_data["histogram"]

    if "bollinger" in indicators:
        bb_data = calculate_bollinger_bands(prices)
        results["bb_upper"] = bb_data["upper"]
        results["bb_middle"] = bb_data["middle"]
        results["bb_lower"] = bb_data["lower"]
        results["bb_width"] = bb_data["width"]
        results["bb_position"] = bb_data["position"]

    if "sma" in indicators:
        results["sma_20"] = calculate_sma(prices, window=20)
        results["sma_50"] = calculate_sma(prices, window=50)
        results["sma_200"] = calculate_sma(prices, window=200)

    if "ema" in indicators:
        results["ema_12"] = calculate_ema(prices, span=12)
        results["ema_26"] = calculate_ema(prices, span=26)

    if "stochastic" in indicators and volume is not None:
        stoch_data = calculate_stochastic(prices, volume)
        results["stoch_k"] = stoch_data["k"]
        results["stoch_d"] = stoch_data["d"]

    return pd.DataFrame(results)


def calculate_rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    """
    Calculate Relative Strength Index (RSI).

    Args:
        prices: Price series
        window: RSI window size

    Returns:
        Series of RSI values (0-100)
    """
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=window).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=window).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))

    return rsi


def calculate_macd(
    prices: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> dict[str, pd.Series]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    Args:
        prices: Price series
        fast: Fast EMA period
        slow: Slow EMA period
        signal: Signal line EMA period

    Returns:
        Dictionary with 'macd', 'signal', and 'histogram' series
    """
    ema_fast = calculate_ema(prices, span=fast)
    ema_slow = calculate_ema(prices, span=slow)

    macd = ema_fast - ema_slow
    signal_line = calculate_ema(macd, span=signal)
    histogram = macd - signal_line

    return {
        "macd": macd,
        "signal": signal_line,
        "histogram": histogram,
    }


def calculate_bollinger_bands(
    prices: pd.Series,
    window: int = 20,
    num_std: float = 2.0,
) -> dict[str, pd.Series]:
    """
    Calculate Bollinger Bands.

    Args:
        prices: Price series
        window: Rolling window size
        num_std: Number of standard deviations

    Returns:
        Dictionary with 'upper', 'middle', 'lower', 'width', and 'position' series
    """
    sma = calculate_sma(prices, window=window)
    std = prices.rolling(window=window).std()

    upper = sma + (std * num_std)
    lower = sma - (std * num_std)
    width = (upper - lower) / sma
    position = (prices - lower) / (upper - lower)

    return {
        "upper": upper,
        "middle": sma,
        "lower": lower,
        "width": width,
        "position": position,
    }


def calculate_sma(prices: pd.Series, window: int) -> pd.Series:
    """Calculate Simple Moving Average."""
    return prices.rolling(window=window).mean()


def calculate_ema(prices: pd.Series, span: int) -> pd.Series:
    """Calculate Exponential Moving Average."""
    return prices.ewm(span=span, adjust=False).mean()


def calculate_stochastic(
    prices: pd.Series,
    volume: pd.Series,
    window: int = 14,
) -> dict[str, pd.Series]:
    """
    Calculate Stochastic Oscillator.

    Args:
        prices: Price series
        volume: Volume series (for volume-weighted stochastic)
        window: Rolling window size

    Returns:
        Dictionary with 'k' and 'd' series
    """
    # Simplified stochastic (using prices only)
    # Full implementation would use high/low
    low = prices.rolling(window=window).min()
    high = prices.rolling(window=window).max()

    k = 100 * (prices - low) / (high - low)
    d = k.rolling(window=3).mean()

    return {"k": k, "d": d}

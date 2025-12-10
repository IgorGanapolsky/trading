"""
Shared Technical Indicators Utility

This module provides a single source of truth for technical indicator calculations
(MACD, RSI, Volume Ratio) used across the trading system.

Consolidates duplicate logic from:
- scripts/autonomous_trader.py
- src/strategies/core_strategy.py
- src/strategies/growth_strategy.py
"""

import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def calculate_macd(
    prices: pd.Series,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
) -> tuple[float, float, float]:
    """
    Calculate MACD (Moving Average Convergence Divergence).

    MACD is a trend-following momentum indicator that shows the relationship between
    two exponential moving averages (EMAs) of a security's price.

    Formula:
    - MACD Line = 12-day EMA - 26-day EMA
    - Signal Line = 9-day EMA of MACD Line
    - Histogram = MACD Line - Signal Line

    Trading Signals:
    - Bullish: MACD crosses above signal line (histogram > 0)
    - Bearish: MACD crosses below signal line (histogram < 0)
    - Momentum strength: Larger histogram = stronger momentum

    Args:
        prices: Price series (typically Close prices)
        fast_period: Fast EMA period (default: 12)
        slow_period: Slow EMA period (default: 26)
        signal_period: Signal line EMA period (default: 9)

    Returns:
        Tuple of (macd_value, signal_line, histogram)
    """
    if len(prices) < slow_period + signal_period:
        logger.warning(
            f"Insufficient data for MACD calculation: {len(prices)} bars, "
            f"need at least {slow_period + signal_period}"
        )
        return (0.0, 0.0, 0.0)

    # Calculate exponential moving averages
    ema_fast = prices.ewm(span=fast_period, adjust=False).mean()
    ema_slow = prices.ewm(span=slow_period, adjust=False).mean()

    # MACD line = Fast EMA - Slow EMA
    macd_line = ema_fast - ema_slow

    # Signal line = 9-day EMA of MACD line
    signal_line = macd_line.ewm(span=signal_period, adjust=False).mean()

    # MACD histogram = MACD line - Signal line
    histogram = macd_line - signal_line

    # Helper to safely get scalar float
    def get_scalar(val):
        try:
            if hasattr(val, "item"):
                return float(val.item())
            if hasattr(val, "iloc") and len(val) > 0:
                return get_scalar(val.iloc[0])
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    # Return most recent values
    return (
        get_scalar(macd_line.iloc[-1]),
        get_scalar(signal_line.iloc[-1]),
        get_scalar(histogram.iloc[-1]),
    )


def calculate_rsi(prices: pd.Series, period: int = 14) -> float:
    """
    Calculate RSI (Relative Strength Index).

    RSI is a momentum oscillator that measures the speed and magnitude of price changes.
    Values range from 0 to 100.

    Trading Signals:
    - Overbought: RSI > 70 (potential sell signal)
    - Oversold: RSI < 30 (potential buy signal)
    - Neutral: 30 < RSI < 70

    Args:
        prices: Price series (typically Close prices)
        period: RSI period (default: 14)

    Returns:
        RSI value (0-100)
    """
    if len(prices) < period + 1:
        logger.warning(
            f"Insufficient data for RSI calculation: {len(prices)} bars, need at least {period + 1}"
        )
        return 50.0  # Neutral RSI

    # Calculate price changes
    delta = prices.diff()

    # Separate gains and losses
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    # Calculate average gain and loss
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()

    # Calculate RS (Relative Strength)
    rs = avg_gain / avg_loss.replace(0, np.nan)

    # Calculate RSI
    rsi = 100 - (100 / (1 + rs))

    # Return most recent value
    rsi_value = rsi.iloc[-1]
    if isinstance(rsi_value, pd.Series):
        rsi_value = rsi_value.iloc[0]

    if pd.isna(rsi_value):
        return 50.0  # Neutral RSI

    return float(rsi_value)


def calculate_volume_ratio(hist: pd.DataFrame, window: int = 20) -> float:
    """
    Calculate volume ratio (current vs N-day average).

    Volume ratio helps confirm price movements:
    - High volume (>1.5x average) = Strong conviction
    - Low volume (<0.8x average) = Weak conviction

    Args:
        hist: Historical price DataFrame with 'Volume' column
        window: Window size for average volume calculation (default: 20)

    Returns:
        Volume ratio (current / average)
    """
    if len(hist) < window:
        logger.warning(
            f"Insufficient data for volume ratio: {len(hist)} bars, need at least {window}"
        )
        return 1.0

    if "Volume" not in hist.columns:
        logger.warning("Volume column not found in DataFrame")
        return 1.0

    current_volume = hist["Volume"].iloc[-1]
    avg_volume = hist["Volume"].iloc[-window:].mean()

    # yfinance sometimes returns multi-indexed frames even for single symbols.
    if isinstance(current_volume, pd.Series):
        current_volume = current_volume.iloc[-1]
    if isinstance(avg_volume, pd.Series):
        avg_volume = avg_volume.iloc[-1]

    if avg_volume == 0 or pd.isna(avg_volume):
        return 1.0

    return float(current_volume / avg_volume)


def calculate_technical_score(
    hist: pd.DataFrame,
    symbol: str,
    macd_threshold: float = 0.0,
    rsi_overbought: float = 70.0,
    volume_min: float = 0.8,
) -> tuple[float, dict]:
    """
    Calculate composite technical score for a symbol.

    This function implements the same logic as autonomous_trader.py but
    uses the shared indicator functions.

    Args:
        hist: Historical price DataFrame with 'Close' and 'Volume' columns
        symbol: Symbol name (for logging)
        macd_threshold: Minimum MACD histogram value (default: 0.0)
        rsi_overbought: Maximum RSI value (default: 70.0)
        volume_min: Minimum volume ratio (default: 0.8)

    Returns:
        Tuple of (technical_score, indicators_dict)
        Returns (0, {}) if symbol is rejected by filters
    """
    if hist.empty or len(hist) < 26:
        logger.warning(f"{symbol}: Insufficient data ({len(hist)} bars)")
        return (0.0, {})

    # Calculate indicators
    macd_value_raw, macd_signal_raw, macd_histogram_raw = calculate_macd(hist["Close"])
    rsi_val_raw = calculate_rsi(hist["Close"])
    volume_ratio_raw = calculate_volume_ratio(hist)

    # Helper to ensure scalar float
    def to_float(val):
        try:
            if hasattr(val, "item"):
                return float(val.item())
            if hasattr(val, "iloc") and len(val) > 0:
                return to_float(val.iloc[0])
            return float(val) if not pd.isna(val) else 0.0
        except Exception:
            return 0.0

    # Convert all to scalars for safety
    macd_value = to_float(macd_value_raw)
    macd_signal = to_float(macd_signal_raw)
    macd_histogram = to_float(macd_histogram_raw)
    rsi_val = to_float(rsi_val_raw)
    volume_ratio = to_float(volume_ratio_raw)

    price_raw = hist["Close"].iloc[-1]
    current_price = to_float(price_raw)

    indicators = {
        "macd_value": macd_value,
        "macd_signal": macd_signal,
        "macd_histogram": macd_histogram,
        "rsi": rsi_val,
        "volume_ratio": volume_ratio,
        "current_price": current_price,
    }

    # HARD FILTERS - Reject entries that don't meet criteria
    if macd_histogram < macd_threshold:
        logger.info(f"{symbol}: REJECTED - Bearish MACD histogram ({macd_histogram:.3f})")
        return (0.0, indicators)

    if rsi_val > rsi_overbought:
        logger.info(f"{symbol}: REJECTED - Overbought RSI ({rsi_val:.1f})")
        return (0.0, indicators)

    if volume_ratio < volume_min:
        logger.info(f"{symbol}: REJECTED - Low volume ({volume_ratio:.2f}x)")
        return (0.0, indicators)

    # Calculate composite score (price weighted by technical strength)
    technical_score = (
        current_price * (1 + macd_histogram / 10) * (1 + (70 - rsi_val) / 100) * volume_ratio
    )

    logger.info(
        f"{symbol}: Score {technical_score:.2f} | "
        f"MACD: {macd_histogram:.3f} | RSI: {rsi_val:.1f} | Vol: {volume_ratio:.2f}x"
    )

    return (technical_score, indicators)


def calculate_atr(hist: pd.DataFrame, period: int = 14) -> float:
    """
    Calculate Average True Range (ATR) for dynamic stop-loss placement.

    ATR measures market volatility by calculating the average of true ranges
    over a specified period. True Range is the maximum of:
    1. Current High - Current Low
    2. |Current High - Previous Close|
    3. |Current Low - Previous Close|

    ATR-based stop-losses adapt to volatility:
    - High volatility = wider stops (less likely to be stopped out by noise)
    - Low volatility = tighter stops (protect profits better)

    Args:
        hist: Historical price DataFrame with 'High', 'Low', 'Close' columns
        period: ATR period (default: 14)

    Returns:
        ATR value (in price units)
    """
    if len(hist) < period + 1:
        logger.warning(
            f"Insufficient data for ATR calculation: {len(hist)} bars, need at least {period + 1}"
        )
        return 0.0

    if not all(col in hist.columns for col in ["High", "Low", "Close"]):
        logger.warning("Missing required columns for ATR: High, Low, Close")
        return 0.0

    # Calculate True Range for each period
    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]

    # True Range = max of:
    # 1. High - Low
    # 2. |High - Previous Close|
    # 3. |Low - Previous Close|
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))

    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Calculate ATR as simple moving average of True Range
    atr = true_range.rolling(window=period).mean()

    # Return most recent value
    atr_value = atr.iloc[-1]
    if isinstance(atr_value, pd.Series):
        atr_value = atr_value.iloc[0]

    if pd.isna(atr_value) or atr_value <= 0:
        return 0.0

    return float(atr_value)


def calculate_atr_stop_loss(
    entry_price: float, atr: float, multiplier: float = 2.0, direction: str = "long"
) -> float:
    """
    Calculate ATR-based stop-loss price.

    Stop-loss is placed at entry_price ± (multiplier × ATR)
    - Long positions: entry_price - (multiplier × ATR)
    - Short positions: entry_price + (multiplier × ATR)

    Common multipliers:
    - 1.5x ATR: Tighter stop (more sensitive)
    - 2.0x ATR: Balanced (default)
    - 2.5x ATR: Wider stop (less sensitive, good for volatile stocks)

    Args:
        entry_price: Entry price of the position
        atr: Average True Range value
        multiplier: ATR multiplier (default: 2.0)
        direction: 'long' or 'short' (default: 'long')

    Returns:
        Stop-loss price
    """
    if atr <= 0:
        # Fallback to percentage-based stop if ATR unavailable
        if direction == "long":
            return entry_price * 0.97  # 3% stop-loss
        else:
            return entry_price * 1.03  # 3% stop-loss

    stop_distance = multiplier * atr

    if direction == "long":
        stop_price = entry_price - stop_distance
    else:  # short
        stop_price = entry_price + stop_distance

    return max(0.0, stop_price)  # Ensure non-negative


def calculate_bollinger_bands(
    prices: pd.Series, period: int = 20, num_std: float = 2.0
) -> tuple[float, float, float]:
    """
    Calculate Bollinger Bands (upper, middle, lower).

    Bollinger Bands consist of:
    - Middle Band: Simple Moving Average (SMA)
    - Upper Band: SMA + (num_std × standard deviation)
    - Lower Band: SMA - (num_std × standard deviation)

    Trading Signals:
    - Price touches upper band: Potentially overbought
    - Price touches lower band: Potentially oversold
    - Band width: Measures volatility (wider = more volatile)

    Args:
        prices: Price series (typically Close prices)
        period: Moving average period (default: 20)
        num_std: Number of standard deviations (default: 2.0)

    Returns:
        Tuple of (upper_band, middle_band, lower_band)
    """
    if len(prices) < period:
        logger.warning(
            f"Insufficient data for Bollinger Bands: {len(prices)} bars, need at least {period}"
        )
        current_price = float(prices.iloc[-1]) if not prices.empty else 0.0
        return (current_price, current_price, current_price)

    # Calculate middle band (SMA)
    middle_band = prices.rolling(window=period).mean()

    # Calculate standard deviation
    std = prices.rolling(window=period).std()

    # Calculate upper and lower bands
    upper_band = middle_band + (num_std * std)
    lower_band = middle_band - (num_std * std)

    # Helper to safely get scalar float
    def get_scalar(val, default):
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        return float(val) if not pd.isna(val) else float(default)

    # Return most recent values
    current_price = prices.iloc[-1]
    if isinstance(current_price, pd.Series):
        current_price = current_price.iloc[0]

    return (
        get_scalar(upper_band.iloc[-1], current_price),
        get_scalar(middle_band.iloc[-1], current_price),
        get_scalar(lower_band.iloc[-1], current_price),
    )


def calculate_adx(hist: pd.DataFrame, period: int = 14) -> tuple[float, float, float]:
    """
    Calculate ADX (Average Directional Index) and Directional Movement Indicators.

    ADX measures trend strength (0-100):
    - ADX < 20: Weak/no trend (ranging market)
    - ADX 20-40: Moderate trend
    - ADX > 40: Strong trend

    Components:
    - +DI (Plus Directional Indicator): Measures upward price movement
    - -DI (Minus Directional Indicator): Measures downward price movement
    - ADX: Average of the absolute difference between +DI and -DI

    Args:
        hist: Historical price DataFrame with 'High', 'Low', 'Close' columns
        period: ADX period (default: 14)

    Returns:
        Tuple of (adx, plus_di, minus_di)
    """
    if len(hist) < period + 1:
        logger.warning(f"Insufficient data for ADX: {len(hist)} bars, need at least {period + 1}")
        return (0.0, 0.0, 0.0)

    if not all(col in hist.columns for col in ["High", "Low", "Close"]):
        logger.warning("Missing required columns for ADX: High, Low, Close")
        return (0.0, 0.0, 0.0)

    high = hist["High"]
    low = hist["Low"]
    close = hist["Close"]

    # Calculate Directional Movement
    plus_dm = high.diff()
    minus_dm = -low.diff()

    # Filter: only keep positive directional movement
    plus_dm = plus_dm.where((plus_dm > minus_dm) & (plus_dm > 0), 0.0)
    minus_dm = minus_dm.where((minus_dm > plus_dm) & (minus_dm > 0), 0.0)

    # Calculate True Range (same as ATR)
    tr1 = high - low
    tr2 = abs(high - close.shift(1))
    tr3 = abs(low - close.shift(1))
    true_range = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)

    # Smooth the values using Wilder's smoothing (similar to EMA)
    atr = true_range.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * (plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)
    minus_di = 100 * (minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr)

    # Calculate DX (Directional Index)
    dx = 100 * abs(plus_di - minus_di) / (plus_di + minus_di).replace(0, np.nan)

    # Calculate ADX as smoothed average of DX
    adx = dx.ewm(alpha=1 / period, adjust=False).mean()

    # Helper to safely get scalar float
    def get_scalar(val):
        if isinstance(val, pd.Series):
            val = val.iloc[0]
        return float(val) if not pd.isna(val) else 0.0

    # Return most recent values
    return (
        get_scalar(adx.iloc[-1]),
        get_scalar(plus_di.iloc[-1]),
        get_scalar(minus_di.iloc[-1]),
    )


def calculate_all_features(hist: pd.DataFrame, symbol: str = "") -> dict[str, float]:
    """
    Calculate comprehensive feature set (30-50 features) for deep learning models.

    This function extracts all technical indicators needed for LSTM-PPO ensemble
    as specified in RL_TRADING_STRATEGY_GUIDE.md.

    Features include:
    - Price features (OHLCV, returns, volatility)
    - Trend indicators (MA, MACD, ADX)
    - Momentum indicators (RSI, ROC)
    - Volatility indicators (Bollinger Bands, ATR)
    - Volume indicators (volume ratio, OBV)

    Args:
        hist: Historical price DataFrame with OHLCV columns
        symbol: Symbol name (for logging)

    Returns:
        Dictionary of feature values (normalized where appropriate)
    """
    if hist.empty or len(hist) < 200:
        logger.warning(f"{symbol}: Insufficient data for feature extraction ({len(hist)} bars)")
        return {}

    close = hist["Close"]
    high = hist["High"] if "High" in hist.columns else close
    low = hist["Low"] if "Low" in hist.columns else close
    volume = hist["Volume"] if "Volume" in hist.columns else pd.Series([1.0] * len(hist))

    features = {}

    # Price Features (10 features)
    features["close"] = float(close.iloc[-1])
    features["open"] = float(hist["Open"].iloc[-1]) if "Open" in hist.columns else features["close"]
    features["high"] = float(high.iloc[-1])
    features["low"] = float(low.iloc[-1])

    # Returns (log returns for better normalization)
    returns_1d = np.log(close.iloc[-1] / close.iloc[-2]) if len(close) > 1 else 0.0
    returns_5d = np.log(close.iloc[-1] / close.iloc[-6]) if len(close) > 5 else 0.0
    returns_20d = np.log(close.iloc[-1] / close.iloc[-21]) if len(close) > 20 else 0.0
    features["return_1d"] = returns_1d
    features["return_5d"] = returns_5d
    features["return_20d"] = returns_20d

    # Volatility (rolling std of returns)
    daily_returns = close.pct_change().dropna()
    volatility_20d = (
        daily_returns.iloc[-20:].std() * np.sqrt(252) if len(daily_returns) >= 20 else 0.0
    )
    features["volatility_20d"] = volatility_20d

    # Trend Indicators (15 features)
    # Moving Averages
    ma_20 = close.rolling(20).mean()
    ma_50 = close.rolling(50).mean()
    ma_200 = close.rolling(200).mean() if len(close) >= 200 else ma_50
    features["ma_20"] = float(ma_20.iloc[-1]) if not pd.isna(ma_20.iloc[-1]) else features["close"]
    features["ma_50"] = float(ma_50.iloc[-1]) if not pd.isna(ma_50.iloc[-1]) else features["close"]
    features["ma_200"] = (
        float(ma_200.iloc[-1]) if not pd.isna(ma_200.iloc[-1]) else features["close"]
    )
    features["price_vs_ma20"] = (
        (features["close"] - features["ma_20"]) / features["ma_20"]
        if features["ma_20"] > 0
        else 0.0
    )
    features["price_vs_ma50"] = (
        (features["close"] - features["ma_50"]) / features["ma_50"]
        if features["ma_50"] > 0
        else 0.0
    )
    features["price_vs_ma200"] = (
        (features["close"] - features["ma_200"]) / features["ma_200"]
        if features["ma_200"] > 0
        else 0.0
    )

    # MACD
    macd_val, macd_signal, macd_hist = calculate_macd(close)
    features["macd"] = macd_val
    features["macd_signal"] = macd_signal
    features["macd_histogram"] = macd_hist

    # ADX
    adx, plus_di, minus_di = calculate_adx(hist)
    features["adx"] = adx
    features["plus_di"] = plus_di
    features["minus_di"] = minus_di

    # Momentum Indicators (5 features)
    features["rsi"] = calculate_rsi(close)

    # Rate of Change (ROC)
    roc_10 = (
        ((close.iloc[-1] - close.iloc[-11]) / close.iloc[-11] * 100) if len(close) > 10 else 0.0
    )
    roc_20 = (
        ((close.iloc[-1] - close.iloc[-21]) / close.iloc[-21] * 100) if len(close) > 20 else 0.0
    )
    features["roc_10"] = roc_10
    features["roc_20"] = roc_20

    # Volatility Indicators (8 features)
    # Bollinger Bands
    bb_upper, bb_middle, bb_lower = calculate_bollinger_bands(close)
    features["bb_upper"] = bb_upper
    features["bb_middle"] = bb_middle
    features["bb_lower"] = bb_lower
    features["bb_width"] = (bb_upper - bb_lower) / bb_middle if bb_middle > 0 else 0.0
    features["bb_position"] = (
        (features["close"] - bb_lower) / (bb_upper - bb_lower) if (bb_upper - bb_lower) > 0 else 0.5
    )

    # ATR
    atr = calculate_atr(hist)
    features["atr"] = atr
    features["atr_pct"] = (atr / features["close"] * 100) if features["close"] > 0 else 0.0

    # Volume Indicators (5 features)
    features["volume"] = float(volume.iloc[-1])
    features["volume_ratio"] = calculate_volume_ratio(hist)

    # On-Balance Volume (OBV) - simplified
    price_change = close.diff()
    obv = (volume * np.sign(price_change)).fillna(0).cumsum()
    features["obv"] = float(obv.iloc[-1])
    features["obv_ma"] = (
        float(obv.rolling(20).mean().iloc[-1]) if len(obv) >= 20 else features["obv"]
    )

    # Volume Rate of Change
    vol_roc = (
        ((volume.iloc[-1] - volume.iloc[-10]) / volume.iloc[-10] * 100)
        if len(volume) > 10 and volume.iloc[-10] > 0
        else 0.0
    )
    features["volume_roc"] = vol_roc

    logger.debug(f"{symbol}: Extracted {len(features)} features")

    return features

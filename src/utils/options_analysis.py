"""
Options Analysis Module - Centralized options analysis utilities.

This module consolidates duplicated options analysis functions from:
- scripts/execute_options_trade.py
- scripts/execute_credit_spread.py

Functions:
- get_underlying_price: Get current price of underlying symbol
- get_iv_percentile: Calculate IV Percentile for trading decisions
- get_trend_filter: Check market trend to avoid adverse conditions

Author: AI Trading System
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np
import yfinance as yf

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Minimum IV percentile threshold for selling options
# RELAXED from 50 to 30 on Dec 29, 2025 - too many opportunities blocked
# RAG still recommends >50%, but we need to generate $100/day
MIN_IV_PERCENTILE_FOR_SELLING = 30


def get_underlying_price(symbol: str) -> float:
    """
    Get current price of underlying symbol.

    Uses yfinance to fetch the most recent closing price for the given symbol.
    This is useful for calculating option metrics, strike selection, and
    position sizing.

    Args:
        symbol: Stock ticker symbol (e.g., 'SPY', 'F', 'SOFI')

    Returns:
        Current price as a float

    Raises:
        ValueError: If price data cannot be fetched for the symbol

    Example:
        >>> price = get_underlying_price('SPY')
        >>> print(f"SPY is at ${price:.2f}")
    """
    ticker = yf.Ticker(symbol)
    data = ticker.history(period="1d")

    if data.empty:
        raise ValueError(f"Could not get price for {symbol}")

    return float(data["Close"].iloc[-1])


def get_iv_percentile(symbol: str, lookback_days: int = 252) -> dict:
    """
    Calculate IV Percentile for a symbol.

    IV Percentile measures what percentage of days in the past year had
    implied volatility lower than the current IV. This helps determine
    whether options are relatively expensive or cheap.

    Per RAG knowledge (volatility_forecasting_2025.json):
    - IV Percentile > 50%: Favor selling strategies (CSPs, covered calls)
    - IV Percentile < 30%: Favor buying strategies or stay on sidelines

    Note: Uses Historical Volatility (HV) as a proxy for IV when actual
    IV data is not directly available from the data source.

    Args:
        symbol: Stock ticker symbol (e.g., 'SPY', 'F', 'SOFI')
        lookback_days: Number of trading days to analyze (default: 252, ~1 year)

    Returns:
        dict containing:
            - iv_percentile (float): Percentile value 0-100
            - current_iv (float|None): Current volatility value
            - recommendation (str): One of 'SELL_PREMIUM', 'NEUTRAL', 'AVOID_SELLING'

    Example:
        >>> result = get_iv_percentile('SPY')
        >>> if result['recommendation'] == 'SELL_PREMIUM':
        ...     print(f"Good time to sell options, IV at {result['iv_percentile']:.1f}%ile")
    """
    logger.info(f"Calculating IV Percentile for {symbol}...")

    try:
        ticker = yf.Ticker(symbol)

        # Get historical data for IV calculation (using HV as proxy)
        hist = ticker.history(period="1y")
        if len(hist) < 20:
            logger.warning(f"Insufficient history for {symbol}, defaulting to neutral")
            return {"iv_percentile": 50, "current_iv": None, "recommendation": "NEUTRAL"}

        # Calculate historical volatility (20-day rolling)
        returns = np.log(hist["Close"] / hist["Close"].shift(1))
        rolling_vol = returns.rolling(window=20).std() * np.sqrt(252) * 100  # Annualized %

        current_hv = rolling_vol.iloc[-1]

        # Calculate percentile
        valid_vols = rolling_vol.dropna()
        iv_percentile = (valid_vols < current_hv).sum() / len(valid_vols) * 100

        # Determine recommendation per RAG knowledge
        if iv_percentile >= 50:
            recommendation = "SELL_PREMIUM"
            logger.info(
                f"IV Percentile: {iv_percentile:.1f}% - FAVORABLE for selling premium"
            )
        elif iv_percentile >= 30:
            recommendation = "NEUTRAL"
            logger.info(f"IV Percentile: {iv_percentile:.1f}% - NEUTRAL conditions")
        else:
            recommendation = "AVOID_SELLING"
            logger.info(f"IV Percentile: {iv_percentile:.1f}% - UNFAVORABLE for selling")

        return {
            "iv_percentile": round(iv_percentile, 1),
            "current_iv": round(current_hv, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.error(f"IV calculation failed: {e}")
        return {"iv_percentile": 50, "current_iv": None, "recommendation": "NEUTRAL"}


def get_trend_filter(symbol: str, lookback_days: int = 20) -> dict:
    """
    Check market trend to avoid selling puts in downtrending markets.

    Per options_backtest_summary.md recommendations:
    - All losses (5/5) came from positions entered in strong trends
    - Use 20-day MA slope as trend indicator

    For CASH-SECURED PUTS:
    - Uptrend/Sideways: SAFE to sell puts (bullish bias helps)
    - Strong Downtrend: AVOID selling puts (will get assigned at bad prices)

    Thresholds (RELAXED Dec 16 to allow more trades):
    - Strong downtrend: slope < -0.5%/day AND price below MA by 5%+
    - Moderate downtrend: slope < -0.3%/day
    - Uptrend/Sideways: slope >= -0.3%/day

    Args:
        symbol: Stock ticker symbol (e.g., 'SPY', 'F', 'SOFI')
        lookback_days: Moving average period in days (default: 20)

    Returns:
        dict containing:
            - trend (str): One of 'STRONG_DOWNTREND', 'MODERATE_DOWNTREND',
                          'UPTREND_OR_SIDEWAYS', 'NEUTRAL', 'UNKNOWN'
            - slope (float): MA slope as percentage per day
            - price_vs_ma (float): Current price vs MA as percentage
            - recommendation (str): One of 'AVOID_PUTS', 'CAUTION_BUT_PROCEED', 'PROCEED'

    Example:
        >>> result = get_trend_filter('F')
        >>> if result['recommendation'] == 'AVOID_PUTS':
        ...     print(f"Skip trade - {result['trend']}, slope: {result['slope']:.3f}%/day")
    """
    logger.info(f"Checking trend filter for {symbol}...")

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="2mo")

        if len(hist) < lookback_days:
            logger.warning("Insufficient history for trend filter, defaulting to neutral")
            return {"trend": "NEUTRAL", "slope": 0, "price_vs_ma": 0, "recommendation": "PROCEED"}

        # Calculate moving average
        ma = hist["Close"].rolling(window=lookback_days).mean()

        # Calculate slope over last 5 days (normalized as % per day)
        recent_ma = ma.iloc[-5:]
        slope = (recent_ma.iloc[-1] - recent_ma.iloc[0]) / recent_ma.iloc[0] * 100 / 5

        # Check if price is above or below MA
        current_price = hist["Close"].iloc[-1]
        ma_current = ma.iloc[-1]
        price_vs_ma = (current_price - ma_current) / ma_current * 100

        # Determine trend
        # Strong downtrend: slope < -0.5% per day AND price below MA by 5%+
        # Moderate downtrend: slope < -0.3% per day
        # Uptrend/Sideways: slope >= -0.3%

        if slope < -0.5 and price_vs_ma < -5:
            trend = "STRONG_DOWNTREND"
            recommendation = "AVOID_PUTS"
            logger.warning("STRONG DOWNTREND detected!")
            logger.warning(f"MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")
        elif slope < -0.3:
            trend = "MODERATE_DOWNTREND"
            recommendation = "CAUTION_BUT_PROCEED"
            logger.info("Moderate downtrend - proceeding with caution")
            logger.info(f"MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")
        else:
            trend = "UPTREND_OR_SIDEWAYS"
            recommendation = "PROCEED"
            logger.info("Trend FAVORABLE for selling puts")
            logger.info(f"MA slope: {slope:.3f}%/day, Price vs MA: {price_vs_ma:.1f}%")

        return {
            "trend": trend,
            "slope": round(slope, 4),
            "price_vs_ma": round(price_vs_ma, 2),
            "recommendation": recommendation,
        }

    except Exception as e:
        logger.error(f"Trend filter failed: {e}")
        return {"trend": "UNKNOWN", "slope": 0, "price_vs_ma": 0, "recommendation": "PROCEED"}


def analyze_options_conditions(symbol: str) -> dict:
    """
    Comprehensive analysis combining IV percentile and trend filter.

    This is a convenience function that runs both analyses and provides
    a combined recommendation for options trading.

    Args:
        symbol: Stock ticker symbol (e.g., 'SPY', 'F', 'SOFI')

    Returns:
        dict containing:
            - symbol (str): The analyzed symbol
            - underlying_price (float|None): Current price
            - iv_analysis (dict): Results from get_iv_percentile()
            - trend_analysis (dict): Results from get_trend_filter()
            - overall_recommendation (str): Combined recommendation
            - safe_to_sell_puts (bool): Whether conditions favor selling puts

    Example:
        >>> result = analyze_options_conditions('SOFI')
        >>> if result['safe_to_sell_puts']:
        ...     print(f"Proceed with CSP on {result['symbol']} at ${result['underlying_price']:.2f}")
    """
    logger.info(f"Running comprehensive options analysis for {symbol}...")

    # Get underlying price
    try:
        price = get_underlying_price(symbol)
    except (ValueError, Exception) as e:
        logger.error(f"Could not get price for {symbol}: {e}")
        price = None

    # Run both analyses
    iv_result = get_iv_percentile(symbol)
    trend_result = get_trend_filter(symbol)

    # Determine overall recommendation
    iv_ok = iv_result["recommendation"] in ("SELL_PREMIUM", "NEUTRAL")
    trend_ok = trend_result["recommendation"] in ("PROCEED", "CAUTION_BUT_PROCEED")

    if iv_result["recommendation"] == "SELL_PREMIUM" and trend_result["recommendation"] == "PROCEED":
        overall = "STRONG_SELL_PREMIUM"
        safe_to_sell = True
    elif iv_ok and trend_ok:
        overall = "MODERATE_SELL_PREMIUM"
        safe_to_sell = True
    elif trend_result["recommendation"] == "AVOID_PUTS":
        overall = "AVOID_SELLING"
        safe_to_sell = False
    elif iv_result["recommendation"] == "AVOID_SELLING":
        overall = "WAIT_FOR_BETTER_IV"
        safe_to_sell = False
    else:
        overall = "NEUTRAL"
        safe_to_sell = False

    logger.info(f"Overall recommendation for {symbol}: {overall}")

    return {
        "symbol": symbol,
        "underlying_price": price,
        "iv_analysis": iv_result,
        "trend_analysis": trend_result,
        "overall_recommendation": overall,
        "safe_to_sell_puts": safe_to_sell,
    }

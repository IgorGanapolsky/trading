"""
Options Analysis Module - Centralized options analysis utilities.

This module consolidates duplicated options analysis functions from:
- scripts/execute_options_trade.py
- scripts/execute_credit_spread.py

Functions:
- get_underlying_price: Get current price of underlying symbol
- get_iv_percentile: Calculate IV Percentile for trading decisions
- get_trend_filter: Check market trend to avoid adverse conditions
- validate_contract_quality: Matt Giannino checklist validation (Jan 2026)
- get_atr: Average True Range for expiration timing
- check_liquidity: Open interest and bid-ask spread validation

Author: AI Trading System

References:
- Matt Giannino "My Top Secrets to Picking the Perfect Option Contract" (Jan 2026)
  https://youtu.be/LRpGK6bOH1Y
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
# LL-269 (Jan 21, 2026): Restored to 50% based on research
# IV Percentile >50% = options expensive enough to sell profitably
# Lower IV = thin premiums, not worth the risk
MIN_IV_PERCENTILE_FOR_SELLING = 50


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
            logger.info(f"IV Percentile: {iv_percentile:.1f}% - FAVORABLE for selling premium")
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

    if (
        iv_result["recommendation"] == "SELL_PREMIUM"
        and trend_result["recommendation"] == "PROCEED"
    ):
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


# =============================================================================
# Matt Giannino Options Contract Validation (Jan 2026)
# Source: https://youtu.be/LRpGK6bOH1Y
# =============================================================================

# Validation thresholds
MIN_DELTA_THETA_RATIO = 3.0  # Delta should be 3x Theta
MAX_THETA_DECAY_PCT = 10.0  # Max 10% daily decay
MIN_OPEN_INTEREST = 500  # Minimum liquidity
MAX_BID_ASK_SPREAD_PCT = 10.0  # Max 10% bid-ask spread


def get_atr(symbol: str, period: int = 14) -> dict:
    """
    Calculate Average True Range (ATR) for expiration timing.

    ATR measures average daily price movement. Use to determine:
    - How many days needed to reach target price
    - Appropriate expiration date (3-5x expected move time)

    Per Matt Giannino: If target is $2 away and ATR is $1/day,
    stock needs ~2 days. Choose expiration 7-10 days out (3-5x buffer).

    Args:
        symbol: Stock ticker symbol
        period: ATR period in days (default: 14)

    Returns:
        dict containing:
            - atr (float): Average True Range in dollars
            - atr_pct (float): ATR as percentage of price
            - current_price (float): Current stock price
            - suggested_min_dte (int): Minimum DTE for typical move

    Example:
        >>> result = get_atr('SPY')
        >>> if result['atr'] > 5:
        ...     print("High volatility - use shorter DTE")
    """
    logger.info(f"Calculating ATR for {symbol}...")

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1mo")

        if len(hist) < period + 1:
            logger.warning(f"Insufficient data for ATR calculation on {symbol}")
            return {"atr": 0, "atr_pct": 0, "current_price": 0, "suggested_min_dte": 30}

        # Calculate True Range
        high = hist["High"]
        low = hist["Low"]
        close = hist["Close"]
        prev_close = close.shift(1)

        tr1 = high - low
        tr2 = abs(high - prev_close)
        tr3 = abs(low - prev_close)

        true_range = np.maximum(tr1, np.maximum(tr2, tr3))

        # Calculate ATR (simple moving average of TR)
        atr = true_range.rolling(window=period).mean().iloc[-1]
        current_price = close.iloc[-1]
        atr_pct = (atr / current_price) * 100

        # Suggested minimum DTE: assume 1 ATR move target, 3x buffer
        # For a credit spread, we want time for theta decay
        suggested_min_dte = max(14, int(3 * (1 / (atr_pct / 100)) if atr_pct > 0 else 30))

        logger.info(f"ATR for {symbol}: ${atr:.2f} ({atr_pct:.2f}%)")

        return {
            "atr": round(atr, 2),
            "atr_pct": round(atr_pct, 2),
            "current_price": round(current_price, 2),
            "suggested_min_dte": min(suggested_min_dte, 60),  # Cap at 60 DTE
        }

    except Exception as e:
        logger.error(f"ATR calculation failed: {e}")
        return {"atr": 0, "atr_pct": 0, "current_price": 0, "suggested_min_dte": 30}


def check_liquidity(
    open_interest: int,
    bid: float,
    ask: float,
    min_oi: int = MIN_OPEN_INTEREST,
    max_spread_pct: float = MAX_BID_ASK_SPREAD_PCT,
) -> dict:
    """
    Validate option contract liquidity.

    Per Matt Giannino:
    - Open Interest should be > 500 (ideally much higher)
    - Bid-Ask spread should be < 10% (tighter is better)
    - Wide spreads mean 20-30% loss on entry

    Args:
        open_interest: Contract open interest
        bid: Current bid price
        ask: Current ask price
        min_oi: Minimum acceptable open interest (default: 500)
        max_spread_pct: Maximum acceptable spread percentage (default: 10%)

    Returns:
        dict containing:
            - is_liquid (bool): Whether contract meets liquidity requirements
            - open_interest (int): Open interest value
            - oi_ok (bool): Whether OI meets minimum
            - bid_ask_spread (float): Spread in dollars
            - spread_pct (float): Spread as percentage
            - spread_ok (bool): Whether spread is acceptable
            - warnings (list): List of liquidity warnings

    Example:
        >>> result = check_liquidity(1200, 1.50, 1.60)
        >>> if not result['is_liquid']:
        ...     print(f"Skip contract: {result['warnings']}")
    """
    warnings = []

    # Check open interest
    oi_ok = open_interest >= min_oi
    if not oi_ok:
        warnings.append(f"Low open interest: {open_interest} < {min_oi}")

    # Check bid-ask spread
    mid_price = (bid + ask) / 2 if bid > 0 and ask > 0 else 0
    spread = ask - bid if bid > 0 and ask > 0 else 0
    spread_pct = (spread / mid_price * 100) if mid_price > 0 else 100

    spread_ok = spread_pct <= max_spread_pct
    if not spread_ok:
        warnings.append(f"Wide bid-ask spread: {spread_pct:.1f}% > {max_spread_pct}%")

    is_liquid = oi_ok and spread_ok

    return {
        "is_liquid": is_liquid,
        "open_interest": open_interest,
        "oi_ok": oi_ok,
        "bid_ask_spread": round(spread, 2),
        "spread_pct": round(spread_pct, 2),
        "spread_ok": spread_ok,
        "warnings": warnings,
    }


def validate_delta_theta_ratio(
    delta: float,
    theta: float,
    contract_price: float,
    min_ratio: float = MIN_DELTA_THETA_RATIO,
    max_decay_pct: float = MAX_THETA_DECAY_PCT,
) -> dict:
    """
    Validate Delta-to-Theta ratio for contract quality.

    Per Matt Giannino's "Top Secret":
    - Delta/Theta ratio should be >= 3:1
    - Theta should not exceed 10% of contract price per day
    - 1:1 or 2:1 ratio is "super risky"

    For SELLING premium (our strategy):
    - We WANT high theta (decay works for us)
    - But we still want decent delta for directional moves
    - Ratio matters less for short positions, but we validate anyway

    Args:
        delta: Option delta (0 to 1 for calls, -1 to 0 for puts)
        theta: Option theta (negative number, daily decay)
        contract_price: Current contract price in dollars
        min_ratio: Minimum acceptable delta/theta ratio (default: 3.0)
        max_decay_pct: Maximum acceptable daily decay % (default: 10%)

    Returns:
        dict containing:
            - is_valid (bool): Whether contract passes validation
            - delta (float): Delta value
            - theta (float): Theta value (negative)
            - ratio (float): Delta/|Theta| ratio
            - ratio_ok (bool): Whether ratio meets minimum
            - theta_decay_pct (float): Daily decay as % of price
            - decay_ok (bool): Whether decay is acceptable
            - warnings (list): List of quality warnings

    Example:
        >>> result = validate_delta_theta_ratio(0.45, -0.10, 2.50)
        >>> if result['ratio'] >= 3:
        ...     print("Good delta/theta ratio!")
    """
    warnings = []

    # Use absolute values for calculation
    # Both delta and theta are per-share, so the 100x multiplier cancels out
    # Delta 0.45 / Theta 0.10 = 4.5 ratio (per Giannino's example)
    abs_delta = abs(delta)
    abs_theta = abs(theta)

    # Calculate ratio
    ratio = abs_delta / abs_theta if abs_theta > 0 else float("inf")
    ratio_ok = ratio >= min_ratio

    if not ratio_ok:
        warnings.append(f"Low delta/theta ratio: {ratio:.1f} < {min_ratio}")

    # Calculate theta decay percentage
    theta_decay_pct = (abs_theta / contract_price * 100) if contract_price > 0 else 0
    decay_ok = theta_decay_pct <= max_decay_pct

    if not decay_ok:
        warnings.append(f"High daily decay: {theta_decay_pct:.1f}% > {max_decay_pct}%")

    # For selling premium, high theta is actually good
    # But we still flag if ratio is dangerously low
    is_valid = ratio_ok and decay_ok

    return {
        "is_valid": is_valid,
        "delta": delta,
        "theta": theta,
        "ratio": round(ratio, 2),
        "ratio_ok": ratio_ok,
        "theta_decay_pct": round(theta_decay_pct, 2),
        "decay_ok": decay_ok,
        "warnings": warnings,
    }


def validate_contract_quality(
    symbol: str,
    delta: float,
    theta: float,
    contract_price: float,
    open_interest: int,
    bid: float,
    ask: float,
    implied_volatility: float | None = None,
) -> dict:
    """
    Complete Matt Giannino options contract validation checklist.

    Combines all quality checks:
    1. Delta/Theta ratio >= 3:1
    2. Theta < 10% daily decay
    3. Open Interest > 500
    4. Bid-Ask spread < 10%
    5. (Optional) IV crush warning

    Args:
        symbol: Underlying symbol for context
        delta: Option delta
        theta: Option theta (negative)
        contract_price: Contract price in dollars
        open_interest: Contract open interest
        bid: Current bid price
        ask: Current ask price
        implied_volatility: Optional IV for crush warning

    Returns:
        dict containing:
            - passes_checklist (bool): Whether contract passes all checks
            - checks_passed (int): Number of checks passed
            - checks_total (int): Total number of checks
            - delta_theta (dict): Delta/theta validation results
            - liquidity (dict): Liquidity validation results
            - iv_warning (str|None): IV crush warning if applicable
            - all_warnings (list): Combined list of all warnings
            - recommendation (str): Overall recommendation

    Example:
        >>> result = validate_contract_quality(
        ...     symbol='SPY', delta=0.45, theta=-0.10,
        ...     contract_price=2.50, open_interest=1500,
        ...     bid=2.45, ask=2.55, implied_volatility=0.25
        ... )
        >>> if result['passes_checklist']:
        ...     print("Contract meets all quality criteria!")
    """
    logger.info(f"Running Matt Giannino checklist for {symbol} contract...")

    all_warnings = []

    # Check 1 & 2: Delta/Theta ratio and decay
    dt_result = validate_delta_theta_ratio(delta, theta, contract_price)
    all_warnings.extend(dt_result["warnings"])

    # Check 3 & 4: Liquidity
    liquidity_result = check_liquidity(open_interest, bid, ask)
    all_warnings.extend(liquidity_result["warnings"])

    # Check 5: IV crush warning (if IV provided)
    iv_warning = None
    if implied_volatility is not None:
        iv_pct = implied_volatility * 100 if implied_volatility < 1 else implied_volatility
        if iv_pct > 50:
            iv_warning = f"HIGH IV ({iv_pct:.1f}%) - potential IV crush risk"
            all_warnings.append(iv_warning)

    # Count passed checks
    checks = [
        dt_result["ratio_ok"],
        dt_result["decay_ok"],
        liquidity_result["oi_ok"],
        liquidity_result["spread_ok"],
    ]
    checks_passed = sum(checks)
    checks_total = len(checks)

    # Overall pass/fail
    passes_checklist = all(checks)

    # Generate recommendation
    if passes_checklist and not iv_warning:
        recommendation = "PROCEED"
    elif passes_checklist and iv_warning:
        recommendation = "PROCEED_WITH_CAUTION"
    elif checks_passed >= 3:
        recommendation = "MARGINAL"
    else:
        recommendation = "SKIP"

    logger.info(f"Checklist result: {checks_passed}/{checks_total} passed, {recommendation}")

    return {
        "passes_checklist": passes_checklist,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "delta_theta": dt_result,
        "liquidity": liquidity_result,
        "iv_warning": iv_warning,
        "all_warnings": all_warnings,
        "recommendation": recommendation,
    }

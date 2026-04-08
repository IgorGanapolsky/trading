"""
Free Greeks + IV data from yfinance + Black-Scholes.

Replaces Alpaca SIP data (which fails: "subscription does not permit querying
recent SIP data") with free sources that actually work.

No API keys. No paid plans. No rate limits.
"""

import logging
import math
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


# ── Black-Scholes Greeks ─────────────────────────────────────────────────────


def _norm_cdf(x: float) -> float:
    """Standard normal CDF (no scipy needed)."""
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _norm_pdf(x: float) -> float:
    """Standard normal PDF."""
    return math.exp(-0.5 * x * x) / math.sqrt(2 * math.pi)


def black_scholes_greeks(
    S: float, K: float, T: float, r: float, sigma: float, option_type: str = "call"
) -> dict:
    """Calculate option Greeks using Black-Scholes.

    Args:
        S: Underlying price (SPY)
        K: Strike price
        T: Time to expiration in years (DTE/365)
        r: Risk-free rate (~0.05)
        sigma: Implied volatility (e.g., 0.18)
        option_type: "call" or "put"

    Returns:
        dict with delta, gamma, theta, vega, price
    """
    if T <= 0 or sigma <= 0:
        return {"delta": 0, "gamma": 0, "theta": 0, "vega": 0, "price": 0}

    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)

    if option_type == "call":
        delta = _norm_cdf(d1)
        price = S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    else:
        delta = _norm_cdf(d1) - 1
        price = K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)

    gamma = _norm_pdf(d1) / (S * sigma * math.sqrt(T))
    vega = S * _norm_pdf(d1) * math.sqrt(T) / 100  # Per 1% IV change
    theta = (
        -(S * _norm_pdf(d1) * sigma) / (2 * math.sqrt(T))
        - r * K * math.exp(-r * T) * _norm_cdf(d2 if option_type == "call" else -d2)
    ) / 365  # Per day

    return {
        "delta": round(delta, 4),
        "gamma": round(gamma, 6),
        "theta": round(theta, 4),
        "vega": round(vega, 4),
        "price": round(price, 4),
    }


# ── VIX from yfinance ────────────────────────────────────────────────────────


def get_vix() -> float | None:
    """Get current VIX from yfinance. Free, no API key."""
    try:
        import yfinance as yf

        vix = yf.Ticker("^VIX")
        hist = vix.history(period="5d")
        if hist.empty:
            return None
        return round(float(hist["Close"].iloc[-1]), 2)
    except Exception as e:
        logger.debug(f"VIX fetch failed: {e}")
        return None


# ── IV from yfinance option chains ───────────────────────────────────────────


def get_spy_iv(expiry: str | None = None) -> float | None:
    """Get SPY ATM implied volatility from yfinance option chain.

    Args:
        expiry: Option expiry date string (YYYY-MM-DD). If None, uses nearest.

    Returns:
        ATM implied volatility as decimal (e.g., 0.18 = 18%)
    """
    try:
        import yfinance as yf

        spy = yf.Ticker("SPY")
        expirations = spy.options

        if not expirations:
            return None

        # Find target expiry
        if expiry and expiry in expirations:
            target = expiry
        else:
            # Find nearest 30-DTE expiry
            today = datetime.now().date()
            target_date = today + timedelta(days=30)
            target = min(expirations, key=lambda e: abs(
                (datetime.strptime(e, "%Y-%m-%d").date() - target_date).days
            ))

        chain = spy.option_chain(target)
        current_price = float(spy.history(period="1d")["Close"].iloc[-1])

        # Get ATM options (closest to current price)
        calls = chain.calls
        if calls.empty:
            return None

        calls = calls.copy()
        calls["distance"] = abs(calls["strike"] - current_price)
        atm = calls.nsmallest(2, "distance")

        iv = atm["impliedVolatility"].mean()
        return round(float(iv), 4) if iv > 0 else None
    except Exception as e:
        logger.debug(f"SPY IV fetch failed: {e}")
        return None


def get_iv_percentile(lookback_days: int = 252) -> float | None:
    """Calculate IV percentile (% of days in past year with lower IV).

    Returns percentile as 0-100.
    """
    try:
        import yfinance as yf

        vix = yf.Ticker("^VIX")
        hist = vix.history(period=f"{lookback_days + 30}d")
        if len(hist) < 30:
            return None

        closes = hist["Close"].values
        current = closes[-1]
        lower_count = sum(1 for v in closes[:-1] if v < current)
        percentile = (lower_count / (len(closes) - 1)) * 100
        return round(percentile, 1)
    except Exception as e:
        logger.debug(f"IV percentile failed: {e}")
        return None


# ── SPY option chain with Greeks ─────────────────────────────────────────────


def get_spy_options_with_greeks(
    target_dte: int = 30, min_delta: float = 0.10, max_delta: float = 0.25
) -> list[dict]:
    """Get SPY option chain with calculated Greeks.

    Returns list of options with strike, type, delta, IV, bid, ask, etc.
    Filters by delta range for iron condor strike selection.
    """
    try:
        import yfinance as yf

        spy = yf.Ticker("SPY")
        current_price = float(spy.history(period="1d")["Close"].iloc[-1])
        expirations = spy.options

        if not expirations:
            return []

        # Find nearest target DTE expiry
        today = datetime.now().date()
        target_date = today + timedelta(days=target_dte)
        target_expiry = min(expirations, key=lambda e: abs(
            (datetime.strptime(e, "%Y-%m-%d").date() - target_date).days
        ))
        expiry_date = datetime.strptime(target_expiry, "%Y-%m-%d").date()
        actual_dte = (expiry_date - today).days
        T = actual_dte / 365.0

        chain = spy.option_chain(target_expiry)
        results = []

        for opt_type, df in [("put", chain.puts), ("call", chain.calls)]:
            for _, row in df.iterrows():
                strike = float(row["strike"])
                iv = float(row.get("impliedVolatility", 0.18))
                bid = float(row.get("bid", 0))
                ask = float(row.get("ask", 0))

                if iv <= 0:
                    iv = 0.18  # Default

                greeks = black_scholes_greeks(
                    S=current_price, K=strike, T=T, r=0.05, sigma=iv, option_type=opt_type
                )

                abs_delta = abs(greeks["delta"])
                if min_delta <= abs_delta <= max_delta:
                    results.append({
                        "strike": strike,
                        "type": opt_type,
                        "expiry": target_expiry,
                        "dte": actual_dte,
                        "bid": bid,
                        "ask": ask,
                        "iv": iv,
                        "delta": greeks["delta"],
                        "gamma": greeks["gamma"],
                        "theta": greeks["theta"],
                        "vega": greeks["vega"],
                        "bs_price": greeks["price"],
                    })

        logger.info(f"SPY options: {len(results)} contracts at {min_delta}-{max_delta} delta, {target_expiry} ({actual_dte} DTE)")
        return results
    except Exception as e:
        logger.debug(f"SPY options chain failed: {e}")
        return []

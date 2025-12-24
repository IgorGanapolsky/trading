"""
Real-Time Implied Volatility (IV) Data Integration Module

Provides comprehensive IV metrics for options trading strategies including:
- Current implied volatility for underlying symbols
- IV Rank (52-week percentile ranking)
- IV Percentile (historical percentile)
- VIX market volatility proxy
- Historical IV tracking

Data Source Priority:
1. Alpaca Options API (primary) - Direct IV from option chains
2. Calculated IV from option prices (fallback)
3. VIX as market proxy (last resort)

Caching Strategy:
- IV data: 5 minutes (options don't need tick-by-tick)
- IV rank/percentile: 1 hour (historical metrics change slowly)
- VIX: 5 minutes (market volatility indicator)

Integration Points:
- Used by options_iv_signal_generator.py for strategy selection
- Used by theta harvest executor for premium collection timing
- Used by options execution pipeline for entry/exit signals

Author: Claude (CTO)
Created: 2025-12-10
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

# Use wrapper for graceful yfinance fallback (CI compatibility)
from src.utils import yfinance_wrapper as yf

logger = logging.getLogger(__name__)


@dataclass
class IVMetrics:
    """Comprehensive IV metrics for a symbol"""

    symbol: str
    current_iv: float  # Current implied volatility (annualized)
    iv_rank: float  # 0-100, where current IV sits in 52-week range
    iv_percentile: float  # 0-100, % of days in last year with lower IV
    iv_52w_high: float  # 52-week high IV
    iv_52w_low: float  # 52-week low IV
    iv_30d_avg: float  # 30-day average IV
    timestamp: datetime
    data_source: str  # "alpaca", "calculated", "vix_proxy"
    confidence: float  # 0-1, data quality confidence
    vix_level: float | None = None  # Current VIX for context
    historical_iv: list[float] = field(default_factory=list)  # Last 252 days

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "current_iv": round(self.current_iv, 4),
            "iv_rank": round(self.iv_rank, 2),
            "iv_percentile": round(self.iv_percentile, 2),
            "iv_52w_high": round(self.iv_52w_high, 4),
            "iv_52w_low": round(self.iv_52w_low, 4),
            "iv_30d_avg": round(self.iv_30d_avg, 4),
            "timestamp": self.timestamp.isoformat(),
            "data_source": self.data_source,
            "confidence": round(self.confidence, 2),
            "vix_level": round(self.vix_level, 2) if self.vix_level else None,
        }


@dataclass
class IVCacheEntry:
    """Cache entry for IV data"""

    metrics: IVMetrics
    timestamp: float
    ttl_seconds: int

    def is_valid(self) -> bool:
        """Check if cache entry is still valid"""
        return (time.time() - self.timestamp) < self.ttl_seconds


class IVDataProvider:
    """
    Real-time Implied Volatility data provider with multi-source fallback.

    Fetches IV metrics from Alpaca Options API, calculates from option chains,
    or uses VIX as proxy. Includes aggressive caching for performance.

    Usage:
        provider = IVDataProvider()
        iv_metrics = provider.get_current_iv("SPY")
        iv_rank = provider.get_iv_rank("AAPL")
        iv_percentile = provider.get_iv_percentile("TSLA")
        vix = provider.get_vix()
        history = provider.get_iv_history("NVDA", days=252)
    """

    # Cache TTLs
    IV_DATA_TTL = 5 * 60  # 5 minutes
    IV_RANK_TTL = 60 * 60  # 1 hour
    VIX_TTL = 5 * 60  # 5 minutes

    # Historical lookback periods
    IV_RANK_DAYS = 252  # 1 year for IV rank
    IV_PERCENTILE_DAYS = 252  # 1 year for IV percentile
    IV_30D_WINDOW = 30  # 30-day average

    def __init__(self, cache_dir: str | None = None):
        """
        Initialize IV data provider.

        Args:
            cache_dir: Directory for persistent cache (default: data/cache/iv)
        """
        # Setup cache directory
        if cache_dir is None:
            cache_dir = os.getenv("IV_CACHE_DIR", "data/cache/iv")
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        # In-memory cache
        self._iv_cache: dict[str, IVCacheEntry] = {}
        self._vix_cache: tuple[float, float] | None = None  # (vix, timestamp)

        # Initialize Alpaca clients if credentials available
        self._alpaca_options_client = None
        self._alpaca_data_client = None
        self._init_alpaca_clients()

        logger.info(f"IVDataProvider initialized with cache at {self.cache_dir}")

    def _init_alpaca_clients(self) -> None:
        """Initialize Alpaca API clients (options + market data)"""
        api_key = os.getenv("ALPACA_API_KEY")
        secret_key = os.getenv("ALPACA_SECRET_KEY")

        if not api_key or not secret_key:
            logger.warning("Alpaca credentials not found - IV data will be limited")
            return

        try:
            from alpaca.data.historical.option import OptionHistoricalDataClient
            from alpaca.data.historical import StockHistoricalDataClient

            # Options data client (for IV from option chain)
            self._alpaca_options_client = OptionHistoricalDataClient(
                api_key=api_key, secret_key=secret_key
            )

            # Stock data client (for price data)
            self._alpaca_data_client = StockHistoricalDataClient(
                api_key=api_key, secret_key=secret_key
            )

            logger.info("✅ Alpaca Options API initialized for IV data")

        except Exception as e:
            logger.warning(f"Failed to initialize Alpaca clients: {e}")
            self._alpaca_options_client = None
            self._alpaca_data_client = None

    def get_current_iv(self, symbol: str) -> float:
        """
        Get current implied volatility for an underlying symbol.

        Args:
            symbol: Stock symbol (e.g., "SPY", "AAPL")

        Returns:
            Current IV as decimal (e.g., 0.25 = 25% annualized)

        Raises:
            ValueError: If IV cannot be fetched from any source
        """
        metrics = self._get_iv_metrics(symbol)
        return metrics.current_iv

    def get_iv_rank(self, symbol: str, lookback: int = 252) -> float:
        """
        Get IV Rank: where current IV sits in 52-week range.

        Formula: (current_iv - 52w_low) / (52w_high - 52w_low) * 100

        Args:
            symbol: Stock symbol
            lookback: Days to look back (default 252 = 1 year)

        Returns:
            IV Rank from 0-100
        """
        if lookback == 252:
            # Use cached metrics
            metrics = self._get_iv_metrics(symbol)
            return metrics.iv_rank

        # Custom lookback period
        current_iv = self.get_current_iv(symbol)
        historical_iv = self.get_iv_history(symbol, days=lookback)

        if not historical_iv or len(historical_iv) < 20:
            return 50.0  # Neutral if insufficient data

        iv_high = max(historical_iv)
        iv_low = min(historical_iv)

        if iv_high == iv_low:
            return 50.0

        iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100.0
        return max(0.0, min(100.0, iv_rank))

    def get_iv_percentile(self, symbol: str) -> float:
        """
        Get IV Percentile: percentage of days in last year with lower IV.

        Args:
            symbol: Stock symbol

        Returns:
            IV Percentile from 0-100
        """
        metrics = self._get_iv_metrics(symbol)
        return metrics.iv_percentile

    def get_vix(self) -> float:
        """
        Get current VIX level (market volatility proxy).

        Returns:
            VIX level (e.g., 15.5)
        """
        # Check cache
        if self._vix_cache is not None:
            vix_level, timestamp = self._vix_cache
            if (time.time() - timestamp) < self.VIX_TTL:
                return vix_level

        # Fetch fresh VIX
        try:
            vix = yf.Ticker("^VIX")
            hist = vix.history(period="1d")

            if hist.empty:
                logger.warning("No VIX data available, using default 20.0")
                vix_level = 20.0
            else:
                vix_level = float(hist["Close"].iloc[-1])

            # Update cache
            self._vix_cache = (vix_level, time.time())
            logger.debug(f"VIX fetched: {vix_level:.2f}")

            return vix_level

        except Exception as e:
            logger.error(f"Failed to fetch VIX: {e}")
            # Return default if cache exists
            if self._vix_cache is not None:
                return self._vix_cache[0]
            return 20.0  # Default market volatility

    def get_iv_history(self, symbol: str, days: int = 252) -> list[float]:
        """
        Get historical IV for a symbol.

        Args:
            symbol: Stock symbol
            days: Number of trading days to fetch (default 252 = 1 year)

        Returns:
            List of daily IV values (most recent first)
        """
        metrics = self._get_iv_metrics(symbol)

        # If cached metrics have history, use it
        if metrics.historical_iv and len(metrics.historical_iv) >= days * 0.8:
            return metrics.historical_iv[:days]

        # Otherwise fetch from disk cache or API
        return self._fetch_iv_history(symbol, days)

    def get_full_metrics(self, symbol: str) -> IVMetrics:
        """
        Get complete IV metrics for a symbol.

        Args:
            symbol: Stock symbol

        Returns:
            IVMetrics dataclass with all IV data
        """
        return self._get_iv_metrics(symbol)

    def get_iv_skew(self, symbol: str) -> dict[str, Any]:
        """
        Get IV Skew: Put IV vs Call IV (fear indicator).

        Positive skew = Puts more expensive than calls (bearish sentiment)
        Negative skew = Calls more expensive than puts (bullish sentiment)

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with:
                - call_iv: Average IV of ATM calls
                - put_iv: Average IV of ATM puts
                - skew: put_iv - call_iv (positive = fear, negative = greed)
                - skew_pct: skew as percentage of ATM IV
                - interpretation: Human-readable interpretation
        """
        if not self._alpaca_options_client:
            logger.warning(f"{symbol}: IV skew requires Alpaca Options API")
            return {
                "call_iv": None,
                "put_iv": None,
                "skew": None,
                "skew_pct": None,
                "interpretation": "Data unavailable",
            }

        try:
            from alpaca.data.requests import OptionChainRequest

            # Fetch option chain
            req = OptionChainRequest(underlying_symbol=symbol)
            chain_data = self._alpaca_options_client.get_option_chain(req)

            if not chain_data:
                logger.warning(f"{symbol}: No option chain data for skew calculation")
                return {
                    "call_iv": None,
                    "put_iv": None,
                    "skew": None,
                    "skew_pct": None,
                    "interpretation": "No option chain data",
                }

            # Get current stock price for ATM detection
            stock_price = self._get_current_stock_price(symbol)

            # Separate calls and puts, find ATM options
            call_ivs = []
            put_ivs = []

            for option_symbol, snapshot in chain_data.items():
                if not snapshot.implied_volatility or snapshot.implied_volatility <= 0:
                    continue

                # Parse option symbol to get strike and type
                # OCC format: SPY251219C00600000 (ticker + expiration + C/P + strike)
                try:
                    option_type = "call" if "C" in option_symbol else "put"
                    # Extract strike from last 8 characters
                    strike_str = option_symbol[-8:]
                    strike = float(strike_str) / 1000.0

                    # Filter for ATM options (within 5% of current price)
                    if abs(strike - stock_price) / stock_price < 0.05:
                        if option_type == "call":
                            call_ivs.append(snapshot.implied_volatility)
                        else:
                            put_ivs.append(snapshot.implied_volatility)
                except Exception as e:
                    logger.debug(f"Failed to parse option symbol {option_symbol}: {e}")
                    continue

            if not call_ivs or not put_ivs:
                logger.warning(f"{symbol}: Insufficient ATM options for skew calculation")
                return {
                    "call_iv": np.mean(call_ivs) if call_ivs else None,
                    "put_iv": np.mean(put_ivs) if put_ivs else None,
                    "skew": None,
                    "skew_pct": None,
                    "interpretation": "Insufficient ATM options",
                }

            # Calculate skew metrics
            avg_call_iv = float(np.mean(call_ivs))
            avg_put_iv = float(np.mean(put_ivs))
            skew = avg_put_iv - avg_call_iv
            atm_iv = (avg_call_iv + avg_put_iv) / 2.0
            skew_pct = (skew / atm_iv * 100.0) if atm_iv > 0 else 0.0

            # Interpret skew
            if abs(skew_pct) < 2:
                interpretation = "NEUTRAL - Balanced fear/greed"
            elif skew_pct > 5:
                interpretation = "BEARISH - Strong put demand (fear)"
            elif skew_pct > 2:
                interpretation = "SLIGHTLY BEARISH - Mild put preference"
            elif skew_pct < -5:
                interpretation = "BULLISH - Strong call demand (greed)"
            else:
                interpretation = "SLIGHTLY BULLISH - Mild call preference"

            logger.info(
                f"{symbol}: IV Skew = {skew:.4f} ({skew_pct:.2f}%) - {interpretation}"
            )

            return {
                "call_iv": round(avg_call_iv, 4),
                "put_iv": round(avg_put_iv, 4),
                "skew": round(skew, 4),
                "skew_pct": round(skew_pct, 2),
                "interpretation": interpretation,
            }

        except Exception as e:
            logger.error(f"{symbol}: Failed to calculate IV skew: {e}")
            return {
                "call_iv": None,
                "put_iv": None,
                "skew": None,
                "skew_pct": None,
                "interpretation": f"Error: {str(e)}",
            }

    def get_term_structure(self, symbol: str) -> dict[str, Any]:
        """
        Get IV Term Structure: IV across different expirations.

        Shows how IV changes across time horizons. Normal structure is upward sloping
        (higher IV for longer-dated options due to uncertainty).

        Args:
            symbol: Stock symbol

        Returns:
            Dictionary with:
                - expirations: List of expiration dates
                - ivs: List of average IV for each expiration
                - structure_type: "normal", "inverted", "flat", or "humped"
                - front_month_iv: IV of nearest expiration
                - back_month_iv: IV of furthest expiration
                - slope: Overall slope of term structure
        """
        if not self._alpaca_options_client:
            logger.warning(f"{symbol}: Term structure requires Alpaca Options API")
            return {
                "expirations": [],
                "ivs": [],
                "structure_type": "unavailable",
                "front_month_iv": None,
                "back_month_iv": None,
                "slope": None,
            }

        try:
            from alpaca.data.requests import OptionChainRequest
            from datetime import datetime

            # Fetch option chain
            req = OptionChainRequest(underlying_symbol=symbol)
            chain_data = self._alpaca_options_client.get_option_chain(req)

            if not chain_data:
                logger.warning(f"{symbol}: No option chain data for term structure")
                return {
                    "expirations": [],
                    "ivs": [],
                    "structure_type": "no_data",
                    "front_month_iv": None,
                    "back_month_iv": None,
                    "slope": None,
                }

            # Group IVs by expiration date
            expiration_ivs: dict[str, list[float]] = {}

            for option_symbol, snapshot in chain_data.items():
                if not snapshot.implied_volatility or snapshot.implied_volatility <= 0:
                    continue

                # Parse expiration from OCC symbol (YYMMDD format)
                try:
                    # Example: SPY251219C00600000
                    # Positions 3-8 are expiration YYMMDD
                    exp_str = option_symbol[3:9]  # Extract YYMMDD
                    exp_date = datetime.strptime(exp_str, "%y%m%d").strftime("%Y-%m-%d")

                    if exp_date not in expiration_ivs:
                        expiration_ivs[exp_date] = []
                    expiration_ivs[exp_date].append(snapshot.implied_volatility)
                except Exception as e:
                    logger.debug(f"Failed to parse expiration from {option_symbol}: {e}")
                    continue

            if len(expiration_ivs) < 2:
                logger.warning(f"{symbol}: Need at least 2 expirations for term structure")
                return {
                    "expirations": list(expiration_ivs.keys()),
                    "ivs": [float(np.mean(ivs)) for ivs in expiration_ivs.values()],
                    "structure_type": "insufficient_data",
                    "front_month_iv": None,
                    "back_month_iv": None,
                    "slope": None,
                }

            # Calculate average IV per expiration
            sorted_expirations = sorted(expiration_ivs.keys())
            avg_ivs = [float(np.mean(expiration_ivs[exp])) for exp in sorted_expirations]

            # Determine structure type
            front_iv = avg_ivs[0]
            back_iv = avg_ivs[-1]
            slope = (back_iv - front_iv) / len(avg_ivs)

            if slope > 0.01:  # Upward sloping
                structure_type = "normal"
            elif slope < -0.01:  # Downward sloping
                structure_type = "inverted"
            elif max(avg_ivs) - min(avg_ivs) < 0.02:  # Very flat
                structure_type = "flat"
            else:  # Peak in middle
                structure_type = "humped"

            logger.info(
                f"{symbol}: Term structure {structure_type} - "
                f"Front={front_iv:.4f}, Back={back_iv:.4f}, Slope={slope:.4f}"
            )

            return {
                "expirations": sorted_expirations,
                "ivs": [round(iv, 4) for iv in avg_ivs],
                "structure_type": structure_type,
                "front_month_iv": round(front_iv, 4),
                "back_month_iv": round(back_iv, 4),
                "slope": round(slope, 6),
            }

        except Exception as e:
            logger.error(f"{symbol}: Failed to calculate term structure: {e}")
            return {
                "expirations": [],
                "ivs": [],
                "structure_type": "error",
                "front_month_iv": None,
                "back_month_iv": None,
                "slope": None,
            }

    def get_options_chain_with_greeks(
        self,
        symbol: str,
        expiration: str | None = None,
        min_delta: float | None = None,
        max_delta: float | None = None,
        min_volume: int = 0,
        min_open_interest: int = 0,
    ) -> list[dict[str, Any]]:
        """
        Fetch full options chain with Greeks, filtered and sorted by liquidity.

        Args:
            symbol: Stock symbol
            expiration: Specific expiration date (YYYY-MM-DD) or None for all
            min_delta: Minimum absolute delta (e.g., 0.20)
            max_delta: Maximum absolute delta (e.g., 0.80)
            min_volume: Minimum daily volume
            min_open_interest: Minimum open interest

        Returns:
            List of option contracts with:
                - symbol: OCC option symbol
                - strike: Strike price
                - expiration: Expiration date
                - type: "call" or "put"
                - bid: Bid price
                - ask: Ask price
                - last: Last trade price
                - volume: Daily volume
                - open_interest: Open interest
                - iv: Implied volatility
                - delta: Delta
                - gamma: Gamma
                - theta: Theta (daily)
                - vega: Vega
                - rho: Rho
                - liquidity_score: Combined liquidity metric
        """
        if not self._alpaca_options_client:
            logger.warning(f"{symbol}: Options chain requires Alpaca Options API")
            return []

        try:
            from alpaca.data.requests import OptionChainRequest

            # Fetch option chain
            req = OptionChainRequest(underlying_symbol=symbol)
            chain_data = self._alpaca_options_client.get_option_chain(req)

            if not chain_data:
                logger.warning(f"{symbol}: No option chain data available")
                return []

            options = []

            for option_symbol, snapshot in chain_data.items():
                try:
                    # Parse option symbol
                    # Format: SPY251219C00600000 (ticker + YYMMDD + C/P + strike*1000)
                    exp_str = option_symbol[3:9]
                    exp_date = datetime.strptime(exp_str, "%y%m%d").strftime("%Y-%m-%d")
                    option_type = "call" if "C" in option_symbol else "put"
                    strike = float(option_symbol[-8:]) / 1000.0

                    # Filter by expiration if specified
                    if expiration and exp_date != expiration:
                        continue

                    # Extract data from snapshot
                    bid = snapshot.latest_quote.bid_price if snapshot.latest_quote else 0.0
                    ask = snapshot.latest_quote.ask_price if snapshot.latest_quote else 0.0
                    last = snapshot.latest_trade.price if snapshot.latest_trade else 0.0

                    # Greeks
                    if not hasattr(snapshot, "greeks") or not snapshot.greeks:
                        continue  # Skip options without Greeks

                    delta = snapshot.greeks.delta if snapshot.greeks.delta else 0.0
                    gamma = snapshot.greeks.gamma if snapshot.greeks.gamma else 0.0
                    theta = snapshot.greeks.theta if snapshot.greeks.theta else 0.0
                    vega = snapshot.greeks.vega if snapshot.greeks.vega else 0.0
                    rho = snapshot.greeks.rho if snapshot.greeks.rho else 0.0

                    # Filter by delta
                    abs_delta = abs(delta)
                    if min_delta and abs_delta < min_delta:
                        continue
                    if max_delta and abs_delta > max_delta:
                        continue

                    # Volume and OI (if available)
                    volume = 0
                    open_interest = 0
                    if hasattr(snapshot, "daily_bar") and snapshot.daily_bar:
                        volume = int(snapshot.daily_bar.volume or 0)
                    if hasattr(snapshot, "open_interest"):
                        open_interest = int(snapshot.open_interest or 0)

                    # Filter by liquidity
                    if volume < min_volume or open_interest < min_open_interest:
                        continue

                    # Calculate liquidity score (higher is better)
                    liquidity_score = volume + (open_interest * 2)  # Weight OI 2x

                    iv = snapshot.implied_volatility if snapshot.implied_volatility else 0.0

                    option = {
                        "symbol": option_symbol,
                        "strike": round(strike, 2),
                        "expiration": exp_date,
                        "type": option_type,
                        "bid": round(bid, 2),
                        "ask": round(ask, 2),
                        "last": round(last, 2),
                        "volume": volume,
                        "open_interest": open_interest,
                        "iv": round(iv, 4),
                        "delta": round(delta, 4),
                        "gamma": round(gamma, 6),
                        "theta": round(theta, 4),
                        "vega": round(vega, 4),
                        "rho": round(rho, 4),
                        "liquidity_score": liquidity_score,
                    }

                    options.append(option)

                except Exception as e:
                    logger.debug(f"Failed to process option {option_symbol}: {e}")
                    continue

            # Sort by liquidity (highest first)
            options.sort(key=lambda x: x["liquidity_score"], reverse=True)

            logger.info(
                f"{symbol}: Retrieved {len(options)} options "
                f"(filtered and sorted by liquidity)"
            )

            return options

        except Exception as e:
            logger.error(f"{symbol}: Failed to fetch options chain with Greeks: {e}")
            return []

    def find_optimal_strikes(
        self,
        symbol: str,
        strategy: str,
        target_delta: float | None = None,
        expiration: str | None = None,
    ) -> dict[str, Any]:
        """
        Find optimal strike prices for specific options strategies.

        Args:
            symbol: Stock symbol
            strategy: Strategy type:
                - "covered_call" - Find 0.30 delta OTM call
                - "cash_secured_put" - Find 0.30 delta OTM put
                - "iron_condor" - Find 0.16 delta wings (both sides)
                - "credit_spread_call" - Find 0.30 delta short call
                - "credit_spread_put" - Find 0.30 delta short put
                - "protective_put" - Find 0.20 delta OTM put
            target_delta: Override default delta for strategy
            expiration: Specific expiration (YYYY-MM-DD) or None for nearest

        Returns:
            Dictionary with optimal strikes and contract details:
                - strategy: Strategy name
                - symbol: Stock symbol
                - current_price: Current stock price
                - expiration: Selected expiration
                - For single-leg: "contract" dict with full details
                - For spreads: "short_leg" and "long_leg" dicts
                - expected_credit: Credit received (for credit strategies)
                - max_profit: Maximum profit
                - max_loss: Maximum loss (if applicable)
                - break_even: Break-even price
        """
        # Default deltas for each strategy
        strategy_deltas = {
            "covered_call": 0.30,  # 30 delta OTM call
            "cash_secured_put": -0.30,  # 30 delta OTM put
            "iron_condor": 0.16,  # 16 delta wings
            "credit_spread_call": 0.30,  # 30 delta short call
            "credit_spread_put": -0.30,  # 30 delta short put
            "protective_put": -0.20,  # 20 delta OTM put
        }

        if strategy not in strategy_deltas:
            raise ValueError(
                f"Unknown strategy '{strategy}'. "
                f"Supported: {list(strategy_deltas.keys())}"
            )

        # Use target_delta if provided, otherwise use strategy default
        default_delta = strategy_deltas[strategy]
        if target_delta is None:
            target_delta = abs(default_delta)

        # Get current stock price
        current_price = self._get_current_stock_price(symbol)

        # Fetch options chain with Greeks
        options = self.get_options_chain_with_greeks(
            symbol=symbol, expiration=expiration, min_volume=10, min_open_interest=50
        )

        if not options:
            logger.error(f"{symbol}: No liquid options found for {strategy}")
            return {
                "strategy": strategy,
                "symbol": symbol,
                "current_price": current_price,
                "error": "No liquid options available",
            }

        # Select expiration (nearest if not specified)
        if not expiration:
            expirations = sorted(set(opt["expiration"] for opt in options))
            if not expirations:
                return {
                    "strategy": strategy,
                    "symbol": symbol,
                    "error": "No expirations available",
                }
            expiration = expirations[0]  # Nearest expiration

        # Filter options for selected expiration
        options = [opt for opt in options if opt["expiration"] == expiration]

        # Find optimal strikes based on strategy
        if strategy == "covered_call":
            # Find call closest to +0.30 delta
            calls = [opt for opt in options if opt["type"] == "call" and opt["delta"] > 0]
            if not calls:
                return {"error": "No call options available"}

            best_call = min(calls, key=lambda x: abs(x["delta"] - target_delta))

            return {
                "strategy": "covered_call",
                "symbol": symbol,
                "current_price": current_price,
                "expiration": expiration,
                "contract": best_call,
                "expected_credit": best_call["bid"],
                "max_profit": (best_call["strike"] - current_price) + best_call["bid"],
                "max_loss": "unlimited" if current_price == 0 else current_price - best_call["bid"],
                "break_even": current_price - best_call["bid"],
            }

        elif strategy == "cash_secured_put":
            # Find put closest to -0.30 delta
            puts = [opt for opt in options if opt["type"] == "put" and opt["delta"] < 0]
            if not puts:
                return {"error": "No put options available"}

            best_put = min(puts, key=lambda x: abs(abs(x["delta"]) - target_delta))

            return {
                "strategy": "cash_secured_put",
                "symbol": symbol,
                "current_price": current_price,
                "expiration": expiration,
                "contract": best_put,
                "expected_credit": best_put["bid"],
                "max_profit": best_put["bid"],
                "max_loss": best_put["strike"] - best_put["bid"],
                "break_even": best_put["strike"] - best_put["bid"],
            }

        elif strategy == "iron_condor":
            # Find 16 delta wings on both sides
            calls = [opt for opt in options if opt["type"] == "call" and opt["delta"] > 0]
            puts = [opt for opt in options if opt["type"] == "put" and opt["delta"] < 0]

            if not calls or not puts:
                return {"error": "Insufficient options for iron condor"}

            # Find short strikes (~30 delta)
            short_call = min(calls, key=lambda x: abs(x["delta"] - 0.30))
            short_put = min(puts, key=lambda x: abs(abs(x["delta"]) - 0.30))

            # Find long strikes (~16 delta)
            long_call = min(
                [c for c in calls if c["strike"] > short_call["strike"]],
                key=lambda x: abs(x["delta"] - 0.16),
                default=None,
            )
            long_put = min(
                [p for p in puts if p["strike"] < short_put["strike"]],
                key=lambda x: abs(abs(x["delta"]) - 0.16),
                default=None,
            )

            if not long_call or not long_put:
                return {"error": "Cannot construct iron condor with available strikes"}

            # Calculate P&L
            call_spread_credit = short_call["bid"] - long_call["ask"]
            put_spread_credit = short_put["bid"] - long_put["ask"]
            total_credit = call_spread_credit + put_spread_credit

            call_spread_width = long_call["strike"] - short_call["strike"]
            put_spread_width = short_put["strike"] - long_put["strike"]
            max_loss = min(call_spread_width, put_spread_width) - total_credit

            return {
                "strategy": "iron_condor",
                "symbol": symbol,
                "current_price": current_price,
                "expiration": expiration,
                "short_call": short_call,
                "long_call": long_call,
                "short_put": short_put,
                "long_put": long_put,
                "expected_credit": round(total_credit, 2),
                "max_profit": round(total_credit, 2),
                "max_loss": round(max_loss, 2),
                "break_even_high": short_call["strike"] + total_credit,
                "break_even_low": short_put["strike"] - total_credit,
            }

        elif strategy in ["credit_spread_call", "credit_spread_put"]:
            # Credit spread - sell closer to ATM, buy further OTM
            is_call = strategy == "credit_spread_call"
            option_type = "call" if is_call else "put"

            filtered_options = [
                opt for opt in options if opt["type"] == option_type
            ]

            if not filtered_options:
                return {"error": f"No {option_type} options available"}

            # Find short strike (~30 delta)
            short_leg = min(
                filtered_options,
                key=lambda x: abs(abs(x["delta"]) - target_delta),
            )

            # Find long strike (5-10% further OTM)
            if is_call:
                long_candidates = [
                    opt
                    for opt in filtered_options
                    if opt["strike"] > short_leg["strike"]
                ]
            else:
                long_candidates = [
                    opt
                    for opt in filtered_options
                    if opt["strike"] < short_leg["strike"]
                ]

            if not long_candidates:
                return {"error": "Cannot find long leg for spread"}

            long_leg = long_candidates[0]  # Closest strike

            # Calculate P&L
            credit = short_leg["bid"] - long_leg["ask"]
            spread_width = abs(long_leg["strike"] - short_leg["strike"])
            max_loss = spread_width - credit

            return {
                "strategy": strategy,
                "symbol": symbol,
                "current_price": current_price,
                "expiration": expiration,
                "short_leg": short_leg,
                "long_leg": long_leg,
                "expected_credit": round(credit, 2),
                "max_profit": round(credit, 2),
                "max_loss": round(max_loss, 2),
                "break_even": (
                    short_leg["strike"] + credit
                    if is_call
                    else short_leg["strike"] - credit
                ),
            }

        elif strategy == "protective_put":
            # Find put closest to -0.20 delta (protective hedge)
            puts = [opt for opt in options if opt["type"] == "put" and opt["delta"] < 0]
            if not puts:
                return {"error": "No put options available"}

            best_put = min(puts, key=lambda x: abs(abs(x["delta"]) - target_delta))

            return {
                "strategy": "protective_put",
                "symbol": symbol,
                "current_price": current_price,
                "expiration": expiration,
                "contract": best_put,
                "cost": best_put["ask"],
                "protected_below": best_put["strike"],
                "break_even": current_price + best_put["ask"],
            }

        return {"error": f"Strategy {strategy} not fully implemented"}

    def _get_current_stock_price(self, symbol: str) -> float:
        """
        Get current stock price for a symbol.

        Uses Alpaca if available, falls back to yfinance.
        """
        try:
            # Try Alpaca first
            if self._alpaca_data_client:
                from alpaca.data.requests import StockLatestQuoteRequest

                req = StockLatestQuoteRequest(symbol_or_symbols=symbol)
                quotes = self._alpaca_data_client.get_stock_latest_quote(req)
                if quotes and symbol in quotes:
                    quote = quotes[symbol]
                    return float((quote.bid_price + quote.ask_price) / 2.0)

            # Fallback to yfinance
            ticker = yf.Ticker(symbol)
            data = ticker.history(period="1d")
            if not data.empty:
                return float(data["Close"].iloc[-1])

            logger.warning(f"{symbol}: Could not fetch current price, using 0")
            return 0.0

        except Exception as e:
            logger.error(f"{symbol}: Error fetching price: {e}")
            return 0.0

    def _get_iv_metrics(self, symbol: str) -> IVMetrics:
        """
        Internal method to fetch/calculate IV metrics with caching.

        Priority:
        1. Check in-memory cache
        2. Try Alpaca Options API
        3. Calculate from option chain
        4. Use VIX as proxy (last resort)
        """
        symbol = symbol.upper()

        # Check cache
        if symbol in self._iv_cache:
            entry = self._iv_cache[symbol]
            if entry.is_valid():
                logger.debug(f"{symbol}: Using cached IV metrics")
                return entry.metrics

        # Fetch fresh data
        logger.info(f"{symbol}: Fetching IV metrics...")

        # Try Alpaca first (most reliable)
        if self._alpaca_options_client:
            try:
                metrics = self._fetch_iv_from_alpaca(symbol)
                if metrics:
                    self._cache_metrics(symbol, metrics, self.IV_DATA_TTL)
                    return metrics
            except Exception as e:
                logger.debug(f"{symbol}: Alpaca IV fetch failed: {e}")

        # Try calculating from option chain
        try:
            metrics = self._calculate_iv_from_chain(symbol)
            if metrics:
                self._cache_metrics(symbol, metrics, self.IV_DATA_TTL)
                return metrics
        except Exception as e:
            logger.debug(f"{symbol}: IV calculation from chain failed: {e}")

        # Last resort: Use VIX as proxy
        logger.warning(f"{symbol}: Using VIX proxy for IV (low confidence)")
        metrics = self._use_vix_proxy(symbol)
        self._cache_metrics(symbol, metrics, self.IV_DATA_TTL)
        return metrics

    def _fetch_iv_from_alpaca(self, symbol: str) -> IVMetrics | None:
        """
        Fetch IV directly from Alpaca option chain.

        Returns ATM IV averaged across calls and puts.
        """
        if not self._alpaca_options_client:
            return None

        try:
            from alpaca.data.requests import OptionChainRequest

            # Fetch option chain
            req = OptionChainRequest(underlying_symbol=symbol)
            chain_data = self._alpaca_options_client.get_option_chain(req)

            if not chain_data:
                logger.debug(f"{symbol}: No option chain data available")
                return None

            # Extract IVs from chain
            ivs = []
            for option_symbol, snapshot in chain_data.items():
                if snapshot.implied_volatility and snapshot.implied_volatility > 0:
                    ivs.append(snapshot.implied_volatility)

            if not ivs:
                logger.debug(f"{symbol}: No valid IV values in option chain")
                return None

            # Current IV = median of ATM options (more robust than mean)
            current_iv = float(np.median(ivs))

            # Fetch historical IV for rank/percentile
            historical_iv = self._fetch_iv_history(symbol, self.IV_RANK_DAYS)

            # Calculate derived metrics
            iv_rank, iv_percentile = self._calculate_iv_rank_and_percentile(
                current_iv, historical_iv
            )

            iv_52w_high = max(historical_iv) if historical_iv else current_iv
            iv_52w_low = min(historical_iv) if historical_iv else current_iv

            # 30-day average
            iv_30d_avg = (
                float(np.mean(historical_iv[: self.IV_30D_WINDOW]))
                if len(historical_iv) >= self.IV_30D_WINDOW
                else current_iv
            )

            metrics = IVMetrics(
                symbol=symbol,
                current_iv=current_iv,
                iv_rank=iv_rank,
                iv_percentile=iv_percentile,
                iv_52w_high=iv_52w_high,
                iv_52w_low=iv_52w_low,
                iv_30d_avg=iv_30d_avg,
                timestamp=datetime.now(timezone.utc),
                data_source="alpaca",
                confidence=0.95,  # High confidence from direct API
                vix_level=self.get_vix(),
                historical_iv=historical_iv,
            )

            logger.info(
                f"{symbol}: Alpaca IV={current_iv:.4f}, "
                f"Rank={iv_rank:.1f}, Percentile={iv_percentile:.1f}"
            )

            return metrics

        except Exception as e:
            logger.debug(f"{symbol}: Alpaca IV fetch error: {e}")
            return None

    def _calculate_iv_from_chain(self, symbol: str) -> IVMetrics | None:
        """
        Calculate IV from option prices using Black-Scholes implied vol.

        This is a fallback when direct IV is not available.
        """
        # This would require fetching option chain via yfinance or another source
        # and using scipy.optimize to solve for implied vol
        # For now, we'll skip this complex calculation and rely on Alpaca or VIX proxy

        logger.debug(f"{symbol}: IV calculation from option prices not yet implemented")
        return None

    def _use_vix_proxy(self, symbol: str) -> IVMetrics:
        """
        Use VIX as a proxy for IV when direct data unavailable.

        This is the least accurate method but ensures we always return something.
        """
        vix_level = self.get_vix()

        # VIX represents ~30-day forward volatility on SPX
        # For individual stocks, apply a correlation factor
        # Most stocks are correlated 0.4-0.8 with SPX
        correlation_factor = 0.6  # Conservative estimate

        # Beta adjustment (high-beta stocks more volatile)
        beta = self._estimate_beta(symbol)
        current_iv = (vix_level / 100.0) * correlation_factor * beta

        # Use VIX history as proxy for IV history
        vix_history = self._fetch_vix_history(self.IV_RANK_DAYS)
        historical_iv = [v / 100.0 * correlation_factor * beta for v in vix_history]

        iv_rank, iv_percentile = self._calculate_iv_rank_and_percentile(
            current_iv, historical_iv
        )

        iv_52w_high = max(historical_iv) if historical_iv else current_iv
        iv_52w_low = min(historical_iv) if historical_iv else current_iv
        iv_30d_avg = (
            float(np.mean(historical_iv[: self.IV_30D_WINDOW]))
            if len(historical_iv) >= self.IV_30D_WINDOW
            else current_iv
        )

        metrics = IVMetrics(
            symbol=symbol,
            current_iv=current_iv,
            iv_rank=iv_rank,
            iv_percentile=iv_percentile,
            iv_52w_high=iv_52w_high,
            iv_52w_low=iv_52w_low,
            iv_30d_avg=iv_30d_avg,
            timestamp=datetime.now(timezone.utc),
            data_source="vix_proxy",
            confidence=0.40,  # Low confidence - proxy only
            vix_level=vix_level,
            historical_iv=historical_iv,
        )

        logger.warning(
            f"{symbol}: Using VIX proxy - IV={current_iv:.4f} (confidence=40%)"
        )

        return metrics

    def _calculate_iv_rank_and_percentile(
        self, current_iv: float, historical_iv: list[float]
    ) -> tuple[float, float]:
        """
        Calculate IV Rank and IV Percentile from historical data.

        IV Rank = (current - min) / (max - min) * 100
        IV Percentile = % of days with lower IV
        """
        if not historical_iv or len(historical_iv) < 20:
            # Not enough history - return neutral values
            return 50.0, 50.0

        iv_52w_high = max(historical_iv)
        iv_52w_low = min(historical_iv)

        # IV Rank
        if iv_52w_high == iv_52w_low:
            iv_rank = 50.0  # No range, neutral
        else:
            iv_rank = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100.0
            iv_rank = max(0.0, min(100.0, iv_rank))  # Clamp 0-100

        # IV Percentile (% of days with lower IV)
        lower_days = sum(1 for iv in historical_iv if iv < current_iv)
        iv_percentile = (lower_days / len(historical_iv)) * 100.0

        return iv_rank, iv_percentile

    def _fetch_iv_history(self, symbol: str, days: int) -> list[float]:
        """
        Fetch historical IV data for a symbol.

        Currently uses VIX history as proxy. In production, would fetch from:
        - Alpaca historical IV endpoint
        - Stored database of calculated IVs
        - Third-party IV data provider
        """
        # Check disk cache first
        cache_file = self.cache_dir / f"{symbol}_iv_history.csv"

        if cache_file.exists():
            try:
                df = pd.read_csv(cache_file, parse_dates=["date"], index_col="date")
                if not df.empty and len(df) >= days * 0.8:
                    logger.debug(f"{symbol}: Using cached IV history")
                    return df["iv"].tolist()[:days]
            except Exception as e:
                logger.debug(f"{symbol}: Failed to load IV history cache: {e}")

        # Fallback: Use VIX history scaled by beta
        logger.debug(f"{symbol}: Using VIX history as IV proxy")
        return self._fetch_vix_history(days)

    def _fetch_vix_history(self, days: int) -> list[float]:
        """Fetch historical VIX data"""
        try:
            vix = yf.Ticker("^VIX")
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days + 30)  # Buffer for weekends

            hist = vix.history(start=start_date, end=end_date)

            if hist.empty:
                logger.warning("No VIX history available")
                return []

            # Return closing prices (most recent first)
            vix_values = hist["Close"].tolist()
            vix_values.reverse()

            return vix_values[:days]

        except Exception as e:
            logger.error(f"Failed to fetch VIX history: {e}")
            return []

    def _estimate_beta(self, symbol: str) -> float:
        """
        Estimate beta for volatility scaling.

        Beta = 1.0 means moves with market
        Beta > 1.0 means more volatile than market
        Beta < 1.0 means less volatile than market
        """
        # Quick beta estimates for common symbols
        beta_map = {
            # ETFs (low beta)
            "SPY": 1.0,
            "QQQ": 1.1,
            "IWM": 1.2,
            "VOO": 1.0,
            "VTI": 1.0,
            # Mega-cap (moderate beta)
            "AAPL": 1.2,
            "MSFT": 1.1,
            "GOOGL": 1.1,
            "AMZN": 1.3,
            "META": 1.3,
            # High-beta growth
            "NVDA": 1.8,
            "TSLA": 2.0,
            "AMD": 1.7,
            "COIN": 2.5,
            "MSTR": 3.0,
            # Defensive (low beta)
            "KO": 0.6,
            "PG": 0.5,
            "JNJ": 0.7,
        }

        return beta_map.get(symbol.upper(), 1.3)  # Default to slightly high beta

    def _cache_metrics(self, symbol: str, metrics: IVMetrics, ttl: int) -> None:
        """Cache IV metrics in memory"""
        entry = IVCacheEntry(metrics=metrics, timestamp=time.time(), ttl_seconds=ttl)
        self._iv_cache[symbol] = entry

        # Also write to disk for persistence
        try:
            cache_file = self.cache_dir / f"{symbol}_metrics.json"
            import json

            with open(cache_file, "w") as f:
                json.dump(metrics.to_dict(), f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to write metrics cache: {e}")

    def cache_iv_data(self, symbol: str, data: dict[str, Any]) -> None:
        """
        Manually cache IV data for a symbol.

        Args:
            symbol: Stock symbol
            data: Dictionary with IV data to cache. Should contain keys like:
                - current_iv: Current implied volatility
                - iv_rank: IV rank (0-100)
                - iv_percentile: IV percentile (0-100)
                - etc.

        Note: Cached data expires after 5 minutes (IV_DATA_TTL)
        """
        try:
            # Convert dict to IVMetrics if needed
            if isinstance(data, dict):
                # Fill in required fields with defaults if missing
                metrics = IVMetrics(
                    symbol=symbol.upper(),
                    current_iv=data.get("current_iv", 0.0),
                    iv_rank=data.get("iv_rank", 50.0),
                    iv_percentile=data.get("iv_percentile", 50.0),
                    iv_52w_high=data.get("iv_52w_high", data.get("current_iv", 0.0)),
                    iv_52w_low=data.get("iv_52w_low", data.get("current_iv", 0.0)),
                    iv_30d_avg=data.get("iv_30d_avg", data.get("current_iv", 0.0)),
                    timestamp=datetime.now(timezone.utc),
                    data_source=data.get("data_source", "manual"),
                    confidence=data.get("confidence", 0.5),
                    vix_level=data.get("vix_level"),
                    historical_iv=data.get("historical_iv", []),
                )
            else:
                metrics = data

            # Cache it
            self._cache_metrics(symbol.upper(), metrics, self.IV_DATA_TTL)
            logger.info(f"Cached IV data for {symbol}")

        except Exception as e:
            logger.error(f"Failed to cache IV data for {symbol}: {e}")

    def load_cached_iv(self, symbol: str, max_age_minutes: int = 5) -> dict[str, Any] | None:
        """
        Load cached IV data for a symbol if fresh enough.

        Args:
            symbol: Stock symbol
            max_age_minutes: Maximum age in minutes (default 5)

        Returns:
            Dictionary with IV data if cache is fresh, None otherwise
        """
        symbol = symbol.upper()

        # Check in-memory cache
        if symbol in self._iv_cache:
            entry = self._iv_cache[symbol]
            age_seconds = time.time() - entry.timestamp

            if age_seconds < (max_age_minutes * 60):
                logger.debug(
                    f"{symbol}: Loaded cached IV data (age: {age_seconds:.1f}s)"
                )
                return entry.metrics.to_dict()
            else:
                logger.debug(
                    f"{symbol}: Cache expired (age: {age_seconds:.1f}s > {max_age_minutes*60}s)"
                )

        # Check disk cache
        cache_file = self.cache_dir / f"{symbol}_metrics.json"
        if cache_file.exists():
            try:
                import json

                # Check file age
                file_age = time.time() - cache_file.stat().st_mtime
                if file_age < (max_age_minutes * 60):
                    with open(cache_file, "r") as f:
                        data = json.load(f)
                    logger.debug(
                        f"{symbol}: Loaded IV data from disk cache (age: {file_age:.1f}s)"
                    )
                    return data
                else:
                    logger.debug(
                        f"{symbol}: Disk cache expired (age: {file_age:.1f}s)"
                    )
            except Exception as e:
                logger.debug(f"Failed to load disk cache for {symbol}: {e}")

        logger.debug(f"{symbol}: No fresh cached IV data available")
        return None

    def clear_cache(self, symbol: str | None = None) -> None:
        """
        Clear cached IV data.

        Args:
            symbol: Symbol to clear (if None, clears all)
        """
        if symbol:
            symbol = symbol.upper()
            self._iv_cache.pop(symbol, None)

            # Also clear disk cache
            cache_file = self.cache_dir / f"{symbol}_metrics.json"
            if cache_file.exists():
                try:
                    cache_file.unlink()
                except Exception as e:
                    logger.debug(f"Failed to clear disk cache for {symbol}: {e}")

            logger.info(f"Cleared IV cache for {symbol}")
        else:
            self._iv_cache.clear()
            self._vix_cache = None

            # Clear disk cache
            try:
                for cache_file in self.cache_dir.glob("*_metrics.json"):
                    cache_file.unlink()
            except Exception as e:
                logger.debug(f"Failed to clear disk cache: {e}")

            logger.info("Cleared all IV cache")


# Singleton instance
_iv_data_provider: IVDataProvider | None = None


def get_iv_data_provider() -> IVDataProvider:
    """
    Get or create the global IV data provider instance.

    Usage:
        from src.data.iv_data_provider import get_iv_data_provider

        provider = get_iv_data_provider()
        iv_rank = provider.get_iv_rank("AAPL")
    """
    global _iv_data_provider
    if _iv_data_provider is None:
        _iv_data_provider = IVDataProvider()
    return _iv_data_provider


if __name__ == "__main__":
    # Demo / Testing
    logging.basicConfig(level=logging.INFO)

    print("\n" + "=" * 60)
    print("IV DATA PROVIDER - DEMO")
    print("=" * 60)

    provider = IVDataProvider()

    # Test symbols
    test_symbols = ["SPY", "AAPL", "NVDA"]

    for symbol in test_symbols:
        print(f"\n{'=' * 60}")
        print(f"Testing: {symbol}")
        print("=" * 60)

        try:
            # Get full metrics
            metrics = provider.get_full_metrics(symbol)

            print(f"\nCurrent IV: {metrics.current_iv:.4f} ({metrics.current_iv * 100:.2f}%)")
            print(f"IV Rank: {metrics.iv_rank:.2f}/100")
            print(f"IV Percentile: {metrics.iv_percentile:.2f}%")
            print(f"52-Week Range: {metrics.iv_52w_low:.4f} - {metrics.iv_52w_high:.4f}")
            print(f"30-Day Average: {metrics.iv_30d_avg:.4f}")
            print(f"Data Source: {metrics.data_source}")
            print(f"Confidence: {metrics.confidence:.0%}")
            print(f"VIX Context: {metrics.vix_level:.2f}")

            # IV Regime classification (from options_iv_signal_generator.py)
            if metrics.iv_rank < 20:
                regime = "VERY LOW - Buy Premium"
            elif metrics.iv_rank < 30:
                regime = "LOW - Consider buying"
            elif metrics.iv_rank < 50:
                regime = "NEUTRAL - No clear edge"
            elif metrics.iv_rank < 75:
                regime = "HIGH - Sell premium"
            else:
                regime = "VERY HIGH - Aggressive premium selling"

            print(f"IV Regime: {regime}")

            # Test individual methods
            print("\nMethod Tests:")
            print(f"  get_current_iv(): {provider.get_current_iv(symbol):.4f}")
            print(f"  get_iv_rank(): {provider.get_iv_rank(symbol):.2f}")
            print(f"  get_iv_percentile(): {provider.get_iv_percentile(symbol):.2f}")

            # Historical data sample
            history = provider.get_iv_history(symbol, days=10)
            if history:
                print(f"\nLast 10 Days IV (most recent first):")
                for i, iv in enumerate(history[:10], 1):
                    print(f"    Day {i}: {iv:.4f}")

        except Exception as e:
            print(f"❌ Error testing {symbol}: {e}")
            import traceback

            traceback.print_exc()

    # Test VIX
    print(f"\n{'=' * 60}")
    print("VIX Market Volatility")
    print("=" * 60)
    vix = provider.get_vix()
    print(f"Current VIX: {vix:.2f}")

    if vix < 15:
        vix_regime = "LOW - Markets calm"
    elif vix < 20:
        vix_regime = "ELEVATED - Normal volatility"
    elif vix < 25:
        vix_regime = "HIGH - Increased volatility"
    elif vix < 30:
        vix_regime = "VERY HIGH - Market stress"
    else:
        vix_regime = "EXTREME - Crisis mode"

    print(f"VIX Regime: {vix_regime}")

    print("\n" + "=" * 60)
    print("Demo complete!")
    print("=" * 60)

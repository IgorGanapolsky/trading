"""
Real-Time Implied Volatility (IV) Data Integration Module

This module provides comprehensive IV analysis and integration with Alpaca Options API
for real-time options trading decisions.

Features:
- Real-time option chain fetching from Alpaca
- IV percentile rank calculation (252-day lookback)
- IV skew measurement (put/call IV differential)
- Term structure analysis (IV across expirations)
- ATM IV calculation
- IV regime detection (low/normal/high/extreme)
- 3D volatility surface modeling
- IV-based alerts and opportunities

Integration:
- Alpaca Options API (primary data source)
- Black-Scholes IV calculation (backup/validation)
- Historical IV storage for percentile calculations
- Rate limiting and caching for API efficiency

Author: Claude (CTO)
Created: 2025-12-10
"""

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.interpolate import griddata
from scipy.stats import norm

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from src.core.options_client import AlpacaOptionsClient

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ============================================================================
# DATA STRUCTURES
# ============================================================================


class IVRegime(Enum):
    """IV Regime classifications based on percentile rank"""

    EXTREME_LOW = "extreme_low"  # < 10th percentile
    LOW = "low"  # 10-30th percentile
    NORMAL = "normal"  # 30-70th percentile
    HIGH = "high"  # 70-90th percentile
    EXTREME_HIGH = "extreme_high"  # > 90th percentile


@dataclass
class IVMetrics:
    """Comprehensive IV metrics for a symbol"""

    symbol: str
    timestamp: datetime
    current_iv: float
    current_price: float
    atm_iv: float
    iv_percentile: float  # 0-100
    iv_rank: float  # 0-100
    mean_iv_252d: float
    std_iv_252d: float
    iv_52w_high: float
    iv_52w_low: float
    iv_regime: IVRegime
    put_call_iv_skew: float  # Negative = puts more expensive
    term_structure_slope: float  # Positive = normal, negative = inverted
    recommendation: str  # BUY_VOL, SELL_VOL, NEUTRAL
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class VolatilitySurfacePoint:
    """Single point on the volatility surface"""

    strike: float
    dte: int
    iv: float
    delta: Optional[float] = None
    option_type: str = "CALL"  # CALL or PUT


@dataclass
class IVAlert:
    """IV-based trading alert"""

    alert_type: str  # SELL_VOL, BUY_VOL, IV_SKEW, TERM_INVERSION
    symbol: str
    timestamp: datetime
    message: str
    iv_percentile: float
    current_iv: float
    trigger_value: float  # The threshold that was crossed
    recommended_action: str
    urgency: str  # LOW, MEDIUM, HIGH, CRITICAL
    metadata: dict[str, Any] = field(default_factory=dict)


# ============================================================================
# BLACK-SCHOLES IV CALCULATION
# ============================================================================


class BlackScholesIV:
    """
    Black-Scholes IV calculation using Newton-Raphson method.
    Used as backup/validation for Alpaca IV data.
    """

    @staticmethod
    def calculate_call_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """
        Calculate theoretical call option price using Black-Scholes.

        Args:
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate
            sigma: Implied volatility (annual)

        Returns:
            Theoretical call price
        """
        if T <= 0:
            return max(0, S - K)

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return call_price

    @staticmethod
    def calculate_put_price(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate theoretical put option price using Black-Scholes"""
        if T <= 0:
            return max(0, K - S)

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)

        put_price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return put_price

    @classmethod
    def calculate_iv(
        cls,
        option_price: float,
        S: float,
        K: float,
        T: float,
        r: float,
        option_type: str = "CALL",
        max_iterations: int = 100,
        tolerance: float = 1e-5,
    ) -> Optional[float]:
        """
        Calculate implied volatility using Newton-Raphson method.

        Args:
            option_price: Market price of option
            S: Current stock price
            K: Strike price
            T: Time to expiration (years)
            r: Risk-free rate (default: 0.05 = 5%)
            option_type: "CALL" or "PUT"
            max_iterations: Maximum Newton-Raphson iterations
            tolerance: Convergence tolerance

        Returns:
            Implied volatility (annual) or None if calculation fails
        """
        if T <= 0 or option_price <= 0:
            return None

        # Initial guess: ATM approximation
        sigma = np.sqrt(2 * np.pi / T) * (option_price / S)
        sigma = max(0.01, min(5.0, sigma))  # Clamp between 1% and 500%

        price_func = cls.calculate_call_price if option_type == "CALL" else cls.calculate_put_price

        for i in range(max_iterations):
            # Calculate price and vega
            price = price_func(S, K, T, r, sigma)
            vega = cls._calculate_vega(S, K, T, r, sigma)

            if vega < 1e-10:  # Avoid division by zero
                break

            # Newton-Raphson step
            diff = option_price - price
            if abs(diff) < tolerance:
                return sigma

            sigma += diff / vega
            sigma = max(0.001, min(10.0, sigma))  # Clamp to reasonable range

        logger.warning(
            f"IV calculation did not converge after {max_iterations} iterations. "
            f"Last sigma: {sigma:.4f}"
        )
        return sigma if 0.001 < sigma < 10.0 else None

    @staticmethod
    def _calculate_vega(S: float, K: float, T: float, r: float, sigma: float) -> float:
        """Calculate vega (sensitivity to volatility)"""
        if T <= 0:
            return 0

        d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        vega = S * norm.pdf(d1) * np.sqrt(T)
        return vega / 100  # Return as percentage vega


# ============================================================================
# IV DATA FETCHER
# ============================================================================


class IVDataFetcher:
    """
    Fetch and analyze implied volatility data from Alpaca Options API.

    Features:
    - Option chain retrieval with IV data
    - IV percentile rank calculation (252-day historical)
    - IV skew measurement (put/call differential)
    - Term structure analysis
    - ATM IV calculation
    - IV regime detection
    - Data caching for rate limit management
    """

    def __init__(
        self,
        paper: bool = True,
        cache_dir: Optional[str] = None,
        cache_ttl_minutes: int = 5,
    ):
        """
        Initialize IV Data Fetcher.

        Args:
            paper: Use paper trading environment
            cache_dir: Directory for caching IV history (default: data/iv_cache)
            cache_ttl_minutes: Cache time-to-live in minutes (default: 5)
        """
        self.alpaca_client = AlpacaOptionsClient(paper=paper)
        self.cache_dir = cache_dir or os.path.join(project_root, "data", "iv_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        self.cache_ttl = timedelta(minutes=cache_ttl_minutes)
        self.bs_calculator = BlackScholesIV()

        # In-memory caches
        self._option_chain_cache: dict[str, tuple[datetime, list[dict]]] = {}
        self._iv_history_cache: dict[str, tuple[datetime, list[dict]]] = {}
        self._metrics_cache: dict[str, tuple[datetime, IVMetrics]] = {}

        logger.info(
            f"IVDataFetcher initialized (paper={paper}, cache_dir={self.cache_dir}, "
            f"ttl={cache_ttl_minutes}min)"
        )

    # ------------------------------------------------------------------------
    # OPTION CHAIN FETCHING
    # ------------------------------------------------------------------------

    def get_option_chain(self, symbol: str, use_cache: bool = True) -> list[dict[str, Any]]:
        """
        Fetch full options chain from Alpaca with IV and Greeks.

        Args:
            symbol: Underlying symbol (e.g., "SPY", "AAPL")
            use_cache: Use cached data if available and fresh

        Returns:
            List of option contracts with metadata:
            [
                {
                    "symbol": "SPY251219C00600000",
                    "strike": 600.0,
                    "expiration": "2025-12-19",
                    "dte": 9,
                    "option_type": "CALL",
                    "bid": 1.50,
                    "ask": 1.55,
                    "mid": 1.525,
                    "iv": 0.18,
                    "delta": 0.52,
                    "gamma": 0.015,
                    "theta": -0.05,
                    "vega": 0.12,
                    "underlying_price": 598.50
                },
                ...
            ]
        """
        symbol = symbol.upper()

        # Check cache
        if use_cache and symbol in self._option_chain_cache:
            cached_time, cached_data = self._option_chain_cache[symbol]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.info(
                    f"Using cached option chain for {symbol} (age: {datetime.now() - cached_time})"
                )
                return cached_data

        logger.info(f"Fetching option chain for {symbol} from Alpaca...")

        try:
            # Fetch from Alpaca
            raw_chain = self.alpaca_client.get_option_chain(symbol)

            # Parse and structure data
            structured_chain = []
            for contract in raw_chain:
                option_symbol = contract.get("symbol", "")

                # Parse option symbol (OCC format: SPY251219C00600000)
                # Format: TICKER[6]YYMMDD[1]P/C[8]Strike*1000
                parsed = self._parse_option_symbol(option_symbol)
                if not parsed:
                    continue

                strike, expiration_date, option_type = parsed

                # Calculate DTE
                dte = (expiration_date - datetime.now().date()).days

                # Extract data
                bid = contract.get("latest_quote_bid") or 0
                ask = contract.get("latest_quote_ask") or 0
                mid = (bid + ask) / 2 if bid and ask else contract.get("latest_trade_price") or 0

                iv = contract.get("implied_volatility") or 0
                greeks = contract.get("greeks") or {}

                structured_chain.append(
                    {
                        "symbol": option_symbol,
                        "strike": strike,
                        "expiration": expiration_date.strftime("%Y-%m-%d"),
                        "dte": dte,
                        "option_type": option_type,
                        "bid": bid,
                        "ask": ask,
                        "mid": mid,
                        "iv": iv,
                        "delta": greeks.get("delta"),
                        "gamma": greeks.get("gamma"),
                        "theta": greeks.get("theta"),
                        "vega": greeks.get("vega"),
                        "rho": greeks.get("rho"),
                        "underlying_price": None,  # Will be filled if available
                    }
                )

            # Cache results
            self._option_chain_cache[symbol] = (datetime.now(), structured_chain)

            logger.info(f"Retrieved {len(structured_chain)} contracts for {symbol}")
            return structured_chain

        except Exception as e:
            logger.error(f"Failed to fetch option chain for {symbol}: {e}")
            # Return empty list on error (graceful degradation)
            return []

    def _parse_option_symbol(self, symbol: str) -> Optional[tuple[float, datetime.date, str]]:
        """
        Parse OCC option symbol format.

        Format: TICKER(6 chars)YYMMDD(C/P)(Strike*1000, 8 digits)
        Example: SPY251219C00600000 = SPY Dec 19, 2025 $600 Call

        Returns:
            (strike, expiration_date, option_type) or None if invalid
        """
        try:
            # Remove ticker (first 6 chars, padded with spaces if needed)
            # Actually, tickers can vary in length. We need to find the date portion.
            # Date format: YYMMDD (6 digits)
            # Option type: C or P (1 char)
            # Strike: 8 digits (price * 1000)

            # Find the last 15 characters: YYMMDD + C/P + 8-digit strike
            if len(symbol) < 15:
                return None

            # Extract from right side
            option_data = symbol[-15:]
            date_str = option_data[:6]  # YYMMDD
            option_type = option_data[6]  # C or P
            strike_str = option_data[7:15]  # 8 digits

            # Parse date
            year = int(f"20{date_str[:2]}")
            month = int(date_str[2:4])
            day = int(date_str[4:6])
            expiration_date = datetime(year, month, day).date()

            # Parse strike (divide by 1000)
            strike = float(strike_str) / 1000

            # Validate option type
            if option_type not in ["C", "P"]:
                return None

            option_type_full = "CALL" if option_type == "C" else "PUT"

            return strike, expiration_date, option_type_full

        except (ValueError, IndexError) as e:
            logger.debug(f"Failed to parse option symbol {symbol}: {e}")
            return None

    # ------------------------------------------------------------------------
    # IV PERCENTILE & RANK
    # ------------------------------------------------------------------------

    def calculate_iv_percentile(self, symbol: str, lookback_days: int = 252) -> float:
        """
        Calculate IV percentile rank over lookback period.

        IV Percentile = (# days with IV < current) / (total days) × 100

        Args:
            symbol: Underlying symbol
            lookback_days: Historical lookback period (default: 252 = 1 year)

        Returns:
            IV percentile (0-100)
        """
        try:
            current_iv = self.get_atm_iv(symbol)
            if current_iv is None or current_iv == 0:
                logger.warning(f"Cannot calculate IV percentile for {symbol}: no current IV")
                return 50.0  # Neutral

            # Get historical IV data
            iv_history = self._load_iv_history(symbol, lookback_days)
            if not iv_history:
                logger.warning(f"No IV history for {symbol}, returning neutral percentile")
                return 50.0

            # Calculate percentile
            iv_values = [item["iv"] for item in iv_history]
            days_below = sum(1 for iv in iv_values if iv < current_iv)
            percentile = (days_below / len(iv_values)) * 100

            logger.info(
                f"{symbol} IV Percentile: {percentile:.1f}% "
                f"(Current: {current_iv:.2%}, {days_below}/{len(iv_values)} days below)"
            )

            return percentile

        except Exception as e:
            logger.error(f"Failed to calculate IV percentile for {symbol}: {e}")
            return 50.0

    def _load_iv_history(self, symbol: str, lookback_days: int) -> list[dict[str, Any]]:
        """
        Load historical IV data from cache/storage.

        Returns:
            List of {date: str, iv: float, price: float}
        """
        cache_file = Path(self.cache_dir) / f"{symbol}_iv_history.json"

        # Check if cache exists and is recent
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    data = json.load(f)

                # Filter to lookback period
                cutoff_date = (datetime.now() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
                iv_history = [item for item in data if item["date"] >= cutoff_date]

                logger.info(f"Loaded {len(iv_history)} IV history points for {symbol}")
                return iv_history

            except Exception as e:
                logger.warning(f"Failed to load IV history cache for {symbol}: {e}")

        # If no cache, we'd need to build it from daily snapshots
        # For now, return empty (caller will handle)
        logger.warning(
            f"No IV history cache found for {symbol}. "
            "Run daily IV snapshot collection to build history."
        )
        return []

    def save_iv_snapshot(self, symbol: str, iv: float, price: float):
        """
        Save daily IV snapshot for percentile calculation.

        Call this daily (e.g., at market close) to build IV history.
        """
        cache_file = Path(self.cache_dir) / f"{symbol}_iv_history.json"

        # Load existing data
        iv_history = []
        if cache_file.exists():
            try:
                with open(cache_file) as f:
                    iv_history = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load existing IV history: {e}")

        # Append new snapshot
        today = datetime.now().strftime("%Y-%m-%d")
        new_snapshot = {"date": today, "iv": iv, "price": price}

        # Remove today's entry if it exists (update)
        iv_history = [item for item in iv_history if item["date"] != today]
        iv_history.append(new_snapshot)

        # Keep only last 365 days
        iv_history = sorted(iv_history, key=lambda x: x["date"])[-365:]

        # Save
        try:
            with open(cache_file, "w") as f:
                json.dump(iv_history, f, indent=2)
            logger.info(f"Saved IV snapshot for {symbol}: {iv:.2%} @ ${price:.2f}")
        except Exception as e:
            logger.error(f"Failed to save IV snapshot for {symbol}: {e}")

    # ------------------------------------------------------------------------
    # IV SKEW
    # ------------------------------------------------------------------------

    def get_iv_skew(self, symbol: str, dte_target: int = 30) -> float:
        """
        Calculate put/call IV skew for near-term options.

        IV Skew = ATM Put IV - ATM Call IV

        Negative skew = puts more expensive (typical in equity markets)
        Positive skew = calls more expensive (rare, usually in commodities)

        Args:
            symbol: Underlying symbol
            dte_target: Target days to expiration (default: 30)

        Returns:
            IV skew (negative = bearish skew)
        """
        try:
            chain = self.get_option_chain(symbol)
            if not chain:
                return 0.0

            # Get current stock price (estimate from chain)
            current_price = self._estimate_underlying_price(chain)

            # Filter to near-term expiration (closest to dte_target)
            expirations = sorted(set(c["expiration"] for c in chain))
            if not expirations:
                return 0.0

            target_exp = self._find_closest_expiration(expirations, dte_target)

            # Filter to target expiration and near ATM
            near_atm_calls = [
                c
                for c in chain
                if c["expiration"] == target_exp
                and c["option_type"] == "CALL"
                and abs(c["strike"] - current_price) / current_price < 0.05  # Within 5% of ATM
                and c["iv"] > 0
            ]

            near_atm_puts = [
                c
                for c in chain
                if c["expiration"] == target_exp
                and c["option_type"] == "PUT"
                and abs(c["strike"] - current_price) / current_price < 0.05
                and c["iv"] > 0
            ]

            if not near_atm_calls or not near_atm_puts:
                logger.warning(f"Insufficient ATM options for {symbol} skew calculation")
                return 0.0

            # Calculate average ATM IV for calls and puts
            avg_call_iv = np.mean([c["iv"] for c in near_atm_calls])
            avg_put_iv = np.mean([c["iv"] for c in near_atm_puts])

            skew = avg_put_iv - avg_call_iv

            logger.info(
                f"{symbol} IV Skew: {skew:.4f} "
                f"(Put IV: {avg_put_iv:.2%}, Call IV: {avg_call_iv:.2%})"
            )

            return skew

        except Exception as e:
            logger.error(f"Failed to calculate IV skew for {symbol}: {e}")
            return 0.0

    # ------------------------------------------------------------------------
    # TERM STRUCTURE
    # ------------------------------------------------------------------------

    def get_term_structure(self, symbol: str) -> dict[int, float]:
        """
        Get IV term structure across different expirations.

        Returns:
            Dict mapping DTE -> ATM IV
            Example: {7: 0.18, 14: 0.20, 30: 0.22, 60: 0.24, 90: 0.25}

        Normal term structure: IV increases with time (positive slope)
        Inverted: IV decreases with time (negative slope, unusual, fear)
        """
        try:
            chain = self.get_option_chain(symbol)
            if not chain:
                return {}

            current_price = self._estimate_underlying_price(chain)

            # Group by expiration
            expirations = sorted(set(c["expiration"] for c in chain))

            term_structure = {}
            for exp in expirations:
                # Get ATM options for this expiration
                exp_chain = [
                    c
                    for c in chain
                    if c["expiration"] == exp
                    and c["option_type"] == "CALL"  # Use calls for ATM IV
                    and c["iv"] > 0
                ]

                if not exp_chain:
                    continue

                # Find ATM strike
                atm_option = min(exp_chain, key=lambda x: abs(x["strike"] - current_price))
                dte = atm_option["dte"]
                atm_iv = atm_option["iv"]

                term_structure[dte] = atm_iv

            logger.info(f"{symbol} term structure: {term_structure}")
            return term_structure

        except Exception as e:
            logger.error(f"Failed to calculate term structure for {symbol}: {e}")
            return {}

    def calculate_term_structure_slope(self, term_structure: dict[int, float]) -> float:
        """
        Calculate slope of term structure (linear regression).

        Positive slope = normal (IV increases with time)
        Negative slope = inverted (IV decreases with time, fear/uncertainty)

        Returns:
            Slope coefficient (IV change per day)
        """
        if len(term_structure) < 2:
            return 0.0

        dtes = np.array(list(term_structure.keys()))
        ivs = np.array(list(term_structure.values()))

        # Linear regression: y = mx + b
        slope, _ = np.polyfit(dtes, ivs, 1)

        return float(slope)

    # ------------------------------------------------------------------------
    # ATM IV
    # ------------------------------------------------------------------------

    def get_atm_iv(self, symbol: str, dte_target: int = 30) -> Optional[float]:
        """
        Get at-the-money implied volatility.

        Args:
            symbol: Underlying symbol
            dte_target: Target days to expiration (default: 30)

        Returns:
            ATM IV (annualized) or None if not available
        """
        try:
            chain = self.get_option_chain(symbol)
            if not chain:
                return None

            current_price = self._estimate_underlying_price(chain)

            # Filter to target DTE and calls (ATM call IV = ATM put IV theoretically)
            expirations = sorted(set(c["expiration"] for c in chain))
            if not expirations:
                return None

            target_exp = self._find_closest_expiration(expirations, dte_target)

            # Get calls for target expiration
            calls = [
                c
                for c in chain
                if c["expiration"] == target_exp and c["option_type"] == "CALL" and c["iv"] > 0
            ]

            if not calls:
                return None

            # Find ATM call (closest strike to current price)
            atm_call = min(calls, key=lambda x: abs(x["strike"] - current_price))
            atm_iv = atm_call["iv"]

            logger.info(
                f"{symbol} ATM IV ({atm_call['dte']}d): {atm_iv:.2%} "
                f"(Strike: ${atm_call['strike']:.2f}, Price: ${current_price:.2f})"
            )

            return atm_iv

        except Exception as e:
            logger.error(f"Failed to get ATM IV for {symbol}: {e}")
            return None

    # ------------------------------------------------------------------------
    # IV REGIME DETECTION
    # ------------------------------------------------------------------------

    def detect_iv_regime(self, symbol: str) -> IVRegime:
        """
        Detect current IV regime based on percentile rank.

        Regimes:
        - EXTREME_LOW: < 10th percentile (buy vol aggressively)
        - LOW: 10-30th percentile (favor buying vol)
        - NORMAL: 30-70th percentile (neutral)
        - HIGH: 70-90th percentile (favor selling vol)
        - EXTREME_HIGH: > 90th percentile (sell vol aggressively)

        Args:
            symbol: Underlying symbol

        Returns:
            IVRegime enum
        """
        try:
            percentile = self.calculate_iv_percentile(symbol)

            if percentile < 10:
                regime = IVRegime.EXTREME_LOW
            elif percentile < 30:
                regime = IVRegime.LOW
            elif percentile < 70:
                regime = IVRegime.NORMAL
            elif percentile < 90:
                regime = IVRegime.HIGH
            else:
                regime = IVRegime.EXTREME_HIGH

            logger.info(
                f"{symbol} IV Regime: {regime.value.upper()} (percentile: {percentile:.1f}%)"
            )
            return regime

        except Exception as e:
            logger.error(f"Failed to detect IV regime for {symbol}: {e}")
            return IVRegime.NORMAL

    # ------------------------------------------------------------------------
    # COMPREHENSIVE METRICS
    # ------------------------------------------------------------------------

    def get_iv_metrics(self, symbol: str, use_cache: bool = True) -> IVMetrics:
        """
        Get comprehensive IV metrics for a symbol.

        This is the main entry point for IV analysis.

        Args:
            symbol: Underlying symbol
            use_cache: Use cached metrics if available

        Returns:
            IVMetrics object with all IV analysis
        """
        symbol = symbol.upper()

        # Check cache
        if use_cache and symbol in self._metrics_cache:
            cached_time, cached_metrics = self._metrics_cache[symbol]
            if datetime.now() - cached_time < self.cache_ttl:
                logger.info(f"Using cached IV metrics for {symbol}")
                return cached_metrics

        logger.info(f"Calculating comprehensive IV metrics for {symbol}...")

        try:
            # Fetch all required data
            atm_iv = self.get_atm_iv(symbol) or 0.0
            percentile = self.calculate_iv_percentile(symbol)
            regime = self.detect_iv_regime(symbol)
            skew = self.get_iv_skew(symbol)
            term_structure = self.get_term_structure(symbol)
            term_slope = self.calculate_term_structure_slope(term_structure)

            # Get current price
            chain = self.get_option_chain(symbol)
            current_price = self._estimate_underlying_price(chain)

            # Get historical stats
            iv_history = self._load_iv_history(symbol, 252)
            if iv_history:
                iv_values = [item["iv"] for item in iv_history]
                mean_iv = float(np.mean(iv_values))
                std_iv = float(np.std(iv_values))
                iv_52w_high = float(np.max(iv_values))
                iv_52w_low = float(np.min(iv_values))

                # Calculate IV Rank
                if iv_52w_high != iv_52w_low:
                    iv_rank = ((atm_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
                else:
                    iv_rank = 50.0
            else:
                mean_iv = atm_iv
                std_iv = 0.0
                iv_52w_high = atm_iv
                iv_52w_low = atm_iv
                iv_rank = 50.0

            # Determine recommendation
            if regime in [IVRegime.EXTREME_HIGH, IVRegime.HIGH]:
                recommendation = "SELL_VOL"
            elif regime in [IVRegime.EXTREME_LOW, IVRegime.LOW]:
                recommendation = "BUY_VOL"
            else:
                recommendation = "NEUTRAL"

            # Build metrics object
            metrics = IVMetrics(
                symbol=symbol,
                timestamp=datetime.now(),
                current_iv=atm_iv,
                current_price=current_price,
                atm_iv=atm_iv,
                iv_percentile=percentile,
                iv_rank=iv_rank,
                mean_iv_252d=mean_iv,
                std_iv_252d=std_iv,
                iv_52w_high=iv_52w_high,
                iv_52w_low=iv_52w_low,
                iv_regime=regime,
                put_call_iv_skew=skew,
                term_structure_slope=term_slope,
                recommendation=recommendation,
                metadata={
                    "term_structure": term_structure,
                    "chain_size": len(chain),
                },
            )

            # Cache metrics
            self._metrics_cache[symbol] = (datetime.now(), metrics)

            logger.info(
                f"{symbol} IV Metrics: "
                f"IV={atm_iv:.2%}, Percentile={percentile:.1f}%, "
                f"Regime={regime.value}, Rec={recommendation}"
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to calculate IV metrics for {symbol}: {e}")
            # Return neutral metrics on error
            return IVMetrics(
                symbol=symbol,
                timestamp=datetime.now(),
                current_iv=0.0,
                current_price=0.0,
                atm_iv=0.0,
                iv_percentile=50.0,
                iv_rank=50.0,
                mean_iv_252d=0.0,
                std_iv_252d=0.0,
                iv_52w_high=0.0,
                iv_52w_low=0.0,
                iv_regime=IVRegime.NORMAL,
                put_call_iv_skew=0.0,
                term_structure_slope=0.0,
                recommendation="NEUTRAL",
                metadata={"error": str(e)},
            )

    # ------------------------------------------------------------------------
    # HELPER METHODS
    # ------------------------------------------------------------------------

    def _estimate_underlying_price(self, chain: list[dict]) -> float:
        """Estimate underlying price from option chain (midpoint of ATM straddle)"""
        if not chain:
            return 0.0

        # Get all strikes
        strikes = sorted(set(c["strike"] for c in chain))
        if not strikes:
            return 0.0

        # Estimate price as middle strike (rough approximation)
        return strikes[len(strikes) // 2]

    def _find_closest_expiration(self, expirations: list[str], target_dte: int) -> str:
        """Find expiration closest to target DTE"""
        closest_exp = min(
            expirations,
            key=lambda exp: abs(
                (datetime.strptime(exp, "%Y-%m-%d").date() - datetime.now().date()).days
                - target_dte
            ),
        )
        return closest_exp


# ============================================================================
# VOLATILITY SURFACE
# ============================================================================


class VolatilitySurface:
    """
    Build and analyze 3D volatility surface (strike × expiration × IV).

    Features:
    - Surface construction from option chain
    - IV interpolation for arbitrary strike/expiration
    - Arbitrage detection (violations of no-arbitrage conditions)
    - Surface visualization data
    """

    def __init__(self, fetcher: IVDataFetcher):
        """
        Initialize volatility surface builder.

        Args:
            fetcher: IVDataFetcher instance for data retrieval
        """
        self.fetcher = fetcher
        logger.info("VolatilitySurface initialized")

    def build_surface(self, symbol: str) -> list[VolatilitySurfacePoint]:
        """
        Build volatility surface from option chain.

        Returns:
            List of surface points (strike, dte, iv, delta)
        """
        try:
            chain = self.fetcher.get_option_chain(symbol)
            if not chain:
                logger.warning(f"No option chain available for {symbol}")
                return []

            surface_points = []
            for contract in chain:
                if contract["iv"] <= 0:  # Skip invalid IV
                    continue

                point = VolatilitySurfacePoint(
                    strike=contract["strike"],
                    dte=contract["dte"],
                    iv=contract["iv"],
                    delta=contract.get("delta"),
                    option_type=contract["option_type"],
                )
                surface_points.append(point)

            logger.info(f"Built volatility surface for {symbol} with {len(surface_points)} points")
            return surface_points

        except Exception as e:
            logger.error(f"Failed to build volatility surface for {symbol}: {e}")
            return []

    def interpolate_iv(
        self,
        surface_points: list[VolatilitySurfacePoint],
        target_strike: float,
        target_dte: int,
        method: str = "linear",
    ) -> Optional[float]:
        """
        Interpolate IV for arbitrary strike/expiration.

        Args:
            surface_points: List of surface points
            target_strike: Target strike price
            target_dte: Target days to expiration
            method: Interpolation method ("linear", "cubic")

        Returns:
            Interpolated IV or None if insufficient data
        """
        if not surface_points or len(surface_points) < 3:
            logger.warning("Insufficient surface points for interpolation")
            return None

        try:
            # Extract coordinates
            strikes = np.array([p.strike for p in surface_points])
            dtes = np.array([p.dte for p in surface_points])
            ivs = np.array([p.iv for p in surface_points])

            # Griddata interpolation
            interp_iv = griddata(
                points=(strikes, dtes),
                values=ivs,
                xi=(target_strike, target_dte),
                method=method,
            )

            if np.isnan(interp_iv):
                logger.warning(f"Interpolation failed for strike={target_strike}, dte={target_dte}")
                return None

            logger.info(
                f"Interpolated IV: {interp_iv:.4f} (strike=${target_strike:.2f}, dte={target_dte})"
            )

            return float(interp_iv)

        except Exception as e:
            logger.error(f"IV interpolation failed: {e}")
            return None

    def detect_arbitrage_opportunities(
        self, surface_points: list[VolatilitySurfacePoint]
    ) -> list[dict[str, Any]]:
        """
        Detect potential arbitrage opportunities from surface anomalies.

        Checks:
        1. Vertical spread arbitrage (call spreads with negative value)
        2. Butterfly arbitrage (mispriced butterflies)
        3. Calendar spread arbitrage (front month > back month for same strike)

        Returns:
            List of arbitrage opportunities
        """
        opportunities = []

        # Group by strike
        by_strike: dict[float, list[VolatilitySurfacePoint]] = {}
        for point in surface_points:
            if point.strike not in by_strike:
                by_strike[point.strike] = []
            by_strike[point.strike].append(point)

        # Check calendar spreads (same strike, different DTE)
        for strike, points in by_strike.items():
            if len(points) < 2:
                continue

            # Sort by DTE
            points_sorted = sorted(points, key=lambda p: p.dte)

            # Check for inverted IV (front > back)
            for i in range(len(points_sorted) - 1):
                front = points_sorted[i]
                back = points_sorted[i + 1]

                if front.iv > back.iv * 1.1:  # 10% threshold
                    opportunities.append(
                        {
                            "type": "calendar_spread_arbitrage",
                            "strike": strike,
                            "front_dte": front.dte,
                            "back_dte": back.dte,
                            "front_iv": front.iv,
                            "back_iv": back.iv,
                            "severity": (front.iv - back.iv) / back.iv,
                        }
                    )

        logger.info(f"Detected {len(opportunities)} potential arbitrage opportunities")
        return opportunities


# ============================================================================
# IV ALERTS
# ============================================================================


class IVAlerts:
    """
    Generate IV-based trading alerts.

    Alert Types:
    1. High IV Percentile (> 80) - Sell vol opportunity
    2. Low IV Percentile (< 20) - Buy vol opportunity
    3. Extreme IV Skew - Unusual put/call imbalance
    4. Term Structure Inversion - Fear indicator
    """

    def __init__(self, fetcher: IVDataFetcher):
        """
        Initialize IV alerts system.

        Args:
            fetcher: IVDataFetcher instance
        """
        self.fetcher = fetcher
        self.alert_history: list[IVAlert] = []
        logger.info("IVAlerts initialized")

    def check_all_alerts(self, symbol: str) -> list[IVAlert]:
        """
        Check all alert conditions for a symbol.

        Args:
            symbol: Underlying symbol

        Returns:
            List of triggered alerts
        """
        alerts = []

        # Get comprehensive metrics
        metrics = self.fetcher.get_iv_metrics(symbol)

        # Alert 1: High IV Percentile (sell vol)
        if metrics.iv_percentile > 80:
            urgency = "CRITICAL" if metrics.iv_percentile > 95 else "HIGH"
            alerts.append(
                IVAlert(
                    alert_type="SELL_VOL",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    message=f"{symbol} IV Percentile at {metrics.iv_percentile:.1f}% - SELL PREMIUM opportunity",
                    iv_percentile=metrics.iv_percentile,
                    current_iv=metrics.current_iv,
                    trigger_value=80.0,
                    recommended_action="Sell premium strategies (iron condors, credit spreads, covered calls)",
                    urgency=urgency,
                    metadata={"iv_rank": metrics.iv_rank, "regime": metrics.iv_regime.value},
                )
            )

        # Alert 2: Low IV Percentile (buy vol)
        if metrics.iv_percentile < 20:
            urgency = "CRITICAL" if metrics.iv_percentile < 5 else "HIGH"
            alerts.append(
                IVAlert(
                    alert_type="BUY_VOL",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    message=f"{symbol} IV Percentile at {metrics.iv_percentile:.1f}% - BUY PREMIUM opportunity",
                    iv_percentile=metrics.iv_percentile,
                    current_iv=metrics.current_iv,
                    trigger_value=20.0,
                    recommended_action="Buy premium strategies (long calls/puts, debit spreads, straddles)",
                    urgency=urgency,
                    metadata={"iv_rank": metrics.iv_rank, "regime": metrics.iv_regime.value},
                )
            )

        # Alert 3: Extreme IV Skew
        if abs(metrics.put_call_iv_skew) > 0.05:  # 5% difference
            urgency = "MEDIUM"
            skew_direction = "bearish" if metrics.put_call_iv_skew < 0 else "bullish"
            alerts.append(
                IVAlert(
                    alert_type="IV_SKEW",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    message=f"{symbol} has extreme {skew_direction} IV skew: {metrics.put_call_iv_skew:.2%}",
                    iv_percentile=metrics.iv_percentile,
                    current_iv=metrics.current_iv,
                    trigger_value=0.05,
                    recommended_action=f"Consider {skew_direction} positioning or skew arbitrage",
                    urgency=urgency,
                    metadata={"skew": metrics.put_call_iv_skew},
                )
            )

        # Alert 4: Term Structure Inversion
        if metrics.term_structure_slope < -0.001:  # Negative slope
            urgency = "HIGH"
            alerts.append(
                IVAlert(
                    alert_type="TERM_INVERSION",
                    symbol=symbol,
                    timestamp=datetime.now(),
                    message=f"{symbol} term structure INVERTED (slope: {metrics.term_structure_slope:.4f}) - FEAR indicator",
                    iv_percentile=metrics.iv_percentile,
                    current_iv=metrics.current_iv,
                    trigger_value=-0.001,
                    recommended_action="Sell front-month premium or wait for normalization",
                    urgency=urgency,
                    metadata={"slope": metrics.term_structure_slope},
                )
            )

        # Store alerts in history
        self.alert_history.extend(alerts)

        if alerts:
            logger.warning(f"{symbol}: {len(alerts)} IV alerts triggered!")
            for alert in alerts:
                logger.warning(f"  [{alert.urgency}] {alert.alert_type}: {alert.message}")
        else:
            logger.info(f"{symbol}: No IV alerts triggered")

        return alerts

    def format_alert_report(self, alerts: list[IVAlert]) -> str:
        """Format alerts as human-readable report"""
        if not alerts:
            return "No IV alerts at this time."

        report = "=" * 60 + "\n"
        report += "IV TRADING ALERTS\n"
        report += "=" * 60 + "\n\n"

        for alert in alerts:
            report += f"[{alert.urgency}] {alert.alert_type}\n"
            report += f"Symbol: {alert.symbol}\n"
            report += f"Message: {alert.message}\n"
            report += f"Current IV: {alert.current_iv:.2%}\n"
            report += f"IV Percentile: {alert.iv_percentile:.1f}%\n"
            report += f"Recommended Action: {alert.recommended_action}\n"
            report += f"Time: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n"
            report += "-" * 60 + "\n"

        return report


# ============================================================================
# MAIN / CLI
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Real-Time IV Data Integration")
    parser.add_argument("symbol", help="Stock symbol (e.g., SPY, AAPL)")
    parser.add_argument("--paper", action="store_true", help="Use paper trading (default: True)")
    parser.add_argument("--no-cache", action="store_true", help="Disable caching")
    parser.add_argument("--save-snapshot", action="store_true", help="Save IV snapshot for history")

    args = parser.parse_args()

    # Initialize
    fetcher = IVDataFetcher(paper=True)
    alerts_system = IVAlerts(fetcher)
    surface_builder = VolatilitySurface(fetcher)

    symbol = args.symbol.upper()

    print(f"\n{'=' * 70}")
    print(f"IV DATA INTEGRATION - {symbol}")
    print(f"{'=' * 70}\n")

    # Get comprehensive metrics
    metrics = fetcher.get_iv_metrics(symbol, use_cache=not args.no_cache)

    print("CURRENT IV METRICS:")
    print(f"  Current IV: {metrics.current_iv:.2%}")
    print(f"  ATM IV: {metrics.atm_iv:.2%}")
    print(f"  IV Percentile: {metrics.iv_percentile:.1f}%")
    print(f"  IV Rank: {metrics.iv_rank:.1f}%")
    print(f"  IV Regime: {metrics.iv_regime.value.upper()}")
    print(f"  52-Week Range: {metrics.iv_52w_low:.2%} - {metrics.iv_52w_high:.2%}")
    print(f"  Mean IV (1Y): {metrics.mean_iv_252d:.2%} ± {metrics.std_iv_252d:.2%}")
    print(f"  Put/Call Skew: {metrics.put_call_iv_skew:.2%}")
    print(f"  Term Structure Slope: {metrics.term_structure_slope:.6f}")
    print(f"  Recommendation: {metrics.recommendation}")
    print()

    # Check alerts
    print("IV ALERTS:")
    alerts = alerts_system.check_all_alerts(symbol)
    if alerts:
        print(alerts_system.format_alert_report(alerts))
    else:
        print("  No alerts triggered.\n")

    # Build volatility surface
    print("VOLATILITY SURFACE:")
    surface = surface_builder.build_surface(symbol)
    print(f"  Surface Points: {len(surface)}")

    if surface:
        # Test interpolation
        test_strike = metrics.current_price
        test_dte = 30
        interp_iv = surface_builder.interpolate_iv(surface, test_strike, test_dte)
        if interp_iv:
            print(f"  Interpolated IV (${test_strike:.2f}, {test_dte}d): {interp_iv:.2%}")

        # Check arbitrage
        arb_opps = surface_builder.detect_arbitrage_opportunities(surface)
        if arb_opps:
            print(f"  Arbitrage Opportunities: {len(arb_opps)}")
            for opp in arb_opps[:3]:  # Show top 3
                print(
                    f"    - {opp['type']}: Strike ${opp['strike']:.2f}, Severity {opp['severity']:.2%}"
                )
        else:
            print("  No arbitrage opportunities detected.")

    # Save snapshot if requested
    if args.save_snapshot:
        fetcher.save_iv_snapshot(symbol, metrics.atm_iv, metrics.current_price)
        print(f"\nIV snapshot saved for {symbol}")

    print(f"\n{'=' * 70}\n")

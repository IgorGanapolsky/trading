"""
Implied Volatility Analyzer for Options Trading

Implements McMillan's volatility-first approach to options trading:
1. IV Rank: Where current IV stands relative to 52-week range
2. IV Percentile: What % of days in past year had lower IV
3. Expected Move: Calculate 1σ and 2σ price movements
4. 2-Std Dev Detection: Identify exceptionally cheap volatility

Strategy Rules:
- IV Rank > 50: SELL PREMIUM (covered calls, iron condors, strangles)
- IV Rank < 50: BUY PREMIUM (long calls/puts, debit spreads)
- IV < (mean - 2σ): AUTO-SELL 20-delta weeklies (volatility is abnormally cheap)

Author: AI Trading System
Date: December 2, 2025
"""

import logging
import os
import sys
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional, List, Tuple
import numpy as np
import json
from pathlib import Path
from dataclasses import dataclass, asdict

# Add project root to path
project_root = Path(__file__).parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Import yfinance for options data
try:
    import yfinance as yf
except ImportError:
    logger.error("yfinance not installed. Run: pip install yfinance")
    yf = None


@dataclass
class IVHistoryPoint:
    """Single IV data point in history"""
    date: str
    iv: float
    underlying_price: float


@dataclass
class IVMetrics:
    """Comprehensive IV metrics for a symbol"""
    symbol: str
    current_iv: float
    current_price: float
    iv_rank: float
    iv_percentile: float
    mean_iv: float
    std_iv: float
    iv_52w_high: float
    iv_52w_low: float
    is_2std_cheap: bool
    recommendation: str
    suggested_strategies: List[str]
    reasoning: str
    timestamp: str


@dataclass
class ExpectedMove:
    """Expected price move based on IV."""

    symbol: str
    current_price: float
    implied_volatility: float
    days_to_expiration: int

    # Expected move (1 std dev)
    move_dollars: float
    move_percent: float

    # Price ranges
    range_low: float  # current_price - move
    range_high: float  # current_price + move

    # 2 std dev range (95% confidence)
    range_low_2std: float
    range_high_2std: float

    timestamp: datetime = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now()


class IVAnalyzer:
    """
    Analyzes Implied Volatility to determine optimal entry/exit for options trades.
    Based on McMillan's volatility-first approach.

    Key Features:
    - IV Rank calculation (0-100)
    - IV Percentile calculation (0-100)
    - Expected move calculations (1σ and 2σ)
    - 2-standard-deviation detection for cheap volatility
    - Strategy recommendations based on IV levels
    """

    def __init__(self, cache_dir: str = None):
        """
        Initialize IV Analyzer.

        Args:
            cache_dir: Directory to cache IV history data (default: data/iv_cache/)
        """
        if yf is None:
            raise ImportError("yfinance required for IV analysis. Run: pip install yfinance")

        self.cache_dir = cache_dir or os.path.join(project_root, "data", "iv_cache")
        os.makedirs(self.cache_dir, exist_ok=True)

        # In-memory cache for current session
        self.iv_history: Dict[str, List[IVHistoryPoint]] = {}
        self.last_fetch: Dict[str, datetime] = {}

        # Cache expiration (refresh IV data every 6 hours)
        self.cache_ttl = timedelta(hours=6)

        logger.info(f"IV Analyzer initialized. Cache directory: {self.cache_dir}")

    def _get_cache_path(self, symbol: str) -> Path:
        """Get file path for cached IV data"""
        return Path(self.cache_dir) / f"{symbol}_iv_history.json"

    def _load_from_cache(self, symbol: str) -> Optional[List[IVHistoryPoint]]:
        """Load IV history from disk cache if available and fresh"""
        cache_path = self._get_cache_path(symbol)

        if not cache_path.exists():
            return None

        try:
            # Check if cache is stale
            cache_age = datetime.now() - datetime.fromtimestamp(cache_path.stat().st_mtime)
            if cache_age > self.cache_ttl:
                logger.info(f"Cache for {symbol} is stale ({cache_age}). Refreshing...")
                return None

            with open(cache_path, 'r') as f:
                data = json.load(f)

            iv_history = [IVHistoryPoint(**item) for item in data]
            logger.info(f"Loaded {len(iv_history)} IV data points for {symbol} from cache")
            return iv_history

        except Exception as e:
            logger.warning(f"Failed to load cache for {symbol}: {e}")
            return None

    def _save_to_cache(self, symbol: str, iv_history: List[IVHistoryPoint]):
        """Save IV history to disk cache"""
        cache_path = self._get_cache_path(symbol)

        try:
            with open(cache_path, 'w') as f:
                json.dump([asdict(item) for item in iv_history], f, indent=2)
            logger.info(f"Saved {len(iv_history)} IV data points for {symbol} to cache")
        except Exception as e:
            logger.warning(f"Failed to save cache for {symbol}: {e}")

    def get_current_iv(self, symbol: str, dte: Optional[int] = None) -> Optional[float]:
        """
        Get current implied volatility for a symbol.

        Args:
            symbol: Stock ticker
            dte: Days to expiration (optional, uses ATM options)

        Returns:
            Current IV as decimal (e.g., 0.30 = 30% annualized)
        """
        try:
            ticker = yf.Ticker(symbol)

            # Get nearest expiration if DTE not specified
            expirations = ticker.options
            if not expirations:
                logger.warning(f"No options available for {symbol}")
                return None

            # Find expiration closest to target DTE
            if dte:
                target_date = datetime.now() + timedelta(days=dte)
                closest_exp = min(
                    expirations,
                    key=lambda x: abs((datetime.strptime(x, "%Y-%m-%d") - target_date).days)
                )
            else:
                closest_exp = expirations[0]  # Nearest expiration

            # Get option chain
            chain = ticker.option_chain(closest_exp)
            calls = chain.calls

            if calls.empty:
                return None

            # Get ATM implied volatility (closest to current price)
            current_price = ticker.info.get('currentPrice', 0)
            calls['strike_diff'] = abs(calls['strike'] - current_price)
            atm_call = calls.loc[calls['strike_diff'].idxmin()]

            iv = atm_call.get('impliedVolatility')
            return float(iv) if iv else None

        except Exception as e:
            logger.error(f"Failed to get current IV for {symbol}: {e}")
            return None

    def get_iv_history(self, symbol: str, days: int = 252) -> List[IVHistoryPoint]:
        """
        Get historical IV data for percentile and rank calculations.

        Method:
        1. Check memory cache first
        2. Check disk cache (if < 6 hours old)
        3. If no cache, fetch from yfinance (historical ATM IV)
        4. Cache results for future use

        Args:
            symbol: Stock ticker symbol
            days: Number of historical days (default: 252 = 1 trading year)

        Returns:
            List of IVHistoryPoint objects with date, IV, and price
        """
        # Check memory cache
        if symbol in self.iv_history and symbol in self.last_fetch:
            age = datetime.now() - self.last_fetch[symbol]
            if age < self.cache_ttl:
                logger.info(f"Using memory cache for {symbol} (age: {age})")
                return self.iv_history[symbol]

        # Check disk cache
        cached_data = self._load_from_cache(symbol)
        if cached_data:
            self.iv_history[symbol] = cached_data
            self.last_fetch[symbol] = datetime.now()
            return cached_data

        # Fetch fresh data from yfinance
        logger.info(f"Fetching IV history for {symbol} ({days} days)...")

        try:
            ticker = yf.Ticker(symbol)

            # Get historical price data
            start_date = date.today() - timedelta(days=days + 30)  # Extra buffer
            hist = ticker.history(start=start_date)

            if hist.empty:
                logger.warning(f"No historical data for {symbol}")
                return []

            # Sample IV at weekly intervals to reduce API calls
            iv_data = []
            sampled_dates = hist.index[::5]  # Every 5 trading days (~weekly)

            for dt in sampled_dates:
                try:
                    price = hist.loc[dt, 'Close']

                    # Calculate Historical Volatility (HV) as IV proxy
                    # HV = std(log returns) * sqrt(252)
                    window_start = dt - timedelta(days=30)
                    window_data = hist.loc[window_start:dt, 'Close']

                    if len(window_data) < 2:
                        continue

                    log_returns = np.log(window_data / window_data.shift(1)).dropna()
                    hv = log_returns.std() * np.sqrt(252)

                    iv_data.append(IVHistoryPoint(
                        date=dt.strftime("%Y-%m-%d"),
                        iv=float(hv),
                        underlying_price=float(price)
                    ))

                except Exception as e:
                    logger.debug(f"Failed to calculate IV for {symbol} on {dt}: {e}")
                    continue

            if not iv_data:
                logger.warning(f"No IV data calculated for {symbol}")
                return []

            # Adjust HV to match current IV scale
            current_iv = self.get_current_iv(symbol)
            if current_iv and current_iv > 0 and len(iv_data) > 0:
                current_hv = iv_data[-1].iv
                scale_factor = current_iv / current_hv if current_hv > 0 else 1.0

                # Scale all historical HV values
                for item in iv_data:
                    item.iv *= scale_factor

            logger.info(f"Fetched {len(iv_data)} IV data points for {symbol}")

            # Cache results
            self.iv_history[symbol] = iv_data
            self.last_fetch[symbol] = datetime.now()
            self._save_to_cache(symbol, iv_data)

            return iv_data

        except Exception as e:
            logger.error(f"Failed to get IV history for {symbol}: {e}")
            return []

    def calculate_iv_rank(self, symbol: str) -> float:
        """
        Calculate IV Rank (0-100).

        Formula:
            IV Rank = (Current IV - 52wk Low) / (52wk High - 52wk Low) × 100

        Interpretation:
            100 = IV at 52-week high (expensive volatility - SELL premium)
            0 = IV at 52-week low (cheap volatility - BUY premium)
            50 = IV in middle of range (neutral)

        Args:
            symbol: Stock ticker symbol

        Returns:
            IV Rank (0-100)
        """
        try:
            current_iv = self.get_current_iv(symbol)
            if not current_iv or current_iv == 0:
                return 50.0  # Neutral if no data

            iv_history = self.get_iv_history(symbol, days=252)
            if not iv_history:
                return 50.0  # Neutral if no history

            iv_values = [item.iv for item in iv_history]
            iv_52w_high = max(iv_values)
            iv_52w_low = min(iv_values)

            if iv_52w_high == iv_52w_low:
                return 50.0  # Neutral if no range

            iv_rank = ((current_iv - iv_52w_low) / (iv_52w_high - iv_52w_low)) * 100
            iv_rank = max(0, min(100, iv_rank))  # Clamp to 0-100

            logger.info(
                f"{symbol} IV Rank: {iv_rank:.1f} "
                f"(Current: {current_iv:.2%}, Range: {iv_52w_low:.2%}-{iv_52w_high:.2%})"
            )

            return iv_rank

        except Exception as e:
            logger.error(f"Failed to calculate IV rank for {symbol}: {e}")
            return 50.0

    def calculate_iv_percentile(self, symbol: str) -> float:
        """
        Calculate IV Percentile (0-100).

        Formula:
            IV Percentile = (# days with IV < current) / (total days) × 100

        Interpretation:
            100 = Current IV higher than 100% of past year (very expensive)
            0 = Current IV lower than 100% of past year (very cheap)
            80 = Current IV higher than 80% of past year (expensive - SELL premium)

        Args:
            symbol: Stock ticker symbol

        Returns:
            IV Percentile (0-100)
        """
        try:
            current_iv = self.get_current_iv(symbol)
            if not current_iv or current_iv == 0:
                return 50.0  # Neutral if no data

            iv_history = self.get_iv_history(symbol, days=252)
            if not iv_history:
                return 50.0  # Neutral if no history

            iv_values = [item.iv for item in iv_history]
            days_below = sum(1 for iv in iv_values if iv < current_iv)
            total_days = len(iv_values)

            iv_percentile = (days_below / total_days) * 100

            logger.info(
                f"{symbol} IV Percentile: {iv_percentile:.1f} "
                f"(Current IV: {current_iv:.2%} higher than {days_below}/{total_days} days)"
            )

            return iv_percentile

        except Exception as e:
            logger.error(f"Failed to calculate IV percentile for {symbol}: {e}")
            return 50.0

    def is_2_std_dev_cheap(self, symbol: str) -> bool:
        """
        Check if IV is 2 standard deviations below mean.

        This is the "auto-sell 20-delta weeklies" trigger from McMillan.
        When volatility is this cheap, it's statistically rare and likely to revert.

        Strategy: Sell premium aggressively when IV < (mean - 2σ)

        Args:
            symbol: Stock ticker symbol

        Returns:
            True if IV is exceptionally cheap (< mean - 2σ)
        """
        try:
            current_iv = self.get_current_iv(symbol)
            if not current_iv or current_iv == 0:
                return False

            iv_history = self.get_iv_history(symbol, days=252)
            if not iv_history:
                return False

            iv_values = [item.iv for item in iv_history]
            mean_iv = np.mean(iv_values)
            std_iv = np.std(iv_values)

            threshold = mean_iv - (2 * std_iv)
            is_cheap = current_iv < threshold

            if is_cheap:
                logger.warning(
                    f"🚨 {symbol} IV is 2σ BELOW MEAN! "
                    f"Current: {current_iv:.2%}, Threshold: {threshold:.2%} "
                    f"(Mean: {mean_iv:.2%}, Std: {std_iv:.2%}) - SELL PREMIUM NOW!"
                )
            else:
                logger.info(
                    f"{symbol} IV: {current_iv:.2%} vs Threshold: {threshold:.2%} "
                    f"(Mean: {mean_iv:.2%}, Std: {std_iv:.2%})"
                )

            return is_cheap

        except Exception as e:
            logger.error(f"Failed to check 2-std-dev for {symbol}: {e}")
            return False

    def get_recommendation(self, symbol: str) -> IVMetrics:
        """
        Get comprehensive IV analysis and trading recommendation.

        Decision Logic (McMillan's approach):
        1. IV Rank > 50 + IV Percentile > 50 → SELL PREMIUM
           - Strategies: Covered calls, iron condors, credit spreads, strangles

        2. IV Rank < 50 + IV Percentile < 50 → BUY PREMIUM
           - Strategies: Long calls/puts, debit spreads, calendar spreads

        3. IV < (mean - 2σ) → AGGRESSIVE SELL
           - Strategy: Sell 20-delta weekly calls/puts (auto-trigger)

        4. IV Rank 40-60 → NEUTRAL
           - Strategy: Wait for better entry or use neutral strategies

        Args:
            symbol: Stock ticker symbol

        Returns:
            IVMetrics object with full analysis and recommendations
        """
        try:
            # Gather all metrics
            current_iv = self.get_current_iv(symbol)
            if not current_iv:
                current_iv = 0.0

            iv_rank = self.calculate_iv_rank(symbol)
            iv_percentile = self.calculate_iv_percentile(symbol)
            is_2sd_cheap = self.is_2_std_dev_cheap(symbol)

            # Get IV statistics
            iv_history = self.get_iv_history(symbol, days=252)
            iv_values = [item.iv for item in iv_history] if iv_history else [current_iv]
            mean_iv = np.mean(iv_values)
            std_iv = np.std(iv_values)
            iv_52w_high = max(iv_values)
            iv_52w_low = min(iv_values)

            # Get current price
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period="1d")['Close'].iloc[-1] if not ticker.history(period="1d").empty else 0.0

            # Decision Logic
            recommendation = "NEUTRAL"
            strategies = []
            reasoning = ""

            # Priority 1: Check for 2σ cheap volatility (strongest signal)
            if is_2sd_cheap:
                recommendation = "AGGRESSIVE_SELL_PREMIUM"
                strategies = [
                    "sell_20_delta_weeklies",
                    "covered_calls",
                    "short_strangles",
                    "iron_condors"
                ]
                reasoning = (
                    f"IV is 2σ below mean ({current_iv:.2%} vs {mean_iv:.2%}±{std_iv:.2%}). "
                    "Volatility is statistically CHEAP and likely to revert higher. "
                    "SELL PREMIUM aggressively - McMillan's auto-trigger activated."
                )

            # Priority 2: High IV Rank + High IV Percentile (sell premium)
            elif iv_rank > 50 and iv_percentile > 50:
                if iv_rank > 75 and iv_percentile > 75:
                    recommendation = "STRONG_SELL_PREMIUM"
                    strategies = ["covered_calls", "iron_condors", "credit_spreads", "short_strangles"]
                    reasoning = (
                        f"IV Rank {iv_rank:.0f} and IV Percentile {iv_percentile:.0f} both > 75. "
                        "Volatility is EXPENSIVE relative to recent history. "
                        "Strong opportunity to SELL premium (collect high premiums)."
                    )
                else:
                    recommendation = "SELL_PREMIUM"
                    strategies = ["covered_calls", "iron_condors", "credit_spreads"]
                    reasoning = (
                        f"IV Rank {iv_rank:.0f} and IV Percentile {iv_percentile:.0f} both > 50. "
                        "Volatility is moderately expensive. "
                        "Favor selling premium strategies."
                    )

            # Priority 3: Low IV Rank + Low IV Percentile (buy premium)
            elif iv_rank < 50 and iv_percentile < 50:
                if iv_rank < 25 and iv_percentile < 25:
                    recommendation = "STRONG_BUY_PREMIUM"
                    strategies = ["long_calls", "long_puts", "debit_spreads", "calendar_spreads"]
                    reasoning = (
                        f"IV Rank {iv_rank:.0f} and IV Percentile {iv_percentile:.0f} both < 25. "
                        "Volatility is CHEAP relative to recent history. "
                        "Strong opportunity to BUY premium (cheap options)."
                    )
                else:
                    recommendation = "BUY_PREMIUM"
                    strategies = ["long_calls", "debit_spreads", "calendar_spreads"]
                    reasoning = (
                        f"IV Rank {iv_rank:.0f} and IV Percentile {iv_percentile:.0f} both < 50. "
                        "Volatility is moderately cheap. "
                        "Favor buying premium strategies."
                    )

            # Priority 4: Neutral zone (40-60 range)
            else:
                recommendation = "NEUTRAL"
                strategies = ["wait", "delta_neutral_spreads", "calendar_spreads"]
                reasoning = (
                    f"IV Rank {iv_rank:.0f} and IV Percentile {iv_percentile:.0f} in neutral zone. "
                    "Volatility is neither expensive nor cheap. "
                    "Wait for clearer signal or use delta-neutral strategies."
                )

            # Build metrics object
            metrics = IVMetrics(
                symbol=symbol,
                current_iv=round(current_iv, 4),
                current_price=round(float(current_price), 2),
                iv_rank=round(iv_rank, 1),
                iv_percentile=round(iv_percentile, 1),
                mean_iv=round(mean_iv, 4),
                std_iv=round(std_iv, 4),
                iv_52w_high=round(iv_52w_high, 4),
                iv_52w_low=round(iv_52w_low, 4),
                is_2std_cheap=is_2sd_cheap,
                recommendation=recommendation,
                suggested_strategies=strategies,
                reasoning=reasoning,
                timestamp=datetime.now().isoformat()
            )

            logger.info(
                f"📊 {symbol} IV Analysis Complete:\n"
                f"   Current IV: {current_iv:.2%}\n"
                f"   IV Rank: {iv_rank:.1f}/100\n"
                f"   IV Percentile: {iv_percentile:.1f}/100\n"
                f"   Recommendation: {recommendation}\n"
                f"   Strategies: {', '.join(strategies)}\n"
                f"   Reasoning: {reasoning}"
            )

            return metrics

        except Exception as e:
            logger.error(f"Failed to get recommendation for {symbol}: {e}")
            # Return neutral recommendation on error
            return IVMetrics(
                symbol=symbol,
                current_iv=0.0,
                current_price=0.0,
                iv_rank=50.0,
                iv_percentile=50.0,
                mean_iv=0.0,
                std_iv=0.0,
                iv_52w_high=0.0,
                iv_52w_low=0.0,
                is_2std_cheap=False,
                recommendation="ERROR",
                suggested_strategies=["wait"],
                reasoning=f"Failed to analyze IV: {str(e)}",
                timestamp=datetime.now().isoformat()
            )

    def calculate_expected_move(
        self, symbol: str, dte: int, std_devs: int = 1
    ) -> Dict[str, Any]:
        """
        Calculate Expected Move based on IV.

        Formula:
            Expected Move = Price × IV × √(DTE/365)

        This represents the 1-standard-deviation expected price range.
        - 68% probability price stays within ±1σ
        - 95% probability price stays within ±2σ

        Args:
            symbol: Stock ticker symbol
            dte: Days to expiration
            std_devs: Number of standard deviations (default: 1)

        Returns:
            Dict with expected move details:
            {
                "price": 450.00,
                "iv": 0.20,
                "dte": 30,
                "expected_move_1sd": 18.45,
                "expected_move_1sd_pct": 4.1,
                "range_1sd_low": 431.55,
                "range_1sd_high": 468.45,
                "probability_1sd": 68,
                "expected_move_2sd": 36.90,
                "range_2sd_low": 413.10,
                "range_2sd_high": 486.90,
                "probability_2sd": 95,
            }
        """
        try:
            ticker = yf.Ticker(symbol)
            current_price = ticker.history(period="1d")['Close'].iloc[-1]
            current_iv = self.get_current_iv(symbol)

            if not current_iv or current_iv == 0:
                logger.warning(f"Cannot calculate expected move for {symbol}: IV = 0")
                return {}

            # Calculate expected move (1σ)
            time_factor = np.sqrt(dte / 365)
            expected_move_1sd = current_price * current_iv * time_factor
            expected_move_pct_1sd = (expected_move_1sd / current_price) * 100

            # 1σ range (68% probability)
            range_1sd_low = current_price - expected_move_1sd
            range_1sd_high = current_price + expected_move_1sd

            # 2σ range (95% probability)
            expected_move_2sd = expected_move_1sd * 2
            range_2sd_low = current_price - expected_move_2sd
            range_2sd_high = current_price + expected_move_2sd

            result = {
                "symbol": symbol,
                "price": round(float(current_price), 2),
                "iv": round(current_iv, 4),
                "dte": dte,
                "expected_move_1sd": round(expected_move_1sd, 2),
                "expected_move_1sd_pct": round(expected_move_pct_1sd, 2),
                "range_1sd_low": round(range_1sd_low, 2),
                "range_1sd_high": round(range_1sd_high, 2),
                "probability_1sd": 68,
                "expected_move_2sd": round(expected_move_2sd, 2),
                "range_2sd_low": round(range_2sd_low, 2),
                "range_2sd_high": round(range_2sd_high, 2),
                "probability_2sd": 95,
            }

            logger.info(
                f"{symbol} Expected Move ({dte}d): "
                f"${expected_move_1sd:.2f} ({expected_move_pct_1sd:.1f}%) "
                f"Range: ${range_1sd_low:.2f}-${range_1sd_high:.2f} (68% prob)"
            )

            return result

        except Exception as e:
            logger.error(f"Failed to calculate expected move for {symbol}: {e}")
            return {}


# CLI Interface for testing
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Analyze Implied Volatility for options trading")
    parser.add_argument("symbol", help="Stock ticker symbol (e.g., SPY, AAPL)")
    parser.add_argument(
        "--dte", type=int, default=30, help="Days to expiration for expected move (default: 30)"
    )
    parser.add_argument(
        "--history-days", type=int, default=252, help="Days of IV history (default: 252)"
    )

    args = parser.parse_args()

    # Initialize analyzer
    analyzer = IVAnalyzer()

    print(f"\n{'='*60}")
    print(f"IV ANALYSIS FOR {args.symbol}")
    print(f"{'='*60}\n")

    # Get comprehensive recommendation
    metrics = analyzer.get_recommendation(args.symbol)

    print(f"📊 CURRENT METRICS:")
    print(f"   Price: ${metrics.current_price:.2f}")
    print(f"   Current IV: {metrics.current_iv:.2%}")
    print(f"   IV Range (52w): {metrics.iv_52w_low:.2%} - {metrics.iv_52w_high:.2%}")
    print(f"   Mean IV (1y): {metrics.mean_iv:.2%} ± {metrics.std_iv:.2%}")
    print()

    print(f"📈 IV INDICATORS:")
    print(f"   IV Rank: {metrics.iv_rank:.1f}/100")
    print(f"   IV Percentile: {metrics.iv_percentile:.1f}/100")
    print(f"   2σ Below Mean: {'YES 🚨' if metrics.is_2std_cheap else 'No'}")
    print()

    print(f"💡 RECOMMENDATION: {metrics.recommendation}")
    print(f"   Strategies: {', '.join(metrics.suggested_strategies)}")
    print(f"   Reasoning: {metrics.reasoning}")
    print()

    # Calculate expected move
    print(f"📐 EXPECTED MOVE ({args.dte} days):")
    expected = analyzer.calculate_expected_move(args.symbol, args.dte)
    if expected:
        print(f"   1σ Move: ±${expected['expected_move_1sd']:.2f} ({expected['expected_move_1sd_pct']:.1f}%)")
        print(f"   1σ Range: ${expected['range_1sd_low']:.2f} - ${expected['range_1sd_high']:.2f} (68% prob)")
        print(f"   2σ Range: ${expected['range_2sd_low']:.2f} - ${expected['range_2sd_high']:.2f} (95% prob)")

    print(f"\n{'='*60}\n")

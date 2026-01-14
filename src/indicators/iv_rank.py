"""
IV Rank and IV Percentile Calculator for Options Trading.

IV Rank: Where current IV sits in the 52-week range (0-100)
IV Percentile: Percentage of days IV was lower than current (0-100)

High IV (>50) = Good for selling premium (credit spreads)
Low IV (<30) = Consider buying options (debit spreads)
"""

from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import logging

# Constants for trading decisions
IV_RANK_SELL_THRESHOLD = 50  # Only sell premium above this
IV_RANK_BUY_THRESHOLD = 30   # Consider buying options below this
LOOKBACK_DAYS = 252          # Trading days in a year (~52 weeks)

logger = logging.getLogger(__name__)


class IVRankCalculator:
    """
    Calculates IV Rank and IV Percentile for options trading decisions.

    IV Rank = (Current IV - 52-week Low) / (52-week High - 52-week Low) * 100
    IV Percentile = (Days with IV < Current) / Total Days * 100
    """

    def __init__(self, use_cache: bool = True, cache_ttl_minutes: int = 15):
        """
        Initialize the IV Rank Calculator.

        Args:
            use_cache: Whether to cache IV data to reduce API calls
            cache_ttl_minutes: Cache time-to-live in minutes
        """
        self.use_cache = use_cache
        self.cache_ttl_minutes = cache_ttl_minutes
        self._cache: Dict[str, Tuple[datetime, Dict[str, Any]]] = {}
        self._yfinance_available: Optional[bool] = None

    def _check_yfinance(self) -> bool:
        """Check if yfinance is available."""
        if self._yfinance_available is None:
            try:
                import yfinance  # noqa: F401
                self._yfinance_available = True
                logger.info("yfinance is available for IV calculations")
            except ImportError:
                self._yfinance_available = False
                logger.warning("yfinance not available, using fallback data")
        return self._yfinance_available

    def _get_from_cache(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get cached IV data if still valid."""
        if not self.use_cache or symbol not in self._cache:
            return None

        cached_time, data = self._cache[symbol]
        if datetime.now() - cached_time < timedelta(minutes=self.cache_ttl_minutes):
            return data

        # Cache expired
        del self._cache[symbol]
        return None

    def _set_cache(self, symbol: str, data: Dict[str, Any]) -> None:
        """Cache IV data for a symbol."""
        if self.use_cache:
            self._cache[symbol] = (datetime.now(), data)

    def _fetch_iv_data_yfinance(self, symbol: str) -> Dict[str, Any]:
        """
        Fetch IV data using yfinance.

        Returns dict with:
            - current_iv: Current implied volatility
            - iv_history: List of historical IV values
            - iv_high: 52-week high IV
            - iv_low: 52-week low IV
        """
        import yfinance as yf

        ticker = yf.Ticker(symbol)

        # Get current IV from options chain
        current_iv = self._extract_current_iv_from_options(ticker)

        # Get historical volatility to estimate IV history
        # (True IV history requires expensive data feeds)
        hist = ticker.history(period="1y")

        if hist.empty:
            raise ValueError(f"No historical data available for {symbol}")

        # Calculate historical volatility as proxy for IV
        # Using 20-day rolling standard deviation of returns, annualized
        returns = hist['Close'].pct_change().dropna()
        rolling_vol = returns.rolling(window=20).std() * (252 ** 0.5) * 100
        iv_history = rolling_vol.dropna().tolist()

        if not iv_history:
            raise ValueError(f"Insufficient data to calculate IV history for {symbol}")

        # If we got current IV from options, use that
        # Otherwise use the latest historical vol
        if current_iv is None:
            current_iv = iv_history[-1] if iv_history else 20.0

        return {
            'current_iv': current_iv,
            'iv_history': iv_history,
            'iv_high': max(iv_history),
            'iv_low': min(iv_history),
            'source': 'yfinance'
        }

    def _extract_current_iv_from_options(self, ticker) -> Optional[float]:
        """
        Extract current implied volatility from options chain.
        Uses ATM options with nearest expiration.
        """
        try:
            # Get available expiration dates
            expirations = ticker.options
            if not expirations:
                return None

            # Use nearest expiration (30-45 DTE preferred)
            today = datetime.now().date()
            target_dte = 30

            best_exp = None
            best_diff = float('inf')

            for exp in expirations:
                exp_date = datetime.strptime(exp, '%Y-%m-%d').date()
                dte = (exp_date - today).days
                if 7 <= dte <= 60:  # Valid range
                    diff = abs(dte - target_dte)
                    if diff < best_diff:
                        best_diff = diff
                        best_exp = exp

            if not best_exp:
                best_exp = expirations[0]

            # Get options chain
            opt = ticker.option_chain(best_exp)

            # Get current stock price
            current_price = ticker.info.get('regularMarketPrice') or ticker.info.get('previousClose')
            if not current_price:
                return None

            # Find ATM options (closest to current price)
            puts = opt.puts
            if puts.empty:
                return None

            # Find strike closest to current price
            puts['strike_diff'] = abs(puts['strike'] - current_price)
            atm_put = puts.loc[puts['strike_diff'].idxmin()]

            # Get implied volatility (yfinance returns as decimal)
            iv = atm_put.get('impliedVolatility')
            if iv is not None and iv > 0:
                return float(iv) * 100  # Convert to percentage

            return None

        except Exception as e:
            logger.debug(f"Could not extract IV from options: {e}")
            return None

    def _get_fallback_iv_data(self, symbol: str) -> Dict[str, Any]:
        """
        Provide fallback IV data when yfinance is not available.

        Uses realistic default values based on typical market conditions.
        SPY typically has IV around 15-25%, individual stocks higher.
        """
        # Default IV ranges by symbol type
        fallback_data = {
            # ETFs - lower volatility
            'SPY': {'current': 18.5, 'low': 10.0, 'high': 45.0},
            'QQQ': {'current': 22.0, 'low': 12.0, 'high': 50.0},
            'IWM': {'current': 24.0, 'low': 14.0, 'high': 55.0},
            'DIA': {'current': 16.0, 'low': 9.0, 'high': 40.0},

            # Stocks from our watchlist
            'F': {'current': 35.0, 'low': 20.0, 'high': 65.0},
            'T': {'current': 22.0, 'low': 15.0, 'high': 40.0},
            'SOFI': {'current': 55.0, 'low': 35.0, 'high': 90.0},

            # Default for unknown symbols
            'DEFAULT': {'current': 30.0, 'low': 18.0, 'high': 60.0},
        }

        data = fallback_data.get(symbol.upper(), fallback_data['DEFAULT'])

        # Generate synthetic IV history
        import random
        random.seed(hash(symbol))  # Reproducible randomness per symbol

        iv_low = data['low']
        iv_high = data['high']
        iv_range = iv_high - iv_low

        # Generate 252 days of IV history
        iv_history = []
        current = data['current']

        for _ in range(LOOKBACK_DAYS):
            # Random walk with mean reversion
            change = random.gauss(0, iv_range * 0.02)
            mean_reversion = (data['current'] - current) * 0.05
            current = max(iv_low, min(iv_high, current + change + mean_reversion))
            iv_history.append(current)

        # Set current IV as the last value
        iv_history[-1] = data['current']

        logger.info(f"Using fallback IV data for {symbol}: IV={data['current']:.1f}%")

        return {
            'current_iv': data['current'],
            'iv_history': iv_history,
            'iv_high': iv_high,
            'iv_low': iv_low,
            'source': 'fallback'
        }

    def _get_iv_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get IV data for a symbol, using cache, yfinance, or fallback.
        """
        # Check cache first
        cached = self._get_from_cache(symbol)
        if cached:
            logger.debug(f"Using cached IV data for {symbol}")
            return cached

        # Try yfinance
        if self._check_yfinance():
            try:
                data = self._fetch_iv_data_yfinance(symbol)
                self._set_cache(symbol, data)
                return data
            except Exception as e:
                logger.warning(f"yfinance failed for {symbol}: {e}, using fallback")

        # Use fallback
        data = self._get_fallback_iv_data(symbol)
        self._set_cache(symbol, data)
        return data

    def get_iv_rank(self, symbol: str) -> float:
        """
        Calculate IV Rank for a symbol.

        IV Rank = (Current IV - 52-week Low) / (52-week High - 52-week Low) * 100

        Returns:
            Float 0-100 representing where current IV sits in the 52-week range

        Example:
            If 52-week IV range is 15-45 and current IV is 30:
            IV Rank = (30 - 15) / (45 - 15) * 100 = 50
        """
        data = self._get_iv_data(symbol)

        iv_high = data['iv_high']
        iv_low = data['iv_low']
        current_iv = data['current_iv']

        # Avoid division by zero
        if iv_high == iv_low:
            return 50.0

        iv_rank = ((current_iv - iv_low) / (iv_high - iv_low)) * 100

        # Clamp to 0-100 range
        iv_rank = max(0.0, min(100.0, iv_rank))

        logger.debug(
            f"{symbol} IV Rank: {iv_rank:.1f}% "
            f"(Current: {current_iv:.1f}%, Low: {iv_low:.1f}%, High: {iv_high:.1f}%)"
        )

        return round(iv_rank, 2)

    def get_iv_percentile(self, symbol: str) -> float:
        """
        Calculate IV Percentile for a symbol.

        IV Percentile = (Days with IV < Current) / Total Days * 100

        Returns:
            Float 0-100 representing percentage of days IV was lower

        Example:
            If current IV is higher than 200 out of 252 days:
            IV Percentile = (200 / 252) * 100 = 79.4
        """
        data = self._get_iv_data(symbol)

        iv_history = data['iv_history']
        current_iv = data['current_iv']

        if not iv_history:
            return 50.0

        days_lower = sum(1 for iv in iv_history if iv < current_iv)
        iv_percentile = (days_lower / len(iv_history)) * 100

        logger.debug(
            f"{symbol} IV Percentile: {iv_percentile:.1f}% "
            f"({days_lower}/{len(iv_history)} days lower)"
        )

        return round(iv_percentile, 2)

    def should_sell_premium(self, symbol: str) -> bool:
        """
        Determine if conditions favor selling premium (credit spreads).

        Premium selling is favorable when IV is elevated because:
        - Options are relatively expensive
        - Time decay works in your favor
        - Better risk/reward on credit spreads

        Returns:
            True if IV Rank > IV_RANK_SELL_THRESHOLD (50)
        """
        iv_rank = self.get_iv_rank(symbol)
        should_sell = iv_rank > IV_RANK_SELL_THRESHOLD

        logger.info(
            f"{symbol}: IV Rank = {iv_rank:.1f}%, "
            f"Sell Premium = {should_sell} (threshold: {IV_RANK_SELL_THRESHOLD})"
        )

        return should_sell

    def should_buy_options(self, symbol: str) -> bool:
        """
        Determine if conditions favor buying options (debit spreads).

        Option buying is favorable when IV is low because:
        - Options are relatively cheap
        - Less theta decay impact
        - Potential for IV expansion

        Returns:
            True if IV Rank < IV_RANK_BUY_THRESHOLD (30)
        """
        iv_rank = self.get_iv_rank(symbol)
        should_buy = iv_rank < IV_RANK_BUY_THRESHOLD

        logger.info(
            f"{symbol}: IV Rank = {iv_rank:.1f}%, "
            f"Buy Options = {should_buy} (threshold: {IV_RANK_BUY_THRESHOLD})"
        )

        return should_buy

    def get_iv_summary(self, symbol: str) -> Dict[str, Any]:
        """
        Get complete IV analysis summary for a symbol.

        Returns dict with:
            - symbol: Ticker symbol
            - current_iv: Current implied volatility
            - iv_rank: IV Rank (0-100)
            - iv_percentile: IV Percentile (0-100)
            - iv_high: 52-week high IV
            - iv_low: 52-week low IV
            - recommendation: 'SELL_PREMIUM', 'BUY_OPTIONS', or 'NEUTRAL'
            - source: Data source ('yfinance' or 'fallback')
        """
        data = self._get_iv_data(symbol)
        iv_rank = self.get_iv_rank(symbol)
        iv_percentile = self.get_iv_percentile(symbol)

        # Determine recommendation
        if iv_rank > IV_RANK_SELL_THRESHOLD:
            recommendation = 'SELL_PREMIUM'
        elif iv_rank < IV_RANK_BUY_THRESHOLD:
            recommendation = 'BUY_OPTIONS'
        else:
            recommendation = 'NEUTRAL'

        return {
            'symbol': symbol.upper(),
            'current_iv': round(data['current_iv'], 2),
            'iv_rank': iv_rank,
            'iv_percentile': iv_percentile,
            'iv_high': round(data['iv_high'], 2),
            'iv_low': round(data['iv_low'], 2),
            'recommendation': recommendation,
            'source': data['source'],
            'thresholds': {
                'sell_threshold': IV_RANK_SELL_THRESHOLD,
                'buy_threshold': IV_RANK_BUY_THRESHOLD
            }
        }

    def clear_cache(self, symbol: Optional[str] = None) -> None:
        """
        Clear cached IV data.

        Args:
            symbol: Specific symbol to clear, or None to clear all
        """
        if symbol:
            self._cache.pop(symbol, None)
            logger.debug(f"Cleared cache for {symbol}")
        else:
            self._cache.clear()
            logger.debug("Cleared all IV cache")


# Convenience function for quick access
def get_iv_rank(symbol: str) -> float:
    """Quick function to get IV Rank for a symbol."""
    calculator = IVRankCalculator(use_cache=True)
    return calculator.get_iv_rank(symbol)


def get_iv_percentile(symbol: str) -> float:
    """Quick function to get IV Percentile for a symbol."""
    calculator = IVRankCalculator(use_cache=True)
    return calculator.get_iv_percentile(symbol)


def should_sell_premium(symbol: str) -> bool:
    """Quick function to check if premium selling is favorable."""
    calculator = IVRankCalculator(use_cache=True)
    return calculator.should_sell_premium(symbol)


if __name__ == '__main__':
    # Demo usage
    logging.basicConfig(level=logging.INFO)

    calc = IVRankCalculator()

    # Test with our primary symbols
    symbols = ['SPY', 'IWM', 'F', 'SOFI']

    print("\n" + "=" * 60)
    print("IV Rank and Percentile Analysis")
    print("=" * 60)

    for symbol in symbols:
        summary = calc.get_iv_summary(symbol)
        print(f"\n{symbol}:")
        print(f"  Current IV: {summary['current_iv']:.1f}%")
        print(f"  52-Week Range: {summary['iv_low']:.1f}% - {summary['iv_high']:.1f}%")
        print(f"  IV Rank: {summary['iv_rank']:.1f}")
        print(f"  IV Percentile: {summary['iv_percentile']:.1f}")
        print(f"  Recommendation: {summary['recommendation']}")
        print(f"  Data Source: {summary['source']}")

    print("\n" + "=" * 60)

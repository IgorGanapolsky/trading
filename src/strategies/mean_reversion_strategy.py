"""
Mean Reversion Strategy - RSI(2) Based

Based on Quantified Strategies research with 75% win rate over 30 years.

Strategy Logic (from training library):
- Buy SPY when RSI(2) < 10
- Sell when RSI(2) > 90
- Enhancement: Add trend filter (price > 200 SMA)
- Enhancement: Add VIX filter (VIX > 20 for higher probability)

Expected Performance:
- Win rate: 75% (30-year backtest)
- Avg gain: 0.8% per trade
- Holding period: 1-5 days

Reference: Quantified Strategies (2024), RSI(2) Mean Reversion
"""

import logging
from dataclasses import dataclass
from datetime import datetime

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)


@dataclass
class MeanReversionSignal:
    """Signal from mean reversion strategy."""

    symbol: str
    timestamp: datetime
    signal_type: str  # 'BUY', 'SELL', 'HOLD'
    rsi_2: float
    rsi_5: float  # Secondary confirmation
    price: float
    sma_200: float
    vix: float | None
    confidence: float  # 0-1
    reason: str

    # Position sizing hints
    suggested_size_pct: float  # % of capital
    stop_loss_pct: float  # Suggested stop loss
    take_profit_pct: float  # Suggested take profit


class MeanReversionStrategy:
    """
    RSI(2) Mean Reversion Strategy.

    Based on empirical research from Quantified Strategies showing
    consistent edge over 30+ years of data.

    Key Rules:
    1. RSI(2) < 10 = extreme oversold = BUY signal
    2. RSI(2) > 90 = extreme overbought = SELL signal
    3. Trend filter: Only buy above 200 SMA
    4. VIX filter: Higher confidence when VIX elevated
    """

    def __init__(
        self,
        rsi_buy_threshold: float = 10.0,
        rsi_sell_threshold: float = 90.0,
        rsi_period: int = 2,
        use_trend_filter: bool = True,
        use_vix_filter: bool = True,
        use_volume_filter: bool = True,
        vix_elevated_threshold: float = 20.0,
        min_volume_ratio: float = 0.8,
    ):
        """
        Initialize mean reversion strategy.

        Args:
            rsi_buy_threshold: RSI level below which to buy (default: 10)
            rsi_sell_threshold: RSI level above which to sell (default: 90)
            rsi_period: RSI lookback period (default: 2 for RSI(2))
            use_trend_filter: Only buy above 200 SMA (default: True)
            use_vix_filter: Boost confidence when VIX elevated (default: True)
            use_volume_filter: Require minimum volume ratio (default: True)
            vix_elevated_threshold: VIX level considered elevated (default: 20)
            min_volume_ratio: Minimum volume vs 20-day avg (default: 0.8)
        """
        self.rsi_buy_threshold = rsi_buy_threshold
        self.rsi_sell_threshold = rsi_sell_threshold
        self.rsi_period = rsi_period
        self.use_trend_filter = use_trend_filter
        self.use_vix_filter = use_vix_filter
        self.use_volume_filter = use_volume_filter
        self.vix_elevated_threshold = vix_elevated_threshold
        self.min_volume_ratio = min_volume_ratio

        logger.info(
            f"MeanReversionStrategy initialized: RSI({rsi_period}) "
            f"buy<{rsi_buy_threshold}, sell>{rsi_sell_threshold}, "
            f"trend_filter={use_trend_filter}, vix_filter={use_vix_filter}, "
            f"volume_filter={use_volume_filter} (min_ratio={min_volume_ratio})"
        )

    def calculate_rsi(self, prices: pd.Series, period: int) -> pd.Series:
        """
        Calculate RSI (Relative Strength Index).

        Args:
            prices: Price series
            period: Lookback period

        Returns:
            RSI series (0-100)
        """
        delta = prices.diff()
        gain = delta.where(delta > 0, 0.0)
        loss = (-delta).where(delta < 0, 0.0)

        avg_gain = gain.ewm(span=period, adjust=False).mean()
        avg_loss = loss.ewm(span=period, adjust=False).mean()

        rs = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))

        return rsi.fillna(50)  # Neutral if no data

    def get_vix(self) -> float | None:
        """Fetch current VIX level."""
        try:
            vix_data = yf.Ticker("^VIX").history(period="5d")
            if not vix_data.empty:
                return float(vix_data["Close"].iloc[-1])
        except Exception as e:
            logger.warning(f"Could not fetch VIX: {e}")
        return None

    def calculate_volume_ratio(self, hist: pd.DataFrame, window: int = 20) -> float:
        """
        Calculate volume ratio (current vs N-day average).

        Args:
            hist: DataFrame with 'Volume' column
            window: Lookback period for average (default: 20)

        Returns:
            Ratio of current volume to average (1.0 = average, >1 = above avg)
        """
        if "Volume" not in hist.columns or len(hist) < window:
            return 1.0  # Neutral if insufficient data

        volume = hist["Volume"]
        current_vol = float(volume.iloc[-1])
        avg_vol = float(volume.rolling(window).mean().iloc[-1])

        if avg_vol == 0 or np.isnan(avg_vol):
            return 1.0

        return current_vol / avg_vol

    def analyze(self, symbol: str = "SPY") -> MeanReversionSignal:
        """
        Analyze symbol for mean reversion signal.

        Args:
            symbol: Stock symbol (default: SPY)

        Returns:
            MeanReversionSignal with buy/sell/hold recommendation
        """
        logger.info(f"Analyzing {symbol} for mean reversion signal")

        # Fetch price data
        try:
            ticker = yf.Ticker(symbol)
            hist = ticker.history(period="1y")

            if hist.empty or len(hist) < 200:
                return self._no_signal(symbol, "Insufficient historical data")

        except Exception as e:
            logger.error(f"Error fetching data for {symbol}: {e}")
            return self._no_signal(symbol, f"Data fetch error: {e}")

        # Calculate indicators
        close = hist["Close"]
        current_price = float(close.iloc[-1])

        # RSI(2) - primary signal
        rsi_2 = self.calculate_rsi(close, 2)
        current_rsi_2 = float(rsi_2.iloc[-1])

        # RSI(5) - confirmation
        rsi_5 = self.calculate_rsi(close, 5)
        current_rsi_5 = float(rsi_5.iloc[-1])

        # 200-day SMA - trend filter
        sma_200 = float(close.rolling(200).mean().iloc[-1])
        above_sma_200 = current_price > sma_200

        # VIX - fear gauge
        vix = self.get_vix() if self.use_vix_filter else None
        vix_elevated = vix is not None and vix > self.vix_elevated_threshold

        # Volume - liquidity/conviction filter
        volume_ratio = self.calculate_volume_ratio(hist) if self.use_volume_filter else 1.0
        volume_sufficient = volume_ratio >= self.min_volume_ratio

        # Generate signal
        signal_type = "HOLD"
        confidence = 0.0
        reason = ""
        suggested_size = 0.0
        stop_loss = 0.02  # 2% default
        take_profit = 0.02  # 2% default

        # BUY SIGNAL: RSI(2) < 10
        if current_rsi_2 < self.rsi_buy_threshold:
            # Check trend filter
            if self.use_trend_filter and not above_sma_200:
                signal_type = "HOLD"
                reason = f"RSI(2)={current_rsi_2:.1f} oversold but below 200 SMA (trend filter)"
                confidence = 0.3
            # Check volume filter - avoid low liquidity whipsaws
            elif self.use_volume_filter and not volume_sufficient:
                signal_type = "HOLD"
                reason = (
                    f"RSI(2)={current_rsi_2:.1f} oversold but volume ratio "
                    f"{volume_ratio:.2f} < {self.min_volume_ratio} (volume filter)"
                )
                confidence = 0.4
            else:
                signal_type = "BUY"

                # Base confidence from RSI level
                # More oversold = higher confidence
                rsi_depth = (self.rsi_buy_threshold - current_rsi_2) / self.rsi_buy_threshold
                confidence = 0.6 + (rsi_depth * 0.2)  # 60-80%

                # Boost for VIX confirmation
                if vix_elevated:
                    confidence = min(0.95, confidence + 0.1)
                    reason = f"RSI(2)={current_rsi_2:.1f} EXTREME oversold + VIX={vix:.1f} elevated"
                else:
                    reason = f"RSI(2)={current_rsi_2:.1f} oversold, price above 200 SMA"

                # Boost for RSI(5) confirmation
                if current_rsi_5 < 30:
                    confidence = min(0.95, confidence + 0.05)
                    reason += f", RSI(5)={current_rsi_5:.1f} confirms"

                # Boost for strong volume (conviction)
                if volume_ratio > 1.5:
                    confidence = min(0.95, confidence + 0.05)
                    reason += f", strong volume ({volume_ratio:.1f}x avg)"
                elif volume_ratio > 1.0:
                    reason += f", vol={volume_ratio:.1f}x"

                # Position sizing based on confidence
                # Per Quantified Strategies: Full size at extreme RSI < 5
                if current_rsi_2 < 5:
                    suggested_size = 0.10  # 10% of capital
                    stop_loss = 0.03  # Wider stop for extreme moves
                else:
                    suggested_size = 0.05  # 5% of capital
                    stop_loss = 0.02

                take_profit = 0.02  # Target 2% gain

        # SELL SIGNAL: RSI(2) > 90 (for existing positions)
        elif current_rsi_2 > self.rsi_sell_threshold:
            signal_type = "SELL"
            confidence = 0.7
            reason = f"RSI(2)={current_rsi_2:.1f} overbought - take profit"
            suggested_size = 1.0  # Sell full position

        # HOLD
        else:
            signal_type = "HOLD"
            confidence = 0.5
            reason = f"RSI(2)={current_rsi_2:.1f} neutral range ({self.rsi_buy_threshold}-{self.rsi_sell_threshold})"

        return MeanReversionSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type=signal_type,
            rsi_2=current_rsi_2,
            rsi_5=current_rsi_5,
            price=current_price,
            sma_200=sma_200,
            vix=vix,
            confidence=confidence,
            reason=reason,
            suggested_size_pct=suggested_size,
            stop_loss_pct=stop_loss,
            take_profit_pct=take_profit,
        )

    def _no_signal(self, symbol: str, reason: str) -> MeanReversionSignal:
        """Return a no-signal result."""
        return MeanReversionSignal(
            symbol=symbol,
            timestamp=datetime.now(),
            signal_type="HOLD",
            rsi_2=50.0,
            rsi_5=50.0,
            price=0.0,
            sma_200=0.0,
            vix=None,
            confidence=0.0,
            reason=reason,
            suggested_size_pct=0.0,
            stop_loss_pct=0.02,
            take_profit_pct=0.02,
        )

    def scan_universe(self, symbols: list[str] = None) -> list[MeanReversionSignal]:
        """
        Scan multiple symbols for mean reversion opportunities.

        Args:
            symbols: List of symbols to scan (default: major ETFs)

        Returns:
            List of signals, sorted by confidence (highest first)
        """
        if symbols is None:
            # Default universe: Major ETFs
            symbols = ["SPY", "QQQ", "IWM", "DIA", "TLT", "GLD"]

        signals = []
        for symbol in symbols:
            try:
                signal = self.analyze(symbol)
                signals.append(signal)
            except Exception as e:
                logger.error(f"Error scanning {symbol}: {e}")

        # Sort by confidence (BUY signals first, then by confidence)
        signals.sort(key=lambda s: (0 if s.signal_type == "BUY" else 1, -s.confidence))

        return signals

    def get_active_signals(self, symbols: list[str] = None) -> list[MeanReversionSignal]:
        """
        Get only actionable (BUY/SELL) signals.

        Returns:
            List of BUY or SELL signals only
        """
        all_signals = self.scan_universe(symbols)
        return [s for s in all_signals if s.signal_type in ("BUY", "SELL")]


def get_mean_reversion_strategy() -> MeanReversionStrategy:
    """Get singleton instance of MeanReversionStrategy."""
    return MeanReversionStrategy()


# Quick test
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    strategy = MeanReversionStrategy()

    print("=" * 60)
    print("MEAN REVERSION STRATEGY - RSI(2)")
    print("Based on Quantified Strategies (75% win rate, 30 years)")
    print("=" * 60)

    # Scan default universe
    signals = strategy.scan_universe()

    print("\nUniverse Scan Results:")
    print("-" * 60)

    for signal in signals:
        status = "***" if signal.signal_type == "BUY" else "   "
        print(
            f"{status} {signal.symbol}: {signal.signal_type} | "
            f"RSI(2)={signal.rsi_2:.1f} | Conf={signal.confidence:.1%} | "
            f"{signal.reason[:50]}..."
        )

    print("-" * 60)

    # Show any active signals
    active = strategy.get_active_signals()
    if active:
        print(f"\n*** ACTIVE SIGNALS: {len(active)} ***")
        for sig in active:
            print(f"  {sig.symbol}: {sig.signal_type} @ {sig.confidence:.1%} confidence")
            print(f"    Reason: {sig.reason}")
            if sig.signal_type == "BUY":
                print(
                    f"    Size: {sig.suggested_size_pct:.1%} | Stop: {sig.stop_loss_pct:.1%} | Target: {sig.take_profit_pct:.1%}"
                )
    else:
        print("\nNo active signals - market in neutral RSI range")

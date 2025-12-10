"""
Simple Moving Average (SMA) crossover baseline strategy.

Buys when short SMA crosses above long SMA, sells when it crosses below.
"""

import pandas as pd


class SMACrossStrategy:
    """
    SMA crossover baseline strategy.

    Classic technical analysis strategy: buy when SMA(short) > SMA(long),
    sell when SMA(short) < SMA(long).
    """

    def __init__(
        self,
        short_window: int = 50,
        long_window: int = 200,
        symbols: list[str] = None,
    ):
        """
        Initialize SMA crossover strategy.

        Args:
            short_window: Short SMA window (default: 50)
            long_window: Long SMA window (default: 200)
            symbols: List of symbols. If None, uses SPY.
        """
        self.short_window = short_window
        self.long_window = long_window
        if symbols is None:
            symbols = ["SPY"]
        self.symbols = symbols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate SMA crossover signals.

        Args:
            data: DataFrame with OHLCV data (must have 'Close' column)

        Returns:
            DataFrame with signals (1 = buy, -1 = sell, 0 = hold)
        """
        signals = pd.DataFrame(index=data.index)

        for symbol in self.symbols:
            # Get symbol data
            if isinstance(data.index, pd.MultiIndex):
                symbol_data = data.xs(symbol, level=0)
            else:
                symbol_data = data[data.get("symbol") == symbol].copy()

            if symbol_data.empty or "Close" not in symbol_data.columns:
                signals[f"{symbol}_signal"] = 0
                continue

            prices = symbol_data["Close"]

            # Calculate SMAs
            sma_short = prices.rolling(window=self.short_window).mean()
            sma_long = prices.rolling(window=self.long_window).mean()

            # Generate signals
            signal = pd.Series(0, index=prices.index)
            signal[sma_short > sma_long] = 1  # Buy
            signal[sma_short < sma_long] = -1  # Sell

            signals[f"{symbol}_signal"] = signal

        return signals.fillna(0)

    def get_name(self) -> str:
        """Get strategy name."""
        return f"SMA Cross ({self.short_window}/{self.long_window})"

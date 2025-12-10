"""
Momentum baseline strategies.

Time-series momentum (absolute returns) and cross-sectional momentum (rank-based).
"""

import pandas as pd


class MomentumStrategy:
    """
    Momentum baseline strategy.

    Buys assets with positive momentum over lookback period.
    """

    def __init__(
        self,
        lookback: int = 20,
        method: str = "time_series",
        symbols: list[str] = None,
    ):
        """
        Initialize momentum strategy.

        Args:
            lookback: Lookback period for momentum calculation
            method: 'time_series' (absolute returns) or 'cross_sectional' (rank-based)
            symbols: List of symbols. If None, uses SPY, QQQ, VOO.
        """
        self.lookback = lookback
        self.method = method
        if symbols is None:
            symbols = ["SPY", "QQQ", "VOO"]
        self.symbols = symbols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate momentum signals.

        Args:
            data: DataFrame with OHLCV data (must have 'Close' column)

        Returns:
            DataFrame with signals (1 = buy positive momentum, -1 = sell negative momentum)
        """
        signals = pd.DataFrame(index=data.index)

        if self.method == "time_series":
            # Time-series momentum: buy if return over lookback > 0
            for symbol in self.symbols:
                if isinstance(data.index, pd.MultiIndex):
                    symbol_data = data.xs(symbol, level=0)
                else:
                    symbol_data = data[data.get("symbol") == symbol].copy()

                if symbol_data.empty or "Close" not in symbol_data.columns:
                    signals[f"{symbol}_signal"] = 0
                    continue

                prices = symbol_data["Close"]
                returns = prices.pct_change(self.lookback)

                signal = pd.Series(0, index=prices.index)
                signal[returns > 0] = 1  # Buy positive momentum
                signal[returns < 0] = -1  # Sell negative momentum

                signals[f"{symbol}_signal"] = signal

        elif self.method == "cross_sectional":
            # Cross-sectional momentum: rank assets by returns, buy top N
            # This requires all symbols to be in the same DataFrame
            all_returns = {}
            for symbol in self.symbols:
                if isinstance(data.index, pd.MultiIndex):
                    symbol_data = data.xs(symbol, level=0)
                else:
                    symbol_data = data[data.get("symbol") == symbol].copy()

                if not symbol_data.empty and "Close" in symbol_data.columns:
                    prices = symbol_data["Close"]
                    returns = prices.pct_change(self.lookback)
                    all_returns[symbol] = returns

            if all_returns:
                returns_df = pd.DataFrame(all_returns)
                ranks = returns_df.rank(axis=1, ascending=False)

                # Buy top 50% (rank <= n_symbols/2)
                n_symbols = len(self.symbols)
                threshold = n_symbols / 2

                for symbol in self.symbols:
                    if symbol in ranks.columns:
                        signal = pd.Series(0, index=ranks.index)
                        signal[ranks[symbol] <= threshold] = 1
                        signals[f"{symbol}_signal"] = signal
                    else:
                        signals[f"{symbol}_signal"] = 0

        return signals.fillna(0)

    def get_name(self) -> str:
        """Get strategy name."""
        return f"Momentum ({self.method}, lookback={self.lookback})"

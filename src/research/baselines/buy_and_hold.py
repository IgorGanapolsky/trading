"""
Buy-and-hold baseline strategy.

The simplest possible strategy: buy and hold.
"""

import pandas as pd


class BuyAndHoldStrategy:
    """
    Buy-and-hold baseline strategy.

    Simply buys and holds the asset(s) for the entire period.
    """

    def __init__(self, symbols: list[str] = None):
        """
        Initialize buy-and-hold strategy.

        Args:
            symbols: List of symbols to hold. If None, uses SPY.
        """
        if symbols is None:
            symbols = ["SPY"]
        self.symbols = symbols

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate buy-and-hold signals.

        Args:
            data: DataFrame with OHLCV data (multi-index: symbol, date)

        Returns:
            DataFrame with signals (1 = hold, 0 = no position)
        """
        signals = pd.DataFrame(index=data.index)
        for symbol in self.symbols:
            if (
                symbol in data.index.get_level_values(0)
                if isinstance(data.index, pd.MultiIndex)
                else data.get("symbol")
            ):
                signals[f"{symbol}_signal"] = 1
            else:
                signals[f"{symbol}_signal"] = 0

        return signals.fillna(0)

    def get_name(self) -> str:
        """Get strategy name."""
        return "Buy-and-Hold"

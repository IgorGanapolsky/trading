"""
Equal-weight portfolio baseline strategy.

Allocates equal weights to all assets in the universe.
"""

import pandas as pd


class EqualWeightStrategy:
    """
    Equal-weight portfolio baseline strategy.

    Allocates equal weights to all assets, rebalanced periodically.
    """

    def __init__(self, symbols: list[str] = None, rebalance_freq: str = "D"):
        """
        Initialize equal-weight strategy.

        Args:
            symbols: List of symbols. If None, uses SPY, QQQ, VOO.
            rebalance_freq: Rebalancing frequency ('D' = daily, 'W' = weekly, 'M' = monthly)
        """
        if symbols is None:
            symbols = ["SPY", "QQQ", "VOO"]
        self.symbols = symbols
        self.rebalance_freq = rebalance_freq

    def generate_signals(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        Generate equal-weight signals.

        Args:
            data: DataFrame with OHLCV data

        Returns:
            DataFrame with equal weights (1/n for n symbols)
        """
        n_symbols = len(self.symbols)
        weight = 1.0 / n_symbols if n_symbols > 0 else 0.0

        signals = pd.DataFrame(index=data.index)
        for symbol in self.symbols:
            signals[f"{symbol}_weight"] = weight

        return signals.fillna(0)

    def get_name(self) -> str:
        """Get strategy name."""
        return f"Equal-Weight (rebalance={self.rebalance_freq})"

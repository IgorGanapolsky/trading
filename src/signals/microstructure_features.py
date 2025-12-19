"""
Microstructure feature extraction for the fast execution loop.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd
from src.utils.market_data import MarketDataProvider


@dataclass
class MicrostructureFeatureExtractor:
    """
    Builds lightweight microstructure proxies from recent OHLCV data.
    """

    lookback_days: int = 40

    def __post_init__(self) -> None:
        self._provider = MarketDataProvider()

    def extract(self, symbol: str) -> dict[str, Any]:
        """
        Return a dictionary of normalized microstructure metrics.
        """
        try:
            result = self._provider.get_daily_bars(symbol, self.lookback_days)
            df = result.data.copy()
        except Exception as exc:  # pragma: no cover - network failures
            return {"microstructure_error": str(exc)}

        if df.empty or len(df) < 5:
            return {"microstructure_error": "insufficient_data"}

        df = df.tail(self.lookback_days)
        returns = df["Close"].pct_change().dropna()
        if returns.empty:
            returns = pd.Series([0.0])

        volatility = float(returns.std() * np.sqrt(252))
        downside = float(returns[returns < 0].std() * np.sqrt(252)) if not returns.empty else 0.0
        trend = float((df["Close"].iloc[-1] / df["Close"].iloc[0]) - 1.0)
        hl_range = df["High"] - df["Low"]
        avg_range = float(hl_range.mean())
        order_flow_imbalance = float(
            np.clip(((df["Close"] - df["Open"]) / (hl_range.replace(0, np.nan))).mean(), -1, 1)
        )
        volume_ratio = float(
            (df["Volume"].iloc[-1] / df["Volume"].rolling(10).mean().iloc[-1])
            if len(df) >= 10 and df["Volume"].rolling(10).mean().iloc[-1] > 0
            else 1.0
        )
        momentum = float(returns.tail(5).mean() * 100)

        return {
            "volatility": round(volatility, 4),
            "downside_volatility": round(downside, 4),
            "trend_strength": round(trend, 4),
            "average_range": round(avg_range, 4),
            "order_flow_imbalance": round(order_flow_imbalance, 4),
            "volume_ratio": round(volume_ratio, 4),
            "short_term_momentum": round(momentum, 4),
        }

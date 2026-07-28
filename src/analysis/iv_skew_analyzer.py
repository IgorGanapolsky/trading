"""Option Implied Volatility Surface & Skew Analyzer.

Calculates real-time IV Rank (IVR), IV Percentile (IVP), and Put-Call Skew
to optimize strike selection and credit collection for SPY/XSP put credit spreads.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class IVSkewMetrics:
    symbol: str
    current_iv: float
    iv_52wk_low: float
    iv_52wk_high: float
    iv_rank: float
    iv_percentile: float
    put_call_skew: float
    is_premium_rich: bool


class IVSkewAnalyzer:
    """Analyzes volatility rank and skew to optimize option selling timing."""

    def __init__(self, min_iv_rank_threshold: float = 25.0):
        self.min_iv_rank_threshold = min_iv_rank_threshold

    def calculate_metrics(
        self,
        symbol: str,
        current_iv: float,
        iv_52wk_low: float,
        iv_52wk_high: float,
        historical_ivs: list[float] | None = None,
        put_iv_015: float = 0.22,
        call_iv_015: float = 0.18,
    ) -> IVSkewMetrics:
        range_iv = max(0.001, iv_52wk_high - iv_52wk_low)
        iv_rank = max(0.0, min(100.0, ((current_iv - iv_52wk_low) / range_iv) * 100.0))

        if historical_ivs:
            below_count = sum(1 for iv in historical_ivs if iv < current_iv)
            iv_percentile = (below_count / max(1, len(historical_ivs))) * 100.0
        else:
            iv_percentile = iv_rank

        put_call_skew = put_iv_015 - call_iv_015
        is_premium_rich = iv_rank >= self.min_iv_rank_threshold

        return IVSkewMetrics(
            symbol=symbol.upper(),
            current_iv=round(current_iv, 4),
            iv_52wk_low=round(iv_52wk_low, 4),
            iv_52wk_high=round(iv_52wk_high, 4),
            iv_rank=round(iv_rank, 2),
            iv_percentile=round(iv_percentile, 2),
            put_call_skew=round(put_call_skew, 4),
            is_premium_rich=is_premium_rich,
        )

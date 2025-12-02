"""
Trend snapshot utilities for ETF regime monitoring.

Provides lightweight SMA/return metrics that power allocation gates,
daily reporting, and telemetry on Tier-1/Tier-2 symbols.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


@dataclass
class TrendMetrics:
    """Container for per-symbol trend data."""

    symbol: str
    price: float
    sma20: float
    sma50: float
    sma200: float
    return_5d: float
    return_21d: float
    gate_open: bool
    regime_bias: str


class TrendSnapshotBuilder:
    """
    Builds and persists SMA-based regime snapshots for downstream consumers.
    """

    def __init__(
        self,
        cache: dict[str, pd.DataFrame] | None = None,
        snapshot_path: Path = Path("data/trend_snapshot.json"),
    ) -> None:
        self._history_cache = cache or {}
        self.snapshot_path = snapshot_path
        self.snapshot_path.parent.mkdir(parents=True, exist_ok=True)

    def build(self, symbols: Iterable[str]) -> dict[str, TrendMetrics]:
        """Return latest metrics for requested symbols."""
        metrics: dict[str, TrendMetrics] = {}
        for symbol in symbols:
            hist = self._history_cache.get(symbol)
            if hist is None or hist.empty:
                hist = self._fetch_history(symbol)
                if hist is not None:
                    self._history_cache[symbol] = hist

            if hist is None or hist.empty:
                logger.debug("No history available for %s - skipping snapshot", symbol)
                continue

            try:
                metrics[symbol] = self._calculate_metrics(symbol, hist)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Trend snapshot failed for %s: %s", symbol, exc)

        return metrics

    def save(self, metrics: dict[str, TrendMetrics]) -> None:
        """Persist snapshot to disk for reporting and CI consumers."""
        payload = {
            "generated_at": datetime.utcnow().isoformat(),
            "symbols": {sym: asdict(data) for sym, data in metrics.items()},
        }
        with open(self.snapshot_path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2)
        logger.info(
            "Trend snapshot updated for %d symbols -> %s",
            len(payload["symbols"]),
            self.snapshot_path,
        )

    def load(self) -> dict[str, TrendMetrics] | None:
        """Load previously saved snapshot if it exists."""
        if not self.snapshot_path.exists():
            return None
        try:
            with open(self.snapshot_path, encoding="utf-8") as fp:
                data = json.load(fp)
            symbols = data.get("symbols", {})
            return {
                sym: TrendMetrics(**vals)  # type: ignore[arg-type]
                for sym, vals in symbols.items()
            }
        except Exception as exc:  # pragma: no cover - best effort
            logger.warning("Failed to load cached trend snapshot: %s", exc)
            return None

    def _fetch_history(self, symbol: str) -> pd.DataFrame | None:
        """Fetch 6 months of daily data via yfinance (fail-open)."""
        try:
            import yfinance as yf

            hist = yf.Ticker(symbol).history(period="6mo")
            if hist.empty:
                return None
            return hist
        except Exception as exc:  # pragma: no cover - network dependent
            logger.debug("yfinance failed for %s: %s", symbol, exc)
            return None

    def _calculate_metrics(self, symbol: str, hist: pd.DataFrame) -> TrendMetrics:
        """Compute SMA/return metrics and gate decision."""
        closes = hist["Close"]
        price = float(closes.iloc[-1])
        sma20 = float(closes.rolling(20).mean().iloc[-1])
        sma50 = float(closes.rolling(50).mean().iloc[-1])
        sma200 = float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else sma50
        return_5d = self._percent_return(closes, 5)
        return_21d = self._percent_return(closes, 21)
        gate_open = bool(sma20 >= sma50)

        if sma20 >= sma50 >= sma200:
            regime_bias = "uptrend"
        elif sma20 < sma50 and sma50 < sma200:
            regime_bias = "downtrend"
        else:
            regime_bias = "sideways"

        return TrendMetrics(
            symbol=symbol,
            price=price,
            sma20=sma20,
            sma50=sma50,
            sma200=sma200,
            return_5d=return_5d,
            return_21d=return_21d,
            gate_open=gate_open,
            regime_bias=regime_bias,
        )

    @staticmethod
    def _percent_return(series: pd.Series, periods: int) -> float:
        """Helper to compute percentage return over lookback."""
        if len(series) <= periods:
            return 0.0
        start = float(series.iloc[-periods])
        end = float(series.iloc[-1])
        return ((end - start) / start) * 100 if start else 0.0

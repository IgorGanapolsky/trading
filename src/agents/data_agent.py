"""
DataAgent - fetches and normalizes market data for downstream agents.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import pandas as pd

from agent_framework import AgentResult, RunContext, TradingAgent
from utils.data_collector import DataCollector
from utils.market_data import get_market_data_provider

logger = logging.getLogger(__name__)

DEFAULT_SYMBOLS = ["SPY", "QQQ", "VOO", "NVDA", "GOOGL", "AMZN"]
WATCHLIST_PATH = Path("data/tier2_watchlist.json")


class DataAgent(TradingAgent):
    """Loads market data for the configured symbol universe."""

    def __init__(self, lookback_days: int = 60, symbols: Iterable[str] | None = None) -> None:
        super().__init__("data-agent")
        self.lookback_days = lookback_days
        self._default_symbols: list[str] = list(symbols) if symbols else DEFAULT_SYMBOLS
        self._provider = get_market_data_provider()
        self._collector = DataCollector()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_watchlist_symbols(self) -> list[str]:
        """Extract symbols from the tier2 watchlist JSON if available."""
        if not WATCHLIST_PATH.exists():
            return []
        try:
            with WATCHLIST_PATH.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            symbols = set()
            for entry in data.get("current_holdings", []):
                symbol = entry.get("symbol")
                if symbol:
                    symbols.add(symbol.upper())
            for entry in data.get("watchlist", []):
                symbol = entry.get("symbol")
                if symbol:
                    symbols.add(symbol.upper())
            return sorted(symbols)
        except Exception as exc:  # pragma: no cover - defensive
            logger.warning("Failed to parse tier2 watchlist: %s", exc)
            return []

    def _resolve_symbol_universe(self, context: RunContext) -> list[str]:
        configured = context.config.get("symbols")
        if configured:
            return [sym.upper() for sym in configured]
        from_watchlist = self._load_watchlist_symbols()
        if from_watchlist:
            return from_watchlist
        return self._default_symbols

    def _summarize_frame(self, df: pd.DataFrame) -> dict[str, Any]:
        if df.empty:
            return {"rows": 0}
        latest_row = df.iloc[-1]
        return {
            "rows": len(df),
            "start": df.index[0].isoformat(),
            "end": df.index[-1].isoformat(),
            "latest_close": float(latest_row["Close"]),
            "latest_volume": float(latest_row["Volume"]),
        }

    # ------------------------------------------------------------------
    # TradingAgent interface
    # ------------------------------------------------------------------
    def execute(self, context: RunContext) -> AgentResult:
        symbols = self._resolve_symbol_universe(context)
        logger.info("Fetching market data for symbols: %s", ", ".join(symbols))

        summaries: dict[str, Any] = {}
        frames: dict[str, pd.DataFrame] = {}
        warnings: list[str] = []

        for symbol in symbols:
            try:
                result = self._provider.get_daily_bars(symbol, lookback_days=self.lookback_days)
                df = result.data
                if df.empty:
                    warnings.append(f"{symbol}: received empty dataframe")
                    continue

                # Persist historical data using existing collector helper.
                self._collector.save_to_csv(symbol, df)

                frames[symbol] = df
                summary = self._summarize_frame(df)
                summary["data_source"] = result.source.value
                summary["fetch_attempts"] = result.total_attempts
                summaries[symbol] = summary
            except Exception as exc:  # pragma: no cover - defensive
                logger.exception("Failed to load data for %s", symbol)
                warnings.append(f"{symbol}: {exc}")

        state_entry = context.state_cache.setdefault("market_data", {})
        state_entry["frames"] = frames
        state_entry["summaries"] = summaries

        payload = {
            "symbols": symbols,
            "summaries": summaries,
            "warnings": warnings,
        }

        succeeded = bool(summaries)
        if not succeeded:
            logger.warning("DataAgent completed with no successful fetches.")
        return AgentResult(
            name=self.agent_name,
            succeeded=succeeded,
            payload=payload,
            warnings=warnings,
        )

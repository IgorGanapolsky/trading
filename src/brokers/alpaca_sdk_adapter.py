"""Alpaca Official SDK Adapter (alpaca-py).

Integrates official Alpaca Python SDK TradingClient and OptionHistoricalDataClient
following official Alpaca example patterns (https://github.com/alpacahq/alpaca-py/tree/master/examples).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from alpaca.trading.client import TradingClient
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]


class AlpacaSDKAdapter:
    """Official alpaca-py SDK wrapper for trading and market data."""

    def __init__(self, env_path: Path | None = None):
        if env_path:
            self.env_path = env_path
        else:
            default_env = ROOT / ".env"
            if not default_env.exists() and (ROOT.parent.parent / ".env").exists():
                default_env = ROOT.parent.parent / ".env"
            self.env_path = default_env
        self.trading_client = self._init_trading_client()

    def _init_trading_client(self) -> TradingClient | None:
        vals = {}
        if self.env_path.exists():
            vals = dotenv_values(self.env_path)

        live_key = vals.get("ALPACA_LIVE_API_KEY") or os.environ.get("ALPACA_LIVE_API_KEY")
        live_secret = vals.get("ALPACA_LIVE_API_SECRET") or os.environ.get("ALPACA_LIVE_API_SECRET")

        if live_key and live_secret:
            try:
                tc = TradingClient(live_key, live_secret, paper=False)
                tc.get_account()
                return tc
            except Exception as e:
                logger.warning("Live TradingClient failed, falling back to paper: %s", e)

        paper_key = vals.get("ALPACA_PAPER_TRADING_API_KEY") or os.environ.get(
            "ALPACA_PAPER_TRADING_API_KEY"
        )
        paper_secret = vals.get("ALPACA_PAPER_TRADING_API_SECRET") or os.environ.get(
            "ALPACA_PAPER_TRADING_API_SECRET"
        )

        if paper_key and paper_secret:
            try:
                return TradingClient(paper_key, paper_secret, paper=True)
            except Exception as e:
                logger.warning("Failed to initialize paper TradingClient: %s", e)

        return None

    def get_account_summary(self) -> dict[str, Any]:
        if not self.trading_client:
            return {"error": "TradingClient not initialized"}

        try:
            acc = self.trading_client.get_account()
            return {
                "account_number": acc.account_number,
                "status": str(acc.status),
                "cash": float(acc.cash),
                "portfolio_value": float(acc.portfolio_value),
                "equity": float(acc.equity),
                "buying_power": float(acc.buying_power),
                "options_approved_level": int(getattr(acc, "options_approved_level", 0)),
            }
        except Exception as e:
            return {"error": str(e)}

    def get_open_positions_count(self) -> int:
        if not self.trading_client:
            return 0

        try:
            positions = self.trading_client.get_all_positions()
            return len(positions)
        except Exception as e:
            logger.warning("Error fetching positions via SDK: %s", e)
            return 0

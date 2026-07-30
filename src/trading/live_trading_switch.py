"""Live Real Money Trading Switch & Readiness Verifier.

Monitors live Alpaca account balance and API credentials to seamlessly switch
from paper execution to live real money options trading as soon as capital is funded.
"""

from __future__ import annotations

import json
import logging
import os
import requests
from dataclasses import asdict, dataclass
from pathlib import Path
from dotenv import dotenv_values

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
LIVE_READINESS_FILE = ROOT / "data" / "audit" / "live_trading_readiness.json"


@dataclass
class LiveReadinessReport:
    live_credentials_present: bool
    live_api_valid: bool
    live_cash_balance: float
    live_buying_power: float
    options_approved_level: int
    live_trading_active: bool
    status_message: str


class LiveTradingSwitch:
    """Verifies live Alpaca brokerage readiness and toggles live execution."""

    def __init__(self, env_path: Path | None = None):
        self.env_path = env_path or (ROOT / ".env")

    def inspect_live_readiness(self) -> LiveReadinessReport:
        vals = {}
        if self.env_path.exists():
            vals = dotenv_values(self.env_path)

        key = vals.get("ALPACA_LIVE_API_KEY") or vals.get("ALPACA_BROKERAGE_TRADING_API_KEY") or os.environ.get("ALPACA_LIVE_API_KEY")
        secret = vals.get("ALPACA_LIVE_API_SECRET") or vals.get("ALPACA_BROKERAGE_TRADING_API_SECRET") or os.environ.get("ALPACA_LIVE_API_SECRET")

        if not key or not secret:
            report = LiveReadinessReport(
                live_credentials_present=False,
                live_api_valid=False,
                live_cash_balance=0.0,
                live_buying_power=0.0,
                options_approved_level=0,
                live_trading_active=False,
                status_message="Live Alpaca API key/secret missing in .env (ALPACA_LIVE_API_KEY)",
            )
            self._save_report(report)
            return report

        # Test live API endpoint
        url = "https://api.alpaca.markets/v2/account"
        headers = {"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret}

        try:
            r = requests.get(url, headers=headers, timeout=10.0)
            if r.status_code != 200:
                report = LiveReadinessReport(
                    live_credentials_present=True,
                    live_api_valid=False,
                    live_cash_balance=0.0,
                    live_buying_power=0.0,
                    options_approved_level=0,
                    live_trading_active=False,
                    status_message=f"Live API returned HTTP {r.status_code}: {r.text}",
                )
                self._save_report(report)
                return report

            data = r.json()
            cash = float(data.get("cash", 0.0))
            bp = float(data.get("buying_power", 0.0))
            opt_lvl = int(data.get("options_approved_level", 0))

            live_active = (cash > 0.0) and (opt_lvl >= 2)

            msg = "✅ LIVE REAL MONEY TRADING ACTIVE" if live_active else f"Live account connected but cash balance is ${cash:,.2f}. Deposit cash to initiate live trades."

            report = LiveReadinessReport(
                live_credentials_present=True,
                live_api_valid=True,
                live_cash_balance=cash,
                live_buying_power=bp,
                options_approved_level=opt_lvl,
                live_trading_active=live_active,
                status_message=msg,
            )
            self._save_report(report)
            return report

        except Exception as e:
            report = LiveReadinessReport(
                live_credentials_present=True,
                live_api_valid=False,
                live_cash_balance=0.0,
                live_buying_power=0.0,
                options_approved_level=0,
                live_trading_active=False,
                status_message=f"Live API connection error: {e}",
            )
            self._save_report(report)
            return report

    def _save_report(self, report: LiveReadinessReport) -> None:
        LIVE_READINESS_FILE.parent.mkdir(parents=True, exist_ok=True)
        try:
            with LIVE_READINESS_FILE.open("w", encoding="utf-8") as h:
                json.dump(asdict(report), h, indent=2)
        except Exception as e:
            logger.warning("Failed to save live readiness report: %s", e)

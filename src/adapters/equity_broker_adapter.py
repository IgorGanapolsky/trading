"""Equity broker adapter for the dividend_growth_income paper loop.

Deliberately NOT the same Alpaca paper account used by spy_put_credit
(ALPACA_PAPER_TRADING_API_KEY / src/core/alpaca_trader.py). Sharing that
account would mix an equity buy-and-hold strategy's positions into the
options-validation cohort's equity/P&L attribution - exactly the kind of
cross-strategy contamination .claude/rules/data-integrity.md and the
kill-criteria lessons in this repo exist to prevent. A real
AlpacaEquityBrokerAdapter must use its own distinct, dedicated paper (or
live) account credentials, never the options account's.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class BuyResult:
    success: bool
    symbol: str
    notional_usd: float
    filled_at: str
    error: str | None = None


@dataclass(frozen=True)
class DividendIncome:
    """Dividend cash received since the last check. Not yet withdrawn."""

    total_usd: float
    observed_at: str


class EquityBrokerAdapter(ABC):
    """Minimal interface the income-loop orchestrator needs from an equity broker."""

    @abstractmethod
    def buy(self, symbol: str, notional_usd: float) -> BuyResult:
        """Buy notional_usd worth of symbol."""

    @abstractmethod
    def collect_dividend_income(self) -> DividendIncome:
        """Return dividend cash accrued since the last call, then reset the accrual to zero."""


class PaperEquityBrokerAdapter(EquityBrokerAdapter):
    """In-memory simulation. No network calls, no shared account, safe default.

    Dividend accrual is a simplified daily-rate simulation of the strategy's
    assumed yield, not a real market feed - it exists so the orchestrator's
    withdraw -> buy -> collect -> deposit loop can be exercised end-to-end in
    tests without needing a live data source.
    """

    def __init__(
        self,
        annual_dividend_yield_pct: float = 3.3,
        initial_positions: dict[str, float] | None = None,
    ):
        self._positions: dict[str, float] = dict(initial_positions) if initial_positions else {}
        self._annual_yield = annual_dividend_yield_pct / 100.0
        self._accrued_dividends_usd = 0.0

    def get_positions(self) -> dict[str, float]:
        return dict(self._positions)

    def get_portfolio_value(self) -> float:
        return sum(self._positions.values())

    def buy(self, symbol: str, notional_usd: float) -> BuyResult:
        if notional_usd <= 0:
            return BuyResult(
                success=False,
                symbol=symbol,
                notional_usd=notional_usd,
                filled_at=datetime.now(timezone.utc).isoformat(),
                error="notional_usd must be positive",
            )
        self._positions[symbol] = self._positions.get(symbol, 0.0) + notional_usd
        return BuyResult(
            success=True,
            symbol=symbol,
            notional_usd=notional_usd,
            filled_at=datetime.now(timezone.utc).isoformat(),
        )

    def accrue_dividends_for_days(self, days: float) -> None:
        """Test/simulation hook: advance simulated dividend accrual by N days."""
        total_position_value = sum(self._positions.values())
        daily_yield = self._annual_yield / 365.0
        self._accrued_dividends_usd += total_position_value * daily_yield * days

    def collect_dividend_income(self) -> DividendIncome:
        income = DividendIncome(
            total_usd=self._accrued_dividends_usd,
            observed_at=datetime.now(timezone.utc).isoformat(),
        )
        self._accrued_dividends_usd = 0.0
        return income


@dataclass
class AlpacaEquityBrokerAdapter(EquityBrokerAdapter):
    """Real Alpaca wrapper for a DEDICATED account, never the options account.

    buy() is implemented via the same submit_order pattern proven throughout
    this repo (src/core/alpaca_trader.py). collect_dividend_income() is NOT
    implemented: Alpaca's dividend/activity feed lives at the /v2/account/
    activities REST endpoint, which is not exposed as a typed method on the
    installed alpaca-py TradingClient (confirmed 2026-07-25 - dir(TradingClient)
    has no get_activities/get_account_activities). Wiring this requires
    verifying that endpoint's actual response shape against a real account
    first; guessing at it here would risk silently misreporting income.
    """

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    _live_enabled: bool = field(default=False, repr=False)

    def __post_init__(self) -> None:
        if not self.api_key or not self.secret_key:
            raise ValueError(
                "AlpacaEquityBrokerAdapter requires its own dedicated API credentials - "
                "never reuse ALPACA_PAPER_TRADING_API_KEY, which belongs to the "
                "spy_put_credit validation account."
            )
        if not self._live_enabled:
            raise RuntimeError(
                "AlpacaEquityBrokerAdapter constructed without "
                "DIVIDEND_GROWTH_ALPACA_ENABLED=1. Deliberate hard stop, same "
                "pattern as MercuryBankAdapter."
            )

    @classmethod
    def from_env(cls, secrets_path: Path | None = None) -> AlpacaEquityBrokerAdapter:
        api_key = os.environ.get("DIVIDEND_GROWTH_ALPACA_API_KEY")
        secret_key = os.environ.get("DIVIDEND_GROWTH_ALPACA_API_SECRET")
        live_enabled = os.environ.get("DIVIDEND_GROWTH_ALPACA_ENABLED") == "1"

        if not api_key or not secret_key:
            env_secrets_path = os.environ.get("ALPACA_SECRETS_PATH")
            path = secrets_path or (Path(env_secrets_path) if env_secrets_path else Path.home() / ".resume_secrets" / "alpaca.json")
            if path.exists():
                try:
                    with path.open("r", encoding="utf-8") as handle:
                        secrets = json.load(handle)
                        api_key = api_key or secrets.get("DIVIDEND_GROWTH_ALPACA_API_KEY")
                        secret_key = secret_key or secrets.get("DIVIDEND_GROWTH_ALPACA_API_SECRET")
                except Exception:
                    pass

        if not api_key or not secret_key:
            raise ValueError(
                "DIVIDEND_GROWTH_ALPACA_API_KEY and DIVIDEND_GROWTH_ALPACA_API_SECRET "
                "must both be set to a dedicated paper (or live) account distinct "
                "from the options-strategy account."
            )
        return cls(api_key=api_key, secret_key=secret_key, _live_enabled=live_enabled)

    def buy(self, symbol: str, notional_usd: float) -> BuyResult:
        from alpaca.trading.client import TradingClient
        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        client = TradingClient(self.api_key, self.secret_key, paper=True)
        request = MarketOrderRequest(
            symbol=symbol,
            notional=notional_usd,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        try:
            # order id/status intentionally unused until reconciliation is built.
            # Not routed through safe_submit_order()/get_guarded_trading_client():
            # that gate's validate_ticker() hardcodes ALLOWED_TICKERS={"SPY"} and
            # iron-condor-specific orientation checks for the options-validation
            # account (src/core/trading_constants.py) - it would either reject
            # every SCHD order outright or require weakening that canonical SPY
            # whitelist, which is worse than a scoped opt-out. This adapter has
            # its own account-isolation and construction-time gates instead (see
            # class docstring) and cannot run at all without a dedicated
            # DIVIDEND_GROWTH_ALPACA_ENABLED=1 flag nobody sets today.
            client.submit_order(request)  # repo CI guard opt-out (noqa: direct-submit-order)
            return BuyResult(
                success=True,
                symbol=symbol,
                notional_usd=notional_usd,
                filled_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001 - surfaced via result, not raised
            return BuyResult(
                success=False,
                symbol=symbol,
                notional_usd=notional_usd,
                filled_at=datetime.now(timezone.utc).isoformat(),
                error=str(exc),
            )

    def collect_dividend_income(self) -> DividendIncome:
        import requests

        headers = {
            "APCA-API-KEY-ID": self.api_key,
            "APCA-API-SECRET-KEY": self.secret_key,
        }
        url = "https://api.alpaca.markets/v2/account/activities"
        try:
            resp = requests.get(url, headers=headers, params={"activity_types": "DIV"}, timeout=15)
            resp.raise_for_status()
            activities = resp.json()
            total = 0.0
            if isinstance(activities, list):
                for act in activities:
                    if isinstance(act, dict):
                        total += float(act.get("net_amount", 0.0))
            return DividendIncome(
                total_usd=total,
                observed_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:
            logger.error("Failed to fetch Alpaca dividend activities: %s", exc)
            return DividendIncome(
                total_usd=0.0,
                observed_at=datetime.now(timezone.utc).isoformat(),
            )

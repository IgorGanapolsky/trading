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

import logging
import os
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BuyResult:
    success: bool
    symbol: str
    notional_usd: float
    filled_at: str
    filled_qty: float | None = None
    filled_avg_price: float | None = None
    order_id: str | None = None
    error: str | None = None


@dataclass(frozen=True)
class DividendDetail:
    """One dividend payment record from the broker activity feed."""

    symbol: str
    net_amount_usd: float
    per_share_amount: float | None
    qty: float | None
    activity_date: str
    activity_sub_type: str  # CDIV, SDIV, SPD
    activity_id: str


@dataclass(frozen=True)
class DividendIncome:
    """Dividend cash received since the last check. Not yet withdrawn."""

    total_usd: float
    observed_at: str
    details: tuple[DividendDetail, ...] = ()


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

    def __init__(self, annual_dividend_yield_pct: float = 3.3):
        self._positions: dict[str, float] = {}
        self._annual_yield = annual_dividend_yield_pct / 100.0
        self._accrued_dividends_usd = 0.0

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

    buy() submits a market order via TradingClient.submit_order and waits for
    the fill (with a configurable timeout), returning actual fill details.

    collect_dividend_income() queries the /v2/account/activities REST endpoint
    via TradingClient.get() (confirmed 2026-07-26: the installed alpaca-py
    TradingClient exposes a generic .get(path, data=...) method that can reach
    /account/activities even though no typed get_activities() wrapper exists).
    Only cash dividends (activity_type=DIV, activity_sub_type=CDIV) with
    status=executed are counted. The last-checked timestamp is tracked on the
    instance so repeated calls never double-count the same payment.
    """

    api_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    _live_enabled: bool = field(default=False, repr=False)
    paper: bool = field(default=False, repr=False)
    _last_checked_at: str = field(default="", repr=False)

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
        # _last_checked_at starts empty; the first collect_dividend_income()
        # call will see ALL activities, then advance the cursor.

    @classmethod
    def from_env(cls) -> AlpacaEquityBrokerAdapter:
        api_key = os.environ.get("DIVIDEND_GROWTH_ALPACA_API_KEY")
        secret_key = os.environ.get("DIVIDEND_GROWTH_ALPACA_API_SECRET")
        live_enabled = os.environ.get("DIVIDEND_GROWTH_ALPACA_ENABLED") == "1"
        paper = os.environ.get("DIVIDEND_GROWTH_ALPACA_PAPER", "0") == "1"
        if not api_key or not secret_key:
            raise ValueError(
                "DIVIDEND_GROWTH_ALPACA_API_KEY and DIVIDEND_GROWTH_ALPACA_API_SECRET "
                "must both be set to a dedicated paper (or live) account distinct "
                "from the options-strategy account."
            )
        return cls(
            api_key=api_key,
            secret_key=secret_key,
            _live_enabled=live_enabled,
            paper=paper,
        )

    def _get_client(self):
        from alpaca.trading.client import TradingClient

        return TradingClient(self.api_key, self.secret_key, paper=self.paper)

    def buy(self, symbol: str, notional_usd: float) -> BuyResult:
        if notional_usd <= 0:
            return BuyResult(
                success=False,
                symbol=symbol,
                notional_usd=notional_usd,
                filled_at=datetime.now(timezone.utc).isoformat(),
                error="notional_usd must be positive",
            )

        from alpaca.trading.enums import OrderSide, TimeInForce
        from alpaca.trading.requests import MarketOrderRequest

        client = self._get_client()
        request = MarketOrderRequest(
            symbol=symbol,
            notional=notional_usd,
            side=OrderSide.BUY,
            time_in_force=TimeInForce.DAY,
        )
        try:
            # Not routed through safe_submit_order()/get_guarded_trading_client():
            # that gate's validate_ticker() hardcodes ALLOWED_TICKERS={"SPY"} and
            # iron-condor-specific orientation checks for the options-validation
            # account (src/core/trading_constants.py) - it would either reject
            # every SCHD order outright or require weakening that canonical SPY
            # whitelist, which is worse than a scoped opt-out. This adapter has
            # its own account-isolation and construction-time gates instead (see
            # class docstring) and cannot run at all without a dedicated
            # DIVIDEND_GROWTH_ALPACA_ENABLED=1 flag nobody sets today.
            order = client.submit_order(request)  # direct-submit-order opt-out: dedicated dividend_growth account
            order_id = str(order.id) if order and getattr(order, "id", None) else None

            # Wait for fill (best-effort, non-blocking on failure)
            filled_qty = None
            filled_avg_price = None
            timeout = float(os.getenv("DIVIDEND_GROWTH_FILL_TIMEOUT_SECONDS", "30"))
            start = time.monotonic()
            while time.monotonic() - start < timeout:
                try:
                    refreshed = client.get_order_by_id(order_id)
                    if str(refreshed.status) in ("filled", "partially_filled"):
                        filled_qty = float(refreshed.filled_qty) if refreshed.filled_qty else None
                        filled_avg_price = (
                            float(refreshed.filled_avg_price)
                            if refreshed.filled_avg_price
                            else None
                        )
                        break
                    if str(refreshed.status) in ("cancelled", "expired", "rejected"):
                        break
                except Exception as exc:  # noqa: BLE001
                    logger.debug("Order status refresh failed for %s: %s", order_id, exc)
                time.sleep(1)

            return BuyResult(
                success=True,
                symbol=symbol,
                notional_usd=notional_usd,
                filled_at=datetime.now(timezone.utc).isoformat(),
                filled_qty=filled_qty,
                filled_avg_price=filled_avg_price,
                order_id=order_id,
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
        """Fetch cash dividend payments from the Alpaca activity feed.

        Queries /v2/account/activities for activity_type=DIV records newer
        than the last check (tracked via _last_checked_at). Only CDIV
        (cash dividend) sub-types with status=executed are counted. The
        last-checked timestamp is advanced after each successful call so
        repeated invocations never double-count the same payment.

        Returns DividendIncome with total_usd=0.0 (and empty details) when
        no new dividends have arrived since the last check.
        """
        client = self._get_client()
        now_iso = datetime.now(timezone.utc).isoformat()
        total = 0.0
        details: list[DividendDetail] = []

        try:
            # Paginate through all DIV activities (newest first)
            page_token: str | None = None
            seen_ids: set[str] = set()
            max_pages = 50  # safety cap

            for _ in range(max_pages):
                data: dict[str, Any] = {
                    "activity_type": "DIV",
                    "page_size": 100,
                    "direction": "desc",
                }
                if page_token:
                    data["page_token"] = page_token

                resp = client.get("/account/activities", data=data)
                activities = resp if isinstance(resp, list) else []

                if not activities:
                    break

                for act in activities:
                    if not isinstance(act, dict):
                        continue
                    act_id = str(act.get("id", ""))
                    if act_id in seen_ids:
                        continue
                    seen_ids.add(act_id)

                    # Only count cash dividends that executed
                    sub_type = str(act.get("activity_sub_type", ""))
                    status = str(act.get("status", ""))
                    if sub_type != "CDIV" or status != "executed":
                        continue

                    # Filter by last-checked timestamp (created_at for non-trade).
                    # On the first call _last_checked_at is empty, so we see all
                    # activities; subsequent calls only see newer ones.
                    created_at = str(act.get("created_at", "")) or str(
                        act.get("date", "")
                    )
                    if self._last_checked_at and created_at and created_at <= self._last_checked_at:
                        continue

                    try:
                        net_amount = float(act.get("net_amount", 0) or 0)
                    except (TypeError, ValueError):
                        continue

                    if net_amount <= 0:
                        continue

                    total += net_amount
                    try:
                        per_share = float(act.get("per_share_amount", 0) or 0)
                    except (TypeError, ValueError):
                        per_share = 0.0
                    try:
                        qty = float(act.get("qty", 0) or 0)
                    except (TypeError, ValueError):
                        qty = 0.0

                    details.append(
                        DividendDetail(
                            symbol=str(act.get("symbol", "")),
                            net_amount_usd=round(net_amount, 2),
                            per_share_amount=round(per_share, 4) if per_share else None,
                            qty=qty if qty else None,
                            activity_date=str(act.get("date", "")),
                            activity_sub_type=sub_type,
                            activity_id=act_id,
                        )
                    )

                # Pagination: check if there's a next page
                page_token = None
                if len(activities) == 100:
                    # Use the last activity's ID as the next page token
                    last_id = str(activities[-1].get("id", ""))
                    if last_id and last_id not in seen_ids:
                        page_token = last_id
                if not page_token:
                    break

        except Exception as exc:  # noqa: BLE001 - log and return empty
            logger.error("Failed to fetch dividend activities: %s", exc)
            return DividendIncome(
                total_usd=0.0,
                observed_at=now_iso,
                details=(),
            )

        # Advance the last-checked timestamp so we don't re-count these
        self._last_checked_at = now_iso

        return DividendIncome(
            total_usd=round(total, 2),
            observed_at=now_iso,
            details=tuple(details),
        )

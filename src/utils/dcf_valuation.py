"""
Discounted Cash Flow (DCF) valuation utilities.

This module fetches fundamental data from Polygon.io (preferred) or Alpha Vantage API (fallback)
and computes a simple two-stage DCF valuation for equities. Results are cached locally to
avoid breaching the provider's rate limits.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


DEFAULT_CACHE_TTL_HOURS = 24
DEFAULT_TERMINAL_GROWTH = 0.025  # 2.5% terminal growth assumption
DEFAULT_RISK_FREE_RATE = 0.04  # 4% risk free proxy
DEFAULT_EQUITY_RISK_PREMIUM = 0.05  # 5% equity risk premium
MIN_DISCOUNT_RATE = 0.08
MAX_DISCOUNT_RATE = 0.18


class DCFError(Exception):
    """Raised when DCF valuation fails."""


@dataclass
class DCFResult:
    """Container for DCF valuation results."""

    intrinsic_value: float
    discount_rate: float
    terminal_growth: float
    projected_growth: float
    timestamp: datetime

    def to_json(self) -> dict:
        return {
            "intrinsic_value": self.intrinsic_value,
            "discount_rate": self.discount_rate,
            "terminal_growth": self.terminal_growth,
            "projected_growth": self.projected_growth,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_json(cls, data: dict) -> DCFResult:
        return cls(
            intrinsic_value=float(data["intrinsic_value"]),
            discount_rate=float(data["discount_rate"]),
            terminal_growth=float(data["terminal_growth"]),
            projected_growth=float(data["projected_growth"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


class DCFValuationCalculator:
    """
    Utility class for computing intrinsic value using a simplified DCF model.

    Steps:
        1. Fetch annual free cash flow history (Operating CF - CapEx)
        2. Estimate forward growth using trailing 3-year CAGR (capped to +/-30%)
        3. Project free cash flow for the next 5 years
        4. Compute terminal value via Gordon Growth Model
        5. Discount cash flows using CAPM-derived rate based on beta
        6. Divide enterprise value by shares outstanding to get intrinsic price
    """

    # Alpha Vantage endpoints (fallback)
    OVERVIEW_ENDPOINT = (
        "https://www.alphavantage.co/query?function=OVERVIEW&symbol={ticker}&apikey={api_key}"
    )
    CASH_FLOW_ENDPOINT = (
        "https://www.alphavantage.co/query?function=CASH_FLOW&symbol={ticker}&apikey={api_key}"
    )

    # Polygon.io endpoints (preferred)
    POLYGON_BASE_URL = "https://api.polygon.io/v2"

    def __init__(
        self,
        api_key: str | None = None,
        cache_dir: Path | None = None,
        cache_ttl_hours: int = DEFAULT_CACHE_TTL_HOURS,
    ) -> None:
        # Try Polygon.io first (preferred), then Alpha Vantage (fallback)
        self.polygon_api_key = os.getenv("POLYGON_API_KEY")
        self.api_key = api_key or os.getenv("ALPHA_VANTAGE_API_KEY")

        if not self.polygon_api_key and not self.api_key:
            logger.warning(
                "Neither POLYGON_API_KEY nor ALPHA_VANTAGE_API_KEY set. DCF valuations will be unavailable."
            )
        elif self.polygon_api_key:
            logger.info("Using Polygon.io API for DCF valuations (preferred)")
        elif self.api_key:
            logger.info("Using Alpha Vantage API for DCF valuations (fallback)")

        self.cache_dir = cache_dir or Path("data/cache/dcf")
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_ttl = timedelta(hours=cache_ttl_hours)

        # In-memory session cache to limit disk reads
        self._session_cache: dict[str, DCFResult] = {}

    # ------------------------------------------------------------------ #
    # Public API
    # ------------------------------------------------------------------ #
    def get_intrinsic_value(self, ticker: str, force_refresh: bool = False) -> DCFResult | None:
        """
        Return cached or freshly computed DCF valuation for a ticker.

        Args:
            ticker: Equity ticker symbol
            force_refresh: Skip cache and recompute

        Returns:
            DCFResult if successful, otherwise None.
        """
        ticker = ticker.upper().strip()
        if not ticker:
            return None

        if not self.polygon_api_key and not self.api_key:
            logger.debug("Skipping DCF valuation for %s (no API key)", ticker)
            return None

        if not force_refresh:
            cached = self._load_from_cache(ticker)
            if cached:
                return cached

        # Try Polygon.io first (preferred), then Alpha Vantage (fallback)
        try:
            if self.polygon_api_key:
                overview = self._fetch_polygon_overview(ticker)
                cash_flows = self._fetch_polygon_cash_flows(ticker)
            else:
                overview = self._fetch_company_overview(ticker)
                cash_flows = self._fetch_cash_flows(ticker)

            dcf_result = self._compute_dcf(ticker, overview, cash_flows)
            self._store_in_cache(ticker, dcf_result)
            return dcf_result
        except DCFError as exc:
            # If Polygon.io fails and we have Alpha Vantage, try fallback
            if self.polygon_api_key and self.api_key:
                logger.info(
                    "Polygon.io failed for %s, trying Alpha Vantage fallback: %s",
                    ticker,
                    exc,
                )
                try:
                    overview = self._fetch_company_overview(ticker)
                    cash_flows = self._fetch_cash_flows(ticker)
                    dcf_result = self._compute_dcf(ticker, overview, cash_flows)
                    self._store_in_cache(ticker, dcf_result)
                    return dcf_result
                except Exception as fallback_exc:
                    logger.warning(
                        "DCF valuation unavailable for %s (both Polygon.io and Alpha Vantage failed): %s",
                        ticker,
                        fallback_exc,
                    )
            else:
                logger.warning("DCF valuation unavailable for %s: %s", ticker, exc)
        except Exception as exc:  # noqa: BLE001
            logger.error("Unexpected error computing DCF for %s: %s", ticker, exc, exc_info=True)

        return None

    def calculate_margin_of_safety(self, ticker: str, market_price: float) -> float | None:
        """
        Compute margin of safety given a market price.

        Returns:
            Margin of safety as a decimal (e.g. 0.2 == 20% discount) or None.
        """
        if market_price <= 0:
            return None

        result = self.get_intrinsic_value(ticker)
        if not result or result.intrinsic_value <= 0:
            return None

        return (result.intrinsic_value - market_price) / result.intrinsic_value

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #
    def _load_from_cache(self, ticker: str) -> DCFResult | None:
        # In-memory cache first
        if ticker in self._session_cache:
            cached = self._session_cache[ticker]
            if datetime.utcnow() - cached.timestamp <= self.cache_ttl:
                return cached

        cache_file = self.cache_dir / f"{ticker}.json"
        if not cache_file.exists():
            return None

        try:
            with cache_file.open("r", encoding="utf-8") as f:
                payload = json.load(f)

            result = DCFResult.from_json(payload)
            if datetime.utcnow() - result.timestamp > self.cache_ttl:
                return None

            self._session_cache[ticker] = result
            return result
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to load cached DCF for %s: %s", ticker, exc)
            return None

    def _store_in_cache(self, ticker: str, result: DCFResult) -> None:
        self._session_cache[ticker] = result
        cache_file = self.cache_dir / f"{ticker}.json"
        try:
            with cache_file.open("w", encoding="utf-8") as f:
                json.dump(result.to_json(), f, indent=2)
        except Exception as exc:  # noqa: BLE001
            logger.debug("Failed to persist DCF cache for %s: %s", ticker, exc)

    def _fetch_polygon_overview(self, ticker: str) -> dict:
        """Fetch company overview from Polygon.io."""
        # Polygon.io v3 API endpoint
        url = f"https://api.polygon.io/v3/reference/tickers/{ticker}"
        params = {"apiKey": self.polygon_api_key}

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Polygon.io v3 returns results directly, not nested
            if data.get("status") != "OK":
                raise DCFError(f"Polygon.io API error: {data.get('error', 'Unknown error')}")

            result = data.get("results", {})
            if not result:
                raise DCFError("Polygon.io overview unavailable - no results")

            # Convert Polygon.io format to Alpha Vantage-like format for compatibility
            shares_outstanding = result.get("share_class_shares_outstanding") or result.get(
                "weighted_shares_outstanding", 0
            )
            market_cap = result.get("market_cap", 0)

            overview = {
                "Symbol": result.get("ticker", ticker),
                "Beta": "1.0",  # Polygon.io doesn't provide beta in ticker endpoint, use default
                "SharesOutstanding": (str(int(shares_outstanding)) if shares_outstanding else "0"),
                "MarketCapitalization": str(int(market_cap)) if market_cap else "0",
                "Name": result.get("name", ""),
            }

            return overview
        except requests.RequestException as exc:
            raise DCFError(f"Polygon.io HTTP error: {exc}") from exc
        except (ValueError, KeyError) as exc:
            raise DCFError("Invalid Polygon.io JSON response") from exc

    def _fetch_polygon_cash_flows(self, ticker: str) -> dict:
        """
        Fetch cash flow statements from Polygon.io.

        Note: Polygon.io Starter plan may not include financials endpoint.
        This will raise DCFError to trigger Alpha Vantage fallback.
        """
        # Polygon.io v2 API endpoint for financials (may require higher tier)
        url = "https://api.polygon.io/v2/reference/financials"
        params = {
            "ticker": ticker,
            "apiKey": self.polygon_api_key,
            "timeframe": "annual",
            "filing_date.gte": "2015-01-01",  # 10 years of data
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            # Check for API errors (plan limitations, etc.)
            if data.get("status") != "OK":
                error_msg = data.get("error", "Unknown error")
                # If access denied, trigger fallback
                if "access" in error_msg.lower() or "permission" in error_msg.lower():
                    raise DCFError(
                        "Polygon.io financials endpoint requires higher tier plan - using Alpha Vantage fallback"
                    )
                raise DCFError(f"Polygon.io API error: {error_msg}")

            results = data.get("results", [])
            if not results:
                raise DCFError("No cash flow data from Polygon.io - using Alpha Vantage fallback")

            # Convert Polygon.io format to Alpha Vantage-like format
            annual_reports = []
            for result in results:
                financials = result.get("financials", {})
                cash_flow = financials.get("cash_flow_statement", {})

                # Extract operating cash flow and capital expenditures
                operating_cf = None
                capex = None

                for item in cash_flow.get("financials", []):
                    label = item.get("label", "").lower()
                    value = item.get("value")

                    if "operating" in label and "cash" in label and "flow" in label:
                        operating_cf = value
                    elif "capital" in label and "expenditure" in label:
                        capex = value

                if operating_cf is not None:
                    annual_reports.append(
                        {
                            "fiscalDateEnding": result.get("filing_date", ""),
                            "operatingCashflow": (str(operating_cf) if operating_cf else "0"),
                            "capitalExpenditures": str(capex) if capex else "0",
                        }
                    )

            if not annual_reports:
                raise DCFError(
                    "No cash flow reports from Polygon.io - using Alpha Vantage fallback"
                )

            return {"annualReports": annual_reports}
        except requests.RequestException as exc:
            # Trigger fallback for HTTP errors
            raise DCFError(
                f"Polygon.io HTTP error (will use Alpha Vantage fallback): {exc}"
            ) from exc
        except (ValueError, KeyError) as exc:
            raise DCFError(
                "Invalid Polygon.io JSON response - using Alpha Vantage fallback"
            ) from exc

    def _fetch_company_overview(self, ticker: str) -> dict:
        """Fetch company overview from Alpha Vantage (fallback)."""
        url = self.OVERVIEW_ENDPOINT.format(ticker=ticker, api_key=self.api_key)
        data = self._perform_request(url)

        if not data or "Symbol" not in data:
            raise DCFError("Company overview unavailable")
        return data

    def _fetch_cash_flows(self, ticker: str) -> dict:
        """Fetch cash flows from Alpha Vantage (fallback)."""
        url = self.CASH_FLOW_ENDPOINT.format(ticker=ticker, api_key=self.api_key)
        data = self._perform_request(url)

        reports = data.get("annualReports")
        if not reports:
            raise DCFError("Cash flow reports missing")
        return reports

    def _perform_request(self, url: str) -> dict:
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            # Alpha Vantage returns a dict with "Information" on throttling
            if "Note" in data or "Information" in data:
                raise DCFError(data.get("Note") or data.get("Information") or "API limit reached")
            return data
        except requests.RequestException as exc:
            raise DCFError(f"HTTP error: {exc}") from exc
        except ValueError as exc:
            raise DCFError("Invalid JSON response") from exc

    def _compute_dcf(self, ticker: str, overview: dict, cash_reports: dict) -> DCFResult:
        free_cash_flows = self._extract_free_cash_flows(cash_reports)
        if len(free_cash_flows) < 2:
            raise DCFError("Insufficient FCF history")

        latest_fcf = free_cash_flows[0]
        if latest_fcf <= 0:
            raise DCFError("Negative free cash flow")

        growth_rate = self._estimate_growth(free_cash_flows)
        discount_rate = self._estimate_discount_rate(overview)
        shares_outstanding = self._parse_float(overview.get("SharesOutstanding"))

        if not shares_outstanding or shares_outstanding <= 0:
            raise DCFError("Shares outstanding unavailable")

        intrinsic_value = self._discount_cash_flows(
            latest_fcf=latest_fcf,
            growth_rate=growth_rate,
            discount_rate=discount_rate,
            shares_outstanding=shares_outstanding,
        )

        return DCFResult(
            intrinsic_value=intrinsic_value,
            discount_rate=discount_rate,
            terminal_growth=DEFAULT_TERMINAL_GROWTH,
            projected_growth=growth_rate,
            timestamp=datetime.utcnow(),
        )

    # ------------------------------------------------------------------ #
    # Numeric helpers
    # ------------------------------------------------------------------ #
    def _extract_free_cash_flows(self, cash_reports: dict) -> tuple[float, ...]:
        fcfs = []
        for report in cash_reports:
            operating_cf = self._parse_float(report.get("operatingCashflow"))
            capex = self._parse_float(report.get("capitalExpenditures"))
            if operating_cf is None or capex is None:
                continue
            fcfs.append(operating_cf - capex)
        if not fcfs:
            raise DCFError("Unable to compute free cash flow")
        return tuple(fcfs)

    def _estimate_growth(self, fcfs: tuple[float, ...]) -> float:
        # Use CAGR over the last 3 intervals where possible
        if len(fcfs) < 2:
            return 0.0

        latest = fcfs[0]
        oldest_index = min(len(fcfs) - 1, 3)
        oldest = fcfs[oldest_index]
        if oldest <= 0 or latest <= 0:
            return 0.0

        years = oldest_index
        cagr = (latest / oldest) ** (1 / years) - 1 if years > 0 else 0.0
        # Clamp growth to a reasonable range to avoid runaway projections
        return max(-0.15, min(0.30, cagr))

    def _estimate_discount_rate(self, overview: dict) -> float:
        beta = self._parse_float(overview.get("Beta"), default=1.0)
        discount = DEFAULT_RISK_FREE_RATE + beta * DEFAULT_EQUITY_RISK_PREMIUM
        return max(MIN_DISCOUNT_RATE, min(MAX_DISCOUNT_RATE, discount))

    def _discount_cash_flows(
        self,
        latest_fcf: float,
        growth_rate: float,
        discount_rate: float,
        shares_outstanding: float,
        projection_years: int = 5,
    ) -> float:
        projected_fcfs = []
        fcf = latest_fcf
        for year in range(1, projection_years + 1):
            fcf *= 1 + growth_rate
            discounted = fcf / ((1 + discount_rate) ** year)
            projected_fcfs.append(discounted)

        terminal_value = (
            projected_fcfs[-1]
            * (1 + DEFAULT_TERMINAL_GROWTH)
            / (discount_rate - DEFAULT_TERMINAL_GROWTH)
            if discount_rate > DEFAULT_TERMINAL_GROWTH
            else 0.0
        )
        discounted_terminal = terminal_value / ((1 + discount_rate) ** projection_years)

        equity_value = sum(projected_fcfs) + discounted_terminal
        intrinsic_value = equity_value / shares_outstanding
        return intrinsic_value

    @staticmethod
    def _parse_float(value: str | None, default: float | None = None) -> float | None:
        if value in (None, "", "None"):
            return default
        try:
            return float(value)
        except (TypeError, ValueError):
            try:
                return float(value.replace(",", ""))
            except Exception:
                return default


# Convenience singleton for reuse across modules without repeated initialization
_GLOBAL_DCF_CALCULATOR: DCFValuationCalculator | None = None


def get_global_dcf_calculator() -> DCFValuationCalculator:
    global _GLOBAL_DCF_CALCULATOR
    if _GLOBAL_DCF_CALCULATOR is None:
        _GLOBAL_DCF_CALCULATOR = DCFValuationCalculator()
    return _GLOBAL_DCF_CALCULATOR

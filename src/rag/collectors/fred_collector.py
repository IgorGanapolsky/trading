"""
FRED Collector - Real Federal Reserve Economic Data API Integration

Fetches live Treasury yield data for the TreasuryLadderStrategy.
Used for yield curve analysis, TLT/ZROZ switching, and bond allocation decisions.

API Documentation: https://fred.stlouisfed.org/docs/api/fred/
Rate Limit: 120 requests per minute

Author: Trading System
Created: 2025-12-23
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)


class FREDCollector:
    """Collector for Federal Reserve Economic Data (FRED) API."""

    BASE_URL = "https://api.stlouisfed.org/fred/series/observations"

    # Key Treasury yield series
    SERIES = {
        "DGS2": "2-Year Treasury Yield",
        "DGS5": "5-Year Treasury Yield",
        "DGS10": "10-Year Treasury Yield",
        "DGS30": "30-Year Treasury Yield",
        "T10Y2Y": "10-Year minus 2-Year Spread",
        "T10Y3M": "10-Year minus 3-Month Spread",
        "DFEDTARU": "Fed Funds Upper Target",
    }

    def __init__(self, api_key: str | None = None):
        """Initialize FRED collector.

        Args:
            api_key: FRED API key. If not provided, uses env var FRED_API_KEY.
        """
        self.api_key = api_key or os.environ.get("FRED_API_KEY")

        if not self.api_key:
            logger.warning("FRED_API_KEY not configured - will use fallback values")
        else:
            logger.info("FREDCollector initialized with API key")

    def _fetch_series(
        self,
        series_id: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict[str, Any]:
        """Fetch a data series from FRED.

        Args:
            series_id: FRED series ID (e.g., 'DGS2', 'DGS10', 'T10Y2Y')
            start_date: Optional start date (YYYY-MM-DD)
            end_date: Optional end date (YYYY-MM-DD)

        Returns:
            Dict with 'value' and 'date' keys, or empty dict on failure.
        """
        if not self.api_key:
            return self._get_fallback(series_id)

        # Default to last 7 days if no dates specified
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

        url = (
            f"{self.BASE_URL}"
            f"?series_id={series_id}"
            f"&api_key={self.api_key}"
            f"&file_type=json"
            f"&observation_start={start_date}"
            f"&observation_end={end_date}"
            f"&sort_order=desc"
            f"&limit=1"
        )

        try:
            req = Request(url, headers={"Accept": "application/json"})
            with urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())

            observations = data.get("observations", [])
            if observations:
                latest = observations[0]
                value = latest.get("value", ".")

                # FRED uses "." for missing values
                if value == ".":
                    logger.warning(f"FRED {series_id}: No data available for date range")
                    return self._get_fallback(series_id)

                result = {
                    "value": float(value),
                    "date": latest.get("date"),
                    "series_id": series_id,
                    "source": "FRED_API",
                }
                logger.debug(f"FRED {series_id}: {result['value']} ({result['date']})")
                return result
            else:
                logger.warning(f"FRED {series_id}: No observations returned")
                return self._get_fallback(series_id)

        except HTTPError as e:
            logger.error(f"FRED API HTTP error for {series_id}: {e.code} - {e.reason}")
            return self._get_fallback(series_id)
        except URLError as e:
            logger.error(f"FRED API URL error for {series_id}: {e.reason}")
            return self._get_fallback(series_id)
        except json.JSONDecodeError as e:
            logger.error(f"FRED API JSON error for {series_id}: {e}")
            return self._get_fallback(series_id)
        except Exception as e:
            logger.error(f"FRED API error for {series_id}: {e}")
            return self._get_fallback(series_id)

    def _get_fallback(self, series_id: str) -> dict[str, Any]:
        """Get fallback values when API is unavailable.

        These are approximate values - should only be used temporarily.
        """
        # Conservative fallback values (Dec 2025 approximate)
        fallbacks = {
            "DGS2": {"value": 4.30, "date": "2025-12-23", "source": "fallback"},
            "DGS5": {"value": 4.35, "date": "2025-12-23", "source": "fallback"},
            "DGS10": {"value": 4.50, "date": "2025-12-23", "source": "fallback"},
            "DGS30": {"value": 4.70, "date": "2025-12-23", "source": "fallback"},
            "T10Y2Y": {"value": 0.20, "date": "2025-12-23", "source": "fallback"},
            "T10Y3M": {"value": 0.10, "date": "2025-12-23", "source": "fallback"},
            "DFEDTARU": {"value": 4.50, "date": "2025-12-23", "source": "fallback"},
        }

        if series_id in fallbacks:
            logger.warning(f"Using fallback value for {series_id}")
            return fallbacks[series_id]

        logger.error(f"Unknown FRED series: {series_id}")
        return {}

    def get_treasury_yields(self) -> dict[str, float]:
        """Get current Treasury yields for all maturities.

        Returns:
            Dict mapping maturity to yield (e.g., {'2Y': 4.17, '10Y': 4.19})
        """
        yields = {}

        for series_id, name in [
            ("DGS2", "2Y"),
            ("DGS5", "5Y"),
            ("DGS10", "10Y"),
            ("DGS30", "30Y"),
        ]:
            data = self._fetch_series(series_id)
            if data and "value" in data:
                yields[name] = data["value"]

        return yields

    def get_yield_curve_spread(self) -> float | None:
        """Get the 10Y-2Y yield curve spread.

        Positive = normal curve (bullish for economy)
        Negative = inverted curve (recession warning)

        Returns:
            Spread in percentage points, or None if unavailable.
        """
        data = self._fetch_series("T10Y2Y")
        if data and "value" in data:
            return data["value"]
        return None

    def is_yield_curve_inverted(self) -> bool:
        """Check if yield curve is inverted (10Y < 2Y).

        Inverted curve historically precedes recessions.
        """
        spread = self.get_yield_curve_spread()
        if spread is not None:
            return spread < 0
        return False


# Backwards compatibility alias
FredCollector = FREDCollector

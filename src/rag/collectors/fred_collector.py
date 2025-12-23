"""
FRED Collector Stub

Provides yield data from FRED API for treasury ladder strategy.
This is a minimal stub - actual implementation would use fredapi or requests.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


class FREDCollector:
    """Collector for Federal Reserve Economic Data (FRED) API."""

    def __init__(self, api_key: str | None = None):
        """Initialize FRED collector.

        Args:
            api_key: Optional FRED API key. If not provided, uses env var FRED_API_KEY.
        """
        self.api_key = api_key
        logger.info("FREDCollector initialized (stub mode)")

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
            Dict with series data or empty dict on failure.
        """
        # Stub implementation - return reasonable defaults for treasury yields
        # Actual implementation would use fredapi or requests to FRED API
        logger.debug(f"FREDCollector._fetch_series({series_id}) - returning stub data")

        # Default yield values (Dec 2025 approximate)
        defaults = {
            "DGS2": {"value": 4.17, "date": "2025-12-23"},    # 2-year treasury
            "DGS10": {"value": 4.19, "date": "2025-12-23"},   # 10-year treasury
            "DGS30": {"value": 4.36, "date": "2025-12-23"},   # 30-year treasury
            "T10Y2Y": {"value": 0.02, "date": "2025-12-23"},  # 10yr-2yr spread
        }

        if series_id in defaults:
            return defaults[series_id]

        logger.warning(f"Unknown FRED series: {series_id}")
        return {}

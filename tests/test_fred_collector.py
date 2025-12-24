import json
import types
from unittest.mock import patch, MagicMock

from src.rag.collectors import FredCollector
from src.rag.collectors.fred_collector import FREDCollector


def test_fredcollector_alias():
    """Ensure camel-case alias works."""
    # Alias is exposed for backward compatibility
    assert FredCollector is FREDCollector


def test_fredcollector_get_treasury_yields():
    """Test get_treasury_yields returns parsed data."""
    collector = FredCollector(api_key="dummy-key")

    # Mock the _fetch_series method to return test data
    def mock_fetch(series_id, start_date=None, end_date=None):
        yields = {
            "DGS2": {"value": 4.25, "date": "2025-12-03", "series_id": "DGS2"},
            "DGS5": {"value": 4.35, "date": "2025-12-03", "series_id": "DGS5"},
            "DGS10": {"value": 4.50, "date": "2025-12-03", "series_id": "DGS10"},
            "DGS30": {"value": 4.75, "date": "2025-12-03", "series_id": "DGS30"},
        }
        return yields.get(series_id, {})

    collector._fetch_series = mock_fetch

    result = collector.get_treasury_yields()

    # get_treasury_yields returns short names like '2Y', '10Y'
    assert "2Y" in result
    assert "10Y" in result
    assert "30Y" in result
    assert result["2Y"] == 4.25
    assert result["10Y"] == 4.50


def test_fredcollector_yield_curve_spread():
    """Test yield curve spread calculation."""
    collector = FredCollector(api_key="dummy-key")

    # Mock T10Y2Y series (pre-computed 10Y-2Y spread)
    def mock_fetch(series_id, start_date=None, end_date=None):
        if series_id == "T10Y2Y":
            return {"value": 0.25, "date": "2025-12-03"}
        return {}

    collector._fetch_series = mock_fetch

    spread = collector.get_yield_curve_spread()

    assert spread == 0.25


def test_fredcollector_inverted_curve():
    """Test yield curve inversion detection."""
    collector = FredCollector(api_key="dummy-key")

    # Mock inverted curve (negative T10Y2Y spread)
    def mock_fetch(series_id, start_date=None, end_date=None):
        if series_id == "T10Y2Y":
            return {"value": -0.50, "date": "2025-12-03"}  # Inverted!
        return {}

    collector._fetch_series = mock_fetch

    assert collector.is_yield_curve_inverted() is True

import types

from src.rag.collectors import FredCollector
from src.rag.collectors.fred_collector import FREDCollector


def _fake_response(payload, status_code: int = 200):
    """Minimal fake requests.Response-like object."""
    resp = types.SimpleNamespace()
    resp.status_code = status_code
    resp.json = lambda: payload

    def raise_for_status():
        if status_code >= 400:
            raise Exception(f"HTTP {status_code}")

    resp.raise_for_status = raise_for_status
    return resp


def test_fredcollector_alias_and_get_series(monkeypatch):
    """Ensure camel-case alias works and get_series returns observations in order."""

    # Alias is exposed for backward compatibility
    assert FredCollector is FREDCollector

    # Mock requests.get used inside get_series
    called = {}

    def fake_get(url, params=None, timeout=None):
        called["url"] = url
        called["params"] = params
        return _fake_response(
            {
                "observations": [
                    {"date": "2025-12-03", "value": "4.06"},
                    {"date": "2025-12-02", "value": "4.02"},
                ]
            }
        )

    monkeypatch.setattr("src.rag.collectors.fred_collector.requests.get", fake_get)

    collector = FredCollector(api_key="dummy-key")
    obs = collector.get_series("DGS10", limit=2, sort_order="desc")

    assert called["url"].endswith("/fred/series/observations")
    assert called["params"]["series_id"] == "DGS10"
    assert called["params"]["sort_order"] == "desc"
    assert len(obs) == 2
    assert obs[0]["date"] == "2025-12-03"
    assert obs[0]["value"] == "4.06"

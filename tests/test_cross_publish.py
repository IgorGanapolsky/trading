from __future__ import annotations

from scripts import cross_publish


def test_absolutize_site_relative_urls_converts_markdown_and_html():
    body = """
![Paper](/trading/assets/snapshots/alpaca_paper_latest.png)
<img src="/trading/assets/snapshots/paperbanana_paper_latest.svg" />
"""
    updated = cross_publish.absolutize_site_relative_urls(
        body,
        "https://igorganapolsky.github.io/trading/reports/2026-02-19-daily-report/",
    )
    assert (
        "https://igorganapolsky.github.io/trading/assets/snapshots/alpaca_paper_latest.png"
        in updated
    )
    assert (
        'src="https://igorganapolsky.github.io/trading/assets/snapshots/paperbanana_paper_latest.svg"'
        in updated
    )


def test_publish_to_devto_treats_canonical_duplicate_as_success(monkeypatch):
    monkeypatch.setenv("DEVTO_API_KEY", "test-key")

    class DuplicateResp:
        status_code = 422
        text = (
            '{"error":"Canonical url has already been taken. Email support@dev.to for further details."}'
        )

        @staticmethod
        def json():
            return {}

    class ExistingResp:
        status_code = 200

        @staticmethod
        def json():
            return [
                {
                    "title": "Daily Report",
                    "canonical_url": "https://igorganapolsky.github.io/trading/reports/2026-02-19-daily-report/",
                    "url": "https://dev.to/igorganapolsky/daily-report-123",
                }
            ]

    def fake_post(*_args, **_kwargs):
        return DuplicateResp()

    def fake_get(*_args, **_kwargs):
        return ExistingResp()

    class UpdateResp:
        status_code = 200

        @staticmethod
        def json():
            return {"url": "https://dev.to/igorganapolsky/daily-report-123"}

    def fake_put(*_args, **_kwargs):
        return UpdateResp()

    monkeypatch.setattr(cross_publish.requests, "post", fake_post)
    monkeypatch.setattr(cross_publish.requests, "get", fake_get)
    monkeypatch.setattr(cross_publish.requests, "put", fake_put)

    url = cross_publish.publish_to_devto(
        "Daily Report",
        "Body",
        ["ai", "trading"],
        "https://igorganapolsky.github.io/trading/reports/2026-02-19-daily-report/",
    )
    assert url == "https://dev.to/igorganapolsky/daily-report-123"

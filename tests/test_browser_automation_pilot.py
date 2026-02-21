"""Tests for browser automation pilot analytics."""

from __future__ import annotations

import json
from pathlib import Path

from src.analytics.browser_automation_pilot import (
    AnchorBrowserProvider,
    BrowserPilotRunResult,
    LocalHTTPProvider,
    load_tasks,
    summarize_provider_results,
)


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "", payload: dict | None = None) -> None:
        self.status_code = status_code
        self.text = text
        self._payload = payload or {}

    def json(self) -> dict:
        return self._payload


def test_load_tasks_supports_tasks_wrapper(tmp_path: Path) -> None:
    config = tmp_path / "tasks.json"
    config.write_text(
        json.dumps(
            {
                "tasks": [
                    {
                        "task_id": "home",
                        "url": "https://example.com",
                        "prompt": "Open homepage",
                        "expected_text": "Example Domain",
                        "tags": ["smoke"],
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    tasks = load_tasks(config)
    assert len(tasks) == 1
    assert tasks[0].task_id == "home"
    assert tasks[0].expected_text == "Example Domain"


def test_local_provider_success(monkeypatch) -> None:
    provider = LocalHTTPProvider()
    task = load_tasks(Path("config/browser_automation_pilot_tasks.json"))[
        0
    ]  # has expected_text "AI Trading Journey"

    monkeypatch.setattr(
        "src.analytics.browser_automation_pilot.requests.get",
        lambda *a, **k: _FakeResponse(200, text="AI Trading Journey"),
    )

    result = provider.execute(task, run_index=1, timeout_seconds=2)
    assert result.status == "success"
    assert result.http_status == 200


def test_local_provider_expected_text_failure(monkeypatch) -> None:
    provider = LocalHTTPProvider()
    task = load_tasks(Path("config/browser_automation_pilot_tasks.json"))[
        0
    ]  # expects "AI Trading Journey"

    monkeypatch.setattr(
        "src.analytics.browser_automation_pilot.requests.get",
        lambda *a, **k: _FakeResponse(200, text="Mismatch content"),
    )

    result = provider.execute(task, run_index=1, timeout_seconds=2)
    assert result.status == "failed"
    assert "Expected text" in result.detail


def test_anchor_provider_skips_without_key() -> None:
    provider = AnchorBrowserProvider(api_key=None)
    task = load_tasks(Path("config/browser_automation_pilot_tasks.json"))[0]
    result = provider.execute(task, run_index=1, timeout_seconds=2)
    assert result.status == "skipped"
    assert "ANCHOR_API_KEY missing" in result.detail


def test_summary_cost_per_success() -> None:
    rows = [
        BrowserPilotRunResult(
            provider="anchor",
            task_id="a",
            run_index=1,
            status="success",
            detail="ok",
            started_at_utc="2026-02-21T00:00:00Z",
            latency_ms=100.0,
            retries=0,
            cost_usd=0.12,
        ),
        BrowserPilotRunResult(
            provider="anchor",
            task_id="b",
            run_index=1,
            status="failed",
            detail="fail",
            started_at_utc="2026-02-21T00:00:01Z",
            latency_ms=200.0,
            retries=1,
            cost_usd=0.0,
        ),
    ]
    summary = summarize_provider_results(rows)["anchor"]
    assert summary["attempted"] == 2
    assert summary["success"] == 1
    assert summary["failed"] == 1
    assert summary["success_rate"] == 0.5
    assert summary["cost_usd_total"] == 0.12
    assert summary["cost_per_success_usd"] == 0.12

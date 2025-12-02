from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.orchestration.adk_client import (  # noqa: E402
    ADKClientConfig,
    ADKOrchestratorClient,
    OrchestratorResult,
)


def test_result_parses_structured_payload() -> None:
    payload = {"symbol": "NVDA", "trade_summary": {"action": "BUY"}}
    result = OrchestratorResult(session_id="test", final_text=json.dumps(payload))

    parsed = result.as_structured()

    assert parsed == payload


def test_result_non_json_returns_none(caplog: pytest.LogCaptureFixture) -> None:
    result = OrchestratorResult(session_id="test", final_text="not json")

    parsed = result.as_structured()

    assert parsed is None
    assert "Failed to parse orchestrator response" in caplog.text


def test_run_structured_raises_when_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = ADKOrchestratorClient(config=ADKClientConfig(base_url="http://localhost:8080/api"))

    def fake_run(*_, **__) -> OrchestratorResult:
        return OrchestratorResult(session_id="abc", final_text="{}")

    monkeypatch.setattr(client, "run", fake_run)

    parsed = client.run_structured("QQQ")
    assert parsed == {}


def test_run_structured_allows_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    client = ADKOrchestratorClient()

    def fake_run(*_, **__) -> OrchestratorResult:
        return OrchestratorResult(session_id="abc", final_text="not json")

    monkeypatch.setattr(client, "run", fake_run)

    with pytest.raises(ValueError):
        client.run_structured("QQQ")

    parsed = client.run_structured("QQQ", require_json=False)
    assert parsed == {}

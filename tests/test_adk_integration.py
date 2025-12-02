from __future__ import annotations

from typing import Any

import pytest
from src.orchestration.adk_integration import (
    ADKDecision,
    ADKTradeAdapter,
    summarize_adk_decision,
)


class DummyClient:
    def __init__(self, responses: dict[str, dict[str, Any]]) -> None:
        self.responses = responses
        self.calls: list[str] = []

    def run_structured(
        self, *, symbol: str, context: dict[str, Any], require_json: bool
    ) -> dict[str, Any]:
        self.calls.append(symbol)
        return self.responses.get(symbol, {})


class DummyStore:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows

    def fetch_latest_by_ticker(self, ticker: str, limit: int = 10):
        return self._rows


def _decision_payload(action: str, confidence: float, position_size: float = 0.0) -> dict[str, Any]:
    return {
        "trade_summary": {
            "action": action,
            "confidence": confidence,
        },
        "risk": {
            "decision": "APPROVE",
            "position_size": position_size,
        },
        "execution": {"venue_preference": "alpaca"},
    }


def test_adapter_selects_highest_confidence(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = {
        "SPY": _decision_payload("BUY", 0.6, 100),
        "QQQ": _decision_payload("BUY", 0.8, 120),
    }
    adapter = ADKTradeAdapter(enabled=False)
    adapter.enabled = True
    adapter.client = DummyClient(responses)  # type: ignore[assignment]
    adapter._sentiment_store = DummyStore([])  # type: ignore[attr-defined]

    decision = adapter.evaluate(symbols=["SPY", "QQQ"], context={"mode": "paper"})

    assert decision is not None
    assert decision.symbol == "QQQ"
    assert decision.confidence == pytest.approx(0.8)
    assert adapter.client.calls == ["SPY", "QQQ"]  # type: ignore[union-attr]


def test_adapter_rejects_non_actionable_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = {
        "SPY": _decision_payload("HOLD", 0.9),
        "QQQ": {
            "trade_summary": {"action": "BUY", "confidence": 0.7},
            "risk": {"decision": "REJECT"},
        },
    }
    adapter = ADKTradeAdapter(enabled=False)
    adapter.enabled = True
    adapter.client = DummyClient(responses)  # type: ignore[assignment]
    adapter._sentiment_store = DummyStore([])  # type: ignore[attr-defined]

    decision = adapter.evaluate(symbols=["SPY", "QQQ"], context={})

    assert decision is None


def test_summarize_decision() -> None:
    decision = ADKDecision(
        symbol="NVDA",
        action="BUY",
        confidence=0.75,
        position_size=150.0,
        risk={"decision": "APPROVE"},
        execution={"order_type": "market"},
        sentiment={"score": 0.6},
        raw={},
    )

    summary = summarize_adk_decision(decision)

    assert summary["symbol"] == "NVDA"
    assert summary["action"] == "BUY"
    assert summary["confidence"] == 0.75
    assert summary["position_size"] == 150.0

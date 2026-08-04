"""Production path honesty: source labels and put-credit safety guard."""

from __future__ import annotations

from src.agents.rag_webhook import _source_header, format_rag_response
from src.safety.rag_safety_guard import RAGSafetyGuard


def test_source_header_never_claims_lancedb_for_defended():
    assert "defended" in _source_header("defended").lower()
    assert "lancedb" not in _source_header("defended").lower()
    assert "lancedb" in _source_header("lancedb").lower()
    assert "keyword" in _source_header("keyword").lower()


def test_format_rag_response_uses_source_label():
    text = format_rag_response(
        [{"id": "LL-1", "severity": "HIGH", "content": "stop at 200% credit"}],
        "stop loss",
        "defended",
    )
    assert "defended" in text.lower()
    assert "LanceDB" not in text
    assert "LL-1" in text


def test_safety_guard_put_credit_query_not_iron_condor_default(monkeypatch):
    captured: dict = {}

    def fake_retrieve(query, **kwargs):
        captured["query"] = query
        captured["kwargs"] = kwargs

        class R:
            lessons = [
                {
                    "id": "LL-test",
                    "severity": "CRITICAL",
                    "content": "CRITICAL stop loss inventory failure",
                }
            ]
            meta = {"path": "fts+hybrid+acl"}

        return R()

    monkeypatch.setattr(
        "src.rag.retrieve_for_trade.retrieve_for_trade",
        fake_retrieve,
    )

    guard = RAGSafetyGuard()
    out = guard.check_safety("SPY", 18.0, 0.15)
    assert "put credit" in captured["query"].lower()
    assert "iron condor" not in captured["query"].lower()
    assert captured["kwargs"].get("strategy_family") == "spy_put_credit"
    assert out.get("warning") is True
    assert out.get("source") == "defended"

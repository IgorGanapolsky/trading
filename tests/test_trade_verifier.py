"""Tests for the fail-closed RAG entry verifier."""

from __future__ import annotations

from src.rag.trade_verifier import TradeVerifier


def test_verifier_blocks_when_rag_is_unavailable() -> None:
    verifier = TradeVerifier()
    verifier.rag_available = False
    verifier.rag_engine = None

    approved, reason = verifier.verify_entry("SPY", "spy_put_credit", "15 delta")

    assert approved is False
    assert "blocked" in reason.lower()


def test_advisory_mode_must_be_explicit() -> None:
    verifier = TradeVerifier(fail_closed=False)
    verifier.rag_available = False
    verifier.rag_engine = None

    approved, reason = verifier.verify_entry("SPY", "spy_put_credit", "15 delta")

    assert approved is True
    assert "advisory-only" in reason.lower()


def test_verifier_blocks_search_errors() -> None:
    class BrokenRag:
        def search(self, *_args, **_kwargs):
            raise RuntimeError("index unavailable")

    verifier = TradeVerifier()
    verifier.rag_available = True
    verifier.rag_engine = BrokenRag()

    approved, reason = verifier.verify_entry("SPY", "spy_put_credit", "15 delta")

    assert approved is False
    assert "error" in reason.lower()

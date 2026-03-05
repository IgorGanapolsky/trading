"""Tests for scripts/pre_session_rag_check.py."""

from __future__ import annotations

from unittest.mock import patch

from src.utils.staleness_guard import ContextFreshnessResult


class _Source:
    def __init__(self) -> None:
        self.source = "rag_query_index"
        self.path = "data/rag/lessons_query.json"
        self.last_sync = "2026-03-04T00:00:00Z"
        self.age_minutes = 5.0
        self.max_age_minutes = 1440.0
        self.is_stale = False
        self.reason = "fresh"


def test_pre_session_blocks_on_stale_context(monkeypatch):
    import scripts.pre_session_rag_check as module

    monkeypatch.setenv("PRE_SESSION_AUTO_REFRESH_CONTEXT", "0")
    stale = ContextFreshnessResult(
        is_stale=True,
        blocking=True,
        checked_at="2026-03-04T12:00:00Z",
        stale_sources=["rag_query_index"],
        sources=[_Source()],
        reason="Stale context indexes detected: rag_query_index",
    )

    monkeypatch.setattr(module, "check_context_freshness", lambda is_market_day=True: stale)
    monkeypatch.setattr(module, "check_recent_critical_lessons", lambda **_: [])
    monkeypatch.setattr(module, "query_rag_for_operational_failures", lambda: [])
    monkeypatch.setattr(module.sys, "argv", ["pre_session_rag_check.py"])

    with patch.object(module.sys, "exit") as exit_mock:
        module.main()

    exit_mock.assert_called_once_with(1)


def test_pre_session_allows_when_context_fresh_and_no_recent_lessons(monkeypatch):
    import scripts.pre_session_rag_check as module

    monkeypatch.setenv("PRE_SESSION_AUTO_REFRESH_CONTEXT", "0")
    fresh = ContextFreshnessResult(
        is_stale=False,
        blocking=False,
        checked_at="2026-03-04T12:00:00Z",
        stale_sources=[],
        sources=[_Source()],
        reason="Context freshness check passed",
    )

    monkeypatch.setattr(module, "check_context_freshness", lambda is_market_day=True: fresh)
    monkeypatch.setattr(module, "check_recent_critical_lessons", lambda **_: [])
    monkeypatch.setattr(module, "query_rag_for_operational_failures", lambda: [])
    monkeypatch.setattr(module.sys, "argv", ["pre_session_rag_check.py", "--allow-warnings"])

    assert module.main() == 0

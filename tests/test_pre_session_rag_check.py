"""Tests for scripts/pre_session_rag_check.py."""

from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from scripts import pre_session_rag_check as pre
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
    monkeypatch.setenv("PRE_SESSION_AUTO_REFRESH_CONTEXT", "0")
    stale = ContextFreshnessResult(
        is_stale=True,
        blocking=True,
        checked_at="2026-03-04T12:00:00Z",
        stale_sources=["rag_query_index"],
        sources=[_Source()],
        reason="Stale context indexes detected: rag_query_index",
    )

    monkeypatch.setattr(pre, "check_context_freshness", lambda is_market_day=True: stale)
    monkeypatch.setattr(pre, "check_recent_critical_lessons", lambda **_: [])
    monkeypatch.setattr(pre, "query_rag_for_operational_failures", lambda: [])
    monkeypatch.setattr(pre.sys, "argv", ["pre_session_rag_check.py"])

    with patch.object(pre.sys, "exit") as exit_mock:
        pre.main()

    exit_mock.assert_called_once_with(1)


def test_pre_session_allows_when_context_fresh_and_no_recent_lessons(monkeypatch):
    monkeypatch.setenv("PRE_SESSION_AUTO_REFRESH_CONTEXT", "0")
    fresh = ContextFreshnessResult(
        is_stale=False,
        blocking=False,
        checked_at="2026-03-04T12:00:00Z",
        stale_sources=[],
        sources=[_Source()],
        reason="Context freshness check passed",
    )

    monkeypatch.setattr(pre, "check_context_freshness", lambda is_market_day=True: fresh)
    monkeypatch.setattr(pre, "check_recent_critical_lessons", lambda **_: [])
    monkeypatch.setattr(pre, "query_rag_for_operational_failures", lambda: [])
    monkeypatch.setattr(pre.sys, "argv", ["pre_session_rag_check.py", "--allow-warnings"])

    assert pre.main() == 0


def test_check_recent_lessons_parses_markdown_severity_and_month_name_date(
    tmp_path: Path, monkeypatch
):
    lessons_dir = tmp_path / "rag_knowledge" / "lessons_learned"
    lessons_dir.mkdir(parents=True)
    lesson = lessons_dir / "ll_parser_case.md"
    lesson.write_text(
        "# Parser Case\n\n**Severity:** HIGH\n\n**Date:** January 22, 2026\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(tmp_path)
    results = pre.check_recent_critical_lessons(days_back=400, include_high=True)
    hit = next((row for row in results if row["file"] == "ll_parser_case.md"), None)

    assert hit is not None
    assert hit["severity"] == "HIGH"
    assert hit["date"] == datetime(2026, 1, 22)


def test_script_help_runs_without_pythonpath() -> None:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "scripts/pre_session_rag_check.py", "--help"],
        cwd=Path(__file__).resolve().parents[1],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0
    assert "Pre-session RAG check" in result.stdout


def test_extract_lesson_date_from_title_before_file_mtime() -> None:
    content = """# LL-250: Trading Crisis - System Stuck for 7 Days (Jan 20, 2026)

## Severity: CRITICAL
"""

    parsed = pre._extract_lesson_date(content, Path("ll_250_trading_crisis_jan20_2026.md"))

    assert parsed is not None
    assert parsed.strftime("%Y-%m-%d") == "2026-01-20"

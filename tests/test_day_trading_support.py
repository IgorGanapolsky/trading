"""Unit tests for the day-trading support orchestrator."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.day_trading_support.config_loader import (
    DayTradingResourceConfig,
    load_resource_config,
)
from src.day_trading_support.mentor_monitor import MentorMonitorAgent
from src.day_trading_support.models import (
    BookLesson,
    BookResource,
    CoachingProgram,
    NewsletterResource,
    ReadingSegment,
    SessionTemplate,
)
from src.day_trading_support.newsletter_harvester import MarketPrepAgent
from src.day_trading_support.orchestrator import DayTradeSupportOrchestrator
from src.day_trading_support.reading_ingestor import StudyGuideAgent
from src.day_trading_support.resource_vault import ResourceVault


@pytest.fixture
def sample_yaml(tmp_path: Path) -> Path:
    yaml_text = """
coaching_programs:
  - name: Sample Program
    url: https://example.com
    timezone: America/New_York
    highlights:
      - Focus
    session_templates:
      - name: Daily Prep
        cadence: daily
        start_time: "08:00"
        duration_minutes: 30
        format: chatroom
        focus:
          - prep
    accountability_prompts:
      - Did you journal?
books:
  - title: Sample Book
    author: Jane Doe
    difficulty: beginner
    summary: Basics
    focus_tags:
      - foundation
    lessons:
      - title: Lesson
        trigger: Daily
        actions:
          - Do thing
    reading_plan:
      - label: Section 1
        goal: Learn
        minutes: 20
        difficulty: beginner
newsletters:
  - name: Sample Letter
    provider: Example
    url: https://example.com/newsletter
    feed_url: https://example.com/rss
    cadence: daily
    focus_tags:
      - macro
    emphasis:
      - macro
"""
    path = tmp_path / "resources.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


def test_load_resource_config(sample_yaml: Path) -> None:
    cfg = load_resource_config(sample_yaml)
    assert len(cfg.coaching_programs) == 1
    assert cfg.books[0].title == "Sample Book"
    assert cfg.newsletters[0].name == "Sample Letter"


def test_mentor_monitor_generates_future_sessions() -> None:
    program = CoachingProgram(
        name="Demo",
        url="https://demo",
        timezone="America/New_York",
        highlights=[],
        session_templates=[
            SessionTemplate(
                name="Prep",
                cadence="daily",
                start_time="05:00",
                duration_minutes=30,
                format="chatroom",
                focus=["prep"],
            )
        ],
        accountability_prompts=["Are you green?"],
        escalation_contacts=[],
    )
    agent = MentorMonitorAgent([program])
    reference = datetime(2025, 12, 1, 15, 0, tzinfo=timezone.utc)
    sessions = agent.build_schedule(reference_time=reference)
    assert sessions
    assert sessions[0].scheduled_for > reference


def test_study_agent_generates_assignments() -> None:
    book = BookResource(
        title="Guide",
        author="Author",
        difficulty="beginner",
        summary="",
        focus_tags=["psychology"],
        lessons=[
            BookLesson(title="Reset", trigger="loss", actions=["Stop trade"])
        ],
        reading_plan=[
            ReadingSegment(
                label="Chapter 1",
                goal="Routine",
                minutes=25,
                difficulty="beginner",
            )
        ],
    )
    agent = StudyGuideAgent([book])
    assignments = agent.generate_assignments(focus_tags=["psychology"], minutes=20)
    assert assignments
    assert assignments[0].book == "Guide"


def test_market_agent_extracts_tickers() -> None:
    newsletter = NewsletterResource(
        name="Mock",
        provider="Mock",
        url="https://mock",
        feed_url="mock://rss",
        cadence="daily",
        focus_tags=["macro"],
        emphasis=["macro"],
        window_hours=48,
    )

    def parser(_url: str):
        entry = {
            "title": "SPY rallies on CPI",
            "summary": "Traders rotate into QQQ and IWM ahead of Fed.",
            "published_parsed": (2025, 12, 1, 12, 0, 0, 0, 0, 0),
            "link": "https://mock/article",
        }
        return SimpleNamespace(entries=[entry])

    agent = MarketPrepAgent([newsletter], parser=parser)
    insights = agent.harvest(reference_time=datetime(2025, 12, 1, tzinfo=timezone.utc))
    assert insights
    assert set(insights[0].tickers) >= {"SPY", "QQQ", "IWM"}


def test_orchestrator_writes_plan(tmp_path: Path) -> None:
    program = CoachingProgram(
        name="Demo",
        url="https://demo",
        timezone="America/New_York",
        highlights=[],
        session_templates=[
            SessionTemplate(
                name="Prep",
                cadence="daily",
                start_time="05:00",
                duration_minutes=30,
                format="chatroom",
                focus=["prep"],
            )
        ],
        accountability_prompts=[],
        escalation_contacts=[],
    )
    book = BookResource(
        title="Guide",
        author="Author",
        difficulty="beginner",
        summary="",
        focus_tags=["psychology"],
        lessons=[
            BookLesson(title="Reset", trigger="loss", actions=["Stop trade"])
        ],
        reading_plan=[
            ReadingSegment(
                label="Chapter 1",
                goal="Routine",
                minutes=25,
                difficulty="beginner",
            )
        ],
    )
    newsletter = NewsletterResource(
        name="Mock",
        provider="Mock",
        url="https://mock",
        feed_url="mock://rss",
        cadence="daily",
        focus_tags=["macro"],
        emphasis=["macro"],
        window_hours=48,
    )

    def parser(_url: str):
        entry = {
            "title": "SPY rally",
            "summary": "SPY and QQQ rebound.",
            "published_parsed": (2025, 12, 1, 12, 0, 0, 0, 0, 0),
            "link": "https://mock/article",
        }
        return SimpleNamespace(entries=[entry])

    class _NullVectorStore:
        def upsert_documents(self, _docs):  # pragma: no cover - trivial
            return None

    class DummyVault(ResourceVault):
        def __init__(self, base: Path):
            super().__init__(
                storage_dir=base / "storage",
                report_dir=base / "reports",
                vector_store=_NullVectorStore(),
            )

    orchestrator = DayTradeSupportOrchestrator(
        config=DayTradingResourceConfig(
            coaching_programs=[program],
            books=[book],
            newsletters=[newsletter],
        ),
        mentor_agent=MentorMonitorAgent([program]),
        study_agent=StudyGuideAgent([book]),
        market_agent=MarketPrepAgent([newsletter], parser=parser),
        vault=DummyVault(tmp_path),
    )
    plan = orchestrator.run(focus_tags=["psychology"], study_minutes=20)
    assert plan.coaching and plan.reading and plan.newsletters
    assert (tmp_path / "reports").exists()

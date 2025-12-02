"""Load structured resource definitions from YAML configuration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from .models import (
    BookLesson,
    BookResource,
    CoachingProgram,
    NewsletterResource,
    ReadingSegment,
    SessionTemplate,
)

DEFAULT_CONFIG_PATH = Path("config/day_trading_resources.yaml")


@dataclass
class DayTradingResourceConfig:
    """Top-level configuration payload used by the orchestrator."""

    coaching_programs: list[CoachingProgram]
    books: list[BookResource]
    newsletters: list[NewsletterResource]

    def to_json(self) -> str:
        return json.dumps(
            {
                "coaching_programs": [cp.__dict__ for cp in self.coaching_programs],
                "books": [book.__dict__ for book in self.books],
                "newsletters": [nl.__dict__ for nl in self.newsletters],
            },
            indent=2,
            default=lambda obj: obj.__dict__,
        )


def _ensure_path(path: Path | None) -> Path:
    if path is not None:
        return path
    return DEFAULT_CONFIG_PATH


def _build_session_template(payload) -> SessionTemplate:
    return SessionTemplate(
        name=payload["name"],
        cadence=payload.get("cadence", "daily"),
        start_time=payload.get("start_time", "09:00"),
        duration_minutes=int(payload.get("duration_minutes", 60)),
        format=payload.get("format", "chatroom"),
        focus=list(payload.get("focus", [])),
        day_of_week=payload.get("day_of_week"),
        notes=list(payload.get("notes", [])),
    )


def _build_book(payload) -> BookResource:
    lessons = [
        BookLesson(
            title=item["title"],
            trigger=item.get("trigger", ""),
            actions=list(item.get("actions", [])),
        )
        for item in payload.get("lessons", [])
    ]
    plan = [
        ReadingSegment(
            label=item["label"],
            goal=item.get("goal", ""),
            minutes=int(item.get("minutes", 30)),
            difficulty=item.get("difficulty", payload.get("difficulty", "beginner")),
        )
        for item in payload.get("reading_plan", [])
    ]
    return BookResource(
        title=payload["title"],
        author=payload["author"],
        difficulty=payload.get("difficulty", "beginner"),
        summary=payload.get("summary", ""),
        focus_tags=list(payload.get("focus_tags", [])),
        lessons=lessons,
        reading_plan=plan,
    )


def _build_newsletter(payload) -> NewsletterResource:
    return NewsletterResource(
        name=payload["name"],
        provider=payload.get("provider", payload["name"]),
        url=payload.get("url", ""),
        feed_url=payload.get("feed_url"),
        cadence=payload.get("cadence", "daily"),
        focus_tags=list(payload.get("focus_tags", [])),
        emphasis=list(payload.get("emphasis", [])),
        window_hours=int(payload.get("window_hours", 24)),
    )


def _build_coaching_program(payload) -> CoachingProgram:
    sessions = [_build_session_template(item) for item in payload.get("session_templates", [])]
    return CoachingProgram(
        name=payload["name"],
        url=payload.get("url", ""),
        timezone=payload.get("timezone", "America/New_York"),
        highlights=list(payload.get("highlights", [])),
        session_templates=sessions,
        accountability_prompts=list(payload.get("accountability_prompts", [])),
        escalation_contacts=list(payload.get("escalation_contacts", [])),
    )


def load_resource_config(path: Path | None = None) -> DayTradingResourceConfig:
    """Load the YAML config (default path config/day_trading_resources.yaml)."""

    config_path = _ensure_path(path)
    if not config_path.exists():
        raise FileNotFoundError(
            f"Resource config not found at {config_path}. Create it before running."
        )

    with open(config_path, encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    coaching = [_build_coaching_program(item) for item in raw.get("coaching_programs", [])]
    books = [_build_book(item) for item in raw.get("books", [])]
    newsletters = [_build_newsletter(item) for item in raw.get("newsletters", [])]

    if not (coaching and books and newsletters):
        raise ValueError("Resource config must include coaching_programs, books, newsletters")

    return DayTradingResourceConfig(
        coaching_programs=coaching,
        books=books,
        newsletters=newsletters,
    )

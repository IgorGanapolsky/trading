"""Harvest actionable newsletter highlights for market prep."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable, Iterable
from datetime import datetime, timedelta, timezone

import feedparser

from .models import NewsletterInsight, NewsletterResource

logger = logging.getLogger(__name__)

FeedParser = Callable[[str], feedparser.FeedParserDict]


class MarketPrepAgent:
    """Fetches newsletters (Barchart, Bloomberg, etc.) and extracts signals."""

    def __init__(
        self,
        newsletters: Iterable[NewsletterResource],
        *,
        parser: FeedParser | None = None,
    ) -> None:
        self.newsletters = list(newsletters)
        self._parser = parser or feedparser.parse

    def harvest(self, *, reference_time: datetime | None = None) -> list[NewsletterInsight]:
        now = reference_time or datetime.now(timezone.utc)
        insights: list[NewsletterInsight] = []
        for resource in self.newsletters:
            if not resource.feed_url:
                logger.debug("Newsletter %s missing feed URL", resource.name)
                continue
            try:
                parsed = self._parser(resource.feed_url)
            except Exception as exc:  # pragma: no cover - network failure path
                logger.warning("Failed to fetch %s: %s", resource.name, exc)
                continue
            entries = getattr(parsed, "entries", [])[:5]
            for entry in entries:
                published = self._to_datetime(entry)
                if published and (now - published) > timedelta(hours=resource.window_hours):
                    continue
                text = " ".join(
                    filter(
                        None,
                        [
                            entry.get("title"),
                            entry.get("summary"),
                            entry.get("description"),
                        ],
                    )
                )
                tickers = self._extract_tickers(text)
                urgency = "high" if "breaking" in text.lower() else "normal"
                insight = NewsletterInsight(
                    source=resource.name,
                    headline=entry.get("title", ""),
                    summary=text[:280],
                    tickers=tickers,
                    urgency=urgency,
                    link=entry.get("link"),
                )
                insights.append(insight)
        return insights

    @staticmethod
    def _to_datetime(entry) -> datetime | None:
        published = entry.get("published_parsed") or entry.get("updated_parsed")
        if published:
            return datetime(*published[:6], tzinfo=timezone.utc)
        if entry.get("published"):
            try:
                return datetime.fromisoformat(entry["published"])
            except Exception:  # pragma: no cover - best effort
                return None
        return None

    @staticmethod
    def _extract_tickers(text: str) -> list[str]:
        if not text:
            return []
        pattern = r"\b[A-Z]{2,5}\b"
        tickers = re.findall(pattern, text)
        return sorted({ticker for ticker in tickers if ticker.isalpha()})

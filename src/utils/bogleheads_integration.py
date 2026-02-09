"""
Bogleheads forum integration utilities.

Primary path: pull live feed entries from the forum (if available).
Fallback path: read normalized RAG cache stored under data/rag/normalized.
"""

from __future__ import annotations

import json
import os
import re
import urllib.request
from datetime import datetime, timezone
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

PROJECT_ROOT = Path(__file__).resolve().parents[2]
NORMALIZED_DIR = PROJECT_ROOT / "data" / "rag" / "normalized"
DEFAULT_FEED_URLS = [
    "https://www.bogleheads.org/forum/feed.php",
    "https://www.bogleheads.org/forum/feed.php?mode=active",
    "https://www.bogleheads.org/forum/feed.php?mode=news",
    "https://www.bogleheads.org/forum/feed.php?f=10",
]
FEED_TIMEOUT_SEC = 10


@dataclass(frozen=True)
class BogleheadsEntry:
    title: str
    content: str
    url: str
    published_date: str | None
    ticker: str | None
    sentiment: float | None
    rating: str | None
    rating_score: float | None
    source: str | None
    collected_at: str | None


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _load_feed_urls() -> list[str]:
    configured = os.getenv("BOGLEHEADS_FEED_URLS", "").strip()
    if configured:
        urls = [url.strip() for url in configured.split(",") if url.strip()]
        if urls:
            return urls
    return DEFAULT_FEED_URLS


def _fetch_url(url: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; BogleheadsLearner/1.0)",
            "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=FEED_TIMEOUT_SEC) as response:
        return response.read()


def _parse_feed_bytes(payload: bytes) -> list[dict[str, Any]]:
    try:
        import feedparser  # type: ignore

        feed = feedparser.parse(payload)
        return list(feed.entries)
    except Exception:
        return []


def _extract_entry_content(entry: dict[str, Any]) -> str:
    for field in ("summary", "description", "content"):
        value = entry.get(field)
        if isinstance(value, list) and value:
            candidate = value[0].get("value")
        else:
            candidate = value
        if candidate:
            return str(candidate)
    return ""


def _extract_entry_link(entry: dict[str, Any]) -> str:
    link = entry.get("link")
    if link:
        return str(link)
    links = entry.get("links")
    if isinstance(links, list):
        for item in links:
            href = item.get("href")
            if href:
                return str(href)
    return ""


def _extract_entry_date(entry: dict[str, Any]) -> str | None:
    for field in ("published", "updated", "pubDate", "date"):
        value = entry.get(field)
        if value:
            return str(value)
    return None


def _score_sentiment(text: str) -> float:
    positive = {
        "buy",
        "bull",
        "bullish",
        "uptrend",
        "growth",
        "opportunity",
        "undervalued",
        "strong",
        "positive",
    }
    negative = {
        "sell",
        "bear",
        "bearish",
        "downtrend",
        "recession",
        "risk",
        "overvalued",
        "weak",
        "negative",
    }
    tokens = re.findall(r"[A-Za-z]+", text.lower())
    if not tokens:
        return 0.0
    pos = sum(1 for token in tokens if token in positive)
    neg = sum(1 for token in tokens if token in negative)
    score = (pos - neg) / max(pos + neg, 1)
    return max(min(score, 1.0), -1.0)


def _iter_normalized_entries(max_files: int = 50) -> Iterable[dict[str, Any]]:
    if not NORMALIZED_DIR.exists():
        return []

    files = sorted(
        NORMALIZED_DIR.glob("*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:max_files]

    entries: list[dict[str, Any]] = []
    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue

        if isinstance(payload, list):
            entries.extend(item for item in payload if isinstance(item, dict))
        elif isinstance(payload, dict):
            items = payload.get("items")
            if isinstance(items, list):
                entries.extend(item for item in items if isinstance(item, dict))

    return entries


def _fetch_live_entries(max_items: int = 100) -> tuple[list[BogleheadsEntry], str | None]:
    urls = _load_feed_urls()
    for url in urls:
        try:
            payload = _fetch_url(url)
            entries = _parse_feed_bytes(payload)
            if not entries:
                continue
            parsed_entries: list[BogleheadsEntry] = []
            for entry in entries[:max_items]:
                title = str(entry.get("title") or "")
                content = _extract_entry_content(entry)
                parsed_entries.append(
                    BogleheadsEntry(
                        title=title,
                        content=content,
                        url=_extract_entry_link(entry),
                        published_date=_extract_entry_date(entry),
                        ticker=None,
                        sentiment=_score_sentiment(f"{title} {content}"),
                        rating=None,
                        rating_score=None,
                        source="bogleheads",
                        collected_at=datetime.now(timezone.utc).isoformat(),
                    )
                )
            if parsed_entries:
                return parsed_entries, url
        except Exception:
            continue
    return [], None


def _to_entry(raw: dict[str, Any]) -> BogleheadsEntry:
    return BogleheadsEntry(
        title=str(raw.get("title") or ""),
        content=str(raw.get("content") or ""),
        url=str(raw.get("url") or ""),
        published_date=raw.get("published_date"),
        ticker=raw.get("ticker"),
        sentiment=_safe_float(raw.get("sentiment")),
        rating=raw.get("rating"),
        rating_score=_safe_float(raw.get("rating_score")),
        source=raw.get("source"),
        collected_at=raw.get("collected_at"),
    )


def _filter_bogleheads(entries: Iterable[dict[str, Any]]) -> list[BogleheadsEntry]:
    filtered: list[BogleheadsEntry] = []
    for raw in entries:
        source = str(raw.get("source") or "").lower()
        if source != "bogleheads":
            continue
        filtered.append(_to_entry(raw))
    return filtered


def _entry_sentiment(entry: BogleheadsEntry) -> float:
    if entry.sentiment is not None:
        return entry.sentiment
    return _score_sentiment(f"{entry.title} {entry.content}")


def _entry_matches_symbol(entry: BogleheadsEntry, symbol: str) -> bool:
    symbol_upper = symbol.upper()
    if entry.ticker and entry.ticker.upper() == symbol_upper:
        return True
    pattern = rf"\\b{re.escape(symbol_upper)}\\b"
    return bool(re.search(pattern, entry.title.upper()) or re.search(pattern, entry.content.upper()))


def _get_bogleheads_entries(max_items: int = 100) -> tuple[list[BogleheadsEntry], str]:
    live_entries, feed_url = _fetch_live_entries(max_items=max_items)
    if live_entries:
        return live_entries, f"live_feed:{feed_url}"
    return _filter_bogleheads(_iter_normalized_entries()), "local_cache"


class BogleheadsLearner:
    """
    Lightweight Bogleheads learner backed by local normalized RAG cache.
    """

    def monitor_bogleheads_forum(
        self,
        topics: list[str] | None = None,
        keywords: list[str] | None = None,
        max_posts: int = 50,
    ) -> dict[str, Any]:
        entries, source = _get_bogleheads_entries(max_items=max_posts * 2)

        keyword_terms = [k.lower() for k in (keywords or [])]
        if keyword_terms:
            entries = [
                entry
                for entry in entries
                if any(
                    term in entry.title.lower() or term in entry.content.lower()
                    for term in keyword_terms
                )
            ]

        payload = [
            {
                "title": entry.title,
                "url": entry.url,
                "published_date": entry.published_date,
                "ticker": entry.ticker,
                "sentiment": _entry_sentiment(entry),
                "rating": entry.rating,
                "rating_score": entry.rating_score,
                "source": entry.source,
                "collected_at": entry.collected_at,
            }
            for entry in entries[:max_posts]
        ]

        return {
            "status": "ok",
            "source": source,
            "topics": topics or [],
            "keywords": keywords or [],
            "count": len(payload),
            "items": payload,
        }


def get_bogleheads_signal_for_symbol(
    symbol: str, market_context: dict[str, Any] | None = None
) -> dict[str, Any]:
    entries = _filter_bogleheads(_iter_normalized_entries())
    symbol_upper = symbol.upper()
    symbol_entries = [entry for entry in entries if (entry.ticker or "").upper() == symbol_upper]

    sentiments = [_entry_sentiment(entry) for entry in symbol_entries]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

    if avg_sentiment >= 0.2:
        signal = "bullish"
    elif avg_sentiment <= -0.2:
        signal = "bearish"
    else:
        signal = "neutral"

    return {
        "symbol": symbol.upper(),
        "signal": signal,
        "avg_sentiment": avg_sentiment,
        "samples": len(sentiments),
        "source": source,
        "market_context": market_context or {},
    }


def get_bogleheads_regime() -> dict[str, Any]:
    entries, source = _get_bogleheads_entries(max_items=200)
    sentiments = [_entry_sentiment(entry) for entry in entries]
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0

    if avg_sentiment >= 0.25:
        regime = "risk_on"
    elif avg_sentiment <= -0.25:
        regime = "risk_off"
    else:
        regime = "neutral"

    return {
        "regime": regime,
        "avg_sentiment": avg_sentiment,
        "samples": len(sentiments),
        "source": source,
    }

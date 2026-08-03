"""Bounded, public-feed ingestion for Bogleheads research.

This corpus is deliberately isolated from the trading lesson/tool-call gate.
Forum discussions are untrusted research inputs, not trading policy or proof.
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import sqlite3
import threading
import unicodedata
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence
from urllib.parse import urlparse, urlunparse

import requests
from defusedxml import ElementTree as ET

FEED_URL = "https://www.bogleheads.org/forum/feed.php"
ALLOWED_HOSTS = frozenset({"bogleheads.org", "www.bogleheads.org"})
MAX_FEED_BYTES = 2_000_000
MAX_DOCUMENT_CHARS = 20_000
SCHEMA_VERSION = 1
_TOKEN_RE = re.compile(r"[A-Za-z0-9]{2,}")


class BogleheadsIngestionError(ValueError):
    """Raised when a remote or parsed document violates the ingestion contract."""


class _VisibleTextParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1
        elif tag.lower() in {"br", "p", "div", "li", "blockquote"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth:
            self._skip_depth -= 1
        elif tag.lower() in {"p", "div", "li", "blockquote"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def normalize_public_text(value: str, *, max_chars: int = MAX_DOCUMENT_CHARS) -> str:
    """Return bounded visible text without control characters or markup."""
    parser = _VisibleTextParser()
    parser.feed(html.unescape(value or ""))
    parser.close()
    normalized = unicodedata.normalize("NFKC", "".join(parser.parts))
    normalized = "\n".join(" ".join(line.split()) for line in normalized.splitlines())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized).strip()
    return normalized[:max_chars]


def canonicalize_bogleheads_url(value: str) -> str:
    parsed = urlparse(value.strip())
    if parsed.scheme != "https" or (parsed.hostname or "").lower() not in ALLOWED_HOSTS:
        raise BogleheadsIngestionError("source URL must be HTTPS on bogleheads.org")
    return urlunparse(("https", parsed.netloc.lower(), parsed.path, "", parsed.query, ""))


@dataclass(frozen=True)
class ForumDocument:
    document_id: str
    title: str
    url: str
    author: str
    published_at: str
    fetched_at: str
    text: str
    content_hash: str
    source: str = "bogleheads_public_atom"
    trust_level: str = "untrusted_research"

    def metadata(self) -> dict[str, Any]:
        return {
            "author": self.author,
            "published_at": self.published_at,
            "fetched_at": self.fetched_at,
            "source": self.source,
            "trust_level": self.trust_level,
            "url": self.url,
        }


@dataclass(frozen=True)
class ForumIngestionReport:
    discovered: int
    inserted: int
    updated: int
    unchanged: int
    rejected: int
    chunks_written: int


def _document_id(url: str) -> str:
    return f"bogleheads-{hashlib.sha256(url.encode('utf-8')).hexdigest()[:24]}"


def _build_document(
    *,
    title: str,
    url: str,
    author: str,
    published_at: str,
    fetched_at: str,
    text: str,
) -> ForumDocument:
    canonical_url = canonicalize_bogleheads_url(url)
    clean_title = normalize_public_text(title, max_chars=300)
    clean_text = normalize_public_text(text)
    clean_author = normalize_public_text(author, max_chars=120)
    if len(clean_title) < 3:
        raise BogleheadsIngestionError("document title is missing")
    if not clean_text:
        clean_text = clean_title
    digest_input = json.dumps(
        {"title": clean_title, "text": clean_text, "url": canonical_url},
        sort_keys=True,
        ensure_ascii=True,
    )
    return ForumDocument(
        document_id=_document_id(canonical_url),
        title=clean_title,
        url=canonical_url,
        author=clean_author,
        published_at=published_at.strip(),
        fetched_at=fetched_at,
        text=clean_text,
        content_hash=hashlib.sha256(digest_input.encode("utf-8")).hexdigest(),
    )


def parse_atom_feed(
    payload: bytes,
    *,
    limit: int = 15,
    fetched_at: str | None = None,
) -> tuple[list[ForumDocument], int]:
    """Parse a bounded Atom feed and return accepted documents plus rejects."""
    if not 1 <= limit <= 100:
        raise BogleheadsIngestionError("limit must be between 1 and 100")
    if len(payload) > MAX_FEED_BYTES:
        raise BogleheadsIngestionError("feed exceeds maximum size")
    upper_prefix = payload[:4096].upper()
    if b"<!DOCTYPE" in upper_prefix or b"<!ENTITY" in upper_prefix:
        raise BogleheadsIngestionError("DTD/entity declarations are not accepted")
    try:
        root = ET.fromstring(payload)
    except ET.ParseError as exc:
        raise BogleheadsIngestionError("feed is not valid XML") from exc

    namespace = {"atom": "http://www.w3.org/2005/Atom"}
    observed_at = fetched_at or datetime.now(UTC).isoformat()
    documents: list[ForumDocument] = []
    rejected = 0
    for entry in root.findall("atom:entry", namespace)[:limit]:
        title = entry.findtext("atom:title", default="", namespaces=namespace)
        author = entry.findtext("atom:author/atom:name", default="", namespaces=namespace)
        published_at = entry.findtext("atom:updated", default="", namespaces=namespace)
        content = entry.findtext("atom:content", default="", namespaces=namespace)
        link = next(
            (
                node.attrib.get("href", "")
                for node in entry.findall("atom:link", namespace)
                if node.attrib.get("rel", "alternate") == "alternate"
            ),
            "",
        )
        try:
            documents.append(
                _build_document(
                    title=title,
                    url=link,
                    author=author,
                    published_at=published_at,
                    fetched_at=observed_at,
                    text=content,
                )
            )
        except BogleheadsIngestionError:
            rejected += 1
    return documents, rejected


def fetch_public_feed(
    *,
    limit: int = 15,
    session: requests.Session | None = None,
    timeout_seconds: float = 15.0,
) -> tuple[list[ForumDocument], int]:
    """Fetch one public feed request; no credentials, cookies, or private pages."""
    client = session or requests.Session()
    response = client.get(
        FEED_URL,
        headers={
            "User-Agent": "TradingResearchBot/1.0 (+https://github.com/IgorGanapolsky/trading)"
        },
        timeout=timeout_seconds,
        allow_redirects=True,
    )
    response.raise_for_status()
    canonicalize_bogleheads_url(response.url)
    content_length = int(response.headers.get("content-length", "0") or 0)
    if content_length > MAX_FEED_BYTES or len(response.content) > MAX_FEED_BYTES:
        raise BogleheadsIngestionError("feed exceeds maximum size")
    return parse_atom_feed(response.content, limit=limit)


def chunk_document(text: str, *, max_chars: int = 1_200, overlap_chars: int = 160) -> list[str]:
    """Create bounded paragraph-aware chunks with deterministic overlap."""
    if max_chars < 200 or not 0 <= overlap_chars < max_chars:
        raise ValueError("invalid chunk bounds")
    paragraphs = [part.strip() for part in text.split("\n\n") if part.strip()]
    if not paragraphs:
        return []
    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        pieces = [paragraph[i : i + max_chars] for i in range(0, len(paragraph), max_chars)]
        for piece in pieces:
            candidate = f"{current}\n\n{piece}".strip() if current else piece
            if len(candidate) <= max_chars:
                current = candidate
                continue
            if current:
                chunks.append(current)
            prefix = current[-overlap_chars:] if current and overlap_chars else ""
            current = f"{prefix}\n\n{piece}".strip()
            if len(current) > max_chars:
                chunks.append(current[:max_chars])
                current = current[max_chars - overlap_chars :]
    if current:
        chunks.append(current)
    return chunks


_SCHEMA = """
CREATE TABLE IF NOT EXISTS forum_documents (
    document_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT NOT NULL UNIQUE,
    author TEXT NOT NULL,
    published_at TEXT NOT NULL,
    fetched_at TEXT NOT NULL,
    text TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    version INTEGER NOT NULL,
    source TEXT NOT NULL,
    trust_level TEXT NOT NULL,
    metadata_json TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS forum_chunks (
    rowid INTEGER PRIMARY KEY AUTOINCREMENT,
    chunk_id TEXT NOT NULL UNIQUE,
    document_id TEXT NOT NULL REFERENCES forum_documents(document_id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL
);
CREATE VIRTUAL TABLE IF NOT EXISTS forum_chunks_fts USING fts5(
    title, content, document_id UNINDEXED, chunk_id UNINDEXED,
    content='forum_chunks', content_rowid='rowid', tokenize='unicode61 remove_diacritics 2'
);
CREATE TRIGGER IF NOT EXISTS forum_chunks_ai AFTER INSERT ON forum_chunks BEGIN
    INSERT INTO forum_chunks_fts(rowid, title, content, document_id, chunk_id)
    VALUES (new.rowid, new.title, new.content, new.document_id, new.chunk_id);
END;
CREATE TRIGGER IF NOT EXISTS forum_chunks_ad AFTER DELETE ON forum_chunks BEGIN
    INSERT INTO forum_chunks_fts(forum_chunks_fts, rowid, title, content, document_id, chunk_id)
    VALUES ('delete', old.rowid, old.title, old.content, old.document_id, old.chunk_id);
END;
"""


class BogleheadsResearchStore:
    """Transactional SQLite/FTS5 store for public forum research."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self._conn = sqlite3.connect(str(self.path), timeout=5.0, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(_SCHEMA)
        self._conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> BogleheadsResearchStore:
        return self

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        del exc_type, exc, traceback
        self.close()

    def sync(
        self, documents: Sequence[ForumDocument], *, rejected: int = 0
    ) -> ForumIngestionReport:
        inserted = updated = unchanged = chunks_written = 0
        with self._lock:
            try:
                self._conn.execute("BEGIN IMMEDIATE")
                for document in documents:
                    existing = self._conn.execute(
                        "SELECT content_hash, version FROM forum_documents WHERE document_id = ?",
                        (document.document_id,),
                    ).fetchone()
                    if existing and existing["content_hash"] == document.content_hash:
                        self._conn.execute(
                            "UPDATE forum_documents SET fetched_at = ?, active = 1 WHERE document_id = ?",
                            (document.fetched_at, document.document_id),
                        )
                        unchanged += 1
                        continue
                    version = int(existing["version"] + 1) if existing else 1
                    self._conn.execute(
                        """
                        INSERT INTO forum_documents (
                            document_id, title, url, author, published_at, fetched_at,
                            text, content_hash, version, source, trust_level,
                            metadata_json, active
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1)
                        ON CONFLICT(document_id) DO UPDATE SET
                            title=excluded.title, url=excluded.url, author=excluded.author,
                            published_at=excluded.published_at, fetched_at=excluded.fetched_at,
                            text=excluded.text, content_hash=excluded.content_hash,
                            version=excluded.version, source=excluded.source,
                            trust_level=excluded.trust_level,
                            metadata_json=excluded.metadata_json, active=1
                        """,
                        (
                            document.document_id,
                            document.title,
                            document.url,
                            document.author,
                            document.published_at,
                            document.fetched_at,
                            document.text,
                            document.content_hash,
                            version,
                            document.source,
                            document.trust_level,
                            json.dumps(document.metadata(), sort_keys=True),
                        ),
                    )
                    self._conn.execute(
                        "DELETE FROM forum_chunks WHERE document_id = ?", (document.document_id,)
                    )
                    chunks = chunk_document(document.text) or [document.title]
                    for index, content in enumerate(chunks):
                        self._conn.execute(
                            """
                            INSERT INTO forum_chunks (
                                chunk_id, document_id, chunk_index, title, content
                            ) VALUES (?, ?, ?, ?, ?)
                            """,
                            (
                                f"{document.document_id}::v{version}::c{index}",
                                document.document_id,
                                index,
                                document.title,
                                content,
                            ),
                        )
                    chunks_written += len(chunks)
                    if existing:
                        updated += 1
                    else:
                        inserted += 1
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise
        return ForumIngestionReport(
            discovered=len(documents) + rejected,
            inserted=inserted,
            updated=updated,
            unchanged=unchanged,
            rejected=rejected,
            chunks_written=chunks_written,
        )

    @staticmethod
    def _fts_query(query: str) -> str:
        tokens = _TOKEN_RE.findall(query)[:12]
        if not tokens:
            raise ValueError("search query has no usable terms")
        return " OR ".join(f'"{token}"' for token in tokens)

    def search(self, query: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if not 1 <= limit <= 50:
            raise ValueError("limit must be between 1 and 50")
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT d.document_id, d.title, d.url, d.author, d.published_at,
                       d.fetched_at, d.version, d.source, d.trust_level,
                       c.chunk_id, c.content,
                       bm25(forum_chunks_fts, 3.0, 1.0, 0.1, 0.1) AS rank
                FROM forum_chunks_fts
                JOIN forum_chunks c ON c.rowid = forum_chunks_fts.rowid
                JOIN forum_documents d ON d.document_id = c.document_id
                WHERE forum_chunks_fts MATCH ? AND d.active = 1
                ORDER BY rank ASC
                LIMIT ?
                """,
                (self._fts_query(query), limit * 3),
            ).fetchall()
        deduped: dict[str, dict[str, Any]] = {}
        for row in rows:
            item = dict(row)
            deduped.setdefault(item["document_id"], item)
            if len(deduped) >= limit:
                break
        return list(deduped.values())


def documents_as_json(documents: Sequence[ForumDocument]) -> list[dict[str, Any]]:
    return [asdict(document) for document in documents]

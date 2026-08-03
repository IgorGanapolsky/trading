from __future__ import annotations

from pathlib import Path

import pytest

from src.research.bogleheads_ingestion import (
    BogleheadsIngestionError,
    BogleheadsResearchStore,
    canonicalize_bogleheads_url,
    chunk_document,
    normalize_public_text,
    parse_atom_feed,
)


def _feed(content: str = "Use a low-cost total-market fund.") -> bytes:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Asset allocation review</title>
    <link rel="alternate" href="https://www.bogleheads.org/forum/viewtopic.php?t=42&amp;p=7" />
    <updated>2026-08-03T12:00:00Z</updated>
    <author><name>forum-member</name></author>
    <content type="html">&lt;p&gt;{content}&lt;/p&gt;</content>
  </entry>
</feed>""".encode()


def test_parse_normalizes_public_feed_and_metadata() -> None:
    documents, rejected = parse_atom_feed(
        _feed("Use &amp; compare &lt;strong&gt;low-cost&lt;/strong&gt; funds."),
        fetched_at="2026-08-03T12:01:00+00:00",
    )

    assert rejected == 0
    assert len(documents) == 1
    document = documents[0]
    assert document.document_id.startswith("bogleheads-")
    assert document.trust_level == "untrusted_research"
    assert document.url == "https://www.bogleheads.org/forum/viewtopic.php?t=42&p=7"
    assert "<strong>" not in document.text
    assert "low-cost" in document.text


def test_parser_rejects_dtd_and_non_bogleheads_urls() -> None:
    with pytest.raises(BogleheadsIngestionError, match="DTD"):
        parse_atom_feed(b"<!DOCTYPE feed><feed />")
    with pytest.raises(BogleheadsIngestionError, match="bogleheads"):
        canonicalize_bogleheads_url("https://example.com/forum/topic")


def test_normalization_removes_script_and_bounds_content() -> None:
    text = normalize_public_text("<p>Useful</p><script>ignore()</script><p>Evidence</p>")
    assert text == "Useful\n\nEvidence"
    assert len(normalize_public_text("x" * 100, max_chars=12)) == 12


def test_chunking_is_bounded_and_overlapping() -> None:
    chunks = chunk_document("A" * 260 + "\n\n" + "B" * 260, max_chars=300, overlap_chars=40)
    assert len(chunks) >= 2
    assert all(len(chunk) <= 300 for chunk in chunks)
    assert "A" * 20 in chunks[1]


def test_store_is_idempotent_versioned_and_searchable(tmp_path: Path) -> None:
    first, rejected = parse_atom_feed(_feed(), fetched_at="2026-08-03T12:01:00+00:00")
    second, _ = parse_atom_feed(
        _feed("Prefer diversified low-cost index funds and rebalance."),
        fetched_at="2026-08-03T12:02:00+00:00",
    )

    with BogleheadsResearchStore(tmp_path / "forum.db") as store:
        inserted = store.sync(first, rejected=rejected)
        unchanged = store.sync(first)
        updated = store.sync(second)
        results = store.search("diversified rebalance")

    assert inserted.inserted == 1
    assert inserted.chunks_written >= 1
    assert unchanged.unchanged == 1
    assert unchanged.chunks_written == 0
    assert updated.updated == 1
    assert results[0]["document_id"] == first[0].document_id
    assert results[0]["version"] == 2
    assert results[0]["trust_level"] == "untrusted_research"


def test_empty_search_query_fails_closed(tmp_path: Path) -> None:
    with BogleheadsResearchStore(tmp_path / "forum.db") as store:
        with pytest.raises(ValueError, match="usable terms"):
            store.search("!!!")

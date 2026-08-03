"""Unit tests for Bogleheads automation (no live Chrome/post)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from src.integrations.bogleheads.participate import draft_reply, save_draft
from src.integrations.bogleheads.promote import promote_threads, thread_to_markdown
from src.integrations.bogleheads.rss import score_relevance


def test_score_relevance_prefers_tax_and_allocation():
    high = score_relevance("Section 1256 tax treatment and three fund portfolio VTSAX")
    low = score_relevance("random cat photos weekend")
    assert high > low
    assert high >= 0.25
    assert low == 0.0


def test_thread_to_markdown_contains_url_and_disclaimer():
    md = thread_to_markdown(
        {
            "id": "bh_t1",
            "title": "Tax efficient fund placement",
            "link": "https://www.bogleheads.org/forum/viewtopic.php?t=1",
            "author": "poster",
            "snippet": "Roth vs taxable",
            "relevance_score": 0.5,
        }
    )
    assert "Tax efficient" in md
    assert "viewtopic.php" in md
    assert "not" in md.lower() and "trade signal" in md.lower()


def test_promote_threads_writes_once(tmp_path: Path):
    rag = tmp_path / "bogle"
    threads = [
        {
            "id": "bh_t99",
            "title": "Asset allocation and rebalance bands",
            "link": "https://example.test/t/99",
            "author": "a",
            "snippet": "three fund vti",
            "relevance_score": 0.8,
        }
    ]
    first = promote_threads(threads, rag_dir=rag, min_relevance=0.2, max_promote=5)
    second = promote_threads(threads, rag_dir=rag, min_relevance=0.2, max_promote=5)
    assert len(first["written"]) == 1
    assert len(second["written"]) == 0
    assert len(second["skipped_existing"]) == 1
    assert list(rag.glob("*.md"))


def test_draft_reply_mentions_tax_when_relevant():
    body = draft_reply(
        {
            "title": "Wash sale and Roth conversion tax",
            "snippet": "ira tax 1256",
            "relevance_score": 0.9,
        }
    )
    assert "tax" in body.lower()
    assert "not advice" in body.lower()


def test_save_draft(tmp_path: Path):
    path = save_draft(
        {"id": "bh_t2", "title": "FI withdrawal", "link": "https://x", "relevance_score": 0.5},
        "Hello world",
        draft_dir=tmp_path,
    )
    assert path.exists()
    assert "Hello world" in path.read_text(encoding="utf-8")


def test_credentials_masked_shape():
    from src.integrations.bogleheads.credentials import BogleheadsCredentials

    c = BogleheadsCredentials(email="a@b.com", username="u", password="secret!!")
    m = c.masked()
    assert m["username"] == "u"
    assert m["password_len"] == 8
    assert "secret" not in str(m)


def test_rss_fetch_parses_atom():
    atom = """<?xml version="1.0" encoding="utf-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Three fund portfolio tax</title>
        <link href="https://www.bogleheads.org/forum/viewtopic.php?t=42"/>
        <updated>2026-08-01T00:00:00Z</updated>
        <author><name>alice</name></author>
        <content type="html">VTSAX and bonds</content>
      </entry>
    </feed>
    """

    class FakeResp:
        text = atom

        def raise_for_status(self):
            return None

    with patch("src.integrations.bogleheads.rss.requests.get", return_value=FakeResp()):
        from src.integrations.bogleheads.rss import fetch_bogleheads_feed

        entries = fetch_bogleheads_feed(limit=5)
    assert len(entries) == 1
    assert entries[0]["id"] == "bh_t42"
    assert entries[0]["relevance_score"] > 0

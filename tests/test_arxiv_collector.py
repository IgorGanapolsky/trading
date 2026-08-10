"""Unit tests for continuous arXiv paper ingestion (AGENT-364)."""

from __future__ import annotations

import json
import urllib.error
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline
from src.research.arxiv_collector import (
    ArxivCollector,
    ArxivPaper,
    DEFAULT_MIN_RELEVANCE,
)


SAMPLE_ATOM_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2608.12345v1</id>
    <published>2026-08-10T12:00:00Z</published>
    <updated>2026-08-10T12:00:00Z</updated>
    <title>Deep Reinforcement Learning for Option Trading under Microstructure Noise</title>
    <summary>
      We propose a novel GRPO policy optimization algorithm for option credit spreads
      and SPY put credit risk management with retrieval-augmented grounding.
    </summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
    <category term="q-fin.TR"/>
    <category term="cs.AI"/>
    <link href="http://arxiv.org/abs/2608.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2608.12345v1.pdf" title="pdf" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2608.00001v1</id>
    <published>2026-08-09T12:00:00Z</published>
    <updated>2026-08-09T12:00:00Z</updated>
    <title>A Taxonomy of Unrelated Computer Vision Benchmarks</title>
    <summary>We catalog image classification datasets with no finance content.</summary>
    <author><name>Other Author</name></author>
    <category term="cs.CV"/>
    <link href="http://arxiv.org/abs/2608.00001v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2608.00001v1.pdf" title="pdf" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


def _collector(tmp_path: Path, **kwargs) -> ArxivCollector:
    pipeline = DocumentIngestionPipeline(
        manifest_file=tmp_path / "data" / "audit" / "ingestion_version_manifest.json",
    )
    return ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
        status_file=tmp_path / "data" / "runtime" / "arxiv_ingestion_latest.json",
        curated_dir=tmp_path / "rag_knowledge" / "research" / "arxiv",
        pipeline=pipeline,
        **kwargs,
    )


def test_arxiv_paper_to_dict():
    paper = ArxivPaper(
        arxiv_id="2608.12345v1",
        title="Test Paper",
        authors=["Jane Doe"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="Test summary",
        categories=["q-fin.TR"],
        abs_url="https://arxiv.org/abs/2608.12345v1",
        pdf_url="https://arxiv.org/pdf/2608.12345v1.pdf",
    )
    d = paper.to_dict()
    assert d["arxiv_id"] == "2608.12345v1"
    assert d["title"] == "Test Paper"
    assert d["authors"] == ["Jane Doe"]


def test_parse_arxiv_atom(tmp_path: Path):
    collector = _collector(tmp_path)
    papers = collector._parse_arxiv_atom(SAMPLE_ATOM_XML)

    assert len(papers) == 2
    p = papers[0]
    assert p.arxiv_id == "2608.12345v1"
    assert "Option Trading" in p.title
    assert "Jane Doe" in p.authors
    assert "q-fin.TR" in p.categories
    assert p.pdf_url.startswith("https://")
    assert p.pdf_url.endswith(".pdf")


def test_domain_boost_prefers_options_grpo(tmp_path: Path):
    collector = _collector(tmp_path)
    relevant = ArxivPaper(
        arxiv_id="x",
        title="GRPO for SPY put credit option spreads",
        authors=[],
        published="",
        updated="",
        summary="order book microstructure and RAG grounded risk",
        categories=["q-fin.TR"],
        abs_url="",
        pdf_url="",
    )
    noise = ArxivPaper(
        arxiv_id="y",
        title="Image classification taxonomy",
        authors=[],
        published="",
        updated="",
        summary="computer vision benchmarks",
        categories=["cs.CV"],
        abs_url="",
        pdf_url="",
    )
    assert collector._domain_boost(relevant) > collector._domain_boost(noise)
    assert collector._domain_boost(relevant) >= 0.2


def test_ingest_paper_and_promote(tmp_path: Path):
    collector = _collector(tmp_path, min_relevance=0.0, promote_relevance=0.0)
    paper = ArxivPaper(
        arxiv_id="2608.99999v1",
        title="GRPO Trading Systems for SPY option credit spreads",
        authors=["Alice Bob"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="GRPO policy optimization for financial options markets and RAG.",
        categories=["q-fin.TR"],
        abs_url="https://arxiv.org/abs/2608.99999v1",
        pdf_url="https://arxiv.org/pdf/2608.99999v1.pdf",
    )

    res = collector.ingest_paper(paper)
    assert res["arxiv_id"] == "2608.99999v1"
    assert res["chunks_created"] > 0
    assert not res["is_duplicate"]
    assert Path(res["file_path"]).exists()
    assert res["promoted"] is True
    assert Path(res["curated_path"]).exists()

    # Second ingest of same content is duplicate in DocumentIngestionPipeline
    res2 = collector.ingest_paper(paper)
    assert res2["is_duplicate"]


def test_low_relevance_skipped(tmp_path: Path):
    collector = _collector(tmp_path, min_relevance=0.99, promote_relevance=1.0)
    paper = ArxivPaper(
        arxiv_id="2608.lowrelv1",
        title="Unrelated CV taxonomy",
        authors=["X"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="No finance terms at all in this abstract about photography.",
        categories=["cs.CV"],
        abs_url="https://arxiv.org/abs/2608.lowrelv1",
        pdf_url="https://arxiv.org/pdf/2608.lowrelv1.pdf",
    )
    res = collector.ingest_paper(paper)
    assert res["status"] == "skipped_low_relevance"
    assert paper.arxiv_id not in collector.manifest["papers"]


def test_fetch_papers_mocked(tmp_path: Path):
    collector = _collector(tmp_path)

    mock_resp = MagicMock()
    mock_resp.read.return_value = SAMPLE_ATOM_XML
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        papers = collector.fetch_papers(max_results=2)
        assert len(papers) == 2
        assert papers[0].arxiv_id == "2608.12345v1"


def test_run_continuous_ingestion_dedupes(tmp_path: Path):
    collector = _collector(tmp_path, min_relevance=0.0, promote_relevance=0.5)

    mock_resp = MagicMock()
    mock_resp.read.return_value = SAMPLE_ATOM_XML
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        r1 = collector.run_continuous_ingestion(max_results=5)
        r2 = collector.run_continuous_ingestion(max_results=5)

    assert r1.fetched == 2
    assert r1.ingested >= 1
    assert r2.skipped_duplicate >= 1
    assert collector.status_file.exists()
    status = json.loads(collector.status_file.read_text(encoding="utf-8"))
    assert status["schema_version"] == 1
    assert status["source"] == "arxiv"
    assert "fetched" in status


def test_build_search_query_override(tmp_path: Path):
    collector = _collector(tmp_path)
    q = collector.build_search_query(query="put credit spread")
    assert "put credit spread" in q
    assert "cat:q-fin.TR" in q


def test_default_min_relevance_constant():
    assert 0.0 < DEFAULT_MIN_RELEVANCE < 0.5


def test_http_get_retries_on_429(tmp_path: Path):
    collector = _collector(tmp_path)
    call_count = {"n": 0}

    def fake_urlopen(req, timeout=45):  # noqa: ARG001
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise urllib.error.HTTPError(
                url="https://export.arxiv.org/api/query",
                code=429,
                msg="Too Many Requests",
                hdrs=None,
                fp=None,
            )
        mock_resp = MagicMock()
        mock_resp.read.return_value = SAMPLE_ATOM_XML
        mock_resp.__enter__.return_value = mock_resp
        return mock_resp

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch("src.research.arxiv_collector.time.sleep", return_value=None),
    ):
        papers = collector.fetch_papers(max_results=2)
    assert call_count["n"] == 3
    assert len(papers) == 2

"""Unit tests for ArXiv Research Paper Collector and Ingestion Engine."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from src.research.arxiv_collector import ArxivCollector, ArxivPaper

SAMPLE_ATOM_XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2608.12345v1</id>
    <published>2026-08-10T12:00:00Z</published>
    <updated>2026-08-10T12:00:00Z</updated>
    <title>Deep Reinforcement Learning for Option Trading under Microstructure Noise</title>
    <summary>We propose a novel GRPO policy optimization algorithm for option credit spreads.</summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
    <category term="q-fin.TR"/>
    <category term="cs.AI"/>
    <link href="http://arxiv.org/abs/2608.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2608.12345v1.pdf" title="pdf" rel="related" type="application/pdf"/>
  </entry>
</feed>
"""


def test_arxiv_paper_to_dict():
    paper = ArxivPaper(
        arxiv_id="2608.12345v1",
        title="Test Paper",
        authors=["Jane Doe"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="Test summary",
        categories=["q-fin.TR"],
        abs_url="http://arxiv.org/abs/2608.12345v1",
        pdf_url="http://arxiv.org/pdf/2608.12345v1.pdf",
    )
    d = paper.to_dict()
    assert d["arxiv_id"] == "2608.12345v1"
    assert d["title"] == "Test Paper"
    assert d["authors"] == ["Jane Doe"]


def test_parse_arxiv_atom(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
    )
    papers = collector._parse_arxiv_atom(SAMPLE_ATOM_XML)

    assert len(papers) == 1
    p = papers[0]
    assert p.arxiv_id == "2608.12345v1"
    assert "Option Trading" in p.title
    assert "Jane Doe" in p.authors
    assert "q-fin.TR" in p.categories
    assert p.pdf_url == "http://arxiv.org/pdf/2608.12345v1.pdf"


def test_ingest_paper(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
    )
    paper = ArxivPaper(
        arxiv_id="2608.99999v1",
        title="GRPO Trading Systems",
        authors=["Alice Bob"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="GRPO policy optimization for financial markets.",
        categories=["q-fin.TR"],
        abs_url="http://arxiv.org/abs/2608.99999v1",
        pdf_url="http://arxiv.org/pdf/2608.99999v1.pdf",
    )

    res = collector.ingest_paper(paper)
    assert res["arxiv_id"] == "2608.99999v1"
    assert res["chunks_created"] > 0
    assert not res["is_duplicate"]
    assert Path(res["file_path"]).exists()

    # Ingesting second time should detect duplicate in DocumentIngestionPipeline
    res2 = collector.ingest_paper(paper)
    assert res2["is_duplicate"]


def test_fetch_papers_mocked(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
    )

    mock_resp = MagicMock()
    mock_resp.read.return_value = SAMPLE_ATOM_XML
    mock_resp.__enter__.return_value = mock_resp

    with patch("urllib.request.urlopen", return_value=mock_resp):
        papers = collector.fetch_papers(max_results=1)
        assert len(papers) == 1
        assert papers[0].arxiv_id == "2608.12345v1"

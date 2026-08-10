"""Unit tests for continuous arXiv → Agentic RAG ingestion."""

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
    <title>Deep Reinforcement Learning for Option Credit Spreads under Microstructure Noise</title>
    <summary>
    We propose GRPO policy optimization for SPY put credit spreads with
    implied volatility surfaces, order book features, and risk management stops.
    </summary>
    <author><name>Jane Doe</name></author>
    <author><name>John Smith</name></author>
    <category term="q-fin.TR"/>
    <category term="cs.LG"/>
    <link href="http://arxiv.org/abs/2608.12345v1" rel="alternate" type="text/html"/>
    <link href="http://arxiv.org/pdf/2608.12345v1.pdf" title="pdf" rel="related" type="application/pdf"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2608.00001v1</id>
    <published>2026-08-09T12:00:00Z</published>
    <updated>2026-08-09T12:00:00Z</updated>
    <title>A Survey of Generic Image Captioning</title>
    <summary>We caption pictures of cats using transformers.</summary>
    <author><name>Someone</name></author>
    <category term="cs.CV"/>
    <link href="http://arxiv.org/pdf/2608.00001v1.pdf" title="pdf" rel="related" type="application/pdf"/>
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
        abs_url="https://arxiv.org/abs/2608.12345v1",
        pdf_url="https://arxiv.org/pdf/2608.12345v1.pdf",
    )
    d = paper.to_dict()
    assert d["arxiv_id"] == "2608.12345v1"
    assert d["title"] == "Test Paper"


def test_parse_arxiv_atom(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
    )
    papers = collector._parse_arxiv_atom(SAMPLE_ATOM_XML)
    assert len(papers) == 2
    p = papers[0]
    assert p.arxiv_id == "2608.12345v1"
    assert "Option Credit" in p.title
    assert "Jane Doe" in p.authors
    assert "q-fin.TR" in p.categories
    assert p.pdf_url.startswith("https://")


def test_relevance_prefers_trading_papers(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
        min_relevance=0.18,
    )
    papers = collector._parse_arxiv_atom(SAMPLE_ATOM_XML)
    trading = collector.evaluate_paper_relevance(papers[0])
    cats = collector.evaluate_paper_relevance(papers[1])
    assert trading.relevance_score >= 0.18
    assert trading.relevance_score > cats.relevance_score


def test_ingest_paper_writes_rag_and_audit(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
        min_relevance=0.10,
    )
    paper = ArxivPaper(
        arxiv_id="2608.99999v1",
        title="GRPO for SPY Put Credit Spreads and Implied Volatility",
        authors=["Alice Bob"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="GRPO reinforcement learning for option credit spreads and risk management.",
        categories=["q-fin.TR", "cs.LG"],
        abs_url="https://arxiv.org/abs/2608.99999v1",
        pdf_url="https://arxiv.org/pdf/2608.99999v1.pdf",
    )
    res = collector.ingest_paper(paper)
    assert res["skipped"] is False
    assert res["chunks_created"] > 0
    assert Path(res["file_path"]).exists()
    assert (tmp_path / "data" / "arxiv").exists()
    assert paper.arxiv_id in collector.manifest["papers"]


def test_low_relevance_skipped(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
        min_relevance=0.50,
    )
    paper = ArxivPaper(
        arxiv_id="2608.00002v1",
        title="A Survey of Generic Image Captioning",
        authors=["X"],
        published="2026-08-10",
        updated="2026-08-10",
        summary="We caption pictures of cats.",
        categories=["cs.CV"],
        abs_url="https://arxiv.org/abs/2608.00002v1",
        pdf_url="https://arxiv.org/pdf/2608.00002v1.pdf",
    )
    res = collector.ingest_paper(paper)
    assert res["skipped"] is True
    assert res["reason"] == "low_relevance"
    assert paper.arxiv_id not in collector.manifest.get("papers", {})


def test_fetch_papers_mocked(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = SAMPLE_ATOM_XML
    mock_resp.__enter__.return_value = mock_resp
    with patch("urllib.request.urlopen", return_value=mock_resp):
        papers = collector.fetch_papers(max_results=2)
        assert len(papers) == 2
        assert papers[0].arxiv_id == "2608.12345v1"


def test_continuous_ingestion_dedupes(tmp_path: Path):
    collector = ArxivCollector(
        output_dir=tmp_path / "data" / "arxiv",
        rag_dir=tmp_path / "rag_knowledge" / "arxiv",
        manifest_file=tmp_path / "data" / "audit" / "arxiv_manifest.json",
        min_relevance=0.10,
    )
    mock_resp = MagicMock()
    mock_resp.read.return_value = SAMPLE_ATOM_XML
    mock_resp.__enter__.return_value = mock_resp
    with patch("urllib.request.urlopen", return_value=mock_resp):
        first = collector.run_continuous_ingestion(
            query="option", max_results=5, multi_query=False
        )
        second = collector.run_continuous_ingestion(
            query="option", max_results=5, multi_query=False
        )
    assert any(not r.get("skipped") for r in first)
    # second run: already in manifest → empty new results
    assert second == []

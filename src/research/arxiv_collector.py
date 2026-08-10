"""ArXiv Research Paper Collector & Agentic RAG Ingestion Engine.

Continuously fetches, parses, grades, and ingests quantitative finance,
reinforcement learning (GRPO/PPO), and trading RAG papers from arXiv (arxiv.org).
Integrates with the 9-stage DocumentIngestionPipeline and Financial Graph RAG.
"""

from __future__ import annotations

import datetime
import json
import logging
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from src.rag.answer_metrics import measure_answer_metrics
from src.rag.document_ingestion_pipeline import DocumentIngestionPipeline

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parents[2]
ARXIV_DATA_DIR = ROOT / "data" / "arxiv"
ARXIV_MANIFEST_FILE = ROOT / "data" / "audit" / "arxiv_ingestion_manifest.json"

DEFAULT_CATEGORIES = [
    "q-fin.TR",  # Trading and Market Microstructure
    "q-fin.PM",  # Portfolio Management
    "q-fin.RM",  # Risk Management
    "cs.AI",  # Artificial Intelligence / Multi-Agent
    "cs.LG",  # Machine Learning / RL / GRPO
    "cs.CL",  # Computation and Language / RAG
]

DEFAULT_KEYWORDS = [
    "quantitative trading",
    "reinforcement learning trading",
    "GRPO",
    "option trading",
    "market microstructure",
    "financial RAG",
    "order book",
]


@dataclass
class ArxivPaper:
    arxiv_id: str
    title: str
    authors: list[str]
    published: str
    updated: str
    summary: str
    categories: list[str]
    abs_url: str
    pdf_url: str
    relevance_score: float = 0.0
    faithfulness_score: float = 0.0
    groundedness_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ArxivCollector:
    """Collects papers from arXiv API and ingests them into RAG & Graph RAG."""

    def __init__(
        self,
        output_dir: Path | None = None,
        manifest_file: Path | None = None,
    ) -> None:
        self.output_dir = output_dir or ARXIV_DATA_DIR
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_file = manifest_file or ARXIV_MANIFEST_FILE
        self.manifest = self._load_manifest()
        self.ingestion_pipeline = DocumentIngestionPipeline()

    def _load_manifest(self) -> dict[str, Any]:
        if self.manifest_file.exists():
            try:
                with self.manifest_file.open("r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning("Failed to load arXiv manifest: %s", e)
        return {"papers": {}, "total_ingested": 0, "last_run_utc": ""}

    def _save_manifest(self) -> None:
        self.manifest_file.parent.mkdir(parents=True, exist_ok=True)
        with self.manifest_file.open("w", encoding="utf-8") as f:
            json.dump(self.manifest, f, indent=2)

    def fetch_papers(
        self,
        query: str | None = None,
        categories: list[str] | None = None,
        max_results: int = 10,
    ) -> list[ArxivPaper]:
        """Fetch papers from ArXiv API matching query or categories."""
        cats = categories or DEFAULT_CATEGORIES
        cat_query = " OR ".join(f"cat:{c}" for c in cats)

        if query:
            search_query = f"all:({query}) AND ({cat_query})"
        else:
            kw_query = " OR ".join(f'all:"{kw}"' for kw in DEFAULT_KEYWORDS[:3])
            search_query = f"({kw_query}) AND ({cat_query})"

        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        url = f"http://export.arxiv.org/api/query?{urllib.parse.urlencode(params)}"

        logger.info("Querying ArXiv API: %s", url)
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Antigravity-AI-QuantLab/1.0"},
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                xml_data = resp.read()
        except Exception as e:
            logger.error("ArXiv API request failed: %s", e)
            return []

        return self._parse_arxiv_atom(xml_data)

    def _parse_arxiv_atom(self, xml_bytes: bytes) -> list[ArxivPaper]:
        papers: list[ArxivPaper] = []
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "arxiv": "http://arxiv.org/schemas/atom",
        }
        try:
            root = ET.fromstring(xml_bytes)
        except ET.ParseError as e:
            logger.error("Failed to parse ArXiv XML response: %s", e)
            return []

        for entry in root.findall("atom:entry", ns):
            id_text = entry.findtext("atom:id", default="", namespaces=ns)
            arxiv_id = id_text.split("/abs/")[-1] if "/abs/" in id_text else id_text

            title = entry.findtext("atom:title", default="", namespaces=ns)
            title = re.sub(r"\s+", " ", title).strip()

            summary = entry.findtext("atom:summary", default="", namespaces=ns)
            summary = re.sub(r"\s+", " ", summary).strip()

            published = entry.findtext("atom:published", default="", namespaces=ns)
            updated = entry.findtext("atom:updated", default="", namespaces=ns)

            authors = [
                author.findtext("atom:name", default="", namespaces=ns)
                for author in entry.findall("atom:author", ns)
            ]

            categories = [
                cat.attrib.get("term", "")
                for cat in entry.findall("atom:category", ns)
                if cat.attrib.get("term")
            ]

            abs_url = id_text
            pdf_url = ""
            for link in entry.findall("atom:link", ns):
                if link.attrib.get("title") == "pdf":
                    pdf_url = link.attrib.get("href", "")
                    break
            if not pdf_url and arxiv_id:
                pdf_url = f"http://arxiv.org/pdf/{arxiv_id}.pdf"

            paper = ArxivPaper(
                arxiv_id=arxiv_id,
                title=title,
                authors=authors,
                published=published,
                updated=updated,
                summary=summary,
                categories=categories,
                abs_url=abs_url,
                pdf_url=pdf_url,
            )
            papers.append(paper)

        return papers

    def evaluate_paper_relevance(self, paper: ArxivPaper) -> ArxivPaper:
        """Grade paper relevance and groundedness against financial trading context."""
        context = [
            "Quantitative trading, option credit spreads, SPY put spreads, iron condors.",
            "Group Relative Policy Optimization (GRPO), reinforcement learning in finance.",
            "Market microstructure, order book modeling, statistical arbitrage, risk control.",
            "Agentic RAG, temporal graph RAG, groundedness, faithfulness evaluation.",
        ]
        score = measure_answer_metrics(
            question="How relevant is this paper to quantitative trading and RL policy learning?",
            answer=f"{paper.title}. {paper.summary}",
            context=context,
        )
        paper.faithfulness_score = round(score.faithfulness, 3)
        paper.groundedness_score = round(score.groundedness, 3)
        paper.relevance_score = round(
            (score.faithfulness * 0.6) + (score.answer_relevance * 0.4), 3
        )
        return paper

    def ingest_paper(self, paper: ArxivPaper) -> dict[str, Any]:
        """Ingest paper into markdown file, RAG pipeline, and Financial Graph."""
        paper = self.evaluate_paper_relevance(paper)

        clean_id = re.sub(r"[^a-zA-Z0-9_-]", "_", paper.arxiv_id)
        filename = f"arxiv_{clean_id}.md"
        file_path = self.output_dir / filename

        md_content = f"""# arXiv Paper: {paper.title}

- **arXiv ID**: `{paper.arxiv_id}`
- **Published**: {paper.published}
- **Authors**: {", ".join(paper.authors)}
- **Categories**: {", ".join(paper.categories)}
- **URL**: [{paper.abs_url}]({paper.abs_url})
- **PDF**: [{paper.pdf_url}]({paper.pdf_url})

## RAG Quality Scores
- **Relevance Score**: {paper.relevance_score}
- **Faithfulness Score**: {paper.faithfulness_score}
- **Groundedness Score**: {paper.groundedness_score}

## Abstract / Summary
{paper.summary}

## Trading System Applicability
This research paper was automatically ingested by the Antigravity Agentic RAG pipeline.
It provides potential mathematical models, RL policy techniques, or market microstructure signals
that directly inform the Lab GRPO self-training and option trading engine.
"""
        file_path.write_text(md_content, encoding="utf-8")

        # Ingest through DocumentIngestionPipeline
        doc = self.ingestion_pipeline.ingest_document(file_path, md_content)

        # Update manifest
        self.manifest["papers"][paper.arxiv_id] = {
            "title": paper.title,
            "published": paper.published,
            "relevance_score": paper.relevance_score,
            "faithfulness_score": paper.faithfulness_score,
            "groundedness_score": paper.groundedness_score,
            "file_path": str(file_path),
            "ingested_at": datetime.datetime.now(datetime.UTC).isoformat(),
        }
        self.manifest["total_ingested"] = len(self.manifest["papers"])
        self.manifest["last_run_utc"] = datetime.datetime.now(datetime.UTC).isoformat()
        self._save_manifest()

        logger.info("Ingested paper %s: %s", paper.arxiv_id, paper.title)
        return {
            "arxiv_id": paper.arxiv_id,
            "title": paper.title,
            "relevance_score": paper.relevance_score,
            "file_path": str(file_path),
            "chunks_created": len(doc.chunks),
            "is_duplicate": doc.is_duplicate,
        }

    def run_continuous_ingestion(
        self,
        query: str | None = None,
        max_results: int = 10,
    ) -> list[dict[str, Any]]:
        """Fetch papers, deduplicate, grade, and ingest into the RAG system."""
        papers = self.fetch_papers(query=query, max_results=max_results)
        results = []
        for paper in papers:
            if paper.arxiv_id in self.manifest["papers"]:
                logger.info("Paper %s already ingested; skipping.", paper.arxiv_id)
                continue
            ingest_result = self.ingest_paper(paper)
            results.append(ingest_result)

        logger.info("Ingestion completed: %d new papers ingested.", len(results))
        return results

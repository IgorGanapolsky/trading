#!/usr/bin/env python3
"""Download curated PDF knowledge sources and convert them into raw text."""

from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path

import requests
from PyPDF2 import PdfReader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "rag_knowledge" / "raw"
PDF_CACHE = PROJECT_ROOT / "data" / "cache" / "pdf_ingest"

PDF_SOURCES = [
    {
        "slug": "options_trading_for_beginners",
        "title": "Options Trading for Beginners",
        "url": "https://www.optionstrading.org/blog/wp-content/uploads/2025/03/Options_Trading_for_Beginners_PDF.pdf",
        "citation": "Optionstrading.org (2025)",
        "topics": ["options", "volatility", "education"],
    },
    {
        "slug": "sec_reits_overview",
        "title": "REITs and Capital Markets",
        "url": "https://www.sec.gov/files/reits.pdf",
        "citation": "SEC (2023)",
        "topics": ["reit", "income", "compliance"],
    },
    {
        "slug": "adaptive_multi_agent_btc",
        "title": "An Adaptive Multi-Agent Bitcoin Trading System",
        "url": "https://arxiv.org/pdf/2510.08068.pdf",
        "citation": "ArXiv (2025)",
        "topics": ["crypto", "multi_agent", "ai"],
    },
    {
        "slug": "nn_crypto_forecasting",
        "title": "Neural Network Design Patterns for Cryptocurrency Forecasting",
        "url": "https://arxiv.org/pdf/2508.02356.pdf",
        "citation": "ArXiv (2025)",
        "topics": ["crypto", "forecasting", "ai", "execution"],
    },
    {
        "slug": "nyfed_term_structure",
        "title": "The Term Structure of U.S. Interest Rates and Treasury Risk",
        "url": "https://www.newyorkfed.org/medialibrary/media/research/staff_reports/sr1091.pdf",
        "citation": "New York Fed Staff Report 1091 (2025)",
        "topics": ["treasury", "term_structure", "fixed_income"],
    },
]


def setup_directories() -> None:
    for directory in [RAW_DIR, PDF_CACHE]:
        directory.mkdir(parents=True, exist_ok=True)


HEADERS = {"User-Agent": "IgorTradingAgent/1.0"}


def download_pdf(source: dict[str, str], destination: Path, force: bool) -> bool:
    if destination.exists() and not force:
        logging.info("Skipping download (cached): %s", destination.name)
        return True

    logging.info("Downloading %s", source["title"])
    try:
        response = requests.get(source["url"], stream=True, timeout=30, headers=HEADERS)
        response.raise_for_status()
    except requests.RequestException as exc:
        logging.error("Failed to download %s: %s", source["slug"], exc)
        return False

    with open(destination, "wb") as pdf_file:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                pdf_file.write(chunk)

    return True


def extract_text(pdf_path: Path) -> str:
    reader = PdfReader(str(pdf_path))
    pages = []

    for page in reader.pages:
        text = page.extract_text()
        if text:
            pages.append(text)

    return "\n\n".join(pages)


def save_raw_text(source: dict[str, str], text: str, suffix: str) -> Path:
    filename = f"{suffix}_{source['slug']}.txt"
    destination = RAW_DIR / filename

    header = [
        f"Title: {source['title']}",
        f"URL: {source['url']}",
        f"Citation: {source['citation']}",
        f"Extracted: {datetime.utcnow().isoformat()} UTC",
        "",
    ]

    destination.write_text("\n".join(header) + text.strip())
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description="Download and parse curated PDF sources")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Re-download PDFs even when cached",
    )
    parser.add_argument(
        "--date",
        default=datetime.utcnow().strftime("%Y%m%d"),
        help="Date prefix for raw text files",
    )
    args = parser.parse_args()

    setup_directories()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    for source in PDF_SOURCES:
        pdf_path = PDF_CACHE / f"{source['slug']}.pdf"
        downloaded = download_pdf(source, pdf_path, args.force)
        if not downloaded:
            continue

        try:
            text = extract_text(pdf_path)
        except Exception as exc:
            logging.error("Failed to parse %s: %s", pdf_path.name, exc)
            continue

        if not text.strip():
            logging.warning("No text extracted from %s", pdf_path.name)
            continue

        saved_file = save_raw_text(source, text, args.date)
        logging.info("Extracted text saved to %s", saved_file)


if __name__ == "__main__":
    main()

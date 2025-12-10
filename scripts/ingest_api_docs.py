#!/usr/bin/env python3
"""
Ingest API Documentation for Agentic RAG

Fetches and chunks documentation from:
1. OpenBB (Financial Data Platform)
2. DeFiLlama (Crypto/DeFi Data)

This gives the agent the "manuals" to use these tools effectively.
"""

import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from src.rag.vector_db.chroma_client import get_rag_db

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

DOC_SOURCES = [
    {
        "name": "DeFiLlama API",
        "url": "https://defillama.com/docs/api",
        "base_url": "https://defillama.com",
        "tags": {"source": "defillama", "type": "api_docs", "domain": "crypto"},
    },
    {
        "name": "OpenBB Platform",
        "url": "https://docs.openbb.co/platform",
        "base_url": "https://docs.openbb.co",
        "tags": {"source": "openbb", "type": "api_docs", "domain": "finance"},
    },
]


def fetch_content(url: str) -> str:
    """Fetch and parse text from URL."""
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.114 Safari/537.36"
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for script in soup(["script", "style", "nav", "footer"]):
            script.decompose()

        # Get text
        text = soup.get_text(separator="\n")

        # Basic cleanup
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = "\n".join(chunk for chunk in chunks if chunk)

        return text
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Simple sliding window chunking."""
    if not text:
        return []

    chunks = []
    start = 0
    text_len = len(text)

    while start < text_len:
        end = start + chunk_size
        chunk = text[start:end]
        chunks.append(chunk)
        start += chunk_size - overlap

    return chunks


def ingest_docs():
    """Main ingestion loop."""
    db = get_rag_db()

    for source in DOC_SOURCES:
        logger.info(f"Processing {source['name']}...")
        content = fetch_content(source["url"])

        if not content:
            logger.warning(f"No content for {source['name']}, skipping.")
            continue

        chunks = chunk_text(content)
        logger.info(f"Generated {len(chunks)} chunks for {source['name']}")

        metadatas = []
        for i in range(len(chunks)):
            meta = source["tags"].copy()
            meta["date"] = datetime.now().strftime("%Y-%m-%d")
            meta["chunk_index"] = i
            meta["url"] = source["url"]
            metadatas.append(meta)

        db.add_documents(documents=chunks, metadatas=metadatas)
        logger.info(f"Successfully ingested {source['name']}")


if __name__ == "__main__":
    ingest_docs()

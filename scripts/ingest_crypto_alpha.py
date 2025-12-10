#!/usr/bin/env python3
"""
Ingest Crypto Alpha Resources

Scrapes and processes key crypto educational content for the RAG pipeline:
1. MasterTheCrypto.com (Trading guides)
2. YouTube Strategy Videos (Transcripts)
"""

import logging
from datetime import datetime

import requests
from bs4 import BeautifulSoup
from src.rag.vector_db.chroma_client import get_rag_db
from youtube_transcript_api import YouTubeTranscriptApi

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

RESOURCES = [
    {
        "type": "web",
        "url": "https://masterthecrypto.com/",  # Fallback to main page
        "title": "Master The Crypto - Home",
        "tags": {"source": "masterthecrypto", "topic": "crypto_basics"},
    },
    {
        "type": "youtube",
        "video_id": "_OqVDO99YVM",
        "title": "Crypto Trading Strategy Video 1",
        "tags": {"source": "youtube", "topic": "strategy"},
    },
    {
        "type": "youtube",
        "video_id": "hlvf6TXAFfo",
        "title": "Crypto Trading Strategy Video 2",
        "tags": {"source": "youtube", "topic": "strategy"},
    },
]


def fetch_web_content(url: str) -> str:
    """Fetch text from website."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        # Extract main content (heuristically)
        content = []
        for tag in soup.find_all(["h1", "h2", "h3", "p", "li"]):
            text = tag.get_text().strip()
            if len(text) > 20:
                content.append(text)
        return "\n".join(content)
    except Exception as e:
        logger.error(f"Failed to fetch {url}: {e}")
        return ""


def fetch_youtube_transcript(video_id: str) -> str:
    """Fetch transcript from YouTube video."""
    try:
        # Direct call to static method
        transcript = YouTubeTranscriptApi.get_transcript(video_id)
        text = " ".join([t["text"] for t in transcript])
        return text
    except Exception as e:
        logger.error(f"Failed to fetch transcript for {video_id}: {e}")
        return ""


def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 100) -> list[str]:
    """Simple sliding window chunking."""
    if not text:
        return []

    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start += chunk_size - overlap
    return chunks


def main():
    db = get_rag_db()
    logger.info("Starting Crypto Alpha Ingestion...")

    for resource in RESOURCES:
        logger.info(f"Processing: {resource['title']}")

        content = ""
        if resource["type"] == "web":
            content = fetch_web_content(resource["url"])
        elif resource["type"] == "youtube":
            content = fetch_youtube_transcript(resource["video_id"])

        if not content:
            logger.warning(f"No content found for {resource['title']}")
            continue

        chunks = chunk_text(content)
        logger.info(f"Generated {len(chunks)} chunks")

        metadatas = []
        for i in range(len(chunks)):
            meta = resource["tags"].copy()
            meta["title"] = resource["title"]
            meta["date_ingested"] = datetime.now().strftime("%Y-%m-%d")
            meta["chunk_index"] = i
            metadatas.append(meta)

        db.add_documents(documents=chunks, metadatas=metadatas)
        logger.info(f"Ingested {resource['title']}")


if __name__ == "__main__":
    main()

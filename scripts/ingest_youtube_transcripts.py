#!/usr/bin/env python3
"""
Ingest YouTube video transcripts into RAG vector store.

This script:
1. Reads cached YouTube transcripts
2. Chunks transcripts into manageable pieces
3. Ingests into ChromaDB vector store with metadata
4. Makes YouTube financial analysis searchable via semantic search

Usage:
    python scripts/ingest_youtube_transcripts.py
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any, Optional

sys.path.append(".")

from src.rag.vector_db.chroma_client import get_rag_db

logger = logging.getLogger(__name__)

# Chunk size for splitting long transcripts (in characters)
CHUNK_SIZE = 2000  # ~400 words per chunk
CHUNK_OVERLAP = 200  # Overlap between chunks for context


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """
    Split text into overlapping chunks for better retrieval.

    Args:
        text: Text to chunk
        chunk_size: Target chunk size in characters
        overlap: Overlap between chunks

    Returns:
        List of text chunks
    """
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0

    while start < len(text):
        end = start + chunk_size

        # Try to break at sentence boundary
        if end < len(text):
            # Look for sentence endings near the end
            for punct in [". ", ".\n", "! ", "!\n", "? ", "?\n"]:
                last_punct = text.rfind(punct, start, end)
                if last_punct > start + chunk_size // 2:  # Don't break too early
                    end = last_punct + len(punct)
                    break

        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)

        # Move start forward with overlap
        start = end - overlap
        if start >= len(text):
            break

    return chunks


def load_video_metadata(video_id: str, cache_dir: Path) -> Optional[dict[str, Any]]:
    """
    Load video metadata from processed_videos.json if available.

    Args:
        video_id: YouTube video ID
        cache_dir: Cache directory path

    Returns:
        Metadata dict or None
    """
    processed_file = cache_dir / "processed_videos.json"
    if not processed_file.exists():
        return None

    try:
        with open(processed_file) as f:
            processed = json.load(f)
            return processed.get(video_id)
    except Exception as e:
        logger.debug(f"Could not load metadata for {video_id}: {e}")
        return None


def extract_video_id(filename: str) -> Optional[str]:
    """Extract video ID from transcript filename."""
    # Format: {video_id}_transcript.txt
    if "_transcript.txt" in filename:
        return filename.replace("_transcript.txt", "")
    return None


def ingest_youtube_transcripts() -> dict[str, Any]:
    """
    Ingest all YouTube transcripts into RAG vector store.

    Returns:
        Dict with ingestion results
    """
    logger.info("=" * 80)
    logger.info("INGESTING YOUTUBE TRANSCRIPTS INTO RAG")
    logger.info("=" * 80)

    # Set up directories
    cache_dir = Path("data/youtube_cache")

    if not cache_dir.exists():
        logger.error(f"Cache directory not found: {cache_dir}")
        return {"status": "error", "message": "Cache directory not found"}

    # Find all transcript files
    transcript_files = list(cache_dir.glob("*_transcript.txt"))
    logger.info(f"Found {len(transcript_files)} transcript files")

    if not transcript_files:
        logger.warning("No transcript files found")
        return {"status": "error", "message": "No transcript files found"}

    # Load RAG database
    db = get_rag_db()

    total_chunks = 0
    total_videos = 0
    errors = []

    for transcript_file in transcript_files:
        video_id = extract_video_id(transcript_file.name)
        if not video_id:
            logger.warning(f"Could not extract video ID from {transcript_file.name}")
            continue

        try:
            # Read transcript
            transcript_text = transcript_file.read_text(encoding="utf-8")

            if not transcript_text.strip():
                logger.warning(f"Skipping empty transcript: {video_id}")
                continue

            # Load metadata if available
            metadata_dict = load_video_metadata(video_id, cache_dir)

            # Chunk the transcript
            chunks = chunk_text(transcript_text)
            logger.info(f"  {video_id}: {len(chunks)} chunks ({len(transcript_text)} chars)")

            # Prepare documents and metadata
            documents = []
            metadatas = []
            ids = []

            title = (
                metadata_dict.get("title", "Unknown Video") if metadata_dict else "Unknown Video"
            )
            channel = (
                metadata_dict.get("channel", "Unknown Channel")
                if metadata_dict
                else "Unknown Channel"
            )
            upload_date = (
                metadata_dict.get("upload_date", "Unknown") if metadata_dict else "Unknown"
            )
            url = (
                metadata_dict.get("url", f"https://www.youtube.com/watch?v={video_id}")
                if metadata_dict
                else f"https://www.youtube.com/watch?v={video_id}"
            )

            for i, chunk in enumerate(chunks):
                documents.append(chunk)

                # Build metadata
                metadata = {
                    "source": "youtube",
                    "video_id": video_id,
                    "title": title,
                    "channel": channel,
                    "upload_date": upload_date,
                    "url": url,
                    "ticker": "MARKET",  # Market-wide analysis
                    "type": "video_transcript",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                }
                metadatas.append(metadata)

                # Generate unique ID
                ids.append(f"youtube_{video_id}_chunk_{i}")

            # Add to RAG database
            result = db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

            if result.get("status") == "success":
                total_chunks += len(chunks)
                total_videos += 1
                logger.info(f"  ✓ Ingested {video_id}: {len(chunks)} chunks - {title[:50]}")
            else:
                errors.append(f"{video_id}: {result.get('message', 'Unknown error')}")
                logger.error(f"  ✗ Failed to ingest {video_id}")

        except Exception as e:
            errors.append(f"{video_id}: {str(e)}")
            logger.error(f"Error processing {video_id}: {e}", exc_info=True)

    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Videos ingested: {total_videos}/{len(transcript_files)}")
    logger.info(f"Total chunks: {total_chunks}")
    if errors:
        logger.warning(f"Errors: {len(errors)}")
        for error in errors:
            logger.warning(f"  - {error}")

    return {
        "status": "success" if not errors else "partial",
        "videos_ingested": total_videos,
        "total_videos": len(transcript_files),
        "total_chunks": total_chunks,
        "errors": errors,
    }


def main():
    argparse.ArgumentParser(
        description="Ingest YouTube transcripts into RAG vector store"
    ).parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = ingest_youtube_transcripts()

    if result["status"] == "error":
        sys.exit(1)

    logger.info("\n✅ YouTube transcripts successfully ingested into RAG!")
    logger.info("You can now query YouTube financial analysis using semantic search.")


if __name__ == "__main__":
    main()

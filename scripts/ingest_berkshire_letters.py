#!/usr/bin/env python3
"""
Ingest Berkshire Hathaway shareholder letters into RAG vector store.

This script:
1. Parses PDF letters if not already parsed
2. Chunks letters into manageable pieces for better retrieval
3. Ingests into ChromaDB vector store with metadata
4. Makes Buffett's wisdom searchable via semantic search

Usage:
    python scripts/ingest_berkshire_letters.py
    python scripts/ingest_berkshire_letters.py --force-reparse
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

sys.path.append(".")

# Import PDF parser directly to avoid dependency chain issues
try:
    import PyPDF2
except ImportError:
    PyPDF2 = None

from src.rag.vector_db.chroma_client import get_rag_db

logger = logging.getLogger(__name__)

# Chunk size for splitting long letters (in characters)
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


def parse_pdf(file_path: Path) -> str:
    """Parse PDF to text."""
    if PyPDF2 is None:
        logger.error("PyPDF2 not installed - cannot parse PDF files")
        return ""

    try:
        text_parts = []
        with open(file_path, "rb") as f:
            pdf_reader = PyPDF2.PdfReader(f)
            for page in pdf_reader.pages:
                text_parts.append(page.extract_text())

        return "\n\n".join(text_parts)

    except Exception as e:
        logger.error(f"Error parsing PDF {file_path}: {e}")
        return ""


def ingest_berkshire_letters(force_reparse: bool = False) -> dict[str, Any]:
    """
    Ingest all Berkshire letters into RAG vector store.

    Args:
        force_reparse: Re-parse letters even if already parsed

    Returns:
        Dict with ingestion results
    """
    logger.info("=" * 80)
    logger.info("INGESTING BERKSHIRE HATHAWAY LETTERS INTO RAG")
    logger.info("=" * 80)

    # Set up directories
    base_dir = Path("data/rag/berkshire_letters")
    raw_dir = base_dir / "raw"
    parsed_dir = base_dir / "parsed"
    parsed_dir.mkdir(parents=True, exist_ok=True)

    # Check for existing parsed files first
    existing_parsed = list(parsed_dir.glob("*.txt"))
    pdf_files = list(raw_dir.glob("*.pdf"))

    logger.info(f"Found {len(existing_parsed)} pre-parsed text files")
    logger.info(f"Found {len(pdf_files)} PDF files")

    if not pdf_files and not existing_parsed:
        logger.warning(
            "No PDF files or parsed texts found. Run collector.download_all_letters() first."
        )
        return {"status": "error", "message": "No PDF files or parsed texts found"}

    # Parse PDFs if not already parsed or if force_reparse
    parsed_count = 0
    for pdf_file in pdf_files:
        year = pdf_file.stem
        parsed_file = parsed_dir / f"{year}.txt"

        if force_reparse or not parsed_file.exists():
            logger.info(f"Parsing {year} letter...")
            text = parse_pdf(pdf_file)
            if text:
                parsed_file.parent.mkdir(parents=True, exist_ok=True)
                with open(parsed_file, "w", encoding="utf-8") as f:
                    f.write(text)
                parsed_count += 1
                logger.info(f"  ✓ Parsed {year} ({len(text)} chars)")
            else:
                logger.warning(f"  ✗ Failed to parse {year}")
        else:
            logger.debug(f"  {year} already parsed, skipping")

    if parsed_count > 0:
        logger.info(f"Parsed {parsed_count} new letters")

    # Load parsed letters and ingest into RAG
    parsed_files = sorted(parsed_dir.glob("*.txt"))
    logger.info(f"\nIngesting {len(parsed_files)} parsed letters into RAG...")

    db = get_rag_db()

    total_chunks = 0
    total_letters = 0
    errors = []

    for parsed_file in parsed_files:
        year = parsed_file.stem
        try:
            # Read parsed text
            with open(parsed_file, encoding="utf-8") as f:
                text = f.read()

            if not text.strip():
                logger.warning(f"Skipping empty letter: {year}")
                continue

            # Chunk the letter
            chunks = chunk_text(text)
            logger.info(f"  {year}: {len(chunks)} chunks")

            # Prepare documents and metadata
            documents = []
            metadatas = []
            ids = []

            for i, chunk in enumerate(chunks):
                documents.append(chunk)

                # Extract metadata
                metadata = {
                    "source": "berkshire_letters",
                    "year": int(year),
                    "date": f"{year}-01-01",  # Approximate date
                    "ticker": "MARKET",  # Market-wide wisdom
                    "type": "shareholder_letter",
                    "author": "Warren Buffett",
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "url": f"https://www.berkshirehathaway.com/letters/{year}.html",
                }
                metadatas.append(metadata)

                # Generate unique ID
                ids.append(f"berkshire_{year}_chunk_{i}")

            # Add to RAG database
            result = db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

            if result.get("status") == "success":
                total_chunks += len(chunks)
                total_letters += 1
                logger.info(f"  ✓ Ingested {year}: {len(chunks)} chunks")
            else:
                errors.append(f"{year}: {result.get('message', 'Unknown error')}")
                logger.error(f"  ✗ Failed to ingest {year}")

        except Exception as e:
            errors.append(f"{year}: {str(e)}")
            logger.error(f"Error processing {year}: {e}", exc_info=True)

    logger.info("\n" + "=" * 80)
    logger.info("INGESTION COMPLETE")
    logger.info("=" * 80)
    logger.info(f"Letters ingested: {total_letters}/{len(parsed_files)}")
    logger.info(f"Total chunks: {total_chunks}")
    if errors:
        logger.warning(f"Errors: {len(errors)}")
        for error in errors:
            logger.warning(f"  - {error}")

    return {
        "status": "success" if not errors else "partial",
        "letters_ingested": total_letters,
        "total_letters": len(parsed_files),
        "total_chunks": total_chunks,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Ingest Berkshire Hathaway letters into RAG vector store"
    )
    parser.add_argument(
        "--force-reparse",
        action="store_true",
        help="Re-parse PDFs even if already parsed",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    result = ingest_berkshire_letters(force_reparse=args.force_reparse)

    if result["status"] == "error":
        sys.exit(1)

    logger.info("\n✅ Berkshire letters successfully ingested into RAG!")
    logger.info("You can now query Buffett's wisdom using semantic search.")


if __name__ == "__main__":
    main()

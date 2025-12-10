#!/usr/bin/env python3
"""
RAG Knowledge Ingestion Script

Ingests curated trading knowledge into the RAG system:
- Books (López de Prado, Carver, etc.)
- Research papers
- Newsletter insights

Usage:
    python scripts/ingest_rag_knowledge.py --source-dir rag_knowledge
    python scripts/ingest_rag_knowledge.py --book afml
    python scripts/ingest_rag_knowledge.py --all
"""

import argparse
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Import directly to avoid pulling in all collectors (some have optional deps like bs4)
import importlib.util

# Load training_library_collector directly
spec = importlib.util.spec_from_file_location(
    "training_library_collector",
    Path(__file__).parent.parent / "src/rag/collectors/training_library_collector.py",
)
training_lib_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(training_lib_module)

CANONICAL_BOOKS = training_lib_module.CANONICAL_BOOKS
NEWSLETTERS = training_lib_module.NEWSLETTERS
RESEARCH_PAPERS = training_lib_module.RESEARCH_PAPERS
KnowledgeChunk = training_lib_module.KnowledgeChunk
TrainingLibraryCollector = training_lib_module.TrainingLibraryCollector
get_training_library_collector = training_lib_module.get_training_library_collector

# Import vector DB directly
spec_db = importlib.util.spec_from_file_location(
    "chroma_client",
    Path(__file__).parent.parent / "src/rag/vector_db/chroma_client.py",
)
chroma_module = importlib.util.module_from_spec(spec_db)
spec_db.loader.exec_module(chroma_module)
get_rag_db = chroma_module.get_rag_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def ingest_book(collector: TrainingLibraryCollector, book_id: str, force: bool = False) -> dict:
    """Ingest a single book into the RAG system."""
    books_dir = Path("rag_knowledge/books")

    # Map book_id to file
    file_mapping = {
        "afml": "afml_chapters.json",
        "systematic_trading": "systematic_trading_chapters.json",
        "dual_momentum": "dual_momentum_chapters.json",
        "quantitative_trading": "quantitative_trading_chapters.json",
        "ivy_portfolio": "ivy_portfolio_chapters.json",
    }

    if book_id not in file_mapping:
        logger.error(f"Unknown book: {book_id}. Available: {list(file_mapping.keys())}")
        return {"status": "error", "message": f"Unknown book: {book_id}"}

    book_file = books_dir / file_mapping[book_id]

    if not book_file.exists():
        logger.warning(f"Book file not found: {book_file}")
        return {"status": "error", "message": f"File not found: {book_file}"}

    # Check if already ingested
    if not force and book_id in collector.index.get("books", {}):
        logger.info(f"Book {book_id} already ingested. Use --force to re-ingest.")
        return {"status": "already_ingested", "book_id": book_id}

    logger.info(f"Ingesting book: {book_id} from {book_file}")

    with open(book_file) as f:
        book_data = json.load(f)

    result = collector.ingest_book_summary(book_id, book_data.get("chapters", []))
    return result


def ingest_newsletter(
    collector: TrainingLibraryCollector, newsletter_id: str, force: bool = False
) -> dict:
    """Ingest newsletter insights into the RAG system."""
    newsletters_dir = Path("rag_knowledge/newsletters")

    file_mapping = {
        "alpha_architect": "alpha_architect_insights.json",
        "quantified_strategies": "quantified_strategies_insights.json",
        "flirting_with_models": "flirting_with_models_insights.json",
        "moontower": "moontower_insights.json",
    }

    if newsletter_id not in file_mapping:
        logger.error(f"Unknown newsletter: {newsletter_id}")
        return {"status": "error", "message": f"Unknown newsletter: {newsletter_id}"}

    newsletter_file = newsletters_dir / file_mapping[newsletter_id]

    if not newsletter_file.exists():
        logger.warning(f"Newsletter file not found: {newsletter_file}")
        return {"status": "error", "message": f"File not found: {newsletter_file}"}

    if not force and newsletter_id in collector.index.get("newsletters", {}):
        logger.info(f"Newsletter {newsletter_id} already ingested. Use --force to re-ingest.")
        return {"status": "already_ingested", "newsletter_id": newsletter_id}

    logger.info(f"Ingesting newsletter: {newsletter_id}")

    with open(newsletter_file) as f:
        newsletter_data = json.load(f)

    # Convert newsletter insights to chunks
    chunks = []
    for insight in newsletter_data.get("insights", []):
        chunk = {
            "source_type": "newsletter",
            "source_name": newsletter_data.get("name", newsletter_id),
            "author": newsletter_data.get("author", ""),
            "chapter_or_section": insight.get("title", ""),
            "page_or_timestamp": insight.get("date", ""),
            "content": f"{insight.get('content', '')}\n\nKey Takeaway: {insight.get('key_takeaway', '')}",
            "content_type": "strategy"
            if "strategy" in insight.get("title", "").lower()
            else "concept",
            "topics": insight.get("topics", []),
            "edge_category": insight.get("topics", ["general"])[0]
            if insight.get("topics")
            else "general",
            "citation": insight.get(
                "citation", f"{newsletter_data.get('name')} ({insight.get('date', '2024')})"
            ),
        }
        chunks.append(chunk)

    # Save chunks
    chunks_file = collector.chunks_dir / f"{newsletter_id}_chunks.json"
    with open(chunks_file, "w") as f:
        json.dump(chunks, f, indent=2)

    # Update index
    if "newsletters" not in collector.index:
        collector.index["newsletters"] = {}

    collector.index["newsletters"][newsletter_id] = {
        "name": newsletter_data.get("name", newsletter_id),
        "chunks_file": str(chunks_file),
        "chunk_count": len(chunks),
        "ingested_at": datetime.now().isoformat(),
    }
    collector._save_index()

    logger.info(f"Ingested {len(chunks)} insights from {newsletter_data.get('name')}")
    return {"status": "success", "newsletter_id": newsletter_id, "chunks": len(chunks)}


def sync_to_vector_db(collector: TrainingLibraryCollector) -> dict:
    """Sync all ingested knowledge to ChromaDB vector store."""
    logger.info("Syncing knowledge to ChromaDB vector store...")

    db = get_rag_db()
    chunks = collector.get_chunks_for_rag()

    if not chunks:
        logger.warning("No chunks to sync")
        return {"status": "no_chunks", "count": 0}

    documents = []
    metadatas = []
    ids = []

    for chunk in chunks:
        documents.append(chunk["content"])

        # Flatten metadata for ChromaDB
        metadata = {
            "source_type": chunk["metadata"]["source_type"],
            "source_name": chunk["metadata"]["source_name"],
            "author": chunk["metadata"]["author"],
            "chapter": chunk["metadata"].get("chapter", ""),
            "content_type": chunk["metadata"]["content_type"],
            "edge_category": chunk["metadata"]["edge_category"],
            "citation": chunk["metadata"]["citation"],
            "topics": chunk["metadata"].get("topics", ""),
            "source": "training_library",
        }
        metadatas.append(metadata)
        ids.append(chunk["id"])

    result = db.add_documents(documents=documents, metadatas=metadatas, ids=ids)

    if result.get("status") == "success":
        logger.info(f"Successfully synced {result.get('count', 0)} chunks to vector store")
        stats = db.get_stats()
        logger.info(f"Vector store now has {stats.get('total_documents', 0)} total documents")
    else:
        logger.error(f"Failed to sync: {result.get('message')}")

    return result


def main():
    parser = argparse.ArgumentParser(description="Ingest trading knowledge into RAG system")
    parser.add_argument("--source-dir", default="rag_knowledge", help="Source directory")
    parser.add_argument("--book", help="Ingest specific book (afml, systematic_trading, etc.)")
    parser.add_argument("--newsletter", help="Ingest specific newsletter")
    parser.add_argument("--all", action="store_true", help="Ingest all available sources")
    parser.add_argument("--force", action="store_true", help="Force re-ingestion")
    parser.add_argument("--sync", action="store_true", help="Sync to vector DB after ingestion")
    parser.add_argument("--list", action="store_true", help="List available sources")

    args = parser.parse_args()

    if args.list:
        print("\n📚 Available Books:")
        for book_id, book_info in CANONICAL_BOOKS.items():
            print(f"  - {book_id}: {book_info['title']} by {book_info['author']}")

        print("\n📰 Available Newsletters:")
        for newsletter_id, newsletter_info in NEWSLETTERS.items():
            print(f"  - {newsletter_id}: {newsletter_info['name']}")

        print("\n📄 Available Papers:")
        for paper_id, paper_info in RESEARCH_PAPERS.items():
            authors = paper_info.get("authors", paper_info.get("author", "Unknown"))
            print(f"  - {paper_id}: {paper_info['title']} by {authors}")
        return

    collector = get_training_library_collector()
    results = {"books": {}, "newsletters": {}}

    if args.book:
        results["books"][args.book] = ingest_book(collector, args.book, args.force)

    if args.newsletter:
        results["newsletters"][args.newsletter] = ingest_newsletter(
            collector, args.newsletter, args.force
        )

    if args.all:
        print("\n" + "=" * 60)
        print("🚀 Ingesting ALL available knowledge sources")
        print("=" * 60)

        # Ingest books
        book_files = list(Path("rag_knowledge/books").glob("*_chapters.json"))
        for book_file in book_files:
            book_id = book_file.stem.replace("_chapters", "")
            results["books"][book_id] = ingest_book(collector, book_id, args.force)

        # Ingest newsletters
        newsletter_files = list(Path("rag_knowledge/newsletters").glob("*_insights.json"))
        for newsletter_file in newsletter_files:
            newsletter_id = newsletter_file.stem.replace("_insights", "")
            results["newsletters"][newsletter_id] = ingest_newsletter(
                collector, newsletter_id, args.force
            )

    if args.sync or args.all:
        print("\n" + "=" * 60)
        print("💾 Syncing to ChromaDB vector store")
        print("=" * 60)
        sync_result = sync_to_vector_db(collector)
        results["sync"] = sync_result

    # Print summary
    print("\n" + "=" * 60)
    print("📊 Ingestion Summary")
    print("=" * 60)

    total_chunks = 0
    for book_id, result in results.get("books", {}).items():
        status = result.get("status", "unknown")
        chunks = result.get("chunks", 0)
        total_chunks += chunks
        print(f"  📚 {book_id}: {status} ({chunks} chunks)")

    for newsletter_id, result in results.get("newsletters", {}).items():
        status = result.get("status", "unknown")
        chunks = result.get("chunks", 0)
        total_chunks += chunks
        print(f"  📰 {newsletter_id}: {status} ({chunks} chunks)")

    if "sync" in results:
        sync_count = results["sync"].get("count", 0)
        print(f"\n  💾 Vector DB: {sync_count} documents synced")

    print(f"\n  ✅ Total chunks ingested: {total_chunks}")
    print("=" * 60)


if __name__ == "__main__":
    main()
